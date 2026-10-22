import pytest
from fastapi.testclient import TestClient

from eduvision.api.analyses import get_chat_model
from eduvision.config import get_settings
from eduvision.llm.errors import LLMUnavailableError
from eduvision.schemas.llm_outputs import Classification, Explanation, ExtractionResult
from tests.fakes import FakeChatModel, Invalid, Raises, Text, Valid, fake_model

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32

CLASSIFICATION = Classification(
    subject="biology", topic="photosynthesis", content_type="definition", difficulty="beginner"
)
EXPLANATION = Explanation(
    title="How Plants Make Food",
    summary="Plants turn light into sugar.",
    key_points=["Light", "Water", "CO2"],
    examples=["A leaf in the sun"],
    diagram_mermaid=None,
)


def extracted(
    text: str, *, has_text: bool = True, layout: str | None = None, **tokens: int
) -> Valid:
    return Valid(ExtractionResult(has_text=has_text, text=text, layout=layout), **tokens)


def happy_script() -> list:
    return [
        extracted("Photosynthesis is teh process", input_tokens=100, output_tokens=10),
        Text("Photosynthesis is the process", input_tokens=20, output_tokens=5),
        Valid(CLASSIFICATION, input_tokens=30, output_tokens=3),
        Valid(EXPLANATION, input_tokens=40, output_tokens=8),
    ]


def use_model(client: TestClient, model: FakeChatModel) -> FakeChatModel:
    client.app.dependency_overrides[get_chat_model] = lambda: model
    return model


def upload(client: TestClient) -> str:
    response = client.post("/api/v1/uploads", files={"file": ("a.png", PNG, "image/png")})
    return response.json()["upload_id"]


def analyse(client: TestClient, upload_id: str | None = None):
    return client.post("/api/v1/analyses", json={"upload_id": upload_id or upload(client)})


def only_analysis(client: TestClient) -> dict:
    items = client.get("/api/v1/analyses").json()["items"]
    assert len(items) == 1
    return items[0]


def assert_failed(client: TestClient, response, status: int, reason: str) -> dict:
    """The error names the failure and the saved analysis; return that saved analysis."""
    assert response.status_code == status
    error = response.json()["error"]
    assert error["code"] == reason
    saved = only_analysis(client)
    assert error["analysis_id"] == saved["analysis_id"]
    assert saved["status"] == "failed"
    assert saved["failure_reason"] == reason
    return saved


def test_create_analysis_returns_full_result(client: TestClient) -> None:
    use_model(client, fake_model(*happy_script()))
    upload_id = upload(client)

    response = analyse(client, upload_id)

    assert response.status_code == 201
    body = response.json()
    assert body["upload_id"] == upload_id
    assert body["status"] == "completed"
    assert body["failure_reason"] is None
    assert body["extracted_text"] == "Photosynthesis is the process"
    assert body["classification"] == CLASSIFICATION.model_dump()
    assert body["explanation"] == EXPLANATION.model_dump()
    assert body["usage"]["input_tokens"] == 190
    assert body["usage"]["output_tokens"] == 26
    assert body["usage"]["duration_ms"] >= 0
    for key in ("created_at", "updated_at"):
        assert body[key].endswith("Z") or body[key].endswith("+00:00")


def test_layout_is_stored_and_returned(client: TestClient) -> None:
    script = happy_script()
    script[0] = extracted("Water\nCloud", layout="Arrow from Water up to Cloud")
    use_model(client, fake_model(*script))

    created = analyse(client).json()

    assert created["layout"] == "Arrow from Water up to Cloud"
    fetched = client.get(f"/api/v1/analyses/{created['analysis_id']}").json()
    assert fetched["layout"] == "Arrow from Water up to Cloud"


def test_layout_is_null_when_the_image_has_none(client: TestClient) -> None:
    use_model(client, fake_model(*happy_script()))

    assert analyse(client).json()["layout"] is None


def test_layout_is_kept_when_a_later_step_fails(client: TestClient) -> None:
    use_model(
        client,
        fake_model(extracted("raw text", layout="Arrow from A to B"), Raises(TimeoutError())),
    )

    saved = assert_failed(client, analyse(client), 502, "llm_unavailable")

    assert saved["layout"] == "Arrow from A to B"


def test_get_analysis_returns_the_stored_result(client: TestClient) -> None:
    use_model(client, fake_model(*happy_script()))
    created = analyse(client).json()

    response = client.get(f"/api/v1/analyses/{created['analysis_id']}")

    assert response.status_code == 200
    assert response.json() == created


def test_unknown_upload_is_404(client: TestClient) -> None:
    use_model(client, fake_model())

    response = analyse(client, "does-not-exist")

    assert response.status_code == 404
    assert response.json()["error"] == {
        "code": "upload_not_found",
        "message": "Upload does-not-exist was not found.",
    }  # no analysis exists, so no analysis_id
    assert client.get("/api/v1/analyses").json()["total"] == 0


def test_unknown_analysis_is_404(client: TestClient) -> None:
    response = client.get("/api/v1/analyses/does-not-exist")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "analysis_not_found"


@pytest.mark.parametrize("body", [{}, {"upload_id": ""}, {"upload_id": 5}])
def test_invalid_request_body_is_422(client: TestClient, body: dict) -> None:
    use_model(client, fake_model())
    response = client.post("/api/v1/analyses", json=body)

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_no_text_is_422_and_saved_as_failed(client: TestClient) -> None:
    model = use_model(client, fake_model(extracted("", has_text=False, input_tokens=7)))

    response = analyse(client)

    saved = assert_failed(client, response, 422, "no_text_found")
    assert len(model.calls) == 1
    assert saved["usage"]["input_tokens"] == 7  # extract tokens are still recorded
    assert saved["explanation"] is None


def test_llm_unavailable_is_502_and_saved_as_failed(client: TestClient) -> None:
    use_model(client, fake_model(Raises(TimeoutError())))

    response = analyse(client)

    saved = assert_failed(client, response, 502, "llm_unavailable")
    assert saved["extracted_text"] is None


def test_invalid_llm_output_is_500_and_saved_as_failed(client: TestClient) -> None:
    use_model(client, fake_model(extracted("raw"), Text("clean"), Invalid(), Invalid()))

    response = analyse(client)

    assert_failed(client, response, 500, "invalid_llm_output")


def test_step_limit_is_500_and_saved_as_failed(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("WORKFLOW_RECURSION_LIMIT", "2")
    get_settings.cache_clear()
    use_model(client, fake_model(*happy_script()))

    response = analyse(client)

    assert_failed(client, response, 500, "step_limit_exceeded")


def test_unexpected_error_is_500_and_saved_as_failed(client: TestClient) -> None:
    use_model(client, fake_model(Raises(RuntimeError("boom"))))

    response = analyse(client)

    assert_failed(client, response, 500, "internal_error")
    assert "boom" not in response.text


def test_failed_analysis_is_saved_before_the_error_is_returned(client: TestClient) -> None:
    use_model(client, fake_model(Raises(LLMUnavailableError("down"))))
    upload_id = upload(client)

    assert analyse(client, upload_id).status_code == 502

    saved = only_analysis(client)
    assert saved["upload_id"] == upload_id
    assert client.get(f"/api/v1/analyses/{saved['analysis_id']}").json()["status"] == "failed"


def test_analysis_id_is_passed_into_the_workflow(
    client: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    use_model(client, fake_model(*happy_script()))

    with caplog.at_level("INFO", logger="eduvision.workflow.nodes"):
        analysis_id = analyse(client).json()["analysis_id"]

    step_records = [r for r in caplog.records if r.name == "eduvision.workflow.nodes"]
    assert len(step_records) == 8  # a start and a finish line for each of the four nodes
    assert all(r.analysis_id == analysis_id for r in step_records)


def test_list_is_newest_first_with_pagination(client: TestClient) -> None:
    ids = []
    for _ in range(3):
        use_model(client, fake_model(*happy_script()))
        ids.append(analyse(client).json()["analysis_id"])

    page = client.get("/api/v1/analyses", params={"limit": 2}).json()
    assert [item["analysis_id"] for item in page["items"]] == [ids[2], ids[1]]
    assert (page["total"], page["limit"], page["offset"]) == (3, 2, 0)

    rest = client.get("/api/v1/analyses", params={"limit": 2, "offset": 2}).json()
    assert [item["analysis_id"] for item in rest["items"]] == [ids[0]]
    assert rest["offset"] == 2


def test_list_defaults_and_empty(client: TestClient) -> None:
    body = client.get("/api/v1/analyses").json()

    assert body == {"items": [], "total": 0, "limit": 20, "offset": 0}


@pytest.mark.parametrize("params", [{"limit": 0}, {"limit": 101}, {"offset": -1}])
def test_list_rejects_out_of_range_pagination(client: TestClient, params: dict) -> None:
    response = client.get("/api/v1/analyses", params=params)

    assert response.status_code == 422


def test_failure_in_classify_keeps_tokens_and_cleaned_text(client: TestClient) -> None:
    use_model(
        client,
        fake_model(
            extracted("Photosynthesis is teh process", input_tokens=100, output_tokens=10),
            Text("Photosynthesis is the process", input_tokens=20, output_tokens=5),
            Invalid(input_tokens=30, output_tokens=3),
            Invalid(input_tokens=40, output_tokens=4),  # the retry's tokens count too
        ),
    )

    response = analyse(client)

    saved = assert_failed(client, response, 500, "invalid_llm_output")
    assert saved["extracted_text"] == "Photosynthesis is the process"
    assert saved["usage"]["input_tokens"] == 100 + 20 + 30 + 40
    assert saved["usage"]["output_tokens"] == 10 + 5 + 3 + 4
    assert saved["usage"]["duration_ms"] >= 0
    assert saved["classification"] is None
    assert saved["explanation"] is None


def test_failure_in_clean_keeps_the_raw_text(client: TestClient) -> None:
    use_model(
        client,
        fake_model(extracted("raw text", input_tokens=50, output_tokens=5), Raises(TimeoutError())),
    )

    response = analyse(client)

    saved = assert_failed(client, response, 502, "llm_unavailable")
    assert saved["extracted_text"] == "raw text"
    assert saved["usage"]["input_tokens"] == 50


def test_step_limit_keeps_progress(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WORKFLOW_RECURSION_LIMIT", "3")  # extract, clean, classify; generate trips
    get_settings.cache_clear()
    use_model(client, fake_model(*happy_script()))

    response = analyse(client)

    saved = assert_failed(client, response, 500, "step_limit_exceeded")
    assert saved["extracted_text"] == "Photosynthesis is the process"
    assert saved["usage"]["input_tokens"] == 100 + 20 + 30
