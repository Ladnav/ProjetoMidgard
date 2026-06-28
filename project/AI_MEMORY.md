# AI Memory

This file provides durable working context for AI-assisted contributions. It supplements, but
does not override, explicit user instructions or approved task decisions.

## Stable facts

- The project is named Project Midgard.
- The repository is the permanent project memory.
- Python 3.12/3.14 is the approved primary language version.
- The executable graphical foundation is Midgard Studio, built with PySide6.
- SQLite is the approved embedded database.
- Communication is event-oriented, using a local TCP loopback (`127.0.0.1`) IPC socket with length-prefixed JSON serialization to safely cross privilege boundaries.
- Configuration will be managed through the UI.
- Each character has an independent profile stored in the SQLite database (`profiles`, `profile_rules`, `profile_stats` tables).
- The bot execution engine uses a multi-process model: the Studio UI launches and manages independent `RuntimeEngine` subprocesses via `RuntimeLauncher`.
- Documentation is part of the product and must track implementation.
- The engineering workflow uses uv (or fallback pip), Ruff, pytest, Semantic Versioning, and GitHub Actions.
- Midgard Studio 0.2.0 has seven page shells, light/dark themes, SQLite-backed preferences, ProfileStore backend, and basic application logging.
- The Runtime page is a placeholder and contains no runtime logic.
- Changes must not be merged automatically into `main`.

## Working protocol

1. Read `START_HERE.md` and all files in `project/` before substantial work.
2. Inspect the current repository and Git state before proposing changes.
3. Separate approved facts from proposals and open decisions.
4. Present a bounded plan when the mission requires approval before editing.
5. Keep changes small, testable, documented, and limited to the mission.
6. Preserve unrelated work and never discard user changes without explicit permission.
7. Run the relevant quality checks and report exact results.
8. Update project memory whenever implementation state or approved decisions change.
9. Stop at the mission boundary; do not continue into an unapproved task.

## Current scope boundary

The graphical application foundation is authorized. Game automation, gameplay runtime behavior,
screen capture, computer vision, OCR, input automation, rule engines, bot logic, plugins, and AI
features remain prohibited unless a later task explicitly approves them.

## Open decisions

The authoritative list is maintained in `PROJECT_CONTEXT.md`. Do not resolve those decisions by
assumption.
