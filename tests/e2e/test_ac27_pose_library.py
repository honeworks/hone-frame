"""AC-27: pose images take their pose from a mannequin of the project's pose library, drawn once and
reused (change 0005)."""

from pathlib import Path

import hone_frame as hf
from hone_frame.testing import FakeModels

from .conftest import FILE, run_all


def test_mannequins_first_then_reused(tmp_path: Path) -> None:
    fake = FakeModels()
    ws = hf.Workspace(tmp_path / "ws", models=fake)
    p = ws.project(ws.import_file(FILE).project)
    rostam, sohrab = p.subjects("character")[:2]
    plan = p.plan(hf.CharacterPacks(subject_id=rostam.id, packs=["poses"]))
    mannequins = [o for o in plan.outputs if o.pack == "pose-library"]
    poses = [o for o in plan.outputs if o.pack == "poses"]
    assert len(mannequins) == 5  # every pose but standing
    running = next(o for o in poses if o.item == "Running")
    assert {d.role for d in running.depends_on} == {"identity", "pose"}
    assert "artist's mannequin" in mannequins[0].prompt_inputs["fixed_prompt"]
    p.submit(hf.CharacterPacks(subject_id=rostam.id, packs=["poses"], selection=hf.Selection(rounds=1)))
    run_all(p)
    prompt = next(i.generation.prompt for i in p.images(subject_id=rostam.id) if i.item == "Running")
    assert "body pose of the wooden mannequin in image 2" in prompt
    again = p.plan(hf.CharacterPacks(subject_id=sohrab.id, packs=["poses"]))
    assert not [o for o in again.outputs if o.pack == "pose-library"]  # the library is reused
    kneel = next(o for o in again.outputs if o.item == "Kneeling")
    assert any(r.role == "pose" for r in kneel.references)
