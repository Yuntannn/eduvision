import uuid
from datetime import UTC, datetime

from sqlmodel import Field, SQLModel


def new_id() -> str:
    return str(uuid.uuid4())


def utcnow() -> datetime:
    return datetime.now(UTC)


class Upload(SQLModel, table=True):
    id: str = Field(default_factory=new_id, primary_key=True)
    original_filename: str
    stored_filename: str
    content_type: str
    size_bytes: int
    created_at: datetime = Field(default_factory=utcnow)


class Analysis(SQLModel, table=True):
    id: str = Field(default_factory=new_id, primary_key=True)
    upload_id: str = Field(foreign_key="upload.id", index=True)
    status: str = "pending"  # pending | completed | failed
    failure_reason: str | None = None
    extracted_text: str | None = None
    layout: str | None = None
    classification_json: str | None = None
    explanation_json: str | None = None
    input_tokens: int = 0
    output_tokens: int = 0
    duration_ms: int = 0
    created_at: datetime = Field(default_factory=utcnow, index=True)
    updated_at: datetime = Field(default_factory=utcnow)
