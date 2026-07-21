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
- Screen capture is handled by a Windows GDI BitBlt pipeline (`WindowCaptureService` via ctypes) returning Pillow Image buffers.
- Keyboard input simulation is abstracted via `BaseInputAdapter`, utilizing native Windows `SendInput` hardware scan codes (`Win32InputAdapter`) to bypass hooks.
- Gameplay automation is started with a pixel-based `HealModule` checking health state coordinates and executing healing triggers with human-like delays.
- Documentation is part of the product and must track implementation.
- The engineering workflow uses uv (or fallback pip), Ruff, pytest, Semantic Versioning, and GitHub Actions.
- Midgard Studio has an operational Dashboard, an interactive Profiles editor (tabbed rules for Healing, Consumables, Looting, Experience, Combat, Navigation, Security, Stash), a Runtime control page, a Statistics page with a real telemetry chart, Settings, a searchable Logs viewer, and About — with light/dark themes, SQLite-backed preferences, and application logging.
- The Runtime page controls live automation sessions: it launches the `RuntimeEngine` subprocess, streams telemetry over IPC, and (2026-07-20) throttles chart/database sampling to one sample per second while accumulating real runtime.
- Implemented automation modules include Heal (pixel + OCR HP/SP), Combat (colour/OpenCV/hover), Navigation (A*, multi-map, custom-script plugins), Loot (colour clusters, nearest label), Consumables/buffs, Stash (Kafra/NPC selling), Anomaly/security, Discord notifications, and an OCR `ExperienceTracker`.
- Changes must not be merged automatically into `main`; work lands on feature branches via pull request.

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

Game automation is implemented and authorized: healing, combat target selection, map navigation
pathfinding, computer-vision template matching, OCR text reading, a custom-script plugin loader,
looting, consumables, stash/selling, notifications, and anti-detection input behaviours all exist
in the runtime. What remains out of scope: machine-learning behaviour, memory reading, cloud sync,
a plugin marketplace, and automatic updates.

This section previously read "graphical foundation only; automation prohibited," which described
the TASK-002 milestone and was never updated as tasks 003–035 shipped. It was corrected on
2026-07-20 with Product Owner approval so that AI contributors are not misled into treating existing
features as forbidden. See `PROJECT_HISTORY.md` (2026-07-20 documentation reconciliation) for the
background.

## Open decisions

The authoritative list is maintained in `PROJECT_CONTEXT.md`. Do not resolve those decisions by
assumption.
