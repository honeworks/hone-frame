"""Shared pytest fixtures: the machine-wide GPU lock for real-model tests."""

from __future__ import annotations

import fcntl
import os
from collections.abc import Iterator
from pathlib import Path

import pytest


@pytest.fixture(scope="session")
def gpu_lock() -> Iterator[None]:
    """Hold the machine-wide GPU lock for the session (no-op if scripts/gpu-lock.sh already holds it)."""
    if os.environ.get("HONE_GPU_LOCK_HELD") == "1":
        yield
        return
    path = Path(os.environ.get("HONE_GPU_LOCK", "/tmp/honeworks-gpu.lock"))  # noqa: S108 - shared machine-wide lock by design
    path.touch(exist_ok=True)
    with path.open("r+") as fh:
        fcntl.flock(fh, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(fh, fcntl.LOCK_UN)
