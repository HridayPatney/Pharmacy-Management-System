"""Object storage for prescription uploads (local disk or S3)."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from pathlib import Path
from uuid import uuid4

from backend.core.config import PROJECT_ROOT, _env

logger = logging.getLogger(__name__)


class StorageBackend(ABC):
    """Minimal storage interface used by OCR upload flow."""

    @abstractmethod
    def save_bytes(self, key: str, data: bytes, content_type: str | None = None) -> str:
        """Persist ``data`` under ``key`` and return the stored key."""

    @abstractmethod
    def materialize_to_path(self, key: str, dest_path: str) -> None:
        """Write the object identified by ``key`` to ``dest_path`` for local processing."""


class LocalStorageBackend(StorageBackend):
    """Store files under ``UPLOAD_DIR`` (default ``<repo>/uploads``)."""

    def __init__(self, root: Path | None = None) -> None:
        override = _env("UPLOAD_DIR")
        self.root = Path(override).expanduser().resolve() if override else (root or PROJECT_ROOT / "uploads")
        self.root.mkdir(parents=True, exist_ok=True)

    def save_bytes(self, key: str, data: bytes, content_type: str | None = None) -> str:
        path = self.root / key
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return key

    def materialize_to_path(self, key: str, dest_path: str) -> None:
        src = self.root / key
        Path(dest_path).write_bytes(src.read_bytes())


class S3StorageBackend(StorageBackend):
    """S3-compatible storage (AWS S3, R2, MinIO)."""

    def __init__(self) -> None:
        try:
            import boto3
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

    def save_bytes(self, key: str, data: bytes, content_type: str | None = None) -> str:
        extra: dict = {}
        if content_type:
            extra["ContentType"] = content_type
        self.client.put_object(Bucket=self.bucket, Key=key, Body=data, **extra)
        return key

    def materialize_to_path(self, key: str, dest_path: str) -> None:
        self.client.download_file(self.bucket, key, dest_path)


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
