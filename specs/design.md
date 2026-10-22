# Design – EduVision (Basic Backend Version)

## 1. Tech Stack

| Concern | Choice | Reason |
|---|---|---|
| Language | Python 3.12 | Required by the AI ecosystem (LangChain/LangGraph) |
| Package manager | `uv` | Fast installs, lockfile, simple virtualenv management |
| Web framework | FastAPI | Async, Pydantic-native, built-in OpenAPI docs |
| Agent workflow | LangGraph | Explicit state graph, step limits, easy to extend with RAG / human review later |
| LLM client | LangChain chat models (`langchain-anthropic` by default) | Supports vision input and `with_structured_output()`; provider can be swapped |
| Validation / schemas | Pydantic v2 | Shared by FastAPI, structured outputs and settings |
| Settings | `pydantic-settings` | Typed config from env / `.env` |
| Database | SQLite via SQLModel (SQLAlchemy) | Zero setup locally; easy to move to PostgreSQL later |
| Testing | `pytest`, `pytest-asyncio`, `httpx` (FastAPI TestClient) | Standard, async-friendly |
| Quality | `ruff`, `mypy` | Lint, format, type checks |

## 2. Architecture

```
            ┌─────────────────────────────────────────────┐
 Client ──► │ FastAPI routers (api/)                      │
 (Swagger,  │   /health  /api/v1/uploads  /api/v1/analyses│
  curl)     └──────────────┬──────────────────────────────┘
                           │
                ┌──────────▼───────────┐
                │ Services (services/) │  upload_service, analysis_service
                └───┬──────────────┬───┘
                    │              │
        ┌───────────▼──┐     ┌─────▼──────────────────────────┐
        │ Repositories │     │ Workflow (workflow/)           │
        │ (db/)        │     │ LangGraph: extract → clean →   │
        │ SQLite       │     │            classify → generate │
        └──────────────┘     └─────┬──────────────────────────┘
                                   │
                         ┌─────────▼─────────┐
                         │ LLM provider      │  llm/factory.py
                         │ (real or fake)    │
                         └───────────────────┘
```

**Layering rules**

- Routers only handle HTTP concerns (parsing, status codes). No business logic.
- Services orchestrate: load data, call the workflow, save results.
- The workflow knows nothing about HTTP or the database. It takes an image and returns a result.
- The LLM is created through a single factory, so tests can inject a fake model.

## 3. Project Structure

```
eduvision/
├── CLAUDE.md
├── README.md
├── pyproject.toml
├── .env.example
├── specs/
│   ├── requirements.md
│   ├── design.md
│   └── tasks.md
├── src/eduvision/
│   ├── main.py                 # FastAPI app factory
│   ├── config.py               # Settings (pydantic-settings)
│   ├── logging_config.py
│   ├── api/
│   │   ├── health.py
│   │   ├── uploads.py
│   │   ├── analyses.py
│   │   └── errors.py           # exception → HTTP response mapping
│   ├── schemas/
│   │   ├── upload.py           # API request/response models
│   │   ├── analysis.py
│   │   └── llm_outputs.py      # ExtractionResult, Classification, Explanation (structured outputs)
│   ├── db/
│   │   ├── session.py
│   │   ├── models.py           # SQLModel tables
│   │   └── repositories.py
│   ├── services/
│   │   ├── upload_service.py
│   │   └── analysis_service.py
│   ├── storage/
│   │   └── local_storage.py    # save/read files on disk
│   ├── llm/
│   │   ├── factory.py          # build chat model from settings
│   │   └── structured.py       # structured call + one retry helper
│   └── workflow/
│       ├── state.py            # AnalysisState TypedDict
│       ├── prompts.py
│       ├── nodes.py            # extract, clean, classify, generate
│       └── graph.py            # build + compile graph
└── tests/
    ├── conftest.py             # app, temp DB, temp upload dir, fake LLM
    ├── fakes.py                # FakeChatModel with scripted responses
    ├── test_health.py
    ├── test_uploads.py
    ├── test_workflow.py
    └── test_analyses.py
```

## 4. Configuration

`config.py` defines a `Settings` class. `.env.example` lists every variable.

| Variable | Default | Notes |
|---|---|---|
| `LLM_PROVIDER` | `anthropic` | `anthropic` or `fake` |
| `LLM_MODEL` | *(required for real provider)* | Any vision-capable model ID |
| `ANTHROPIC_API_KEY` | – | Required when provider is `anthropic` |
| `LLM_TIMEOUT_SECONDS` | `60` | Per LLM call |
| `WORKFLOW_RECURSION_LIMIT` | `10` | Max graph steps |
| `UPLOAD_DIR` | `./data/uploads` | Created on startup if missing |
| `MAX_UPLOAD_BYTES` | `10485760` | 10 MB |
| `DATABASE_URL` | `sqlite:///./data/eduvision.db` | |
| `LOG_LEVEL` | `INFO` | |

## 5. Data Model

### `Upload` table

| Column | Type | Notes |
|---|---|---|
| `id` | UUID (str) | Primary key |
| `original_filename` | str | For display only |
| `stored_filename` | str | Generated: `{uuid}.{ext}` |
| `content_type` | str | `image/jpeg`, `image/png`, `image/webp` |
| `size_bytes` | int | |
| `created_at` | datetime (UTC) | |

### `Analysis` table

| Column | Type | Notes |
|---|---|---|
| `id` | UUID (str) | Primary key |
| `upload_id` | UUID (str) | FK → `Upload.id` |
| `status` | str | `pending`, `completed`, `failed` |
| `failure_reason` | str \| null | `no_text_found`, `invalid_llm_output`, `step_limit_exceeded`, `llm_unavailable` |
| `extracted_text` | text \| null | After the Clean step |
| `classification_json` | text \| null | Serialised `Classification` |
| `explanation_json` | text \| null | Serialised `Explanation` |
| `input_tokens` | int | Default 0 |
| `output_tokens` | int | Default 0 |
| `duration_ms` | int | Default 0 |
| `created_at` / `updated_at` | datetime (UTC) | |

## 6. API Contracts

### `GET /health`
`200` → `{"status": "ok"}`

### `POST /api/v1/uploads`
- Request: `multipart/form-data`, field `file`
- `201` →
```json
{ "upload_id": "uuid", "original_filename": "notes.jpg", "content_type": "image/jpeg", "size_bytes": 123456, "created_at": "..." }
```
- Errors: `413`, `415`, `422`

### `POST /api/v1/analyses`
- Request: `{ "upload_id": "uuid" }`
- `201` → `AnalysisResponse` (below)
- Errors: `404` (upload not found), `422` (no text found), `502` (LLM unavailable), `500` (other failures, analysis still saved as `failed`)

### `GET /api/v1/analyses/{analysis_id}`
`200` → `AnalysisResponse`, or `404`

### `GET /api/v1/analyses?limit=20&offset=0`
`200` → `{ "items": [AnalysisResponse], "total": 42, "limit": 20, "offset": 0 }`

### `AnalysisResponse`
```json
{
  "analysis_id": "uuid",
  "upload_id": "uuid",
  "status": "completed",
  "failure_reason": null,
  "extracted_text": "Photosynthesis is the process...",
  "classification": {
    "subject": "biology",
    "topic": "photosynthesis",
    "content_type": "definition",
    "difficulty": "beginner"
  },
  "explanation": {
    "title": "How Plants Make Food",
    "summary": "...",
    "key_points": ["...", "..."],
    "examples": ["..."],
    "diagram_mermaid": "flowchart LR\n  Sunlight --> Leaf ..."
  },
  "usage": { "input_tokens": 1234, "output_tokens": 567, "duration_ms": 8450 },
  "created_at": "...",
  "updated_at": "..."
}
```

### Error format (all errors)
```json
{ "error": { "code": "unsupported_media_type", "message": "Only JPEG, PNG and WebP images are supported." } }
```

## 7. Workflow Design (LangGraph)

### Why this structure

- **Four small nodes instead of one big prompt.** Each step has a single job and its own prompt, so it is easier to test, debug and later replace (e.g. adding RAG only touches `generate`).
- **Sequential pipeline, not a free-form orchestrator, for now.** The steps always run in the same order, so a fixed pipeline is simpler and more predictable. A routing orchestrator can be added later if steps become conditional.
- **One conditional edge** after `extract` to stop early when no text is found, which avoids wasting tokens on later steps.

### Graph

```
START → extract ──(has text?)──► clean → classify → generate → END
                     │
                     └─(no text)──► END   (failure_reason = no_text_found)
```

### State (`workflow/state.py`)

```python
class AnalysisState(TypedDict, total=False):
    image_bytes: bytes
    image_media_type: str
    raw_text: str
    cleaned_text: str
    classification: Classification
    explanation: Explanation
    failure_reason: str | None
    input_tokens: int      # accumulated across nodes
    output_tokens: int
```

### Nodes

| Node | Input | Output | LLM call |
|---|---|---|---|
| `extract` | image | `raw_text` | Vision call (image + instruction), structured output → `ExtractionResult(has_text, text)`. Unless `has_text` is true and `text` is non-empty after stripping, set `failure_reason = "no_text_found"`. |
| `clean` | `raw_text` | `cleaned_text` | Text call. Fix obvious recognition errors; must not add new content. |
| `classify` | `cleaned_text` | `classification` | Structured output → `Classification` |
| `generate` | `cleaned_text`, `classification` | `explanation` | Structured output → `Explanation` |

### Structured outputs and retry (`llm/structured.py`)

- `ExtractionResult`, `Classification` and `Explanation` are Pydantic models in `schemas/llm_outputs.py`, using `Literal` types for enum fields and `Field(min_length=..., max_length=...)` for list sizes.
- Helper `call_structured(model, schema, messages)`:
  1. Calls `model.with_structured_output(schema, include_raw=True)`.
  2. If parsing or validation fails, appends a message containing the validation error and retries **once**.
  3. If the retry fails, raises `InvalidLLMOutputError`.
- Token usage is read from the raw response's `usage_metadata` and added to state.

### Limits and failures

- The graph is invoked with `config={"recursion_limit": settings.workflow_recursion_limit}`. `GraphRecursionError` → `step_limit_exceeded`.
- Provider timeouts / connection errors → `LLMUnavailableError` → `llm_unavailable`.
- `analysis_service` catches all workflow exceptions, saves the analysis as `failed` with the mapped reason, then re-raises a typed error that `api/errors.py` maps to the HTTP status in Section 6.

## 8. Logging

- Standard library `logging` with a consistent format: `timestamp level analysis_id step duration_ms outcome message`.
- Each node logs start and end. Never log API keys, image bytes or full prompts.

## 9. Testing Strategy

- **Fake LLM** (`tests/fakes.py`): a chat model that returns scripted responses in order, including structured outputs and token usage, and can be scripted to return invalid output or raise errors. Injected via the `LLM_PROVIDER=fake` setting or a FastAPI dependency override.
- **Isolation:** each test gets a temporary SQLite database and a temporary upload directory.
- **Coverage by layer:**
  - API tests for every status code in Section 6
  - Workflow tests for the happy path, `no_text_found`, retry-then-success, retry-then-fail and step limit
  - Repository tests for save/get/list with pagination
- **Fixtures:** a small sample PNG generated in `conftest.py` (no binary files committed except optional examples in `samples/`).

## 10. Git Workflow

- `main` – stable; `develop` – integration branch.
- One branch per task: `feature/EDU-<task-number>-<short-name>`, e.g. `feature/EDU-3-upload-endpoint`.
- Each task ends with: `ruff check`, `ruff format --check`, `mypy`, `pytest` all green → commit → PR into `develop` → merge.
- Merge `develop` into `main` at the end of this version, tagged `v0.1.0`.
- Commit messages follow Conventional Commits: `feat:`, `fix:`, `test:`, `chore:`, `docs:`.

## 11. Code Quality Configuration

Add the following to `pyproject.toml`.

### mypy

Strict for application code, relaxed for tests, and tolerant of third-party libraries with incomplete type information (e.g. parts of LangChain / LangGraph).

```toml
[tool.mypy]
python_version = "3.12"
strict = true                   # strict checking for src/
ignore_missing_imports = true   # don't fail on third-party libs without type stubs
plugins = ["pydantic.mypy"]

[[tool.mypy.overrides]]
module = "tests.*"
disallow_untyped_defs = false   # test functions don't need full annotations
disallow_incomplete_defs = false
```

**Rules for handling mypy errors:**
- Fix the code first. Do not silence errors by default.
- `# type: ignore[<error-code>]` is allowed only for genuine third-party typing gaps, must include the specific error code, and must have a short comment explaining why.
- Avoid `Any` in application code unless it comes directly from a third-party API boundary.

### ruff

```toml
[tool.ruff]
line-length = 100
target-version = "py312"

[tool.ruff.lint]
select = ["E", "F", "I", "B", "UP", "SIM"]
# E/F: pycodestyle + pyflakes, I: import sorting, B: bugbear,
# UP: modern Python syntax, SIM: simplifications
```

### Commands

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy src
uv run pytest
```
