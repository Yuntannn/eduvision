from pathlib import Path

import pytest

from eduvision.storage.local_storage import LocalStorage


def test_save_uses_generated_name_and_round_trips(storage: LocalStorage, upload_dir: Path) -> None:
    stored = storage.save(b"image-bytes", "png")

    assert stored.endswith(".png")
    assert (upload_dir / stored).exists()
    assert storage.read(stored) == b"image-bytes"


def test_save_generates_unique_names(storage: LocalStorage) -> None:
    assert storage.save(b"a", "jpg") != storage.save(b"a", "jpg")


def test_save_normalises_extension(storage: LocalStorage) -> None:
    assert storage.save(b"a", ".PNG").endswith(".png")


def test_read_rejects_path_traversal(storage: LocalStorage) -> None:
    with pytest.raises(ValueError):
        storage.read("../secret.txt")


def test_read_missing_file_raises(storage: LocalStorage) -> None:
    with pytest.raises(FileNotFoundError):
        storage.read("missing.png")
