# Current State

Last updated: 2026-06-28

## Phase

TASK-027 — Gravity Evasion & Auto-Stash Management.

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
- Autonomous `HealModule` cropping HP/SP character status regions and executing template-matching character OCR to parse actual health ratios (supporting both HP/SP independently)
- Zero-dependency `DigitRecognizer` resolving digit outputs (e.g. '120/150' or '90%') from binarized UI crops and computing exact health metrics
- Autonomous `CombatModule` performing target scanning: color-based centroid, OpenCV template matching (monsters sprites folders), and Hover Red HP Bar cursor validations.
- Autonomous `NavigationModule` executing sequential waypoint walking loops, loading obstacle maps from PNG/BMP visual images and JSON coordinate matrices, and routing paths via A* pathfinding.
- Autonomous `StashModule` monitoring weight indicators and running automated Kafra storage banking workflows.
- Autonomous `ConsumablesModule` evaluating duration intervals to recast buffs and use utility items
- Interactive `ProfilesPage` with tabbed rule forms (Healing, Consumables, Looting, Combat, Navigation, Security, Stash) that persist configurations directly into SQLite. Healing tab contains a 'Verify Crop' modal helper to visually inspect cropped image segments (scaled x3) and check parsed OCR values before starting the engine. The Looting tab allows configuring dropped item name label colors, color tolerance, and cooldowns. The Combat tab configures multiple OpenCV target modes, template offsets, and hover check box dimensions.
- SettingsPage containing appearance theme selectors, GameGuard Evasion Desktop Capture Fallback checks, and border safety input clamps.
- Interactive `RuntimePage` allowing profile selection, start/pause/stop runtime triggers, background event collection via a non-blocking `RuntimeWorker` thread, live terminal logging, and operational statistics metrics (HP, XP, Loot)
- Searchable and clearable `LogsPage` visual terminal with real-time file reading, filtering by text patterns, and severity level selections (INFO, WARNING, ERROR)
- Active `StatisticsPage` displaying profile operational metrics (XP accumulated, loot collected, deaths, session times) directly queried from SQLite storage
- Targeting Game Window Attachment: selector dialog that fetches active Win32 client handles (HWNDs) and process IDs (PIDs) to bypass anti-cheat hooks. Stores target as `WindowName [PID: 1234]` to lock the bot to a specific client instance while displaying character identity inside the Studio UI.
- Single, standalone executable build compiled using PyInstaller (`dist/MidgardStudio.exe`) for portable Windows distribution
- Searchable and clearable `LogsPage` visual terminal with real-time file reading, filtering by text patterns, and severity level selections (INFO, WARNING, ERROR)
- Active `StatisticsPage` displaying profile operational metrics (XP accumulated, loot collected, deaths, session times) directly queried from SQLite storage
- Single, standalone executable build compiled using PyInstaller (`dist/MidgardStudio.exe`) for portable Windows distribution
- Visual `PickDialog` coordinate and color picker overlay displaying target window GDI captures with hover tooltips and automatic coordinate/RGB population
- Antidetection input protections: Bezier curve smooth mouse trajectories, randomized key/click hold durations mimicking human behavior
- Alarm notification system: engine emits IPC TCP `alarm` events for character death (HP=0%) and game client disconnection; Studio plays audio beep and flashes red UI alerts
- A* pathfinding navigation: grid-based pathfinding route solver for custom game obstacle maps and coordinate sequential walks
- Emergency Evasion Module: panic triggers using configurable hotkeys (teleport/logout) if player health drops below critical threshold (e.g. 20%)
- OpenCV image template detector using TM_SQDIFF_NORMED for visual state recognition (full inventory, client errors, UI dialogs)
- Integration of GDI screen capture, input services, and multiple prioritized evaluation modules (Heal > Evasion > Looting > Consumables > Combat > Navigation) into the active `RuntimeEngine` loop
- Console and rotating-file application logging
- Application version 0.2.0 displayed on the About page
- uv dependency declaration and lock-file workflow
- Ruff formatter and linter configuration
- pytest coverage for package metadata, settings, character profiles, runtime/IPC, GDI capture, Win32/Dummy inputs, Heal triggers, Combat scanning, Waypoint navigation, Consumables timers, Profiles rules GUI, Runtime GUI, Pick Dialog overlay, Antidetection/Alarm system, A* Pathfinding route solver, Evasion triggers, OpenCV Template Matching, Searchable Logs/Statistics GUI layouts, PyInstaller builder script configurations, and Win32 process ID (PID) window binding methods
- GitHub Actions quality workflow for Ubuntu Latest (selectively skipping Windows GDI capture and Win32 input/mouse tests)
- Bootstrap, contributor, licensing, changelog, and project-memory documentation

## Not present

- Pathfinding path meshes (A* navmesh navigation) [Implemented grid-based A* routing, mesh structures not present]
- Computer vision or OCR (YOLO object detection)
- Plugin system
- AI features
- Distribution or release artifacts [Standalone .exe generated at dist/MidgardStudio.exe]

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
- pytest passed with 69 tests
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
- Visual Pick Dialog coordinate pixel clicks, hover tooltip updates, screen capture conversions, and automatic UI form population tests passed
- Bezier path smoothing (start/end coverage, intermediate steps), randomized key hold times, engine death and disconnect alarm events, and GUI alarm handler display tests passed
- A* path routing solvers (basic path, obstacle detours, blocked targets) and Evasion panic health hotkey actions tested and passed
- OpenCV image Template Matching searches and threshold matching logic tested and passed
- Digit character recognizer OCR image text extraction and visual verification crop dialogs tested and passed
- Searchable diagnostics logs, text query matching, level filters, and active profile statistics page updates tested and passed
- Executable compiler builder script (`build_executable.py`) successfully generated standalone executable binary `MidgardStudio.exe` at project root `dist/` directory
- Win32 Process ID (PID) query functions, window handle (HWND) discovery by PID, and target selection UI list dialogs tested and passed
- Native Windows launch and dark/light theme screenshots were visually inspected
- The uv lock resolves the full PySide6 dependency for CI installation

## Delivery state

TASK-027 is completed and verified. Integration into `main` remains subject to human review and will not occur automatically.
