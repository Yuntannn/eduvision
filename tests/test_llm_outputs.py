import pytest
from pydantic import ValidationError

from eduvision.schemas.llm_outputs import Classification, ExtractionResult


def classification(**overrides: str) -> Classification:
    fields = {
        "subject": "biology",
        "topic": "photosynthesis",
        "content_type": "definition",
        "difficulty": "beginner",
    }
    return Classification.model_validate({**fields, **overrides})


def test_subject_and_topic_are_lowercased() -> None:
    result = classification(subject="Physics", topic="Newton's Second Law")

    assert result.subject == "physics"
    assert result.topic == "newton's second law"


def test_subject_and_topic_are_stripped() -> None:
    result = classification(subject="  Mathematics\n", topic=" Linear Equations ")

    assert (result.subject, result.topic) == ("mathematics", "linear equations")


def test_lowercasing_leaves_the_enum_fields_alone() -> None:
    result = classification(subject="BIOLOGY")

    assert result.content_type == "definition"
    assert result.difficulty == "beginner"


@pytest.mark.parametrize("field", ["subject", "topic"])
@pytest.mark.parametrize("value", ["", "   "])
def test_blank_subject_or_topic_is_rejected(field: str, value: str) -> None:
    with pytest.raises(ValidationError):
        classification(**{field: value})


def test_validation_applies_when_loading_stored_json() -> None:
    stored = (
        '{"subject": "Physics", "topic": "Motion", "content_type": "notes", '
        '"difficulty": "advanced"}'
    )

    result = Classification.model_validate_json(stored)

    assert (result.subject, result.topic) == ("physics", "motion")


def test_extraction_layout_is_optional() -> None:
    assert ExtractionResult(has_text=True, text="x = 1").layout is None
    assert ExtractionResult(has_text=True, text="F", layout="Triangle with F on top").layout == (
        "Triangle with F on top"
    )
