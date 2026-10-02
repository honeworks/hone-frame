"""Workspace files: atomic JSON, format versions, sequential ids and the per-project lock (design §4.1)."""

from __future__ import annotations

import fcntl
import json
import os
import re
import threading
from collections.abc import Generator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from hone_frame.errors import HoneFrameError

FORMAT_VERSION = "1"


def now() -> str:
    """The current UTC time, ISO-8601 with microseconds and a Z (it orders runs submitted together)."""
    return datetime.now(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")


def write_json(path: Path, data: Any) -> None:
    """Write `data` as JSON atomically: readers see the old file or the new one, never half of one."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{os.getpid()}.{threading.get_ident()}.tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def read_json(path: Path) -> dict[str, Any]:
    """Read a workspace JSON file and check its `format_version`."""
    loaded: Any = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise HoneFrameError(f"{path} is not a hone-frame record (expected a JSON object)")
    data: dict[str, Any] = loaded  # pyright: ignore[reportUnknownVariableType]
    version = data.get("format_version", FORMAT_VERSION)
    if version != FORMAT_VERSION:
        raise HoneFrameError(
            f"{path} has format_version {version!r}; this hone-frame reads {FORMAT_VERSION!r}: "
            "upgrade hone-frame"
        )
    return data


def next_id(folder: Path, prefix: str, width: int = 3) -> str:
    """The next `<prefix>_<n>` id in `folder`, from the files already there (decisions D-003)."""
    pattern = re.compile(rf"^{re.escape(prefix)}_(\d+)\.json$")
    numbers = [int(m.group(1)) for p in folder.glob(f"{prefix}_*.json") if (m := pattern.match(p.name))]
    return f"{prefix}_{max(numbers, default=0) + 1:0{width}d}"


def slug(name: str) -> str:
    """A safe folder name from a display name: lowercase words joined by hyphens."""
    words = re.findall(r"[a-z0-9]+", name.lower())
    return "-".join(words) or "project"


_LOCKS: dict[str, threading.RLock] = {}
_LOCKS_GUARD = threading.Lock()
_HELD = threading.local()


@contextmanager
def project_lock(folder: Path) -> Generator[None]:
    """One writer per project: a re-entrant thread lock plus an `fcntl` lock across processes (D-004)."""
    key = str(folder.resolve())
    with _LOCKS_GUARD:
        lock = _LOCKS.setdefault(key, threading.RLock())
    with lock:
        depth: dict[str, int] = getattr(_HELD, "depth", {})
        _HELD.depth = depth
        if depth.get(key, 0):
            depth[key] += 1
            try:
                yield
            finally:
                depth[key] -= 1
            return
        folder.mkdir(parents=True, exist_ok=True)
        with (folder / ".lock").open("a") as handle:
            fcntl.flock(handle, fcntl.LOCK_EX)
            depth[key] = 1
            try:
                yield
            finally:
                depth[key] = 0
                fcntl.flock(handle, fcntl.LOCK_UN)
