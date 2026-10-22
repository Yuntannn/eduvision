from typing import Literal

from pydantic import BaseModel, Field

ContentType = Literal["definition", "worked_example", "exercise", "notes", "diagram", "other"]
Difficulty = Literal["beginner", "intermediate", "advanced"]


class ExtractionResult(BaseModel):
    """What the extract step read from the image (R3.2, R3.6)."""

    has_text: bool = Field(description="True only if the image contains readable, meaningful text.")
    text: str = Field(
        description="Only the text actually visible in the image; empty when has_text is false."
    )
    layout: str | None = Field(
        default=None,
        description=(
            "Short description of arrows, shapes or positions in a diagram or figure; "
            "null when the image is plain text."
        ),
    )


class Classification(BaseModel):
    """What the extracted content is about (R3.3)."""

    subject: str = Field(min_length=1, description="School subject, e.g. 'mathematics'.")
    topic: str = Field(min_length=1, description="Short topic, e.g. 'photosynthesis'.")
    content_type: ContentType
    difficulty: Difficulty


class Explanation(BaseModel):
    """A student-friendly explanation of the content (R3.4)."""

    title: str = Field(min_length=1)
    summary: str = Field(min_length=1, description="2-4 sentences.")
    key_points: list[str] = Field(min_length=3, max_length=6)
    examples: list[str] = Field(min_length=1, max_length=3)
    diagram_mermaid: str | None = Field(
        default=None, description="A Mermaid diagram as text, or null if a diagram does not help."
    )
