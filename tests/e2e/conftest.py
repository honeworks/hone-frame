"""Shared fixtures for the acceptance cases: a workspace with fake models."""

from pathlib import Path

import pytest

import hone_frame as hf
from hone_frame.testing import FakeModels, sample_workspace


@pytest.fixture
def fake() -> FakeModels:
    return FakeModels()


@pytest.fixture
def ws(tmp_path: Path, fake: FakeModels) -> hf.Workspace:
    return hf.Workspace(tmp_path / "studio", models=fake)


@pytest.fixture
def sample(tmp_path: Path, fake: FakeModels) -> hf.ProjectStore:
    """ "Morning at home" with a woman, a kitchen, a cup and a toothbrush, each with one image."""
    return sample_workspace(tmp_path / "studio", models=fake)


def run_all(store: hf.ProjectStore) -> None:
    """Execute every queued run of the workspace in this process."""
    runner = hf.Runner(store.workspace)
    while runner.run_next() is not None:
        pass
