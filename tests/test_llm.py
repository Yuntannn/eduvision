import anthropic
import httpx
import pytest
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage

from eduvision.config import Settings
from eduvision.llm.errors import InvalidLLMOutputError, LLMUnavailableError
from eduvision.llm.factory import create_chat_model
from eduvision.llm.structured import call_structured
from eduvision.schemas.llm_outputs import Classification, Explanation
from tests.fakes import FakeChatModel, Invalid, Raises, Valid, fake_model

CLASSIFICATION = Classification(
    subject="biology", topic="photosynthesis", content_type="definition", difficulty="beginner"
)
MESSAGES = [HumanMessage("Classify this.")]


def test_valid_on_first_try():
    model = fake_model(Valid(CLASSIFICATION, input_tokens=10, output_tokens=4))

    result = call_structured(model, Classification, MESSAGES)

    assert result.parsed == CLASSIFICATION
    assert len(model.calls) == 1


def test_invalid_then_valid_retries_with_the_validation_error():
    model = fake_model(Invalid(), Valid(CLASSIFICATION))

    result = call_structured(model, Classification, MESSAGES)

    assert result.parsed == CLASSIFICATION
    assert len(model.calls) == 2
    retry_prompt = model.calls[1]
    assert retry_prompt[: len(MESSAGES)] == MESSAGES
    retry_text = str(retry_prompt[-1].content)
    assert "subject" in retry_text  # the validation error is passed back
    assert "poem" in retry_text  # ...together with what the model actually returned
    assert all(isinstance(m.content, str) for m in retry_prompt)  # plain text, no tool calls
    assert not getattr(retry_prompt[-1], "tool_calls", None)


def test_retry_message_truncates_long_invalid_output():
    model = fake_model(Invalid(content="x" * 5000), Valid(CLASSIFICATION))

    call_structured(model, Classification, MESSAGES)

    retry_text = str(model.calls[1][-1].content)
    assert "x" * 2000 in retry_text
    assert "x" * 2001 not in retry_text


def test_invalid_twice_raises():
    model = fake_model(Invalid(), Invalid())

    with pytest.raises(InvalidLLMOutputError):
        call_structured(model, Classification, MESSAGES)

    assert len(model.calls) == 2  # one retry only


def test_token_usage_is_returned():
    model = fake_model(Valid(CLASSIFICATION, input_tokens=120, output_tokens=30))

    result = call_structured(model, Classification, MESSAGES)

    assert (result.input_tokens, result.output_tokens) == (120, 30)


def test_token_usage_includes_the_retry():
    model = fake_model(Invalid(input_tokens=100, output_tokens=20), Valid(CLASSIFICATION, 130, 25))

    result = call_structured(model, Classification, MESSAGES)

    assert (result.input_tokens, result.output_tokens) == (230, 45)


@pytest.mark.parametrize(
    "error",
    [
        anthropic.APITimeoutError(request=httpx.Request("POST", "https://example.test")),
        anthropic.APIConnectionError(request=httpx.Request("POST", "https://example.test")),
        TimeoutError(),
    ],
)
def test_provider_outage_raises_llm_unavailable(error):
    model = fake_model(Raises(error))

    with pytest.raises(LLMUnavailableError):
        call_structured(model, Classification, MESSAGES)


def test_unrelated_errors_are_not_masked():
    model = fake_model(Raises(KeyError("bug")))

    with pytest.raises(KeyError):
        call_structured(model, Classification, MESSAGES)


@pytest.mark.parametrize(
    "overrides",
    [
        {"content_type": "poem"},
        {"difficulty": "expert"},
        {"subject": ""},
    ],
)
def test_classification_rejects_bad_values(overrides):
    with pytest.raises(ValueError):
        Classification(**{**CLASSIFICATION.model_dump(), **overrides})


@pytest.mark.parametrize(
    "overrides",
    [
        {"key_points": ["a", "b"]},
        {"key_points": list("abcdefg")},
        {"examples": []},
        {"examples": list("abcd")},
    ],
)
def test_explanation_enforces_list_lengths(overrides):
    valid = {"title": "t", "summary": "s", "key_points": list("abc"), "examples": ["e"]}
    assert Explanation(**valid).diagram_mermaid is None
    with pytest.raises(ValueError):
        Explanation(**{**valid, **overrides})


def test_factory_returns_the_injected_fake():
    fake = fake_model()
    assert create_chat_model(Settings(_env_file=None, llm_provider="fake"), fake=fake) is fake


def test_factory_fake_without_a_model_is_an_error():
    with pytest.raises(ValueError, match="fake"):
        create_chat_model(Settings(_env_file=None, llm_provider="fake"))


def test_factory_builds_anthropic_model_without_network():
    settings = Settings(
        _env_file=None, llm_provider="anthropic", llm_model="test-model", anthropic_api_key="k"
    )

    model = create_chat_model(settings)

    assert isinstance(model, ChatAnthropic)
    assert not isinstance(model, FakeChatModel)


def test_factory_passes_max_retries_and_timeout_to_the_sdk():
    settings = Settings(
        _env_file=None,
        llm_provider="anthropic",
        llm_model="test-model",
        anthropic_api_key="k",
        llm_max_retries=5,
        llm_timeout_seconds=7,
    )

    model = create_chat_model(settings)

    assert isinstance(model, ChatAnthropic)
    assert model.max_retries == 5
    assert model.default_request_timeout == 7


def test_max_retries_defaults_to_two():
    assert Settings(_env_file=None).llm_max_retries == 2


@pytest.mark.parametrize("missing", ["llm_model", "anthropic_api_key"])
def test_factory_requires_model_and_key_for_anthropic(missing, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("LLM_MODEL", raising=False)
    values = {"llm_model": "test-model", "anthropic_api_key": "k", missing: None}
    values["llm_provider"] = "anthropic"  # the test env defaults to the fake provider
    with pytest.raises(ValueError, match=missing.upper()):
        create_chat_model(Settings(_env_file=None, **values))
