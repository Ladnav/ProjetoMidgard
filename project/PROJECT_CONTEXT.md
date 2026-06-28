# Project Context

## Purpose

Project Midgard is a long-term software engineering project intended to become a modular desktop
automation platform. Early product versions are expected to focus on simple automation
capabilities such as hunting, healing, looting, and navigation. Those capabilities are context
only: none are designed or implemented in the current foundation.

## Approved decisions

- Primary language: Python 3.12
- Embedded database: SQLite
- Product form: desktop application with a PySide6 graphical interface
- Architecture direction: modular
- Communication direction: event-oriented where appropriate
- Configuration: performed through the application UI
- Data organization: independent profile per character
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

## Current scope boundary

The current application is a graphical shell only. It specifically excludes game automation,
gameplay runtime behavior, screen capture, computer vision, OCR, input automation, rule engines,
bot logic, plugins, and AI features. The page named Runtime is an empty navigation destination and
does not authorize or implement runtime logic.

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
- Event communication mechanism and its delivery semantics
- SQLite schema migration strategy beyond the initial settings table
- Character profile storage model
- Method for delivering built-in documentation in the application
- Runtime lifecycle and process model
- Release process, initial release date, and tagging procedure
- Formal copyright ownership beyond the current contributor notice

These decisions are intentionally deferred. Future tasks must not infer answers without approval.
