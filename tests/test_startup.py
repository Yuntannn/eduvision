import pytest
from fastapi.testclient import TestClient

from eduvision.main import create_app


def configure(monkeypatch: pytest.MonkeyPatch, *, model: str, key: str) -> None:
    # Empty values override anything a local .env file provides.
    monkeypatch.setenv("LLM_PROVIDER", "anthropic")
    monkeypatch.setenv("LLM_MODEL", model)
    monkeypatch.setenv("ANTHROPIC_API_KEY", key)


@pytest.mark.parametrize(
    ("model", "key", "missing"),
    [
        ("", "k", ["LLM_MODEL"]),
        ("test-model", "", ["ANTHROPIC_API_KEY"]),
        ("", "", ["LLM_MODEL", "ANTHROPIC_API_KEY"]),
    ],
)
def test_startup_fails_when_anthropic_settings_are_missing(monkeypatch, model, key, missing):
    configure(monkeypatch, model=model, key=key)

    with pytest.raises(ValueError) as exc_info, TestClient(create_app()):
        pass

    assert all(name in str(exc_info.value) for name in missing)


def test_fake_provider_needs_no_llm_settings(monkeypatch):
    configure(monkeypatch, model="", key="")
    monkeypatch.setenv("LLM_PROVIDER", "fake")

    with TestClient(create_app()) as client:
        assert client.get("/health").status_code == 200


def test_validation_error_is_not_masked_by_the_model(monkeypatch):
    configure(monkeypatch, model="test-model", key="not-a-real-key")

    with TestClient(create_app()) as client:
        response = client.post("/api/v1/analyses", json={})

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"
