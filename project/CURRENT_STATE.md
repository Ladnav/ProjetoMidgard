# Current State

Last updated: 2026-06-28

## Phase

TASK-004 — Midgard Runtime Process Model and IPC implementation.

## Present

- Git repository connected to the `Ladnav/ProjetoMidgard` GitHub repository
- Python project metadata (compatible up to Python 3.14)
- Executable PySide6 application through `midgard-studio` or `python -m midgard`
- Main window with left navigation sidebar
- Dashboard, Profiles, Runtime, Statistics, Settings, Logs, and About pages
- Light and dark themes selectable in Settings
- Theme preference persisted in a local SQLite `app_settings` table
- SQLite database schema and `ProfileStore` manager for Character Profiles (supporting cascading deletes on rules/stats)
- Multi-process runtime architecture with `RuntimeLauncher` spawning `RuntimeEngine` subprocesses
- TCP-based IPC loopback protocol with JSON event framing and command control
- Console and rotating-file application logging
- Application version 0.2.0 displayed on the About page
- uv dependency declaration and lock-file workflow
- Ruff formatter and linter configuration
- pytest coverage for package metadata, settings persistence, navigation, themes, logging, character profiles, and runtime/IPC
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
python -m ruff format --check .
python -m ruff check .
python -m pytest
```

Last verified on 2026-06-28 with CPython 3.14.5 and PySide6 6.11.1:

- Ruff formatting check passed
- Ruff lint check passed
- pytest passed with 16 tests
- SQLite theme persistence passed across application starts
- SQLite character profiles CRUD, rules, cascading deletion, and stats tracking passed
- Runtime launcher, TCP protocol packing, engine cycle commands, and graceful subprocess termination passed
- Native Windows launch and dark/light theme screenshots were visually inspected
- The uv lock resolves the full PySide6 dependency for CI installation

## Delivery state

TASK-004 is completed and verified. Integration into `main` remains subject to human review and will not occur automatically.
