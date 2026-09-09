"""Environment variables, read under the current name and the one before it.

Every setting this package reads was published as `ORBIT_*` before the
rename. A process started by an older launcher, a shell profile written last
year, or a Harness Profile someone configured once and forgot still exports
those names, and a rename that silently ignored them would look like the
setting had stopped working rather than like it had moved.

The new name wins when both are set, so a deliberate override is never
shadowed by a stale one.
"""

from __future__ import annotations

import os


LEGACY_PREFIX = "ORBIT_"
PREFIX = "PROMPTAFLOW_"


def env(suffix: str, default: str | None = None) -> str | None:
    """Read ``PROMPTAFLOW_<suffix>``, falling back to ``ORBIT_<suffix>``.

    :param suffix: The part after the prefix, e.g. ``HUB_ROOT``.
    :param default: Returned when neither name is set.
    """
    value = os.environ.get(f"{PREFIX}{suffix}")
    if value is not None:
        return value
    return os.environ.get(f"{LEGACY_PREFIX}{suffix}", default)
