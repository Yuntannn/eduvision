# Requirements – EduVision (Basic Backend Version)

## 1. Overview

EduVision is an AI-powered educational app. A teacher uploads a photo of handwritten or printed teaching content, and the system extracts the text, works out what the content is about, and generates a structured, student-friendly explanation with examples and a simple diagram.

This spec covers the **basic backend version only**:

- Python backend exposing a REST API
- A multi-agent workflow (LangGraph) that processes an uploaded image end to end
- Local persistence so results can be retrieved later
- Automated tests that run without calling a real LLM

**Out of scope for this version** (planned for later phases, see Section 6):

- Frontend (Next.js)
- RAG over curriculum materials
- Langfuse tracing and eval harness
- Human-in-the-loop review
- Authentication and multi-user support
- Cloud deployment

## 2. Users

| User | Description |
|---|---|
| Teacher | Uploads content and receives a generated explanation. In this version, the "teacher" is anyone calling the API (e.g. via Swagger UI or curl). |
| Developer | Runs, tests and extends the backend locally. |

## 3. User Stories and Acceptance Criteria

### R1. Health check

**As a** developer, **I want** a health endpoint, **so that** I can confirm the service is running.

- **R1.1** WHEN a client calls `GET /health` THEN the system SHALL return `200` with `{"status": "ok"}`.

### R2. Upload an image

**As a** teacher, **I want** to upload a photo of my teaching content, **so that** the system can analyse it.

- **R2.1** WHEN a client uploads a JPEG, PNG or WebP image up to 10 MB to `POST /api/v1/uploads` THEN the system SHALL store the file and return `201` with an `upload_id`.
- **R2.2** IF the file type is not JPEG, PNG or WebP THEN the system SHALL return `415` with a clear error message.
- **R2.3** IF the file is larger than 10 MB THEN the system SHALL return `413` with a clear error message.
- **R2.4** IF no file is provided THEN the system SHALL return `422`.
- **R2.5** The system SHALL store uploaded files on local disk under a configurable directory, using a generated file name (never the client-supplied name).

### R3. Analyse an uploaded image

**As a** teacher, **I want** the system to read my content and produce an explanation, **so that** I can share it with students.

- **R3.1** WHEN a client calls `POST /api/v1/analyses` with a valid `upload_id` THEN the system SHALL run the analysis workflow and return `201` with the analysis result.
- **R3.2** The workflow SHALL perform these steps in order:
  1. **Extract** – read the text from the image using a vision-capable LLM.
  2. **Clean** – fix obvious recognition errors and normalise formatting without changing meaning.
  3. **Classify** – identify subject, topic, content type and difficulty level.
  4. **Generate** – produce a student-friendly explanation.
- **R3.3** The classification SHALL be returned as structured data with these fields:
  - `subject` (e.g. "mathematics", "biology")
  - `topic` (short free text, e.g. "photosynthesis")
  - `content_type` (one of: `definition`, `worked_example`, `exercise`, `notes`, `diagram`, `other`)
  - `difficulty` (one of: `beginner`, `intermediate`, `advanced`)
- **R3.4** The generated explanation SHALL be returned as structured data with these fields:
  - `title`
  - `summary` (2–4 sentences)
  - `key_points` (3–6 items)
  - `examples` (1–3 items)
  - `diagram_mermaid` (a Mermaid diagram as text, or `null` if a diagram does not help)
- **R3.5** IF the `upload_id` does not exist THEN the system SHALL return `404`.
- **R3.6** IF no meaningful text can be extracted from the image THEN the system SHALL stop the workflow, mark the analysis as `failed` with reason `no_text_found`, and return `422`.
- **R3.7** IF an LLM step returns output that does not match the expected schema THEN the system SHALL retry that step once, passing the validation error back to the model. IF the retry also fails THEN the analysis SHALL be marked `failed` with reason `invalid_llm_output`.
- **R3.8** The workflow SHALL enforce a maximum number of steps. IF the limit is reached THEN the analysis SHALL be marked `failed` with reason `step_limit_exceeded`.
- **R3.9** IF the LLM provider is unavailable or times out THEN the analysis SHALL be marked `failed` with reason `llm_unavailable` and the API SHALL return `502`.
- **R3.10** IF any other unexpected error occurs during analysis THEN the analysis SHALL be marked `failed` with reason `internal_error` and the API SHALL return `500` without exposing internal details.
- **R3.11** A failed analysis SHALL keep the token usage, duration and any extracted text produced before the failure, and the error response SHALL include its `analysis_id`.

### R4. Retrieve an analysis

**As a** teacher, **I want** to retrieve a previous analysis, **so that** I don't have to re-run it.

- **R4.1** WHEN a client calls `GET /api/v1/analyses/{analysis_id}` THEN the system SHALL return the stored analysis, including status, extracted text, classification, explanation, failure reason (if any) and timestamps.
- **R4.2** IF the analysis does not exist THEN the system SHALL return `404`.
- **R4.3** WHEN a client calls `GET /api/v1/analyses` THEN the system SHALL return a list of analyses, newest first, with pagination (`limit`, default 20, max 100; `offset`, default 0).

### R5. Record usage

**As a** developer, **I want** to see how much each analysis costs and how long it takes, **so that** I can find slow or expensive steps.

- **R5.1** For each analysis, the system SHALL record total input tokens, total output tokens and total duration in milliseconds.
- **R5.2** These values SHALL be included in the analysis response.

## 4. Non-Functional Requirements

- **NFR1 – Configuration:** All secrets and settings (API keys, model name, upload directory, database URL, limits) SHALL be read from environment variables or a `.env` file. No secrets in code or Git.
- **NFR2 – Testability:** All tests SHALL run offline using a fake LLM. A real API key is never required to run the test suite.
- **NFR3 – Code quality:** Code SHALL pass `ruff` (lint + format) and `mypy` type checks.
- **NFR4 – Documentation:** The API SHALL expose OpenAPI docs at `/docs`. The README SHALL explain setup, configuration, running and testing.
- **NFR5 – Logging:** The system SHALL log each workflow step with the analysis ID, step name, duration and outcome. Logs SHALL NOT contain API keys or full image data.
- **NFR6 – Provider flexibility:** The LLM provider and model SHALL be configurable, so switching models does not require changes to workflow code.

## 5. Definition of Done (for this version)

- All acceptance criteria in Section 3 are covered by automated tests.
- `ruff`, `mypy` and `pytest` all pass.
- A developer can clone the repo, follow the README, upload a real image through `/docs` and get a valid explanation back.

## 6. Future Phases (not in this spec)

| Phase | Scope |
|---|---|
| 2 | Langfuse tracing; token budget per analysis |
| 3 | RAG over curriculum materials (Pinecone or Chroma) in the Generate step |
| 4 | Confidence check after Extract, with human-in-the-loop review via LangGraph `interrupt()` |
| 5 | Eval harness (fixed test images, accuracy / latency / cost report) |
| 6 | Next.js frontend |
| 7 | Deployment (Docker, cloud hosting, CI/CD) |
| Later | Downscale large images before sending them to the model (cuts tokens and latency) |
| Later | Validate Mermaid output before storing it, and retry or drop an invalid diagram |
