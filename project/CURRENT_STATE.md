# Current State

Last updated: 2026-06-28

## Phase

TASK-011 — Midgard Studio GUI Runtime Page Integration.

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
- Windows GDI screen capture service (`WindowCaptureService`) using ctypes to capture target window client areas
- DPI-awareness configuration and 64-bit compatible HWND window discovery by title substring
- Win32 keyboard and mouse emulation service (`Win32InputAdapter` via `SendInput` hardware scan codes and coordinates) and in-memory test adapter (`DummyInputAdapter`)
- Client-to-screen coordinate converter using Win32 API (`ClientToScreen`) to support window-relative mouse actions
- Autonomous `HealModule` analyzing captured screen pixels to trigger recovery actions respecting random human-like delays
- Autonomous `CombatModule` performing color-based target scanning (centroid detection of matching pixel clusters) and triggering mouse attack commands
- Autonomous `NavigationModule` executing sequential waypoint walking loops via window client clicks and arrival timers
- Autonomous `ConsumablesModule` evaluating duration intervals to recast buffs and use utility items
- Interactive `ProfilesPage` with tabbed rule forms (Healing, Consumables, Combat, Navigation) that persist configurations directly into SQLite
- Interactive `RuntimePage` allowing profile selection, start/pause/stop runtime triggers, background event collection via a non-blocking `RuntimeWorker` thread, live terminal logging, and operational statistics metrics (HP, XP, Loot)
- Integration of GDI screen capture, input services, and multiple prioritized evaluation modules (Heal > Consumables > Combat > Navigation) into the active `RuntimeEngine` loop
- Console and rotating-file application logging
- Application version 0.2.0 displayed on the About page
- uv dependency declaration and lock-file workflow
- Ruff formatter and linter configuration
- pytest coverage for package metadata, settings, character profiles, runtime/IPC, GDI capture, Win32/Dummy inputs, Heal triggers, Combat scanning, Waypoint navigation, Consumables timers, Profiles rules GUI, and Runtime GUI
- GitHub Actions quality workflow for Ubuntu Latest (selectively skipping Windows GDI capture and Win32 input/mouse tests)
- Bootstrap, contributor, licensing, changelog, and project-memory documentation

## Not present

- Pathfinding path meshes (A* navmesh navigation)
- Computer vision or OCR (YOLO object detection)
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
- pytest passed with 39 tests
- SQLite theme persistence passed across application starts
- SQLite character profiles CRUD, rules, cascading deletion, and stats tracking passed
- Runtime launcher, TCP protocol packing, engine cycle commands, and graceful subprocess termination passed
- Windows GDI screen capture, DPI-awareness, 64-bit title discovery, and mock GDI fallback tests passed
- Win32 key/mouse input packing, Heal Module pixel color deviation triggers, and random cooldown tests passed
- Combat Module color target scanning, centroid calculation, and target clicking tests passed
- Navigation Module waypoint parsing, sequential index walking, wait cooldowns, and Heal/Combat interrupt priority tests passed
- Consumables Module duration interval recasting, parser configuration, and prioritized (Heal > Consumables > Combat > Navigation) execution tests passed
- Profiles GUI Rules Editor tab loading, selector creation, and database saving tests passed
- Runtime GUI controller profile selection, start/pause/stop process triggers, worker thread updates, live logging terminal, and telemetry tests passed
- Native Windows launch and dark/light theme screenshots were visually inspected
- The uv lock resolves the full PySide6 dependency for CI installation

## Delivery state

TASK-011 is completed and verified. Integration into `main` remains subject to human review and will not occur automatically.
