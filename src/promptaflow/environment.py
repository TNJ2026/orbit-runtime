"""PromptaFlow environment variable access."""

from __future__ import annotations

import os


PREFIX = "PROMPTAFLOW_"


def env(suffix: str, default: str | None = None) -> str | None:
    """Read ``PROMPTAFLOW_<suffix>`` or return ``default``."""

    return os.environ.get(f"{PREFIX}{suffix}", default)
