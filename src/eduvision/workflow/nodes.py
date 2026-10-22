import base64
import logging
import time

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel

from eduvision.llm.errors import UNAVAILABLE_EXCEPTIONS, LLMError, LLMUnavailableError
from eduvision.llm.structured import StructuredResult, call_structured
from eduvision.schemas.llm_outputs import Classification, Explanation, ExtractionResult
from eduvision.workflow.progress import WorkflowProgress
from eduvision.workflow.prompts import (
    CLASSIFY_PROMPT,
    CLEAN_PROMPT,
    EXTRACT_PROMPT,
    GENERATE_PROMPT,
)
from eduvision.workflow.state import AnalysisState

logger = logging.getLogger(__name__)

NO_TEXT_FAILURE = "no_text_found"


def _log_extra(state: AnalysisState, **fields: object) -> dict[str, object]:
    """Log fields for a node; `analysis_id` is left out (logged as "-") when the run has none."""
    analysis_id = state.get("analysis_id")
    return {**fields, "analysis_id": analysis_id} if analysis_id else dict(fields)


def _log_start(state: AnalysisState, step: str) -> None:
    logger.info("step started", extra=_log_extra(state, step=step))


def _log_step(state: AnalysisState, step: str, started: float, outcome: str) -> None:
    duration_ms = int((time.perf_counter() - started) * 1000)
    logger.info(
        "step finished",
        extra=_log_extra(state, step=step, duration_ms=duration_ms, outcome=outcome),
    )


def _progress(config: RunnableConfig) -> WorkflowProgress:
    """The run's progress tracker; a throwaway one when the node is called without it."""
    progress = config.get("configurable", {}).get("progress")
    return progress if isinstance(progress, WorkflowProgress) else WorkflowProgress()


def _call_structured[T: BaseModel](
    model: BaseChatModel,
    schema: type[T],
    messages: list[BaseMessage],
    progress: WorkflowProgress,
) -> StructuredResult[T]:
    """call_structured, recording the tokens spent whether the call succeeds or fails."""
    try:
        result = call_structured(model, schema, messages)
    except LLMError as exc:
        progress.add_tokens(exc.input_tokens, exc.output_tokens)
        raise
    progress.add_tokens(result.input_tokens, result.output_tokens)
    return result


def _with_layout(text: str, state: AnalysisState) -> str:
    """The content for a prompt: the text, plus the layout description when there is one."""
    layout = state.get("layout")
    return f"{text}\n\nLayout:\n{layout}" if layout else text


def _call_text(model: BaseChatModel, messages: list[BaseMessage]) -> tuple[str, int, int]:
    """Plain-text call; returns the reply text and the tokens it used."""
    try:
        reply = model.invoke(messages)
    except UNAVAILABLE_EXCEPTIONS as exc:
        raise LLMUnavailableError(f"LLM provider unavailable: {type(exc).__name__}") from exc
    usage = reply.usage_metadata
    return (
        reply.text.strip(),
        usage["input_tokens"] if usage else 0,
        usage["output_tokens"] if usage else 0,
    )


def extract(state: AnalysisState, model: BaseChatModel, config: RunnableConfig) -> AnalysisState:
    progress = _progress(config)
    started = time.perf_counter()
    _log_start(state, "extract")
    image_b64 = base64.b64encode(state["image_bytes"]).decode("ascii")
    data_uri = f"data:{state['image_media_type']};base64,{image_b64}"
    messages: list[BaseMessage] = [
        HumanMessage(
            content=[
                {"type": "text", "text": EXTRACT_PROMPT},
                {"type": "image_url", "image_url": {"url": data_uri}},
            ]
        )
    ]
    result = _call_structured(model, ExtractionResult, messages, progress)

    update: AnalysisState = {}
    text = result.parsed.text.strip()
    if not result.parsed.has_text or not text:
        update["failure_reason"] = NO_TEXT_FAILURE
        _log_step(state, "extract", started, NO_TEXT_FAILURE)
    else:
        update["raw_text"] = text
        progress.raw_text = text
        layout = (result.parsed.layout or "").strip()
        if layout:
            update["layout"] = layout
            progress.layout = layout
        _log_step(state, "extract", started, "ok")
    return update


def clean(state: AnalysisState, model: BaseChatModel, config: RunnableConfig) -> AnalysisState:
    progress = _progress(config)
    started = time.perf_counter()
    _log_start(state, "clean")
    messages: list[BaseMessage] = [SystemMessage(CLEAN_PROMPT), HumanMessage(state["raw_text"])]
    text, in_tokens, out_tokens = _call_text(model, messages)
    progress.add_tokens(in_tokens, out_tokens)
    progress.cleaned_text = text
    _log_step(state, "clean", started, "ok")
    return {"cleaned_text": text}


def classify(state: AnalysisState, model: BaseChatModel, config: RunnableConfig) -> AnalysisState:
    progress = _progress(config)
    started = time.perf_counter()
    _log_start(state, "classify")
    messages: list[BaseMessage] = [
        SystemMessage(CLASSIFY_PROMPT),
        HumanMessage(_with_layout(state["cleaned_text"], state)),
    ]
    result = _call_structured(model, Classification, messages, progress)
    _log_step(state, "classify", started, "ok")
    return {"classification": result.parsed}


def generate(state: AnalysisState, model: BaseChatModel, config: RunnableConfig) -> AnalysisState:
    progress = _progress(config)
    started = time.perf_counter()
    _log_start(state, "generate")
    classification = state["classification"].model_dump_json()
    messages: list[BaseMessage] = [
        SystemMessage(GENERATE_PROMPT),
        HumanMessage(
            f"Classification:\n{classification}\n\n"
            f"Content:\n{_with_layout(state['cleaned_text'], state)}"
        ),
    ]
    result = _call_structured(model, Explanation, messages, progress)
    _log_step(state, "generate", started, "ok")
    return {"explanation": result.parsed}
