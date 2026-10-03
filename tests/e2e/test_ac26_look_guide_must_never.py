"""AC-26: the world's look guide goes into every prompt that brings something new (heroes, outfits,
objects, scenes) and not into edits of the same subject; a subject's must list is in its prompts and its
never list is a judge check and a negative (change 0005)."""

from pathlib import Path

import hone_frame as hf
from hone_frame.testing import FakeModels

from .conftest import FILE, run_all

LOOK = "Knee-length lamellar coats laced with red cord over silk kaftans with roundel patterns"


def test_look_guide_where_it_belongs(tmp_path: Path) -> None:
    fake = FakeModels()
    ws = hf.Workspace(tmp_path / "ws", models=fake)
    p = ws.project(ws.import_file(FILE).project)
    p.update(look=LOOK)
    rostam = p.subjects("character")[0]
    p.edit_subject(rostam.id, must=["a long scar across the left cheek"], never=["plate armour", "a cape"])
    p.submit(
        hf.CharacterPacks(
            subject_id=rostam.id, packs=["expressions", "outfits"], selection=hf.Selection(rounds=1)
        )
    )
    run_all(p)
    prompts = {(i.pack, i.item): i.generation.prompt for i in p.images(subject_id=rostam.id) if i.generation}
    assert LOOK in prompts[("hero", "Hero")] and LOOK in prompts[("outfits", "Feast")]
    assert LOOK not in prompts[("expressions", "Happy")]  # the hero image shows it already
    assert "Always visible: a long scar across the left cheek" in prompts[("expressions", "Happy")]
    judged = [c.prompt for c in fake.asked if "quality judge" in c.prompt and "Rostam" in c.prompt]
    assert judged
    assert all("- never_shown: Is none of these in the picture: plate armour; a cape" in j for j in judged)
    assert all("- must_shown: Are all of these visible" in j and "left cheek" in j for j in judged)
    prompts_sent = [g.prompt for g in fake.generated]
    assert prompts_sent and not any("plate armour" in t for t in prompts_sent)  # never in a positive prompt
    negatives = [str(g.inputs.get("negative", "")) for g in fake.generated]
    assert negatives and all("plate armour" in n and "a cape" in n for n in negatives if n)
    assert any("plate armour" in n for n in negatives)


def test_small_marks_are_warned(tmp_path: Path) -> None:
    ws = hf.Workspace(tmp_path / "ws", models=FakeModels())
    p = ws.create_project("Marks")
    who = p.add_subject("character", "Mina", fields={"features": "a small beauty mark on her cheek"})
    warnings = p.plan(hf.CharacterPacks(subject_id=who.id, packs=["turnaround"])).warnings
    assert any("beauty mark" in w and "exact place and size" in w for w in warnings)
