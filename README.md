# Project Midgard

Project Midgard is a long-term software engineering project for a modular desktop automation
platform. **Midgard Studio** is its executable graphical foundation: a PySide6 desktop shell with
local settings, logging, and intentionally empty workspaces for future capabilities.

## Approved direction

- Python 3.12 desktop application using PySide6
- SQLite as the embedded database
- Modular architecture with event-oriented communication where appropriate
- Configuration through the application UI
- Independent profiles per character
- Built-in documentation, maintained as part of the product

Midgard Studio does not implement game automation, runtime behavior, capture, OCR, computer
vision, input automation, or a rule engine. See
[PROJECT_CONTEXT.md](project/PROJECT_CONTEXT.md) for the authoritative scope and open decisions.

## Current capabilities

- Main desktop window with seven navigation pages
- Light and dark themes
- SQLite-backed theme preference
- Console and rotating-file application logging
- Application version displayed on the About page

## Getting started

The primary development workflow uses [uv](https://docs.astral.sh/uv/):

```shell
uv sync
uv run midgard-studio
```

The module entry point is equivalent:

```shell
uv run python -m midgard
```

Run the quality checks with:

```shell
uv run ruff format --check .
uv run ruff check .
uv run pytest
```

As a fallback, create and activate a Python 3.12 virtual environment using the command for your
operating system and shell, then install the development tools with pip:

```shell
python -m venv .venv
python -m pip install -e .
python -m pip install "ruff>=0.11,<1" "pytest>=8,<10"
midgard-studio
```

After activating the environment, the fallback quality commands are:

```shell
python -m ruff format --check .
python -m ruff check .
python -m pytest
```

Application settings, the SQLite database, and logs are written to the operating system's
standard per-user application-data directory. The Logs page displays the active log-file path.

## Repository guide

- [START_HERE.md](START_HERE.md): navigation and onboarding
- [`project/`](project/): durable project memory and current status
- [`src/midgard/`](src/midgard/): executable application foundation
- [`tests/`](tests/): foundation tests
- [CONTRIBUTING.md](CONTRIBUTING.md): contribution and quality workflow
- [CHANGELOG.md](CHANGELOG.md): notable changes by version

Directories for architecture, specifications, research, experiments, scripts, or tools will be
introduced only when real artifacts require them.

## License

Project Midgard is available under the [MIT License](LICENSE).
