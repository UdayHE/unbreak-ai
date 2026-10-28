---
name: spec-review
description: Review a pull request against specs/ (one task, requirement tests, done-when, import contracts, secrets, spec drift), not just general code quality. Argument is owner/repo/pull/N.
---

# Spec review

Review the PR named in the argument. Read `CLAUDE.md` and `specs/` first, then the diff (`gh pr diff`, `gh pr view`).

## Checks

1. **One task.** The title has a `T-xx` id, the diff implements exactly that task in `specs/tasks.md`, and nothing outside it.
2. **Requirement tests.** Every requirement the task cites has at least one test marked `@pytest.mark.req("...")` (or `NFR-...`).
3. **Done when.** The task's "done when" check is demonstrated by tests in the PR, not only asserted in the description.
4. **Import contracts.** The import-linter config is untouched, or extended deliberately and explained. `providers` never imports upstream modules.
5. **Secrets.** No inline credentials. Every credential field is `SecretStr`. Error messages never include input values.
6. **Spec drift.** If code and spec disagree, the PR has a separate spec commit. Models match `specs/report.schema.json`.
7. **Ticked.** The task is ticked in `specs/tasks.md`.

## Output

Post inline comments on specific lines for findings. Then a short summary comment:

- **Verdict:** `approve` or `changes needed`.
- One line per failed check, citing the file and requirement id.

Be concise. Do not comment on style that ruff or mypy already enforce.
