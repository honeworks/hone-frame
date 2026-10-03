"""AC-33: a stronger judge for the base images or for everything, chosen when generation starts; without
one set in the settings the plan says so (change 0006)."""

from pathlib import Path

import hone_frame as hf
from hone_frame.testing import FakeModels
from hone_frame.workspace import Settings

from .conftest import FILE, run_all


def test_stronger_judge_where_asked(tmp_path: Path) -> None:
    fake = FakeModels()
    ws = hf.Workspace(tmp_path / "ws", models=fake)
    p = ws.project(ws.import_file(FILE).project)
    request = hf.CharacterPacks(
        subject_id="char_001",
        packs=["turnaround"],
        judge_mode="strong_base",
        selection=hf.Selection(rounds=1),
    )
    assert "no stronger judge is set" in p.plan(request).errors[0]
    ws.save_settings(Settings.model_validate(ws.settings.model_dump() | {"strong_judge": "qwen2.5vl-72b"}))
    p.submit(request)
    run_all(p)
    calls = [c for c in fake.asked if "quality judge" in c.prompt]
    hero = [c.model for c in calls if "It was asked to show: Hero" in c.prompt]
    others = [c.model for c in calls if "It was asked to show: Hero" not in c.prompt]
    assert hero == ["qwen2.5vl-72b"] and others and "qwen2.5vl-72b" not in others  # only the base image
