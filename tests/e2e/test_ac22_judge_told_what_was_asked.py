"""AC-22: in a real run (FakeModels), the judge is told what each image was asked for, from the plan; back
views get their own faces-away check and other views no back-view wording; the anatomy check names hands
and feet (change 0004)."""

from pathlib import Path

import hone_frame as hf
from hone_frame.testing import FakeModels

from .conftest import FILE, run_all


def test_the_judge_is_told_what_was_asked(tmp_path: Path) -> None:
    fake = FakeModels()
    ws = hf.Workspace(tmp_path / "ws", models=fake)
    p = ws.project(ws.import_file(FILE).project)
    rostam = p.subjects("character")[0]
    p.submit(
        hf.CharacterPacks(
            subject_id=rostam.id, packs=["turnaround", "poses"], selection=hf.Selection(rounds=1)
        )
    )
    run_all(p)
    judged = [c.prompt for c in fake.asked if "quality judge" in c.prompt]
    running = next(j for j in judged if "Requested pose: running fast" in j and "Rostam" in j)
    assert "Requested background: a plain pure white background" in running
    assert "Requested: empty hands" in running and "- pose:" in running
    back = next(j for j in judged if "from directly behind" in j.split("The prompt it was made from")[0])
    side = next(j for j in judged if "Requested view: from the side" in j)
    assert "- faces_away:" in back and "- identity_from_behind:" in back
    assert "- faces_away:" not in side and "rear view" not in side.lower()
    assert "foot" in side and "same way as the face" in side
