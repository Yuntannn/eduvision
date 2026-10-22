from langchain_anthropic import ChatAnthropic
from langchain_core.language_models import BaseChatModel
from pydantic import SecretStr

from eduvision.config import Settings


def validate_llm_settings(settings: Settings) -> None:
    """Raise ValueError naming every setting the configured provider needs but lacks."""
    if settings.llm_provider != "anthropic":
        return
    missing = [
        name
        for name, value in (
            ("LLM_MODEL", settings.llm_model),
            ("ANTHROPIC_API_KEY", settings.anthropic_api_key),
        )
        if not value
    ]
    if missing:
        raise ValueError(f"LLM_PROVIDER=anthropic requires these settings: {', '.join(missing)}.")


def create_chat_model(settings: Settings, *, fake: BaseChatModel | None = None) -> BaseChatModel:
    """Build the chat model for `settings.llm_provider`.

    The `fake` provider has no implementation in `src/`: tests pass their scripted model in.
    """
    if settings.llm_provider == "fake":
        if fake is None:
            raise ValueError("LLM_PROVIDER=fake requires a fake model to be passed in.")
        return fake

    validate_llm_settings(settings)
    assert settings.llm_model and settings.anthropic_api_key  # checked by validate_llm_settings
    return ChatAnthropic(
        model=settings.llm_model,
        api_key=SecretStr(settings.anthropic_api_key),
        timeout=float(settings.llm_timeout_seconds),
        max_retries=settings.llm_max_retries,  # transport errors only; see structured.py
    )
