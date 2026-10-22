from pathlib import Path

from fastapi.testclient import TestClient

from eduvision.config import get_settings


def test_settings_point_at_temporary_locations(tmp_path: Path) -> None:
    settings = get_settings()

    assert settings.database_url == f"sqlite:///{tmp_path / 'test.db'}"
    assert Path(settings.upload_dir).is_relative_to(tmp_path)


def test_app_startup_uses_temporary_database(client: TestClient, tmp_path: Path) -> None:
    assert (tmp_path / "test.db").exists()
