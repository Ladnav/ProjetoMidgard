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

The current application is a graphical shell only. It specifically excludes game automation (beyond the basic Heal trigger), combat target selection, map navigation pathfinding, computer vision object detection (like YOLO), OCR text reading, plugin loaders, and AI features. The page named Runtime is an empty navigation destination and does not authorize or implement runtime logic. (Note: Window capture, Win32 keyboard emulation, and pixel-based Heal monitoring are implemented in the library/engine foundation, but active gameplay loop automation remains excluded.)

## Repository principles

- Prefer small, explicit, reviewable changes.
- Add structure only when a real artifact requires it.
- Keep implementation, tests, and documentation synchronized.
- Treat approved decisions as constraints and unresolved matters as open decisions.
- Preserve modularity without inventing speculative abstractions.
- Require human review before changes are integrated into `main`.

## Open decisions

- Supported desktop operating systems
- Application packaging and distribution format
- Domain module boundaries beyond the current application foundation
- SQLite schema migration strategy beyond the initial settings table
- Method for delivering built-in documentation in the application
- Release process, initial release date, and tagging procedure
- Formal copyright ownership beyond the current contributor notice

These decisions are intentionally deferred. Future tasks must not infer answers without approval.
