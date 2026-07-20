# Changelog

All notable changes to Project Midgard will be documented in this file.

The project follows [Semantic Versioning](https://semver.org/). Changes that have not been
released remain under **Unreleased** until a version is intentionally published.

## [Unreleased]

### Added

- Persisted per-profile telemetry time series (`profile_stat_samples` table) with
  `add_stat_sample`, `get_stat_samples`, and `clear_stat_samples` on `ProfileStore`.
- Live performance trend chart on the Runtime page, fed by real runtime telemetry samples.

### Changed

- `StatisticsTrendChart` now follows the active light/dark theme, draws numeric Y-axis
  labels, aligns loot bars with the XP line, keeps the hover tooltip inside the plot area,
  moves the legend below the axis, and renders an explicit empty state.
- The Statistics page now plots the real recorded telemetry history instead of a fabricated
  fixed-percentage curve.

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
