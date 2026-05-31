from __future__ import annotations

import tomllib
from pathlib import Path

import waymark


def test_package_version_matches_project_metadata() -> None:
    pyproject = Path(__file__).resolve().parents[1] / "pyproject.toml"
    metadata = tomllib.loads(pyproject.read_text(encoding="utf-8"))

    assert metadata["project"]["version"] == waymark.__version__


def test_distribution_name_keeps_waymark_command() -> None:
    pyproject = Path(__file__).resolve().parents[1] / "pyproject.toml"
    metadata = tomllib.loads(pyproject.read_text(encoding="utf-8"))

    assert metadata["project"]["name"] == "waymark-memory"
    assert metadata["project"]["scripts"]["waymark"] == "waymark.cli:app"
