"""The suite must never reach a real model, whatever the developer's .env says."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from langchain_anthropic import ChatAnthropic

from eduvision.config import Settings, get_settings
from eduvision.main import create_app

REAL_ENV = "LLM_PROVIDER=anthropic\nLLM_MODEL=real-model\nANTHROPIC_API_KEY=sk-real-looking-key\n"


@pytest.fixture
def real_dotenv(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A .env in the working directory that selects the real provider with a key."""
    (tmp_path / ".env").write_text(REAL_ENV)
    monkeypatch.chdir(tmp_path)
    get_settings.cache_clear()


def test_dotenv_would_select_anthropic_without_the_test_override(
    real_dotenv: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Control: proves the .env above is picked up, so the next test is meaningful."""
    monkeypatch.delenv("LLM_PROVIDER")

    assert Settings().llm_provider == "anthropic"


def test_dotenv_with_anthropic_does_not_leak_into_tests(real_dotenv: None) -> None:
    assert Settings().llm_provider == "fake"

    with TestClient(create_app()) as client:
        assert client.app.state.chat_model is None  # no ChatAnthropic was built


def test_real_api_calls_are_blocked_and_recorded(real_llm_attempts: list[str]) -> None:
    model = ChatAnthropic(model="test-model", api_key="k", max_retries=0)

    with pytest.raises(AssertionError, match="real Anthropic API"):
        model.invoke("hello")

    assert real_llm_attempts  # an unexpected attempt would fail its test at teardown
    real_llm_attempts.clear()  # this test attempted on purpose
