# Project Context

## Purpose

Project Midgard is a long-term software engineering project intended to become a modular desktop
automation platform. Early product versions are expected to focus on simple automation
capabilities such as hunting, healing, looting, and navigation. Those capabilities are context
only: none are designed or implemented in the current foundation.

## Approved decisions

- Primary language: Python 3.12/3.14
- Embedded database: SQLite
- Product form: desktop application with a PySide6 graphical interface
- Architecture direction: modular
- Communication direction: event-oriented where appropriate
- Configuration: performed through the application UI
- Data organization: independent profile per character
- Character profile storage model: SQLite database using relational tables (`profiles`, `profile_rules`, `profile_stats` with cascading deletes)
- Documentation: built into the product and treated as a maintained deliverable
- Project memory: stored permanently in this repository
- Dependency workflow: uv, with pip as a fallback
- Formatting and linting: Ruff
- Testing: pytest
- Versioning: Semantic Versioning
- License: MIT
- Continuous integration: GitHub Actions on Ubuntu Latest
- Python import package: `midgard`
- Current application version: 0.2.0
- Local preference persistence: SQLite using Python's standard `sqlite3` module
- Application logging: console and local rotating file
- Runtime lifecycle and process model: multi-process isolation (each profile runs in its own subprocess `RuntimeEngine`)
- Event communication mechanism: TCP socket loopback (`127.0.0.1`) with length-prefixed JSON serialization to cross privilege boundaries safely
- Screen capture technology: Windows GDI BitBlt via ctypes (returning PIL Image buffers)
- Keyboard input simulation: native Windows `SendInput` API using hardware scan codes (with abstract adapter interface)

## Current scope boundary

The application has grown well past the original graphical shell. As delivered on `main` (through
TASK-035) and extended on 2026-07-20, it implements a full multi-process automation runtime: window
capture (GDI), Win32 input emulation, pixel/OCR HP-SP monitoring and healing, combat target
selection (colour, OpenCV template matching, hover validation), A* and multi-map navigation with a
custom-script plugin loader, auto-looting, consumables/buffs, auto-stash and NPC selling, Discord
notifications, an OCR experience tracker, and anti-detection input behaviours. The Runtime page
controls live sessions; the Dashboard aggregates real per-profile data; Statistics render a real
persisted telemetry time series.

This boundary was previously stated as "graphical shell only, automation excluded." That text
described the intended TASK-002 milestone and was never updated as tasks 003–035 shipped, so it
contradicted the code and the project history. It was corrected on 2026-07-20 with Product Owner
approval. What remains genuinely **not** implemented: machine-learning behaviour, memory reading,
cloud sync, a plugin marketplace, and automatic updates (see the roadmap's deferred features).

Note on process: several of these capabilities — computer vision, OCR, and anti-detection in
particular — were listed as DEFERRED in the external Engineering Decisions and were implemented
ahead of a formal per-feature Decision record. Retroactively formalising those decisions is an open
item below.

## Repository principles

- Prefer small, explicit, reviewable changes.
- Add structure only when a real artifact requires it.
- Keep implementation, tests, and documentation synchronized.
- Treat approved decisions as constraints and unresolved matters as open decisions.
- Preserve modularity without inventing speculative abstractions.
- Require human review before changes are integrated into `main`.

## Open decisions

- Supported desktop operating systems (the runtime is currently Windows-only due to GDI/Win32)
- Application packaging and distribution format (a PyInstaller build exists; no release process)
- SQLite schema migration strategy beyond additive `CREATE TABLE IF NOT EXISTS` tables
- Method for delivering built-in documentation in the application
- Release process, initial release date, and tagging procedure
- Formal copyright ownership beyond the current contributor notice
- Whether to retroactively record the already-implemented computer-vision, OCR, and
  anti-detection capabilities as formal approved Engineering Decisions (they were built while the
  external spec still marked them DEFERRED)

These decisions are intentionally deferred. Future tasks must not infer answers without approval.
