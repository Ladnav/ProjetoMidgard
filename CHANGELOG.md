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

### Fixed

- Experience was never counted: `xp_gained` was initialised and reported but never
  incremented, so every XP figure was permanently zero.
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
