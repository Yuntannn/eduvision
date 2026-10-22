import pytest

from eduvision.llm.errors import InvalidLLMOutputError, LLMUnavailableError
from eduvision.schemas.llm_outputs import Classification, Explanation, ExtractionResult
from eduvision.workflow.errors import StepLimitExceededError
from eduvision.workflow.graph import build_graph, run_workflow
from eduvision.workflow.progress import WorkflowProgress
from tests.fakes import Invalid, Raises, Text, Valid, fake_model


def extracted(text, *, has_text=True, layout=None, input_tokens=0, output_tokens=0):
    result = ExtractionResult(has_text=has_text, text=text, layout=layout)
    return Valid(result, input_tokens, output_tokens)


CLASSIFICATION = Classification(
    subject="biology", topic="photosynthesis", content_type="definition", difficulty="beginner"
)
EXPLANATION = Explanation(
    title="How Plants Make Food",
    summary="Plants turn light into sugar.",
    key_points=["Light", "Water", "CO2"],
    examples=["A leaf in the sun"],
    diagram_mermaid="flowchart LR\n  Sunlight --> Leaf",
)


def run(model, recursion_limit=10, analysis_id=None, progress=None):
    return run_workflow(
        model,
        analysis_id=analysis_id,
        progress=progress,
        image_bytes=b"fake-image",
        image_media_type="image/png",
        recursion_limit=recursion_limit,
    )


def test_happy_path_populates_every_field():
    model = fake_model(
        extracted("Photosynthesis is teh process"),
        Text("Photosynthesis is the process"),
        Valid(CLASSIFICATION),
        Valid(EXPLANATION),
    )

    state = run(model)

    assert state["raw_text"] == "Photosynthesis is teh process"
    assert state["cleaned_text"] == "Photosynthesis is the process"
    assert state["classification"] == CLASSIFICATION
    assert state["explanation"] == EXPLANATION
    assert not state.get("failure_reason")
    assert len(model.calls) == 4


def message_text(call):
    return call[-1].content


def test_layout_reaches_classify_and_generate_but_not_clean():
    model = fake_model(
        extracted("Water\nCloud", layout="Arrow from Water up to Cloud"),
        Text("Water\nCloud"),
        Valid(CLASSIFICATION),
        Valid(EXPLANATION),
    )
    progress = WorkflowProgress()

    state = run(model, progress=progress)

    assert state["layout"] == "Arrow from Water up to Cloud"
    assert progress.layout == "Arrow from Water up to Cloud"
    clean_call, classify_call, generate_call = model.calls[1:]
    assert "Arrow from Water" not in message_text(clean_call)
    assert message_text(classify_call) == "Water\nCloud\n\nLayout:\nArrow from Water up to Cloud"
    assert "Content:\nWater\nCloud\n\nLayout:\nArrow from Water up to Cloud" in message_text(
        generate_call
    )


@pytest.mark.parametrize("layout", [None, "", "  \n "])
def test_no_layout_is_left_out_of_state_and_prompts(layout):
    model = fake_model(
        extracted("Photosynthesis", layout=layout),
        Text("Photosynthesis"),
        Valid(CLASSIFICATION),
        Valid(EXPLANATION),
    )
    progress = WorkflowProgress()

    state = run(model, progress=progress)

    assert "layout" not in state
    assert progress.layout is None
    assert all("Layout" not in message_text(call) for call in model.calls[1:])


NO_TEXT_REPLIES = [
    pytest.param(False, "", id="has_text_false"),
    pytest.param(True, "", id="has_text_true_empty_text"),
    pytest.param(True, "  \n\t ", id="has_text_true_blank_text"),
    pytest.param(False, "some stray text", id="has_text_false_with_text"),
]


@pytest.mark.parametrize(("has_text", "text"), NO_TEXT_REPLIES)
def test_no_text_stops_after_extract(has_text, text, monkeypatch):
    import eduvision.workflow.graph as graph_module

    def forbidden(name):
        def node(*args, **kwargs):
            raise AssertionError(f"{name} must not be called when no text is found")

        return node

    for name in ("clean", "classify", "generate"):
        monkeypatch.setattr(graph_module, name, forbidden(name))
    model = fake_model(extracted(text, has_text=has_text, input_tokens=7, output_tokens=2))
    progress = WorkflowProgress()

    state = run(model, progress=progress)

    assert state["failure_reason"] == "no_text_found"
    assert len(model.calls) == 1  # extract only
    for key in ("raw_text", "cleaned_text", "classification", "explanation"):
        assert key not in state
    assert (progress.input_tokens, progress.output_tokens) == (7, 2)


def test_normal_extraction_continues_to_clean():
    model = fake_model(
        extracted("  Photosynthesis is the process\n"),
        Text("Photosynthesis is the process"),
        Valid(CLASSIFICATION),
        Valid(EXPLANATION),
    )

    state = run(model)

    assert state["raw_text"] == "Photosynthesis is the process"
    assert not state.get("failure_reason")


def test_extract_retries_invalid_output():
    model = fake_model(
        Invalid(payload={"has_text": "maybe"}),
        extracted("raw"),
        Text("clean"),
        Valid(CLASSIFICATION),
        Valid(EXPLANATION),
    )

    state = run(model)

    assert state["raw_text"] == "raw"
    assert len(model.calls) == 5


def test_invalid_output_twice_fails():
    model = fake_model(extracted("raw"), Text("clean"), Invalid(), Invalid())

    with pytest.raises(InvalidLLMOutputError):
        run(model)

    assert len(model.calls) == 4  # extract, clean, classify + its single retry
    # generate is never reached


def test_invalid_then_valid_recovers():
    model = fake_model(
        extracted("raw"), Text("clean"), Invalid(), Valid(CLASSIFICATION), Valid(EXPLANATION)
    )

    state = run(model)

    assert state["explanation"] == EXPLANATION


def test_step_limit_exceeded():
    model = fake_model(extracted("raw"), Text("clean"), Valid(CLASSIFICATION), Valid(EXPLANATION))

    with pytest.raises(StepLimitExceededError):
        run(model, recursion_limit=2)


def test_token_usage_accumulates_across_nodes():
    model = fake_model(
        extracted("raw", input_tokens=100, output_tokens=10),
        Text("clean", input_tokens=20, output_tokens=5),
        Invalid(input_tokens=30, output_tokens=3),  # retry tokens count too
        Valid(CLASSIFICATION, input_tokens=40, output_tokens=4),
        Valid(EXPLANATION, input_tokens=50, output_tokens=6),
    )

    progress = WorkflowProgress()

    run(model, progress=progress)

    assert progress.input_tokens == 100 + 20 + 30 + 40 + 50
    assert progress.output_tokens == 10 + 5 + 3 + 4 + 6


def test_provider_failure_in_text_node_maps_to_unavailable():
    with pytest.raises(LLMUnavailableError):
        run(fake_model(Raises(TimeoutError())))


def test_node_log_records_carry_the_analysis_id(caplog):
    model = fake_model(extracted("raw"), Text("clean"), Valid(CLASSIFICATION), Valid(EXPLANATION))

    with caplog.at_level("INFO", logger="eduvision.workflow.nodes"):
        run(model, analysis_id="abc-123")

    records = [r for r in caplog.records if hasattr(r, "step")]
    assert {r.step for r in records} == {"extract", "clean", "classify", "generate"}
    assert all(r.analysis_id == "abc-123" for r in records)


def test_conditional_edge_after_extract_has_labelled_routes():
    mermaid = build_graph(fake_model()).get_graph().draw_mermaid()

    assert "extract -. &nbsp;has text&nbsp; .-> clean;" in mermaid
    assert "extract -. &nbsp;no text&nbsp; .-> __end__;" in mermaid


def test_progress_tracks_tokens_and_text_when_the_run_fails():
    progress = WorkflowProgress()
    model = fake_model(
        extracted("raw", input_tokens=10, output_tokens=1),
        Text("clean", input_tokens=20, output_tokens=2),
        Invalid(input_tokens=30, output_tokens=3),
        Invalid(input_tokens=40, output_tokens=4),
    )

    with pytest.raises(InvalidLLMOutputError):
        run_workflow(
            model,
            image_bytes=b"x",
            image_media_type="image/png",
            recursion_limit=10,
            progress=progress,
        )

    assert (progress.input_tokens, progress.output_tokens) == (100, 10)
    assert (progress.raw_text, progress.cleaned_text) == ("raw", "clean")
    assert progress.extracted_text == "clean"
