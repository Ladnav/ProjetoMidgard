# Changelog

All notable changes to Project Midgard will be documented in this file.

The project follows [Semantic Versioning](https://semver.org/). Changes that have not been
released remain under **Unreleased** until a version is intentionally published.

## [Unreleased]

### Added

- Persisted per-profile telemetry time series (`profile_stat_samples` table) with
  `add_stat_sample`, `get_stat_samples`, and `clear_stat_samples` on `ProfileStore`.
- Live performance trend chart on the Runtime page, fed by real runtime telemetry samples.

- OCR-based `ExperienceTracker` that samples a configured EXP screen region and accumulates
  the gains, plus an Experience tab in Profiles to configure and verify the region.
- Automatic re-binding to the game window when the bound handle becomes invalid, so a
  restarted client no longer leaves the runtime permanently blind.

### Changed

- `StatisticsTrendChart` now follows the active light/dark theme, draws numeric Y-axis
  labels, aligns loot bars with the XP line, keeps the hover tooltip inside the plot area,
  moves the legend below the axis, and renders an explicit empty state.
- The Statistics page now plots the real recorded telemetry history instead of a fabricated
  fixed-percentage curve.
- The desktop-capture fallback preference is cached instead of opening a SQLite connection
  on every runtime tick.

- Metric tiles (`StatCard`) on the Runtime and Statistics pages, a colour-coded HP progress
  bar, and theme-aware console styling for the runtime terminal and the log viewer.
- Navigation route preview: a "Preview Route Map" button on the Navigation tab renders the
  configured waypoints as a numbered, connected route (`NavigationMapView`), parsed with the same
  runtime parser the engine uses.
- Operational Dashboard replacing the placeholder page: aggregate XP/loot/deaths/runtime
  totals across all profiles plus a per-profile overview of which automation modules are
  configured on.

### Fixed

- Game-window capture in the Profiles pick/verify flow always failed and fell back to the
  primary screen, because it built a QImage with `pil_img.width()` / `pil_img.height()` —
  PIL exposes those as int attributes, so calling them raised `'int' object is not callable`.
  Extracted a tested `_pil_to_qpixmap` helper using the attributes.
- A* navigation never actually routed: `NavigationModule` built walkable grids as
  `1 = walkable, 0 = obstacle` but `AStarNavigator` expects the opposite, so `find_path`
  treated walkable cells as blocked, returned `None`, and silently fell back to a direct
  click. Grids are now converted to the pathfinder's convention at the boundary.
- A* routes started from a hardcoded map origin `(0, 0)` instead of the previous waypoint,
  producing paths from the wrong place. They now start from the waypoint being walked from.
- Experience was never counted: `xp_gained` was initialised and reported but never
  incremented, so every XP figure was permanently zero.
- Runtime telemetry arrives ~20x/second, which caused three defects: the database grew by
  roughly 72k sample rows per hour, the live chart held only ~12 seconds of history, and
  `runtime_seconds` (which added a flat 1.0 per message) overstated session duration by
  about 20x. Sampling is now throttled to once per second and runtime accumulates real
  elapsed wall time.
- The live chart discarded its opening samples whenever a session legitimately started at
  zero, because the placeholder was detected by comparing the series to `[0]`.
- Recorded samples from previous sessions are cleared when a run starts, since the engine
  restarts its counters from zero and mixing sessions produced a meaningless sawtooth.
- The runtime terminal and log viewer had hardcoded dark colours that were unreadable under
  the light theme.
- Auto-looting clicked empty ground whenever more than one item label was visible, because
  it averaged every matching pixel on screen into a single centroid. Matches are now grouped
  into distinct labels and the closest one is clicked.
- `find_hwnd_by_pid` returned the first visible window of a process, which could bind the
  runtime to a splash or helper window instead of the game client; the largest client area
  is now selected.

## [0.2.0] - 2026-06-27

### Added

- Initial Python 3.12 repository foundation.
- Ruff formatting and linting configuration.
- pytest test foundation.
- uv dependency management and reproducible lock file workflow.
- Ubuntu-based GitHub Actions quality checks.
- Project memory and contributor guidance.
- Executable PySide6 Midgard Studio shell.
- Left navigation with Dashboard, Profiles, Runtime, Statistics, Settings, Logs, and About pages.
- Light and dark themes with SQLite persistence.
- Console and rotating-file application logging.
- Application version information on the About page.
