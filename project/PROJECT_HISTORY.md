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

## 2026-06-28 — TASK-011 Midgard Studio GUI Runtime Page Integration

- Replaced the placeholder runtime page in PySide6 app with an interactive execution engine controller (`RuntimePage`).
- Implemented the `RuntimeWorker` `QThread` to read engine IPC TCP events in the background, updating the GUI with status and telemetry without blocking.
- Implemented Start, Pause, and Stop buttons to control subprocess launches and states, displaying monospaced logger windows and real-time HP/XP/Loot stats.
- Wired graceful termination lifecycle hooks inside MainWindow closeEvent to prevent lingering launcher or engine processes.
- Added comprehensive unit and UI integration tests in `tests/test_gui_runtime.py`.
- Verified all 39 tests passing under Python 3.14.5 and Ruff check formatting validation.

## 2026-06-28 — TASK-012 Midgard Studio GUI Color & Position Picker

- Implemented `PickDialog` and `PickerLabel` custom widget in `src/midgard/ui/picker.py` to enable pixel position and color selections.
- Added mouse hover tracking to display live coordinate `(x, y)` and RGB color values in tooltip overlays.
- Integrated "Pick" buttons in healing coordinate and combat target color fields of the ProfilesPage settings view.
- Handled game client window captures using GDI fallback to full screen monitor snapshot if the window discovery fails.
- Added comprehensive unit and integration tests in `tests/test_gui_picker.py` asserting dialog clicks and form updates.
- Verified all 41 tests passing under Python 3.14.5 and Ruff check formatting validation.

## 2026-06-28 — TASK-013 Antidetection Protections & Alarm Notification System

- Implemented cubic Bezier mouse curve trajectories in `src/midgard/runtime/input.py` to move the cursor smoothly with human-like acceleration and micro-sleeps.
- Added randomized key and mouse button press-and-hold durations (40ms to 90ms) mimicking human typing behavior.
- Added background engine alarms via IPC TCP for character death (HP=0%) and window client capture failures (disconnected/crashed client).
- Implemented visual indicators, red console warnings, and audio alerts (`QApplication.beep()`) in PySide6 `RuntimePage` to signal engine alarms.
- Created `tests/test_antidetect_alarms.py` to verify Bezier calculation, hold time delays, and alarm notifications.
- Verified all 48 tests passing under Python 3.14.5 and Ruff format validation.

## 2026-06-28 — TASK-014 A* Pathfinding & Emergency Evasion

- Implemented grid-based A* pathfinding search in `src/midgard/runtime/pathfinding.py` to route coordinates around map obstacles.
- Integrated pathfinder within the sequential waypoint loops of `src/midgard/runtime/navigation.py`.
- Implemented `EvasionModule` inside `src/midgard/runtime/evasion.py` to trigger hotkeys (e.g. Teleport F9) during critical HP danger levels.
- Created `tests/test_pathfinding_evasion.py` verifying path searching, blocked routes, and panic evasion hotkey triggers.
- Verified all 52 tests passing under Python 3.14.5 and Ruff check formatting validation.

## 2026-06-28 — TASK-015 OpenCV Template Matching Recognition

- Added `opencv-python-headless` dependency to the project package config (`pyproject.toml`).
- Implemented `TemplateDetector` in `src/midgard/vision/detector.py` performing BGR-aligned image sub-search matching via OpenCV's `TM_SQDIFF_NORMED`.
- Wired template checks into the main execution cycle in `src/midgard/runtime/engine.py` to report matches and trigger IPC events.
- Extended GUI alarm visual warnings on the RuntimePage when template match states are encountered.
- Created `tests/test_visual_detector.py` validating matching coords accuracy, threshold scaling, and fail conditions.
- Verified all 55 tests passing under Python 3.14.5 and Ruff check formatting validation.

## 2026-06-28 — TASK-017 Standalone Executable Packaging

- Added `pyinstaller` dependency to development groups inside `pyproject.toml`.
- Created build compiler script `build_executable.py` configuring PyInstaller bundle mappings (bundling PySide6, OpenCV, Pillow, SQLite schemas).
- Triggered automated build task successfully compiling portable standalone binary `dist/MidgardStudio.exe`.
- Succeeded packaging verification with clean Ruff checks.

## 2026-06-28 — TASK-020 PID Window Attachment and Binding

- Added Process ID query helper `list_windows_by_title_with_pid` and `find_hwnd_by_pid` using Windows User32 thread DLL calls inside `src/midgard/vision/capture.py`.
- Updated `WindowListDialog` inside `src/midgard/ui/picker.py` to display dynamic PID columns.
- Integrated targeted window attachment using PID string formats (e.g. `Ragnarok [PID: 1244]`) inside `src/midgard/ui/pages.py` to bypass anti-cheat protectors and uniquely track clients while displaying profile configurations cleanly.
- Implemented `tests/test_pid_binding.py` validating PID lookup and selector UI dialogs.
- Verified all 61 tests passing under Python 3.14.5 and Ruff check formatting validation.

## 2026-06-28 — TASK-021 Character OCR HP/SP Status Detection

- Created zero-dependency `DigitRecognizer` inside `src/midgard/vision/ocr.py` using shape-width heuristics to parse binarized crop strings.
- Modified `HealModule` inside `src/midgard/runtime/heal.py` to crop HP and SP regions of the game window and parse actual percentages using the OCR engine, enabling recovery actions for both HP and SP independently.
- Updated `ProfilesPage` inside `src/midgard/ui/pages.py` to configure and save crop parameters (X, Y, W, H) for HP and SP text bounding boxes.
- Created `tests/test_ocr_parser.py` validating OCR parser, crop parameters, and evaluate status checking.
- Succeeded verification checks with all 62 tests passing cleanly and clean Ruff formatting.

## 2026-06-28 — TASK-022 Visual Crop Verification Helper

- Created a `Verify Crop` modal helper inside `ProfilesPage` (`src/midgard/ui/pages.py`) that captures a game frame, extracts HP/SP crop areas, and runs them through the `DigitRecognizer` OCR parser.
- Displayed scaled cropped image blocks (x3) and calculated numerical values side-by-side inside the modal.
- Fixed an attribute lookup error inside `RuntimeEngine` (`src/midgard/runtime/engine.py`) where legacy color check properties were evaluated on the updated `HealModule` object.
- Updated mock test cases verifying the new verification dialog workflows inside `tests/test_gui_picker.py`.
- Verified all 62 test suites passing cleanly.

## 2026-06-28 — TASK-023 Auto-Looting Module

- Created `LootModule` inside `src/midgard/runtime/loot.py` identifying dropped item nameplate color pixel clusters and clicking centroids.
- Added a "Looting" rules configuration tab to the `ProfilesPage` editor in `src/midgard/ui/pages.py`, enabling nameplate color selections, tolerance settings, and cooldown sliders.
- Integrated `LootModule` into the `RuntimeEngine` execution loop (`src/midgard/runtime/engine.py`) prioritized below Heal and Evasion triggers but above Consumables, Combat, and Navigation tasks.
- Created `tests/test_looting.py` validating color centroid coordinates evaluation.
- Added GUI rule loads and saves test assertions in `tests/test_gui_rules.py` and `tests/test_gui_picker.py`.
- Verified all 63 tests passing successfully under pytest.

## 2026-06-28 — TASK-024 Advanced Combat OpenCV Target Scanning

- Refactored `CombatModule` in `src/midgard/runtime/combat.py` to support three target scanning modes: Color Centroid, Monster Template Matching, and Hover HP Bar Sweep validation.
- Implemented OpenCV-based template matching, loading monster sprites from a configurable directory.
- Implemented a Hover HP Bar sweep pattern, checking red color thresholds above the cursor to validate valid targets.
- Updated the Combat tab rules GUI in `src/midgard/ui/pages.py` to expose the new mode selectors, template match directories, threshold parameters, and hover check offset inputs.
- Created `tests/test_combat_opencv.py` verifying template matching and hover HP bar scanning workflows.
- Succeeded verification checks with all 66 tests passing successfully under pytest.

## 2026-06-28 — TASK-025 Visual Anomaly Detection (Anti-Detecção / Segurança)

- Implemented `AnomalyModule` in `src/midgard/runtime/anomaly.py` verifying captchas and GM visual prompts.
- Integrated highest priority tick check in `RuntimeEngine` loop to pause client on alarms or trigger ALT+F4 client force quits.
- Created `tests/test_anomaly.py` and updated GUI test suite rules.

## 2026-06-28 — TASK-026 Mesh-Based Navigation & GameGuard Evasion

- Implemented desktop monitor screen capture crops fallback option in `WindowCaptureService` (`src/midgard/vision/capture.py`) to bypass direct HWND anti-cheat process locks.
- Integrated SQLite database settings schema configurations load and save hooks inside `SettingsPage` (`src/midgard/ui/pages.py`).
- Added PNG/BMP visual image maps and JSON walkable grid matrices loader parser supporting A* pathfinding solvers inside `NavigationModule` (`src/midgard/runtime/navigation.py`).
- Created `tests/test_mesh_navigation.py` verifying visual A* path solvers and completed full verification check with all 68 tests passing successfully.

## 2026-06-28 — TASK-027 Gravity Evasion & Auto-Stash Management

- Added safety coordinate boundary clamping inside `Win32InputAdapter.move_mouse_relative` (`src/midgard/runtime/input.py`) to prevent Ragexe cursor-edge crashes.
- Created `StashModule` in `src/midgard/runtime/stash.py` monitoring weight balança indicators and clicking Kafra storage NPCs.
- Integrated Stash tab GUI rules rules inside `ProfilesPage` and database loader/saver (`src/midgard/ui/pages.py`).
- Created `tests/test_stash.py` verifying weight warning detection and Kafra storage dialog click flows. Completed verification check with all 69 tests passing successfully.

## 2026-06-28 — TASK-028 Anti-Cheat Polymorphic Input, Auto-Restocking, and Discord Webhooks

- Added Gaussian noise coordinate offsets and dampings inside `generate_bezier_path` (`src/midgard/runtime/input.py`) to create polymorphic, unique hand mouse movement curves.
- Created `DiscordNotifier` in `src/midgard/runtime/discord.py` posting styled embeds alert status warnings.
- Updated `StashModule` in `src/midgard/runtime/stash.py` to trigger merchant NPC buy transactions.
- Updated Security and Stash GUI settings rules in `src/midgard/ui/pages.py` to support discord webhooks and merchant restocks.
- Created `tests/test_polymorphic_discord.py` and succeeded verification check with all 72 tests passing.




