"""AC-32: "Generate again" with standard issues ticked adds their fixes to the new attempt and judges them
(change 0006)."""

from pathlib import Path

import pytest

import hone_frame as hf
from hone_frame.errors import InvalidRequest
from hone_frame.testing import FakeModels

from .conftest import FILE, run_all


def test_ticked_issues_fix_and_judge(tmp_path: Path) -> None:
    fake = FakeModels()
    ws = hf.Workspace(tmp_path / "ws", models=fake)
    p = ws.project(ws.import_file(FILE).project)
    run = p.submit(
        hf.CharacterPacks(subject_id="char_001", packs=["poses"], selection=hf.Selection(rounds=1))
    )
    run_all(p)
    out = next(o for o in p.run_view(run.id).outputs if o.label == "Kneeling")
    again = p.rerun(run.id, out.id, note="the left knee on the ground", issues=["wrong_pose", "feet"])
    run_all(p)
    image = next(i for i in p.images() if i.run_id == again.id)
    prompt = (image.generation.prompt if image.generation else "").lower()
    assert (
        "the body pose must be exactly the one asked for" in prompt and "both pointing the same way" in prompt
    )
    assert "the left knee on the ground" in prompt
    judged = next(
        c.prompt
        for c in fake.asked
        if "quality judge" in c.prompt and again.id and "Kneeling" in c.prompt and "issue_" in c.prompt
    )
    assert "- issue_wrong_pose:" in judged and "- issue_feet:" in judged
    with pytest.raises(InvalidRequest, match="unknown issues"):
        p.rerun(run.id, out.id, issues=["sparkles"])
