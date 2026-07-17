"""Object storage for prescription uploads (local disk or S3)."""

from __future__ import annotations

import logging
import mimetypes
from abc import ABC, abstractmethod
from pathlib import Path
from uuid import uuid4

from backend.core.config import PROJECT_ROOT, _env

logger = logging.getLogger(__name__)

_PRESCRIPTION_PREFIX = "prescriptions/"


class StorageBackend(ABC):
    """Minimal storage interface used by OCR upload / retrieve flow."""

    @abstractmethod
    def save_bytes(self, key: str, data: bytes, content_type: str | None = None) -> str:
        """Persist ``data`` under ``key`` and return the stored key."""

    @abstractmethod
    def materialize_to_path(self, key: str, dest_path: str) -> None:
        """Write the object identified by ``key`` to ``dest_path`` for local processing."""

    @abstractmethod
    def read_bytes(self, key: str) -> bytes:
        """Return the raw object bytes for ``key``."""

    @abstractmethod
    def exists(self, key: str) -> bool:
        """Return True when ``key`` is present in storage."""


class LocalStorageBackend(StorageBackend):
    """Store files under ``UPLOAD_DIR`` (default ``<repo>/uploads``)."""

    def __init__(self, root: Path | None = None) -> None:
        override = _env("UPLOAD_DIR")
        self.root = Path(override).expanduser().resolve() if override else (root or PROJECT_ROOT / "uploads")
        self.root.mkdir(parents=True, exist_ok=True)

    def _resolve(self, key: str) -> Path:
        path = (self.root / key).resolve()
        if not str(path).startswith(str(self.root.resolve())):
            raise FileNotFoundError(f"Invalid storage key: {key}")
        return path

    def save_bytes(self, key: str, data: bytes, content_type: str | None = None) -> str:
        path = self._resolve(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return key

    def materialize_to_path(self, key: str, dest_path: str) -> None:
        src = self._resolve(key)
        Path(dest_path).write_bytes(src.read_bytes())

    def read_bytes(self, key: str) -> bytes:
        return self._resolve(key).read_bytes()

    def exists(self, key: str) -> bool:
        try:
            return self._resolve(key).is_file()
        except FileNotFoundError:
            return False


class S3StorageBackend(StorageBackend):
    """S3-compatible storage (AWS S3, R2, MinIO)."""

    def __init__(self) -> None:
        try:
            import boto3
            from botocore.exceptions import ClientError
        except ImportError as exc:
            raise RuntimeError(
                "boto3 is required for S3 storage. Install requirements-api.txt."
            ) from exc

        bucket = _env("S3_BUCKET")
        if not bucket:
            raise RuntimeError("S3_BUCKET is required when STORAGE_BACKEND=s3")

        region = _env("S3_REGION", "us-east-1")
        endpoint = _env("S3_ENDPOINT_URL")
        kwargs: dict = {"region_name": region}
        if endpoint:
            kwargs["endpoint_url"] = endpoint

        self.bucket = bucket
        self.client = boto3.client("s3", **kwargs)
        self._ClientError = ClientError

    def save_bytes(self, key: str, data: bytes, content_type: str | None = None) -> str:
        extra: dict = {}
        if content_type:
            extra["ContentType"] = content_type
        self.client.put_object(Bucket=self.bucket, Key=key, Body=data, **extra)
        return key

    def materialize_to_path(self, key: str, dest_path: str) -> None:
        self.client.download_file(self.bucket, key, dest_path)

    def read_bytes(self, key: str) -> bytes:
        try:
            obj = self.client.get_object(Bucket=self.bucket, Key=key)
        except self._ClientError as exc:
            code = (exc.response.get("Error") or {}).get("Code", "")
            if code in ("404", "NoSuchKey", "NotFound"):
                raise FileNotFoundError(key) from exc
            raise
        return obj["Body"].read()

    def exists(self, key: str) -> bool:
        try:
            self.client.head_object(Bucket=self.bucket, Key=key)
            return True
        except self._ClientError:
            return False


def get_storage() -> StorageBackend:
    """Return the configured storage backend (``local`` default, or ``s3``)."""
    backend = (_env("STORAGE_BACKEND", "local") or "local").lower()
    if backend == "s3":
        return S3StorageBackend()
    return LocalStorageBackend()


def build_prescription_key(user_id: int, filename: str) -> str:
    """Build a stable object key for an uploaded prescription image."""
    suffix = Path(filename).suffix.lower() or ".img"
    return f"prescriptions/{user_id}/{uuid4().hex}{suffix}"


def validate_prescription_key(key: str) -> str:
    """Normalize and reject keys outside the prescriptions namespace."""
    cleaned = (key or "").strip().lstrip("/")
    if not cleaned.startswith(_PRESCRIPTION_PREFIX):
        raise ValueError("Prescription key must start with prescriptions/")
    if ".." in cleaned.split("/"):
        raise ValueError("Invalid prescription key")
    return cleaned


def guess_content_type(key: str) -> str:
    """Best-effort MIME type from the object key suffix."""
    ctype, _ = mimetypes.guess_type(key)
    return ctype or "application/octet-stream"
