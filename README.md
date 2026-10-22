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

The server refuses to start unless `LLM_MODEL` and `ANTHROPIC_API_KEY` are set (in `.env` or the
environment).

For local work without an API key, start it with `LLM_PROVIDER=fake`. Analysis requests won't
work in that mode:

```bash
LLM_PROVIDER=fake uv run uvicorn eduvision.main:create_app --factory --reload
```

## Workflow

Each analysis runs a fixed LangGraph pipeline: extract the text, clean it, classify it, then
generate the explanation.

```mermaid
graph TD;
	__start__([start])
	extract(extract)
	clean(clean)
	classify(classify)
	generate(generate)
	__end__([end])
	__start__ --> extract;
	extract -. has text .-> clean;
	extract -. no text .-> __end__;
	clean --> classify;
	classify --> generate;
	generate --> __end__;
```

The dotted edges are the conditional exit after extraction: when no text is found, the workflow
stops there and the analysis fails with `no_text_found`.

## Test

```bash
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run mypy src
```
