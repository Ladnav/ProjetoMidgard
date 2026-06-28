# Project History

This file is the chronological project record. Add entries when approved decisions change or a
task materially changes the repository; do not rewrite past entries to imply knowledge that was
not available at the time.

## 2026-06-27 — Sprint 0 validation

- Established the assistant's role as a long-term engineering collaborator.
- Confirmed that implementation requires an inspected repository, explicit scope, a plan, and
  synchronized documentation.
- Confirmed that changes must not be merged automatically into `main`.

## 2026-06-27 — TASK-001 planning

- Inspected the intentionally empty Git repository.
- Proposed a minimal Python repository foundation and recorded decisions that required approval.
- Made no repository files or commits during planning.

## 2026-06-27 — TASK-001B bootstrap

- Approved Python 3.12, uv with pip fallback, Ruff, pytest, Semantic Versioning, MIT licensing,
  and GitHub Actions on Ubuntu Latest.
- Selected `midgard` as the Python package name.
- Located durable project memory in `project/`, with `START_HERE.md` at the repository root.
- Created the engineering foundation without application or automation logic.
- Verified the locked environment with Python 3.12.13, Ruff, and pytest; all checks passed.
- Left the work uncommitted and unpushed for human review.

## 2026-06-27 — TASK-002 Midgard Studio bootstrap

- Approved PySide6 as the graphical toolkit for the first executable application.
- Added the Midgard Studio main window, left navigation, and seven empty destination pages.
- Added light and dark themes with the selected theme persisted in SQLite.
- Added console and rotating-file application logging.
- Exposed application version 0.2.0 on the About page.
- Added executable entry points, application tests, and synchronized project documentation.
- Preserved the explicit exclusion of automation and gameplay runtime behavior.
- Validated eight tests on Python 3.12.13 and visually inspected both supported themes.
- Prepared the combined TASK-001B and TASK-002 foundation for the repository's first commit.

## 2026-06-28 — TASK-003 Character Profiles SQLite Schema

- Designed and implemented the relational SQLite schema for Character Profiles, including tables for profiles, rules (by category), and stats.
- Created `src/midgard/profile.py` containing the `Profile` and `ProfileStats` data models, and the `ProfileStore` data access layer.
- Hooked the database connection initialization and cleanup for `ProfileStore` into the main application bootstrap process in `src/midgard/application.py`.
- Added comprehensive unit test coverage in `tests/test_profile.py` (6 tests covering CRUD, key-value rules, stats updating, and cascade deletes).
- Validated all 14 tests passing under Python 3.14.5 and formatting checking with Ruff.

## 2026-06-28 — TASK-004 Midgard Runtime Process Model & IPC

- Designed and implemented a multi-process architecture where the bot runtime executes in isolated child processes (`RuntimeEngine`), leaving the parent Studio GUI responsive.
- Created `src/midgard/runtime/protocol.py` defining a length-prefixed JSON-over-TCP framing protocol to prevent packet fragmentation.
- Created `src/midgard/runtime/engine.py` defining the autonomous engine executing a tick loop and reading commands non-blockingly via socket select.
- Created `src/midgard/runtime/launcher.py` managing TCP binding, subprocess spawning with environmental PYTHONPATH injection, and connection handshaking.
- Connected process termination safety checks inside the main application teardown lifecycle (`aboutToQuit` hook).
- Added comprehensive unit and integration tests in `tests/test_runtime.py` covering message framing and full process start, command, and stop lifecycles.
- Verified all 16 tests passing under Python 3.14.5 and Ruff check formatting validation.

## 2026-06-28 — TASK-005 Midgard Vision Foundation

- Designed and implemented the Windows GDI screen capture pipeline using native ctypes integration without requiring extra dependencies.
- Created `src/midgard/vision/capture.py` containing `WindowCaptureService` (BitBlt capture to PIL Image) and `find_window_by_title` (EnumWindows title substring search).
- Added DPI-awareness setup (`SetProcessDpiAwareness`) to prevent OS-level scaling alignment issues.
- Fixed 64-bit calling convention issues in `EnumWindows` using `ctypes.c_void_p` for HWND pointers and fixed callback garbage collection bugs.
- Created `tests/test_vision.py` containing unit tests with complete mock GDI pipelines to allow running GDI tests inside headless Sessions (Session 0) and platform checks to safely skip GDI capture on non-Windows CI runners.
- Verified all 22 tests passing under Python 3.14.5 and Ruff check formatting validation.

## 2026-06-28 — TASK-006 Midgard Automation MVP (Heal & Input)

- Designed and implemented a keyboard input emulation layer (`BaseInputAdapter`, `Win32InputAdapter` using native `SendInput` hardware scan codes, and `DummyInputAdapter` for testing) in `src/midgard/runtime/input.py`.
- Implemented `HealModule` in `src/midgard/runtime/heal.py` that monitors specific pixel coordinates in the game client client area and triggers healing hotkeys (using the input adapter) when colors deviate past a configured tolerance threshold, applying random human-like delays.
- Integrated the GDI capture, input, and healing evaluations into the active `RuntimeEngine` loop cycle, loading rules directly from the profile's SQLite database during initialization.
- Added comprehensive unit tests in `tests/test_automation.py` covering key event histories, disabled states, color distance calculation triggers, and cooldown windows.
- Updated `tests/test_runtime.py` to launch subprocesses with `--dummy-input` to bypass GDI/Win32 hooks warnings on headless CI test environments.
- Verified all 26 tests passing under Python 3.14.5 and Ruff check formatting validation.

## 2026-06-28 — TASK-007 Midgard Advanced Automation Foundation (Mouse & Target Selection)

- Extended `src/midgard/runtime/input.py` to support absolute mouse movements (`move_mouse_relative`) and click events (`click_mouse`) using Win32 `MOUSEINPUT` structures inside `SendInput`.
- Implemented native `ClientToScreen` conversion inside `Win32InputAdapter` to translate window-relative client coordinates into correct screen coordinate space.
- Created `CombatModule` in `src/midgard/runtime/combat.py` implementing a performance-optimized color grid scanner to locate targets (monsters/nameplates) and compute their centroid coordinates for attack clicks.
- Integrated the `CombatModule` into the `RuntimeEngine` tick loop alongside `HealModule`, sharing the same screen capture image to conserve system resources.
- Added comprehensive unit tests in `tests/test_combat.py` verifying Dummy adapter mouse event recording, grid target finding, centroid math accuracy, and combat action cooldown windows.
- Verified all 30 tests passing under Python 3.14.5 and Ruff check formatting validation.

## 2026-06-28 — TASK-008 Midgard Waypoint Navigation & Priority Loop

- Created `NavigationModule` in `src/midgard/runtime/navigation.py` supporting coordinate sequence parsing (format: `x,y,wait;x,y,wait`) and sequential index walk loops using relative mouse click triggers.
- Integrated `NavigationModule` into the `RuntimeEngine` lifecycle and configured it to load path configurations from the profile's SQLite rules.
- Implemented the priority evaluation hierarchy (Heal > Combat > Navigation) inside `RuntimeEngine._tick` to prevent navigation clicks from interrupting critical heal triggers or combat target attacks.
- Added comprehensive unit tests in `tests/test_navigation.py` validating waypoint coordinate parsing, sequential walk index increments, cooldown arrival timers, and priority loop evaluation states.
- Verified all 34 tests passing under Python 3.14.5 and Ruff check formatting validation.

## 2026-06-28 — TASK-009 Midgard Consumables & Buffs

- Created `ConsumablesModule` in `src/midgard/runtime/consumables.py` designed to read and parse timed consumable duration lists (format: `name,key,duration;name,key,duration`) and trigger recasting keypresses as durations expire.
- Integrated `ConsumablesModule` into `RuntimeEngine` and updated the loop tick priority queue (Heal > Consumables > Combat > Navigation).
- Added comprehensive unit tests in `tests/test_consumables.py` verifying duration item parsing, recast checks, and priority execution interrupts.
- Verified all 37 tests passing under Python 3.14.5 and Ruff check formatting validation.

## 2026-06-28 — TASK-010 Midgard Studio GUI Rules Integration

- Replaced the profile placeholder page in the PySide6 app with an interactive tabbed rules configuration view (`ProfilesPage`).
- Implemented forms for all engine modules (Healing, Consumables, Combat, Navigation) mapped directly to SQLite settings fields via `ProfileStore`.
- Added mock dialog coverage to test case GUI automation and verified UI forms, saving updates, and loading states without blocking modal popups.
- Verified all 38 tests passing under Python 3.14.5 and Ruff check formatting validation.
