from datetime import UTC, datetime

from pydantic import BaseModel, Field, field_validator

from eduvision.db.models import Analysis
from eduvision.schemas.llm_outputs import Classification, Explanation


class CreateAnalysisRequest(BaseModel):
    upload_id: str = Field(min_length=1)


class Usage(BaseModel):
    input_tokens: int
    output_tokens: int
    duration_ms: int


class AnalysisResponse(BaseModel):
    analysis_id: str
    upload_id: str
    status: str
    failure_reason: str | None
    extracted_text: str | None
    classification: Classification | None
    explanation: Explanation | None
    usage: Usage
    created_at: datetime
    updated_at: datetime

    @field_validator("created_at", "updated_at")
    @classmethod
    def _as_utc(cls, value: datetime) -> datetime:
        # SQLite drops tzinfo on read; values are always stored as UTC.
        return value.replace(tzinfo=UTC) if value.tzinfo is None else value

    @classmethod
    def from_model(cls, analysis: Analysis) -> "AnalysisResponse":
        return cls(
            analysis_id=analysis.id,
            upload_id=analysis.upload_id,
            status=analysis.status,
            failure_reason=analysis.failure_reason,
            extracted_text=analysis.extracted_text,
            classification=(
                Classification.model_validate_json(analysis.classification_json)
                if analysis.classification_json
                else None
            ),
            explanation=(
                Explanation.model_validate_json(analysis.explanation_json)
                if analysis.explanation_json
                else None
            ),
            usage=Usage(
                input_tokens=analysis.input_tokens,
                output_tokens=analysis.output_tokens,
                duration_ms=analysis.duration_ms,
            ),
            created_at=analysis.created_at,
            updated_at=analysis.updated_at,
        )


class AnalysisListResponse(BaseModel):
    items: list[AnalysisResponse]
    total: int
    limit: int
    offset: int
