from functools import partial
from typing import cast

from langchain_core.language_models import BaseChatModel
from langgraph.errors import GraphRecursionError
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from eduvision.workflow.errors import StepLimitExceededError
from eduvision.workflow.nodes import classify, clean, extract, generate
from eduvision.workflow.state import AnalysisState

HAS_TEXT = "has text"
NO_TEXT = "no text"


def _after_extract(state: AnalysisState) -> str:
    return NO_TEXT if state.get("failure_reason") else HAS_TEXT


def build_graph(model: BaseChatModel) -> CompiledStateGraph[AnalysisState]:
    """START → extract → (text found?) → clean → classify → generate → END."""
    graph = StateGraph(AnalysisState)
    graph.add_node("extract", partial(extract, model=model))
    graph.add_node("clean", partial(clean, model=model))
    graph.add_node("classify", partial(classify, model=model))
    graph.add_node("generate", partial(generate, model=model))

    graph.add_edge(START, "extract")
    graph.add_conditional_edges("extract", _after_extract, {HAS_TEXT: "clean", NO_TEXT: END})
    graph.add_edge("clean", "classify")
    graph.add_edge("classify", "generate")
    graph.add_edge("generate", END)
    return graph.compile()


def run_workflow(
    model: BaseChatModel,
    *,
    image_bytes: bytes,
    image_media_type: str,
    recursion_limit: int,
    analysis_id: str | None = None,
) -> AnalysisState:
    """Run the analysis; raises StepLimitExceededError if `recursion_limit` steps are not enough.

    A run that finds no text returns normally with `failure_reason == "no_text_found"`.
    """
    initial: AnalysisState = {
        "analysis_id": analysis_id,
        "image_bytes": image_bytes,
        "image_media_type": image_media_type,
        "input_tokens": 0,
        "output_tokens": 0,
    }
    try:
        result = build_graph(model).invoke(initial, config={"recursion_limit": recursion_limit})
    except GraphRecursionError as exc:
        raise StepLimitExceededError(
            f"Workflow exceeded the limit of {recursion_limit} steps."
        ) from exc
    return cast(AnalysisState, result)  # invoke() is typed as dict[str, Any]
