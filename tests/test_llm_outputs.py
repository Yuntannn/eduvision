from eduvision.schemas.llm_outputs import ExtractionResult


def test_extraction_layout_is_optional() -> None:
    assert ExtractionResult(has_text=True, text="x = 1").layout is None
    assert ExtractionResult(has_text=True, text="F", layout="Triangle with F on top").layout == (
        "Triangle with F on top"
    )
