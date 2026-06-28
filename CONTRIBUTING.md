# Contributing to Project Midgard

Project Midgard is intended to evolve through small, reviewable, documented changes. Every
contribution should preserve the repository as the durable source of project knowledge.

## Before making changes

1. Read [START_HERE.md](START_HERE.md) and the files in [`project/`](project/).
2. Confirm the task scope, acceptance criteria, constraints, and open decisions.
3. Inspect the existing implementation and tests before proposing a solution.
4. Work on a dedicated branch; changes must not be merged automatically into `main`.
5. Do not silently decide questions recorded as open decisions.

## Development environment

Use Python 3.12. The primary dependency workflow is uv:

```shell
uv sync
```

When uv is unavailable, use a Python 3.12 virtual environment and install the development
dependencies listed in `pyproject.toml` with pip.

## Quality checks

Run all checks before requesting review:

```shell
uv run ruff format --check .
uv run ruff check .
uv run pytest
```

Use `uv run ruff format .` to apply formatting. GitHub Actions runs the same checks on Ubuntu.

## Change discipline

- Keep changes limited to the approved task.
- Add or update tests for behavior that changes.
- Update relevant documentation in the same change as implementation.
- Record user-visible or engineering-significant changes in `CHANGELOG.md`.
- Update `project/CURRENT_STATE.md`, `project/PROJECT_HISTORY.md`, and
  `project/NEXT_TASK.md` when their recorded state changes.
- Never commit secrets, local environment files, generated caches, or runtime output.
- Use Semantic Versioning for releases.

Commit messages should state the outcome clearly. A pull request should explain its scope,
verification, documentation impact, risks, and any unresolved decisions. Human approval is
required before integration into `main`.
