"""Verify S3 credentials from ``.env`` without printing secrets.

Run from repo root (venv activated)::

    python scripts/verify_s3.py
"""

from __future__ import annotations

import sys
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")


def main() -> int:
    from backend.core.config import _env
    from backend.services.storage import S3StorageBackend

    backend = (_env("STORAGE_BACKEND", "local") or "local").lower()
    bucket = _env("S3_BUCKET")
    region = _env("S3_REGION")
    has_key = bool(_env("AWS_ACCESS_KEY_ID"))
    has_secret = bool(_env("AWS_SECRET_ACCESS_KEY"))

    print(f"STORAGE_BACKEND={backend}")
    print(f"S3_BUCKET={'set' if bucket else 'MISSING'}")
    print(f"S3_REGION={region or 'MISSING'}")
    print(f"AWS_ACCESS_KEY_ID={'set' if has_key else 'MISSING'}")
    print(f"AWS_SECRET_ACCESS_KEY={'set' if has_secret else 'MISSING'}")

    if backend != "s3":
        print("Set STORAGE_BACKEND=s3 in .env to exercise S3.")
        return 1
    if not bucket or not has_key or not has_secret:
        print("S3 config incomplete.")
        return 1

    try:
        storage = S3StorageBackend()
        key = f"prescriptions/_healthcheck/{uuid4().hex}.txt"
        payload = b"pharmaassist-s3-ok"
        storage.save_bytes(key, payload, content_type="text/plain")
        tmp = ROOT / "smoke_s3_download.tmp"
        try:
            storage.materialize_to_path(key, str(tmp))
            ok = tmp.read_bytes() == payload
        finally:
            if tmp.exists():
                tmp.unlink()
        # Best-effort cleanup
        try:
            storage.client.delete_object(Bucket=storage.bucket, Key=key)
        except Exception:
            pass
        if not ok:
            print("S3 round-trip failed: downloaded bytes mismatch.")
            return 1
        print("S3 round-trip: OK")
        return 0
    except Exception as exc:
        print(f"S3 check failed: {type(exc).__name__}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
