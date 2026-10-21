# EduVision

Backend service that analyses images of educational content using a LangGraph workflow and a
vision-capable LLM. See `specs/` for requirements, design and tasks.

## Setup

Requires [uv](https://docs.astral.sh/uv/) and Python 3.12.

```bash
uv sync
cp .env.example .env   # then fill in LLM_MODEL and ANTHROPIC_API_KEY
```

## Run

The API entry point is added in EDU-2:

```bash
uv run uvicorn eduvision.main:create_app --factory --reload
```

## Test

```bash
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run mypy src
```
