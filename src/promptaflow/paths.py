"""Where state lives, and where it used to live.

Two different directories were both called `.orbit`: the one under the home
directory that holds every project's database, the Hub registry and the
global control tables, and a per-project one that sits inside the user's own
workspace next to their code.

They cannot be migrated the same way. The home root is ours, there is exactly
one, and moving it once is safe. The per-project directories are inside other
people's repositories — there may be dozens, most of them not checked out on
this machine, some of them named in a `.gitignore` line the user wrote by
hand. Renaming those on sight would be a rename of someone else's files, so
they are only *read* under the old name and created under the new one.

Both lookups fall back rather than assume: a checkout that predates the
rename keeps working with no migration step at all, and the explicit
migration below is what makes the move visible when it does happen.
"""

from __future__ import annotations

from pathlib import Path


DIR_NAME = ".promptaflow"
LEGACY_DIR_NAME = ".orbit"


def home_root() -> Path:
    """The state root under the home directory.

    Returns the legacy `~/.orbit` while that is the directory that actually
    exists, so a Runtime embedded in something that never runs the CLI — and
    therefore never reaches :func:`migrate_home_root` — still finds the data.
    """
    current = Path.home() / DIR_NAME
    if current.exists():
        return current
    legacy = Path.home() / LEGACY_DIR_NAME
    return legacy if legacy.is_dir() else current


def project_state_dir(project_root: Path | str) -> Path:
    """The state directory inside one project.

    Never moved: this path is inside the user's repository. An existing
    `.orbit` keeps being used for the life of that checkout.
    """
    current = Path(project_root) / DIR_NAME
    if current.exists():
        return current
    legacy = Path(project_root) / LEGACY_DIR_NAME
    return legacy if legacy.is_dir() else current


def migrate_home_root() -> Path | None:
    """Move `~/.orbit` to `~/.promptaflow` once, at CLI startup.

    Deliberately not an import-time side effect: importing this package must
    never move a developer's real state, least of all from inside a test.

    :returns: The new path when this call performed the move, else ``None``.
    """
    current = Path.home() / DIR_NAME
    legacy = Path.home() / LEGACY_DIR_NAME
    if current.exists() or not legacy.is_dir():
        return None
    try:
        legacy.rename(current)
    except OSError:
        # A different filesystem, a permission, an open handle on Windows.
        # `home_root` still resolves to the legacy directory, so the only
        # thing lost is the rename itself.
        return None
    return current
