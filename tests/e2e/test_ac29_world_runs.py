"""AC-29: the whole world of a variation in one go, with an estimate first; the scenes follow the last
character, since they need its accepted hero (change 0005)."""

from pathlib import Path

import hone_frame as hf
from hone_frame.testing import FakeModels

from .conftest import FILE, run_all


def test_generate_everything(tmp_path: Path) -> None:
    ws = hf.Workspace(tmp_path / "ws", models=FakeModels())
    p = ws.project(ws.import_file(FILE).project)
    plan = p.world_plan(selection=hf.Selection(rounds=1))
    assert len(plan["runs"]) == 8 and plan["scenes"] == 2 and plan["images"] > 100
    assert plan["estimate_s"] == round(plan["images"] * plan["seconds_per_image"])
    started = p.generate_world(selection=hf.Selection(rounds=1))
    assert len(started["runs"]) == 8 and started["scenes_after"] == 2
    run_all(p)
    titles = [r.title for r in p.runs()]
    assert "Duel" in titles and "Gordafarid unmasked" in titles  # queued after the characters
    duel = next(r for r in p.runs() if r.title == "Duel")
    assert duel.status in ("done", "needs_review")
