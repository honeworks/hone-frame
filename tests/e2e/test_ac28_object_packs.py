"""AC-28: belongings and world objects get a hero and views of their own, made before the actions that use
them; the character page shows each belonging as a section (change 0005)."""

from pathlib import Path

import hone_frame as hf
from hone_frame.testing import FakeModels

from .conftest import FILE, run_all


def test_objects_have_their_own_pack(tmp_path: Path) -> None:
    ws = hf.Workspace(tmp_path / "ws", models=FakeModels())
    p = ws.project(ws.import_file(FILE).project)
    rakhsh = next(s for s in p.subjects("asset") if s.name == "Rakhsh")
    plan = p.plan(hf.CharacterPacks(subject_id=rakhsh.id))
    assert [o.item for o in plan.outputs] == ["Hero", "Front", "Side", "Back", "Top", "Detail"]
    assert all(o.depends_on[0].output == plan.outputs[0].id for o in plan.outputs[1:])
    assert "distinctive detail fills the frame" in plan.outputs[-1].prompt_inputs["framing"]
    p.submit(hf.CharacterPacks(subject_id=rakhsh.id, selection=hf.Selection(rounds=1)))
    run_all(p)
    assert p.world_plan()["runs"][0]["title"] != "Rakhsh character packs"  # Rakhsh has its hero now


def test_belongings_before_actions_and_on_the_character_page(tmp_path: Path) -> None:
    ws = hf.Workspace(tmp_path / "ws", models=FakeModels())
    p = ws.project(ws.import_file(FILE).project)
    rostam = p.subjects("character")[0]
    p.submit(hf.CharacterPacks(subject_id=rostam.id, packs=["actions"], selection=hf.Selection(rounds=1)))
    run_all(p)
    from hone_frame.characters import character_page

    page = character_page(p, rostam.id)
    sections = [r for r in page["packs"] if r["id"].startswith("belonging:")]
    assert [s["label"] for s in sections] == ["Belonging: Rostam's mace", "Belonging: Rostam's lasso"]
    assert [i["item"] for i in sections[0]["items"]] == ["Hero", "Front", "Side", "Back", "Top", "Detail"]
    assert all(i["image"] for i in sections[0]["items"])
