from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from eduvision.config import get_settings
from eduvision.services.upload_service import detect_image_type

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32
JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 32
WEBP = b"RIFF\x24\x00\x00\x00WEBPVP8 " + b"\x00" * 32


def post_file(client: TestClient, content: bytes, filename: str, content_type: str):
    return client.post("/api/v1/uploads", files={"file": (filename, content, content_type)})


@pytest.mark.parametrize(
    ("content", "filename", "content_type", "extension"),
    [
        (JPEG, "notes.jpg", "image/jpeg", "jpg"),
        (PNG, "board.png", "image/png", "png"),
        (WEBP, "slide.webp", "image/webp", "webp"),
    ],
)
def test_valid_image_is_stored(
    client: TestClient,
    upload_dir: Path,
    content: bytes,
    filename: str,
    content_type: str,
    extension: str,
) -> None:
    response = post_file(client, content, filename, content_type)

    assert response.status_code == 201
    body = response.json()
    assert body["original_filename"] == filename
    assert body["content_type"] == content_type
    assert body["size_bytes"] == len(content)
    assert body["upload_id"]
    assert body["created_at"].endswith("Z") or "+00:00" in body["created_at"]
    stored = list(upload_dir.iterdir())
    assert len(stored) == 1
    assert stored[0].suffix == f".{extension}"
    assert stored[0].read_bytes() == content


def test_stored_filename_is_generated_not_client_supplied(
    client: TestClient, upload_dir: Path
) -> None:
    response = post_file(client, PNG, "../../evil name.png", "image/png")

    assert response.status_code == 201
    assert response.json()["original_filename"] == "evil name.png"
    [stored] = list(upload_dir.iterdir())
    assert "evil" not in stored.name
    assert stored.parent == upload_dir


def test_type_is_detected_from_content_not_header_or_extension(
    client: TestClient, upload_dir: Path
) -> None:
    response = post_file(client, PNG, "photo.jpg", "image/jpeg")

    assert response.status_code == 201
    assert response.json()["content_type"] == "image/png"
    assert [p.suffix for p in upload_dir.iterdir()] == [".png"]


@pytest.mark.parametrize(
    ("content", "filename", "content_type"),
    [
        (b"just some text", "notes.png", "image/png"),  # claims PNG, is text
        (b"GIF89a" + b"\x00" * 32, "anim.gif", "image/gif"),
        (b"%PDF-1.7\n", "doc.pdf", "application/pdf"),
        (b"RIFF\x24\x00\x00\x00WAVEfmt ", "sound.webp", "image/webp"),  # RIFF but not WebP
        (b"", "empty.jpg", "image/jpeg"),
    ],
)
def test_unsupported_content_returns_415(
    client: TestClient, upload_dir: Path, content: bytes, filename: str, content_type: str
) -> None:
    response = post_file(client, content, filename, content_type)

    assert response.status_code == 415
    assert response.json()["error"]["code"] == "unsupported_media_type"
    assert not upload_dir.exists() or not list(upload_dir.iterdir())


def test_file_over_limit_returns_413(
    client: TestClient, upload_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("MAX_UPLOAD_BYTES", "100")
    get_settings.cache_clear()

    response = post_file(client, PNG + b"\x00" * 100, "big.png", "image/png")

    assert response.status_code == 413
    assert response.json()["error"]["code"] == "payload_too_large"
    assert not upload_dir.exists() or not list(upload_dir.iterdir())


def test_file_exactly_at_limit_is_accepted(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("MAX_UPLOAD_BYTES", str(len(PNG)))
    get_settings.cache_clear()

    assert post_file(client, PNG, "ok.png", "image/png").status_code == 201


def test_missing_file_returns_422(client: TestClient) -> None:
    response = client.post("/api/v1/uploads")

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_detect_image_type() -> None:
    assert detect_image_type(JPEG) == ("image/jpeg", "jpg")
    assert detect_image_type(PNG) == ("image/png", "png")
    assert detect_image_type(WEBP) == ("image/webp", "webp")
    assert detect_image_type(b"") is None
