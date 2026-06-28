"""Smoke tests for the Python package boundary."""

import tomllib
from importlib import import_module
from pathlib import Path

from midgard import __version__


def test_midgard_package_is_importable() -> None:
    """The configured source layout exposes the approved package name."""
    package = import_module("midgard")

    assert package.__name__ == "midgard"


def test_application_version_matches_project_metadata() -> None:
    """The displayed application version stays aligned with package metadata."""
    project_file = Path(__file__).parents[1] / "pyproject.toml"
    with project_file.open("rb") as file:
        project = tomllib.load(file)

    assert __version__ == project["project"]["version"]
