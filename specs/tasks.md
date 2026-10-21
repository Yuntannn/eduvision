# Tasks – EduVision (Basic Backend Version)

Work through the tasks in order. Each task is one branch and one PR into `develop`.

**Every task is done only when:**
- [ ] `uv run ruff check .` and `uv run ruff format --check .` pass
- [ ] `uv run mypy src` passes
- [ ] `uv run pytest` passes
- [ ] Changes are committed, PR'd into `develop` and merged
- [ ] The next task starts from an up-to-date `develop`

Requirement IDs (e.g. R2.1) refer to `requirements.md`.

---

## EDU-1 · Project setup
**Branch:** `feature/EDU-1-project-setup`

- [ ] Initialise the repo with `uv`, Python 3.12, `src/eduvision` layout
- [ ] Add dependencies: `fastapi`, `uvicorn`, `pydantic-settings`, `sqlmodel`, `python-multipart`, `langgraph`, `langchain-core`, `langchain-anthropic`
- [ ] Add dev dependencies: `pytest`, `pytest-asyncio`, `httpx`, `ruff`, `mypy`
- [ ] Configure `ruff` and `mypy` in `pyproject.toml` exactly as in design §11 (mypy strict for `src/`, relaxed for `tests/`, `ignore_missing_imports = true`, Pydantic plugin)
- [ ] Add `.gitignore` (include `.env`, `data/`, `.venv/`)
- [ ] Add `.env.example` with every variable from design §4
- [ ] Add `CLAUDE.md` (project context, commands, layering rules, "always run checks before committing")
- [ ] Add `README.md` skeleton (setup, run, test)
- [ ] Create `develop` branch

**Done when:** `uv run pytest` runs (0 tests is fine) and lint/type checks pass.
**Commit:** `chore: initialise project structure and tooling`

---

## EDU-2 · App skeleton, config and health check
**Branch:** `feature/EDU-2-app-skeleton`
**Covers:** R1.1, NFR1, NFR4, NFR5

- [ ] `config.py` with `Settings` (design §4)
- [ ] `logging_config.py`
- [ ] `main.py` with an app factory `create_app()`
- [ ] `api/health.py` → `GET /health`
- [ ] `api/errors.py` with the standard error response format (design §6)
- [ ] `tests/conftest.py` with a test client fixture
- [ ] `tests/test_health.py`

**Done when:** `uvicorn` starts, `/health` returns `{"status": "ok"}`, `/docs` loads.
**Commit:** `feat: add app skeleton, settings and health check`

---

## EDU-3 · Database and storage
**Branch:** `feature/EDU-3-db-and-storage`
**Covers:** R2.5 (storage), data model in design §5

- [ ] `db/session.py` (engine, session dependency, create tables on startup)
- [ ] `db/models.py` with `Upload` and `Analysis`
- [ ] `db/repositories.py` (create/get upload; create/update/get/list analyses with pagination)
- [ ] `storage/local_storage.py` (save bytes with generated name, read bytes)
- [ ] Test fixtures: temp DB and temp upload dir
- [ ] Repository and storage tests

**Done when:** repository tests cover create, get, update and paginated list.
**Commit:** `feat: add database models, repositories and local file storage`

---

## EDU-4 · Upload endpoint
**Branch:** `feature/EDU-4-upload-endpoint`
**Covers:** R2.1 – R2.5

- [ ] `schemas/upload.py`
- [ ] `services/upload_service.py` (validate type and size, save file, save record)
- [ ] `api/uploads.py` → `POST /api/v1/uploads`
- [ ] Tests: valid JPEG/PNG/WebP (201), wrong type (415), too large (413), missing file (422), stored filename is generated

**Done when:** you can upload an image through `/docs` and see the file in `data/uploads`.
**Commit:** `feat: add image upload endpoint with validation`

---

## EDU-5 · LLM layer, structured outputs and fake model
**Branch:** `feature/EDU-5-llm-layer`
**Covers:** R3.3, R3.4, R3.7, NFR2, NFR6

- [ ] `schemas/llm_outputs.py` with `Classification` and `Explanation` (Literal enums, list length limits)
- [ ] `llm/factory.py` → returns a chat model based on `LLM_PROVIDER` (`anthropic` or `fake`)
- [ ] `llm/structured.py` → `call_structured()` with one retry and `InvalidLLMOutputError`
- [ ] Error types: `InvalidLLMOutputError`, `LLMUnavailableError`
- [ ] `tests/fakes.py` → scripted fake chat model (valid output, invalid output, raise error, token usage)
- [ ] Tests: valid on first try, invalid then valid (retry works), invalid twice (raises), token usage is returned

**Done when:** structured-output tests pass using only the fake model.
**Commit:** `feat: add LLM factory, structured output helper with retry, and fake model`

---

## EDU-6 · Workflow nodes and graph
**Branch:** `feature/EDU-6-workflow`
**Covers:** R3.2, R3.6, R3.8, R5.1

- [ ] `workflow/state.py`
- [ ] `workflow/prompts.py` (one prompt per node; extract prompt defines the `NO_TEXT_FOUND` sentinel)
- [ ] `workflow/nodes.py` → `extract`, `clean`, `classify`, `generate`; each adds token usage to state and logs duration
- [ ] `workflow/graph.py` → build and compile the graph, conditional edge after `extract`
- [ ] Run function that applies `recursion_limit` and maps `GraphRecursionError`
- [ ] Tests: happy path (all fields populated), no text found (stops after extract), invalid output twice (fails with `invalid_llm_output`), step limit exceeded, token usage accumulated

**Done when:** the full workflow runs end to end with the fake model.
**Commit:** `feat: add LangGraph analysis workflow with extract, clean, classify and generate nodes`

---

## EDU-7 · Analysis endpoints
**Branch:** `feature/EDU-7-analysis-endpoints`
**Covers:** R3.1, R3.5 – R3.9, R4.1 – R4.3, R5.2

- [ ] `schemas/analysis.py` (`CreateAnalysisRequest`, `AnalysisResponse`, list response)
- [ ] `services/analysis_service.py` (load upload, run workflow, measure duration, save result or failure)
- [ ] `api/analyses.py` → `POST /api/v1/analyses`, `GET /api/v1/analyses/{id}`, `GET /api/v1/analyses`
- [ ] Map errors to status codes (404, 422, 502, 500) per design §6
- [ ] Tests for every status code; failed analyses are saved with the correct `failure_reason`; list is newest first with pagination

**Done when:** upload → analyse → get → list works through the API with the fake model.
**Commit:** `feat: add analysis endpoints with persistence and error handling`

---

## EDU-8 · Real model smoke test and README
**Branch:** `feature/EDU-8-smoke-test-docs`
**Covers:** NFR4, Definition of Done

- [ ] Add 2–3 sample images to `samples/` (one printed, one handwritten, one with no text)
- [ ] Add `scripts/smoke_test.py` that uploads and analyses a sample against the real model (skipped unless `ANTHROPIC_API_KEY` is set; not part of `pytest`)
- [ ] Run it manually and tune prompts if outputs are poor
- [ ] Complete `README.md`: overview, architecture diagram, setup, config, run, test, example request/response, future phases
- [ ] Record any prompt changes and what you fixed in `docs/notes.md` (useful for interviews)

**Done when:** a real image produces a valid explanation, and a new developer can follow the README.
**Commit:** `docs: add README, samples and real-model smoke test`

---

## Release
- [ ] Merge `develop` into `main`
- [ ] Tag `v0.1.0`
