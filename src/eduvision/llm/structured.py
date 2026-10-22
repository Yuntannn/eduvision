import json
import logging
from dataclasses import dataclass

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from pydantic import BaseModel

from eduvision.llm.errors import UNAVAILABLE_EXCEPTIONS, InvalidLLMOutputError, LLMUnavailableError

logger = logging.getLogger(__name__)

MAX_ECHOED_OUTPUT_CHARS = 2000


def _describe_output(raw: object) -> str:
    """The model's invalid output as plain text (message text plus tool-call arguments)."""
    if not isinstance(raw, AIMessage):
        return ""
    text = str(raw.text)
    parts = [text] if text else []
    parts.extend(json.dumps(call["args"], default=str) for call in raw.tool_calls)
    return "\n".join(parts)[:MAX_ECHOED_OUTPUT_CHARS]


@dataclass(frozen=True)
class StructuredResult[T: BaseModel]:
    """A validated model output plus the tokens spent getting it (retry included)."""

    parsed: T
    input_tokens: int
    output_tokens: int


def call_structured[T: BaseModel](
    model: BaseChatModel, schema: type[T], messages: list[BaseMessage]
) -> StructuredResult[T]:
    """Call `model` for a `schema` output; retry once with the validation error on bad output.

    Raises InvalidLLMOutputError if the retry is also invalid, and LLMUnavailableError if the
    provider times out or cannot be reached.
    """
    structured = model.with_structured_output(schema, include_raw=True)
    input_tokens = 0
    output_tokens = 0
    attempt_messages = list(messages)

    for attempt in (1, 2):
        try:
            result = structured.invoke(attempt_messages)
        except UNAVAILABLE_EXCEPTIONS as exc:
            raise LLMUnavailableError(
                f"LLM provider unavailable: {type(exc).__name__}",
                input_tokens=input_tokens,
                output_tokens=output_tokens,
            ) from exc

        if not isinstance(result, dict):
            raise InvalidLLMOutputError(
                "Structured output was not returned with the raw message.",
                input_tokens=input_tokens,
                output_tokens=output_tokens,
            )

        raw = result.get("raw")
        if isinstance(raw, AIMessage) and raw.usage_metadata:
            input_tokens += raw.usage_metadata["input_tokens"]
            output_tokens += raw.usage_metadata["output_tokens"]

        parsed = result.get("parsed")
        if isinstance(parsed, schema):
            return StructuredResult(parsed, input_tokens, output_tokens)

        error = result.get("parsing_error") or "The response did not contain the expected output."
        logger.warning("Invalid %s output (attempt %d)", schema.__name__, attempt)
        if attempt == 2:
            raise InvalidLLMOutputError(
                f"{schema.__name__} output was invalid after one retry: {error}",
                input_tokens=input_tokens,
                output_tokens=output_tokens,
            )
        attempt_messages = [
            *messages,
            HumanMessage(
                f"Your previous response was invalid.\n"
                f"Your response:\n{_describe_output(raw)}\n"
                f"Validation error:\n{error}\n"
                f"Respond again with output that matches the {schema.__name__} schema exactly."
            ),
        ]

    raise AssertionError("unreachable")  # pragma: no cover
