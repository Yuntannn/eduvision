"""Manual smoke test: upload each sample and analyse it against the real model.

Not part of pytest. Run from the project root:  uv run python scripts/smoke_test.py [sample ...]
Uses the settings in .env, so it makes real (billed) API calls and writes to the configured
database and upload directory. Skipped unless ANTHROPIC_API_KEY is set.
"""

import sys
from pathlib import Path

from fastapi.testclient import TestClient

from eduvision.config import get_settings
from eduvision.main import create_app

SAMPLES_DIR = Path(__file__).resolve().parent.parent / "samples"
SAMPLE_NAMES = ("printed", "handwritten", "no_text", "diagram")
CONTENT_TYPES = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
}


def find_sample(name: str) -> Path | None:
    for path in sorted(SAMPLES_DIR.glob(f"{name}.*")):
        if path.suffix.lower() in CONTENT_TYPES:
            return path
    return None


def analyse(client: TestClient, path: Path) -> dict[str, object]:
    upload = client.post(
        "/api/v1/uploads",
        files={"file": (path.name, path.read_bytes(), CONTENT_TYPES[path.suffix.lower()])},
    )
    upload.raise_for_status()
    created = client.post("/api/v1/analyses", json={"upload_id": upload.json()["upload_id"]})
    if created.status_code == 201:
        body: dict[str, object] = created.json()
        return body
    # Failed analyses are still stored; the error body carries the id to fetch them by.
    error = created.json()["error"]
    print(f"  HTTP {created.status_code}: {error['code']} - {error['message']}")
    analysis_id = error.get("analysis_id")
    if analysis_id is None:
        raise RuntimeError(f"Analysis was not created: {error}")
    fetched = client.get(f"/api/v1/analyses/{analysis_id}")
    fetched.raise_for_status()
    body = fetched.json()
    return body


def show(name: str, result: dict[str, object]) -> None:
    usage = result["usage"]
    assert isinstance(usage, dict)
    classification = result["classification"]
    explanation = result["explanation"]
    print(f"  status:         {result['status']}")
    print(f"  failure_reason: {result['failure_reason']}")
    print("  extracted text:")
    for line in str(result["extracted_text"] or "(none)").splitlines() or [""]:
        print(f"    | {line}")
    print(f"  layout:         {result['layout']}")
    print("  classification:")
    if isinstance(classification, dict):
        for key, value in classification.items():
            print(f"    {key}: {value}")
    else:
        print("    (none)")
    print("  explanation:")
    if isinstance(explanation, dict):
        print(f"    title: {explanation['title']}")
        print(f"    summary: {explanation['summary']}")
        print("    key_points:")
        for point in explanation["key_points"]:
            print(f"      - {point}")
        print("    examples:")
        for example in explanation["examples"]:
            print(f"      - {example}")
        print("    diagram_mermaid:")
        for line in str(explanation["diagram_mermaid"] or "(none)").splitlines():
            print(f"      | {line}")
    else:
        print("    (none)")
    print(f"  input tokens:   {usage['input_tokens']}")
    print(f"  output tokens:  {usage['output_tokens']}")
    print(f"  duration:       {usage['duration_ms']} ms")


def main() -> int:
    settings = get_settings()
    if settings.llm_provider != "anthropic" or not settings.anthropic_api_key:
        print("Skipped: set LLM_PROVIDER=anthropic and ANTHROPIC_API_KEY in .env to run this.")
        return 0
    names = tuple(sys.argv[1:]) or SAMPLE_NAMES  # optionally run only the named samples
    print(f"Model: {settings.llm_model}")
    failures = 0
    with TestClient(create_app()) as client:
        for name in names:
            path = find_sample(name)
            if path is None:
                print(f"\n=== {name} ===")
                print(
                    f"  SKIPPED: no {name}.jpg/.jpeg/.png/.webp in samples/ (see samples/README.md)"
                )
                continue
            print(f"\n=== {name} ({path.name}) ===")
            try:
                show(name, analyse(client, path))
            except Exception as exc:  # keep going so one bad sample doesn't hide the others
                failures += 1
                print(f"  ERROR: {type(exc).__name__}: {exc}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
