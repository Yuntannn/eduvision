from langchain_anthropic import ChatAnthropic
from langchain_core.language_models import BaseChatModel
from pydantic import SecretStr

from eduvision.config import Settings


def create_chat_model(settings: Settings, *, fake: BaseChatModel | None = None) -> BaseChatModel:
    """Build the chat model for `settings.llm_provider`.

    The `fake` provider has no implementation in `src/`: tests pass their scripted model in.
    """
    if settings.llm_provider == "fake":
        if fake is None:
            raise ValueError("LLM_PROVIDER=fake requires a fake model to be passed in.")
        return fake

    if not settings.llm_model:
        raise ValueError("LLM_MODEL must be set when LLM_PROVIDER=anthropic.")
    if not settings.anthropic_api_key:
        raise ValueError("ANTHROPIC_API_KEY must be set when LLM_PROVIDER=anthropic.")
    return ChatAnthropic(
        model=settings.llm_model,
        api_key=SecretStr(settings.anthropic_api_key),
        timeout=float(settings.llm_timeout_seconds),
        max_retries=settings.llm_max_retries,  # transport errors only; see structured.py
    )
