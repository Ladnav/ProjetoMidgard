# Current State

Last updated: 2026-06-27

## Phase

TASK-002 — Midgard Studio graphical bootstrap.

## Present

- Git repository connected to the `Ladnav/ProjetoMidgard` GitHub repository
- Python 3.12 project metadata
- Executable PySide6 application through `midgard-studio` or `python -m midgard`
- Main window with left navigation sidebar
- Dashboard, Profiles, Runtime, Statistics, Settings, Logs, and About pages
- Light and dark themes selectable in Settings
- Theme preference persisted in a local SQLite `app_settings` table
- Console and rotating-file application logging
- Application version 0.2.0 displayed on the About page
- uv dependency declaration and lock-file workflow
- Ruff formatter and linter configuration
- pytest coverage for package metadata, settings persistence, navigation, themes, and logging
- GitHub Actions quality workflow for Ubuntu Latest
- Bootstrap, contributor, licensing, changelog, and project-memory documentation

## Not present

- Gameplay or automation runtime
- Screen capture
- Input automation
- Automation or gameplay behavior
- Computer vision or OCR
- Rule engine or bot logic
- Plugin system
- AI features
- Distribution or release artifacts

## Validation target

The foundation is considered healthy when the locked development environment resolves and the
following checks pass:

```shell
uv run ruff format --check .
uv run ruff check .
uv run pytest
```

Last verified on 2026-06-27 with CPython 3.12.13 and PySide6 6.11.1:

- Ruff formatting check passed
- Ruff lint check passed
- pytest passed with 8 tests
- SQLite theme persistence passed across application starts
- Native Windows launch and dark/light theme screenshots were visually inspected
- The uv lock resolves the full PySide6 dependency for CI installation

## Delivery state

TASK-001B and TASK-002 are being delivered together in the repository's first commit because the
approved TASK-001B foundation was intentionally left uncommitted. Integration into `main` remains
subject to human review and will not occur automatically.
