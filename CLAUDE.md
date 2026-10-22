# EduVision

Backend (Python 3.12, FastAPI) that accepts an image of educational content, runs a LangGraph
workflow (extract → clean → classify → generate) using a vision-capable LLM, and stores/returns
the analysis. Specs live in `specs/` (`requirements.md`, `design.md`, `tasks.md`) and are the
source of truth; work through `specs/tasks.md` in order, one task per branch.

## Commands

```bash
uv sync                          # install dependencies
uv run uvicorn eduvision.main:create_app --factory --reload   # run the API (after EDU-2)
uv run ruff check .              # lint
uv run ruff format --check .     # format check (use `uv run ruff format .` to fix)
uv run mypy src                  # type check (strict for src/)
uv run pytest                    # tests
```

## Layering rules

- `api/` routers handle HTTP only (parsing, status codes). No business logic.
- `services/` orchestrate: load data, call the workflow, save results.
- `workflow/` knows nothing about HTTP or the database: image in, result out.
- `db/` repositories are the only code that touches the database.
- The LLM is created only through `llm/factory.py`, so tests can inject a fake model.

## Conventions

- Settings come from `config.py` (`pydantic-settings`); every variable is listed in `.env.example`.
- mypy errors: fix the code first. `# type: ignore[code]` only for real third-party typing gaps,
  with the specific code and a short reason. Avoid `Any` in application code.
- Never log API keys, image bytes or full prompts.
- Git: branch `feature/EDU-<n>-<short-name>` from `develop`, Conventional Commits
  (`feat:`, `fix:`, `test:`, `chore:`, `docs:`), PR into `develop`.

## Environment

Environment: macOS with BSD command-line tools. Use the file edit tool or Python for in-place edits instead of sed -i.

## Workflow rules

- Only work on the task I name. Never start or partially implement later tasks.
- Never commit directly to `main` or `develop`. Always work on a feature branch.
- Don't commit until I've reviewed the changes and said to commit.
- Never merge PRs. I review and merge them myself.
- Do not add `Co-Authored-By` or any other attribution to commits or PRs.
- If the spec is unclear or conflicts with what the code needs, stop and ask me instead of guessing. If you deviate from the spec, list each deviation and the reason.

## Before committing

**Always run all checks before committing** and make sure they pass:
`ruff check .`, `ruff format --check .`, `mypy src`, `pytest`.

Stop any running dev server before running pytest. The test suite fails if ./data changes during a test run.
