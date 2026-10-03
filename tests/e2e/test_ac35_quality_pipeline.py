"""AC-35 to AC-43: the quality pipeline (change 0007, experimental): garments, own fields, identity from
parameters, objects by shape, worn elements, place coverage and states, measured checks, routing."""

from pathlib import Path
from typing import Any

import pytest

import hone_frame as hf
from hone_frame.testing import FakeModels

from .conftest import FILE, run_all

ZAHHAK = Path(__file__).parent / "zahhak.json"
GARMENTS = "lamellar coat, saffron kaftan, conical helmet, leather belt, dark trousers, brown boots"


def _project(tmp_path: Path, fake: FakeModels) -> hf.ProjectStore:
    ws = hf.Workspace(tmp_path / "ws", models=fake)
    return ws.project(ws.import_file(ZAHHAK).project)


def _named(p: hf.ProjectStore, name: str) -> hf.Subject:
    return next(s for s in p.subjects() if s.name == name)


def _run(p: hf.ProjectStore, request: Any) -> Any:
    run = p.submit(request.model_copy(update={"profile": "quality", "selection": hf.Selection(rounds=1)}))
    run_all(p)
    return p.run_view(run.id)


def _prompt(fake: FakeModels, start: str) -> str:
    return next(c.prompt for c in fake.generated if start in c.prompt)


def test_ac35_garments_in_keep_and_whole_outfit_without(tmp_path: Path, fake: FakeModels) -> None:
    p = _project(tmp_path, fake)
    fereydun = _named(p, "Fereydun")
    _run(p, hf.CharacterPacks(subject_id=fereydun.id, packs=["turnaround"]))
    side = _prompt(fake, "Fereydun, from the side")
    assert f"the same clothes: {GARMENTS}." in side
    ws = hf.Workspace(tmp_path / "old", models=(old := FakeModels()))
    rostam = ws.project(ws.import_file(FILE).project)
    outfit = str(rostam.subjects("character")[0].fields["outfits"])
    _run(rostam, hf.CharacterPacks(subject_id=rostam.subjects("character")[0].id, packs=["turnaround"]))
    assert any(outfit.rstrip(".") in c.prompt for c in old.generated[1:])  # whole, never cut mid-phrase


def test_ac36_object_and_place_fields_reach_the_prompt(tmp_path: Path, fake: FakeModels) -> None:
    p = _project(tmp_path, fake)
    _run(p, hf.CharacterPacks(subject_id=_named(p, "Kaveh's banner").id, packs=["hero"]))
    _run(p, hf.SubjectReferences(subject_id=_named(p, "Kaveh's forge").id, presentation="quality-coverage"))
    banner = _prompt(fake, "Kaveh's banner:")
    assert "burn marks" in banner and "worn brown leather" in banner and "brown leather, dark wood" in banner
    assert "a heavy iron anvil in front of it" in _prompt(fake, "Kaveh's forge")


def test_ac37_ac43_action_roles_routing_and_judge(tmp_path: Path, fake: FakeModels) -> None:
    p = _project(tmp_path, fake)
    fereydun = _named(p, "Fereydun")
    plan = p.plan(hf.CharacterPacks(subject_id=fereydun.id, profile="quality", packs=["actions"]))
    by_item = {o.item: o for o in plan.outputs}
    assert by_item["Ox-headed mace"].model == "qwen-image-edit-2511"  # the compose editor
    assert by_item["Side"].model == "qwen-image-edit-2511"  # a turning view: the turn editor
    assert by_item["Head"].model == "flux.2-klein-4b"  # a close-up: the usual editor
    _run(p, hf.CharacterPacks(subject_id=fereydun.id, packs=["actions"]))
    action = next(c for c in fake.generated if c.prompt.startswith("Reference images:"))
    assert "image 1" in action.prompt and "object in image 2" in action.prompt and "image 3" in action.prompt
    assert len(action.references) == 3
    assert not any("Ox-headed mace" in c.prompt and "prompt writer" in c.prompt for c in fake.asked)
    judge = next(c.prompt for c in fake.asked if "quality judge" in c.prompt and "(interaction)" in c.prompt)
    assert "- object: Is the object the one in image 3" in judge
    assert "- never_shown:" in judge


def test_ac38_identity_by_kind_of_image(tmp_path: Path, fake: FakeModels) -> None:
    p = _project(tmp_path, fake)
    zahhak = _named(p, "Zahhak")
    _run(p, hf.CharacterPacks(subject_id=zahhak.id, packs=["turnaround", "expressions"]))
    front = _prompt(fake, "Zahhak, from the front")
    back = _prompt(fake, "Zahhak, from directly behind")
    face = _prompt(fake, "Zahhak, as a close-up")
    assert "Zahhak: a man, in his fifties; a heavy-set, broad build" in front
    assert "a full beard reaching the chest" in front and "serpents" in front
    assert "beard" not in back.split("Keep exactly")[0] and "serpents" in back  # the shoulders show
    assert "a heavy-set" not in face  # a close-up: no body words
    judge = next(
        c.prompt for c in fake.asked if "quality judge" in c.prompt and "from directly behind" in c.prompt
    )
    assert "- parameters:" in judge and "beard" not in judge.split("- parameters:")[1].split("\n")[0]
    assert "not_assessable" in judge


def test_ac39_object_views_by_shape_with_their_camera(tmp_path: Path, fake: FakeModels) -> None:
    p = _project(tmp_path, fake)
    plan = p.plan(hf.CharacterPacks(subject_id=_named(p, "Kaveh's banner").id, profile="quality"))
    assert [o.item for o in plan.outputs] == ["Hero", "Detail", "Face-on", "Edge-on"]
    _run(p, hf.CharacterPacks(subject_id=_named(p, "Kaveh's banner").id))
    turned = [c for c in fake.generated if c.model == "qwen-image-edit-2511"]
    assert turned and all(c.inputs.get("lora_strength") == 1.0 for c in turned)
    assert not any(c.prompt.startswith("<sks> front view eye-level shot medium shot") for c in turned[1:])
    assert len({c.prompt.split(".")[0] for c in turned}) == len(turned)  # each its own camera phrase


def test_ac40_worn_elements(tmp_path: Path, fake: FakeModels) -> None:
    p = _project(tmp_path, fake)
    zahhak, crown = _named(p, "Zahhak"), _named(p, "Zahhak's crown")
    plan = p.plan(hf.CharacterPacks(subject_id=zahhak.id, profile="quality"))
    of = {o.id: o.subjects[0].subject_id if o.subjects else "" for o in plan.outputs}
    crown_items = [o.item for o in plan.outputs if of[o.id] == crown.id]
    assert crown_items[:2] == ["Hero", "Detail"]  # a hero and a close-up
    assert not any(o.pack == "actions" for o in plan.outputs)  # never used in an action
    hero_id = next(o.id for o in plan.outputs if of[o.id] == crown.id and o.item == "Hero")
    for o in plan.outputs:
        if of[o.id] == zahhak.id:
            assert o.prompt_inputs["worn"] == ["Zahhak's crown on his head"]
        if o.pack == "poses":
            assert hero_id not in [d.output for d in o.depends_on]  # never a reference in a pose
    front = next(o for o in plan.outputs if o.item == "Front" and o.pack == "turnaround")
    assert hero_id in [d.output for d in front.depends_on]


def test_ac41_place_coverage_and_states(tmp_path: Path, fake: FakeModels) -> None:
    p = _project(tmp_path, fake)
    hall = _named(p, "Zahhak's throne hall")
    plan = p.plan(
        hf.SubjectReferences(subject_id=hall.id, profile="quality", presentation="quality-coverage")
    )
    tags = [t for o in plan.outputs for t in o.prompt_inputs.get("tags", [])]
    assert {"view:Reverse", "view:Left", "view:Right", "view:High"} <= set(tags)
    assert {"state:Night, lamps lit", "state:Night, lamps out"} <= set(tags)


def test_ac42_identical_views_fail_without_the_judge(
    tmp_path: Path, fake: FakeModels, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("HONE_FRAME_TOOLS_PYTHON", raising=False)
    p = _project(tmp_path, fake)
    view = _run(p, hf.CharacterPacks(subject_id=_named(p, "Kaveh's banner").id))
    turned = [o for o in view.outputs if o.label in ("Face-on", "Edge-on")]
    assert all(o.status == "needs_review" for o in turned)  # the fakes draw one flat colour: the same
    image = p.image(turned[0].candidates[0])
    assert image.evaluation is not None and image.evaluation.judge == "measured"
    judged = [c.prompt for c in fake.asked if "quality judge" in c.prompt]
    assert not any("Face-on" in j for j in judged)
    events = (p.workspace.root / "projects").rglob("events.jsonl")
    assert any("measured_skipped" in e.read_text() for e in events)
