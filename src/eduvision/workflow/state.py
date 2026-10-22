from typing import TypedDict

from eduvision.schemas.llm_outputs import Classification, Explanation


class AnalysisState(TypedDict, total=False):
    analysis_id: str | None  # only used to tag log lines
    image_bytes: bytes
    image_media_type: str
    raw_text: str
    cleaned_text: str
    classification: Classification
    explanation: Explanation
    failure_reason: str | None
