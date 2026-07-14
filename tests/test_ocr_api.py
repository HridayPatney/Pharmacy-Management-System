"""API tests for OCR temp-file cleanup behavior."""

from __future__ import annotations

from io import BytesIO
from unittest.mock import patch

from backend.api import ocr_api


def test_ocr_extract_deletes_temp_file(client, cashier_headers):
    created: list[str] = []
    real_mkstemp = __import__("tempfile").mkstemp

    def tracking_mkstemp(*args, **kwargs):
        fd, path = real_mkstemp(*args, **kwargs)
        created.append(path)
        return fd, path

    with patch.object(ocr_api.tempfile, "mkstemp", side_effect=tracking_mkstemp):
        response = client.post(
            "/ocr/extract",
            files={"file": ("rx.png", BytesIO(b"fake-image-bytes"), "image/png")},
            headers=cashier_headers,
        )

    assert response.status_code == 200
    assert response.json()["Patient's Name"] == "Test"
    assert created, "expected a temp file to be created"
    for path in created:
        assert not __import__("os").path.exists(path)
