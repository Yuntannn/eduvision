from collections.abc import Iterator
from pathlib import Path

import anthropic._base_client as anthropic_client
import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from eduvision.config import get_settings
from eduvision.db.session import create_db_and_tables, create_db_engine
from eduvision.main import create_app
from eduvision.storage.local_storage import LocalStorage


def _snapshot(path: Path) -> dict[str, int]:
    """Map every path under `path` (including itself) to its mtime; empty if it doesn't exist."""
    if not path.exists():
        return {}
    return {str(p): p.stat().st_mtime_ns for p in [path, *path.rglob("*")]}


@pytest.fixture(autouse=True)
def default_data_dir_untouched() -> Iterator[None]:
    """Fail any test that creates or modifies ./data (the default DB and upload location)."""
    data_dir = Path("data").resolve()
    before = _snapshot(data_dir)
    yield
    assert _snapshot(data_dir) == before, (
        f"{data_dir} was touched: the test is not isolated from the default settings"
    )


@pytest.fixture(autouse=True)
def real_llm_attempts(monkeypatch: pytest.MonkeyPatch) -> Iterator[list[str]]:
    """Block every request to the Anthropic API, and fail any test that attempts one.

    All Anthropic traffic (including through ChatAnthropic) goes through the SDK's `request`.
    The call raises, and the attempt is also recorded and asserted on at teardown, so a test
    can't pass by swallowing the error (the API turns unexpected errors into a 500 response).
    """
    attempts: list[str] = []

    def blocked(self: object, *args: object, **kwargs: object) -> None:
        attempts.append(type(self).__name__)
        raise AssertionError("A test tried to call the real Anthropic API; inject a fake model.")

    monkeypatch.setattr(anthropic_client.SyncAPIClient, "request", blocked)
    monkeypatch.setattr(anthropic_client.AsyncAPIClient, "request", blocked)
    yield attempts
    assert not attempts, f"Test attempted real Anthropic API calls via: {attempts}"


@pytest.fixture
def upload_dir(tmp_path: Path) -> Path:
    return tmp_path / "uploads"


@pytest.fixture(autouse=True)
def isolated_settings(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, upload_dir: Path
) -> Iterator[None]:
    """Point every test at its own temporary database and upload directory."""
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'test.db'}")
    monkeypatch.setenv("UPLOAD_DIR", str(upload_dir))
    monkeypatch.setenv("LLM_PROVIDER", "fake")  # never build a real client or need a real key
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def session(tmp_path: Path) -> Iterator[Session]:
    engine = create_db_engine(f"sqlite:///{tmp_path / 'repo.db'}")
    create_db_and_tables(engine)
    with Session(engine) as db_session:
        yield db_session
    engine.dispose()


@pytest.fixture
def storage(upload_dir: Path) -> LocalStorage:
    return LocalStorage(upload_dir)


@pytest.fixture
def client() -> Iterator[TestClient]:
    with TestClient(create_app()) as test_client:
        yield test_client
