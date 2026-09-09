"""Canonical filesystem locations used by PromptaFlow."""

from __future__ import annotations

from pathlib import Path


DIR_NAME = ".promptaflow"


def home_root() -> Path:
    """Return the PromptaFlow state root under the current user's home."""

    return Path.home() / DIR_NAME


def project_state_dir(project_root: Path | str) -> Path:
    """Return the PromptaFlow state directory inside one project."""

    return Path(project_root) / DIR_NAME
