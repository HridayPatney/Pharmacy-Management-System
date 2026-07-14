"""API tests for OCR temp-file cleanup behavior."""

from __future__ import annotations

from io import BytesIO
from unittest.mock import patch

from backend.api import ocr_api


def test_ocr_extract_deletes_temp_file(client, cashier_headers):
    created: list[str] = []

    real_named = __import__("tempfile").NamedTemporaryFile

    def tracking_named_temporary_file(*args, **kwargs):
        kwargs = dict(kwargs)
        kwargs["delete"] = False
        tmp = real_named(*args, **kwargs)
        created.append(tmp.name)
        return tmp

    with patch.object(ocr_api.tempfile, "NamedTemporaryFile", side_effect=tracking_named_temporary_file):
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
