"""A scripted chat model: tests queue replies and the model plays them back in order."""

from dataclasses import dataclass, field
from typing import Any

from langchain_core.callbacks import CallbackManagerForLLMRun
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.runnables import Runnable, RunnableLambda
from pydantic import BaseModel, Field, ValidationError


@dataclass
class Text:
    """A plain-text reply (extract / clean steps)."""

    content: str
    input_tokens: int = 0
    output_tokens: int = 0


@dataclass
class Valid:
    """A structured reply that parses into `value`."""

    value: BaseModel
    input_tokens: int = 0
    output_tokens: int = 0


@dataclass
class Invalid:
    """A structured reply whose payload fails schema validation."""

    payload: dict[str, Any] = field(default_factory=lambda: {"content_type": "poem"})
    content: str = ""
    input_tokens: int = 0
    output_tokens: int = 0


@dataclass
class Raises:
    """The provider call fails with `error`."""

    error: Exception


Reply = Text | Valid | Invalid | Raises


def _usage(reply: Text | Valid | Invalid) -> dict[str, int]:
    return {
        "input_tokens": reply.input_tokens,
        "output_tokens": reply.output_tokens,
        "total_tokens": reply.input_tokens + reply.output_tokens,
    }


class FakeChatModel(BaseChatModel):
    """Plays `script` back in order; every call (plain or structured) consumes one reply."""

    script: list[Reply] = Field(default_factory=list)
    calls: list[list[BaseMessage]] = Field(default_factory=list)

    @property
    def _llm_type(self) -> str:
        return "fake-scripted"

    def _next(self, messages: list[BaseMessage]) -> Reply:
        self.calls.append(list(messages))
        if not self.script:
            raise AssertionError("FakeChatModel script is exhausted")
        reply = self.script.pop(0)
        if isinstance(reply, Raises):
            raise reply.error
        return reply

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: CallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> ChatResult:
        reply = self._next(messages)
        if not isinstance(reply, Text):
            raise AssertionError(f"Plain call got a structured reply: {reply!r}")
        message = AIMessage(content=reply.content, usage_metadata=_usage(reply))  # type: ignore[arg-type]
        return ChatResult(generations=[ChatGeneration(message=message)])

    def with_structured_output(  # type: ignore[override]
        self, schema: type[BaseModel], *, include_raw: bool = False, **kwargs: Any
    ) -> Runnable[Any, dict[str, Any]]:
        assert include_raw, "the fake only supports include_raw=True"

        def run(messages: list[BaseMessage]) -> dict[str, Any]:
            reply = self._next(messages)
            if isinstance(reply, Text):
                raise AssertionError(f"Structured call got a text reply: {reply!r}")
            tool_calls = (
                [{"name": schema.__name__, "args": reply.payload, "id": "call_1"}]
                if isinstance(reply, Invalid)
                else []
            )
            raw = AIMessage(
                content=reply.content if isinstance(reply, Invalid) else "",
                tool_calls=tool_calls,
                usage_metadata=_usage(reply),  # type: ignore[arg-type]
            )
            if isinstance(reply, Valid):
                return {"raw": raw, "parsed": reply.value, "parsing_error": None}
            try:
                schema.model_validate(reply.payload)
            except ValidationError as exc:
                return {"raw": raw, "parsed": None, "parsing_error": exc}
            raise AssertionError(
                f"{schema.__name__} accepts its payload; cannot build an invalid reply"
            )

        return RunnableLambda(run)


def fake_model(*script: Reply) -> FakeChatModel:
    return FakeChatModel(script=list(script))
