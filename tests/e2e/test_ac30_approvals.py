"""AC-30: when generation starts the person chooses when to check (change 0006): "base" waits after the
images the rest is made from, "each" also after every pack, "auto" never; approving continues the run."""

from pathlib import Path

import hone_frame as hf
from hone_frame.characters import character_page
from hone_frame.testing import FakeModels

from .conftest import FILE, run_all

ONE = hf.Selection(rounds=1)


def _project(tmp_path: Path) -> hf.ProjectStore:
    ws = hf.Workspace(tmp_path / "ws", models=FakeModels())
    return ws.project(ws.import_file(FILE).project)


def test_approve_the_base(tmp_path: Path) -> None:
    p = _project(tmp_path)
    run = p.submit(
        hf.CharacterPacks(
            subject_id="char_001", packs=["turnaround", "poses"], approval="base", selection=ONE
        )
    )
    run_all(p)
    view = p.run_view(run.id)
    assert view.status == "paused" and view.reason.startswith("Waiting for your approval")
    made = [o for o in view.outputs if o.status == "done"]
    assert {o.label for o in made} >= {"Hero"} and all(
        o.label == "Hero" or o.label.startswith("Mannequin") for o in made
    )
    waiting = character_page(p, "char_001")["approvals"]
    assert waiting and waiting[0]["run"] == run.id
    p.resume(run.id)
    run_all(p)
    assert p.run_view(run.id).status == "done" and not character_page(p, "char_001")["approvals"]


def test_each_step_and_automatic(tmp_path: Path) -> None:
    p = _project(tmp_path)
    each = p.plan(
        hf.CharacterPacks(subject_id="char_001", packs=["turnaround", "expressions"], approval="each")
    )
    labels = [o.label for o in each.outputs if o.id in each.checkpoints]
    assert labels == ["Hero", "Back"]  # after the base, after the turnaround; the last pack ends the run
    auto = p.plan(hf.CharacterPacks(subject_id="char_001", packs=["turnaround"]))
    assert auto.checkpoints == []
