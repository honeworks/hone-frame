"""AC-25: one world, several variations (change 0005): each variation draws with its own style and keeps
its own heroes and images; switching the active variation switches what pages and requests use."""

from pathlib import Path

import hone_frame as hf
from hone_frame.testing import FakeModels

from .conftest import FILE, run_all

ONE = hf.Selection(rounds=1)


def _project(tmp_path: Path) -> tuple[hf.ProjectStore, FakeModels]:
    fake = FakeModels()
    ws = hf.Workspace(tmp_path / "ws", models=fake)
    return ws.project(ws.import_file(FILE).project), fake


def test_variations_keep_their_own_images(tmp_path: Path) -> None:
    p, fake = _project(tmp_path)
    first = p.info.variation_of().id
    assert first == "main" and p.info.all_variations()[0].style_pack == "historical-epic"
    p.submit(hf.CharacterPacks(subject_id="char_001", packs=["turnaround"], selection=ONE))
    run_all(p)
    flat = p.add_variation("2D animated", style_pack="clean-2d-animation", direction="thick outlines")
    assert p.info.variation_of().id == flat.id  # the new one is active
    plan = p.plan(hf.CharacterPacks(subject_id="char_001", packs=["turnaround"]))
    assert plan.variation == flat.id and plan.outputs[0].pack == "hero"  # a new hero for this variation
    hero = plan.outputs[0]
    assert "2D" in hero.prompt_inputs["style"]["short"]  # the variation's style pack
        "prefix", "Flat 2D vector animation"
    )
    assert hero.prompt_inputs["style"]["direction"] == "thick outlines"
    p.submit(hf.CharacterPacks(subject_id="char_001", packs=["turnaround"], selection=ONE))
    run_all(p)
    mine = p.images(subject_id="char_001", variation=flat.id)
    theirs = p.images(subject_id="char_001", variation=first)
    assert mine and theirs and not {i.id for i in mine} & {i.id for i in theirs}
    assert any("2d" in i.generation.prompt.lower() for i in mine if i.generation)
    p.use_variation(first)
    again = p.plan(hf.CharacterPacks(subject_id="char_001", packs=["turnaround"]))
    assert again.variation == first and all(o.pack != "hero" for o in again.outputs if o.kind == "character")


def test_compare_and_edit_variations(tmp_path: Path) -> None:
    p, _ = _project(tmp_path)
    v = p.add_variation("Miniature", style_pack="illustrated-storybook", active=False)
    assert p.info.variation_of().id == "main"
    p.edit_variation(v.id, name="Persian miniature", direction="gold leaf")
    assert p.info.variation_of(v.id).name == "Persian miniature"
    assert [x.id for x in p.info.all_variations()] == ["main", v.id]
