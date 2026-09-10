"""Bounded publication of explicitly linked local deliverables, never a cwd scan."""

from pathlib import Path
import os
import re
import stat
from urllib.parse import unquote, urlsplit


MAX_FILES = 64
MAX_FILE_BYTES = 64 * 1024 * 1024
MAX_TOTAL_BYTES = 128 * 1024 * 1024
FILE_TYPES = {
    ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".pdf": "application/pdf", ".png": "image/png", ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg", ".svg": "image/svg+xml", ".md": "text/markdown",
    ".txt": "text/plain", ".csv": "text/csv", ".html": "text/html",
}
_LINK = re.compile(r"!?\[[^\]\n]*\]\(\s*(?:<([^>\n]+)>|([^\s)]+))(?:\s+\"[^\"\n]*\")?\s*\)")


class DeliverableReadError(ValueError):
    """A linked file could not be safely read; execution itself still completed."""


def linked_files(text: str, workspace: Path) -> tuple[str, ...]:
    """Local file links only; remote URLs, directories and unknown types stay prose."""
    root = workspace.resolve()
    paths = []
    for match in _LINK.finditer(text):
        url = urlsplit(match.group(1) or match.group(2))
        if url.scheme not in ("", "file") or url.netloc:
            continue
        path = Path(unquote(url.path))
        if path.is_absolute():
            try:
                path = path.relative_to(root)
            except ValueError:
                continue
        value = path.as_posix()
        if path.suffix.lower() in FILE_TYPES and value not in paths:
            paths.append(value)
    if len(paths) > MAX_FILES:
        raise DeliverableReadError(f"at most {MAX_FILES} deliverables may be published")
    return tuple(paths)


def read_deliverables(workspace: Path, paths):
    """Read regular files beneath the granted cwd, without following symlinks.

    Directory-relative open keeps both parent and leaf checks race-safe on the
    local POSIX runtime. No hidden/runtime files, traversal, directories or
    recursive link chasing. Callers stage only after the entire batch validates.
    """
    if not isinstance(paths, (list, tuple)) or not 1 <= len(paths) <= MAX_FILES:
        raise ValueError(f"paths must contain 1 to {MAX_FILES} files")
    if not hasattr(os, "O_NOFOLLOW") or os.open not in os.supports_dir_fd:
        raise ValueError("safe local file publication is unavailable on this platform")
    result, total, seen = [], 0, set()
    for raw in paths:
        if not isinstance(raw, str) or not raw or "\x00" in raw:
            raise ValueError("invalid deliverable path")
        path = Path(raw)
        if path.is_absolute() or any(part.startswith(".") for part in path.parts):
            raise ValueError("deliverables must be non-hidden relative workspace files")
        content_type = FILE_TYPES.get(path.suffix.lower())
        if content_type is None:
            raise ValueError(f"unsupported deliverable type: {path.suffix}")
        name = path.as_posix()
        if name in seen:
            continue
        seen.add(name)
        fd = os.open(workspace, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            for part in path.parts[:-1]:
                child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
                os.close(fd)
                fd = child
            leaf = os.open(path.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=fd)
            with os.fdopen(leaf, "rb") as stream:
                info = os.fstat(stream.fileno())
                if not stat.S_ISREG(info.st_mode) or info.st_size > MAX_FILE_BYTES:
                    raise ValueError("deliverable is not a regular file within the size limit")
                content = stream.read(MAX_FILE_BYTES + 1)
        finally:
            os.close(fd)
        total += len(content)
        if len(content) > MAX_FILE_BYTES or total > MAX_TOTAL_BYTES:
            raise ValueError("deliverables exceed the publication size limit")
        result.append((name, content_type, content))
    return tuple(result)
