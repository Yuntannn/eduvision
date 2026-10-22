from datetime import UTC, datetime

from pydantic import BaseModel, field_validator


class UploadResponse(BaseModel):
    upload_id: str
    original_filename: str
    content_type: str
    size_bytes: int
    created_at: datetime

    @field_validator("created_at")
    @classmethod
    def _as_utc(cls, value: datetime) -> datetime:
        # SQLite drops tzinfo on read; values are always stored as UTC.
        return value.replace(tzinfo=UTC) if value.tzinfo is None else value
