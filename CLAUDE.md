# Unbreak AI

Incident triage agent. Distribution `unbreak-ai`, import package `unbreak_ai`, Python 3.12, managed with `uv`.

## Rules

- `specs/` is the source of truth (`overview.md`, `requirements.md`, `design.md`, `tasks.md`).
- Implement one task at a time, by its T-number from `specs/tasks.md`. Stop when its "done when" check passes.
- Write tests first. Mark tests that cover a requirement with `@pytest.mark.req("REQ-…")` (or `NFR-…`).
- If the code and the spec disagree, update the spec first, in its own commit.

## Conventions

- Naming follows the table in `specs/design.md` (classes `UnbreakAI…`, env vars `UNBREAK_AI_*`).
- Dependencies point one way: `agent` → `tools` → `providers`. `providers` never imports upstream modules; import-linter enforces it.
- Add files only when a task needs them; the package tree grows task by task.

## Commands

```sh
uv sync
uv run ruff check . && uv run ruff format --check .
uv run mypy
uv run lint-imports
uv run pytest        # includes the 80% coverage gate
```
