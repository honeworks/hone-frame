"""AC-3: three-round automatic generation runs unattended, keeps every candidate, explains its picks."""

from pathlib import Path
from typing import Any

import pytest

import hone_frame as hf
from hone_frame.testing import FakeModels, judge_answer

from .conftest import run_all


def _woman(ws: hf.Workspace) -> tuple[hf.ProjectStore, str]:
    p = ws.create_project("Morning at home")
    return p, p.add_subject("character", "Woman", description="late twenties, black hair in a bun").id


def test_turnaround_three_rounds(ws: hf.Workspace, fake: FakeModels) -> None:
    p, woman = _woman(ws)
    req = hf.SubjectReferences(subject_id=woman, presentation="turnaround")
    plan = p.plan(req)
    assert [o.label for o in plan.outputs] == ["Hero", "Front", "3/4", "Side", "Back"]
    assert (plan.counts.outputs, plan.counts.images, plan.counts.judge_calls) == (5, 15, 15)
    assert all(d.output == "o01" for o in plan.outputs[1:] for d in o.depends_on)
    assert plan.presets["profile:draft"] == 1 and plan.presets["style_pack:cinematic-realism"] == 1
    run = p.submit(req)
    assert run.status == "queued"
    run_all(p)
    view = p.run_view(run.id)
    assert view.status == "done"
    assert view.accepted == ["o01", "o02", "o03", "o04", "o05"] and view.unresolved == []
    assert len(p.images(subject_id=woman)) == 15 == fake.image_calls
    for out in view.outputs:
        assert len(out.candidates) == 3 and out.selected in out.candidates
        assert out.reason.startswith(f"picked {out.selected}")
    hero = view.outputs[0].selected
    assert all(c.references and c.references[0].name.startswith(hero or "") for c in fake.generated[3:])
    assert view.progress["fraction"] == 1.0 and view.usage["images"] == 15


def test_counts_scale(ws: hf.Workspace) -> None:
    p, _ = _woman(ws)
    scene = p.save_scene(hf.Scene(name="S", refs=[]))
    cameras = [
        "wide",
        "medium",
        "close-up",
        "front",
        "profile",
        "rear",
        "three-quarter",
        "overhead",
        "low-angle",
        "reverse",
        "pov",
        "detail",
    ]
    one = p.plan(hf.Coverage(scene_id=scene.id, cameras=cameras))
    assert (one.counts.outputs, one.counts.images) == (12, 36)
    two = p.plan(hf.Coverage(scene_id=scene.id, cameras=cameras, selection=hf.Selection(candidates=2)))
    assert two.counts.images == 72


def test_stop_on_pass_shrinks_the_plan(ws: hf.Workspace, fake: FakeModels) -> None:
    p, woman = _woman(ws)
    req = hf.SubjectReferences(
        subject_id=woman, presentation="neutral-full-body", selection=hf.Selection(stop="stop_on_pass")
    )
    run = p.submit(req)
    run_all(p)
    view = p.run_view(run.id)
    assert view.status == "done" and fake.image_calls == 1
    assert view.progress == {"done": 2, "planned": 2, "fraction": 1.0, "current": None}


def _scripted(scores: list[tuple[float, tuple[str, ...]]]) -> FakeModels:
    def judge(i: int, prompt: str, _images: list[Path]) -> dict[str, Any]:
        overall, fail = scores[i % len(scores)]
        return judge_answer(prompt, fail=fail, overall=overall)

    return FakeModels(judge=judge)


def test_earlier_better_candidate_is_kept(tmp_path: Path) -> None:
    fake = _scripted([(0.9, ()), (0.5, ()), (0.7, ())])
    ws = hf.Workspace(tmp_path, models=fake)
    p, woman = _woman(ws)
    run = p.submit(hf.SubjectReferences(subject_id=woman, presentation="neutral-full-body"))
    run_all(p)
    out = p.run_view(run.id).outputs[0]
    assert out.selected == out.candidates[0]
    assert p.image(out.candidates[2]).status == "candidate"


def test_required_failure_beats_a_high_score(tmp_path: Path) -> None:
    fake = _scripted([(0.99, ("anatomy",)), (0.4, ()), (0.95, ("framing",))])
    ws = hf.Workspace(tmp_path, models=fake)
    p, woman = _woman(ws)
    run = p.submit(hf.SubjectReferences(subject_id=woman, presentation="neutral-full-body"))
    run_all(p)
    out = p.run_view(run.id).outputs[0]
    assert out.selected == out.candidates[1]
    assert p.image(out.candidates[0]).status == "rejected"
    assert p.image(out.candidates[0]).evaluation.overall == 0.99  # pyright: ignore[reportOptionalMemberAccess]


def test_no_pass_needs_review_with_best_available(tmp_path: Path) -> None:
    fake = _scripted([(0.6, ("view",)), (0.8, ("view",)), (0.7, ("view",))])
    ws = hf.Workspace(tmp_path, models=fake)
    p, woman = _woman(ws)
    run = p.submit(hf.SubjectReferences(subject_id=woman, presentation="neutral-full-body"))
    run_all(p)
    view = p.run_view(run.id)
    out = view.outputs[0]
    assert view.status == "needs_review" and out.status == "needs_review" and out.selected is None
    assert out.best_available == out.candidates[1]
    assert p.image(out.best_available or "").status == "best_available"
    assert "no candidate passed view" in out.reason


def test_sequential_strategy_feeds_findings(tmp_path: Path) -> None:
    fake = _scripted([(0.5, ("framing",)), (0.6, ("framing",)), (0.9, ())])
    ws = hf.Workspace(tmp_path, models=fake)
    p, woman = _woman(ws)
    run = p.submit(
        hf.SubjectReferences(
            subject_id=woman, presentation="neutral-full-body", selection=hf.Selection(strategy="sequential")
        )
    )
    run_all(p)
    prompts = [c.prompt for c in fake.generated]
    assert "Fix from the last attempt" not in prompts[0]
    assert "framing: framing looks wrong" in prompts[1] and "framing" in prompts[2]
    assert p.run_view(run.id).outputs[0].selected == p.run_view(run.id).outputs[0].candidates[2]
    assert sum(1 for c in fake.asked if "write the prompt" in c.prompt) == 3


def test_manual_pick_mode(ws: hf.Workspace) -> None:
    p, woman = _woman(ws)
    run = p.submit(
        hf.SubjectReferences(
            subject_id=woman,
            presentation="neutral-full-body",
            selection=hf.Selection(auto_pick=False, rounds=1, candidates=2),
        )
    )
    run_all(p)
    out = p.run_view(run.id).outputs[0]
    assert out.status == "needs_review" and out.reason == "manual pick: choose a candidate"


def test_auto_pick_needs_the_judge(ws: hf.Workspace) -> None:
    p, woman = _woman(ws)
    plan = p.plan(hf.SubjectReferences(subject_id=woman, selection=hf.Selection(auto_judge=False)))
    assert any("automatic pick needs automatic judging" in e for e in plan.errors)
    with pytest.raises(hf.errors.InvalidRequest, match="automatic pick"):
        p.submit(hf.SubjectReferences(subject_id=woman, selection=hf.Selection(auto_judge=False)))


def test_rear_views_are_judged_from_behind(ws: hf.Workspace, fake: FakeModels) -> None:
    p, woman = _woman(ws)
    plan = p.plan(hf.SubjectReferences(subject_id=woman, presentation="turnaround"))
    back = next(o for o in plan.outputs if o.label == "Back")
    assert "rear" in back.conditions and "rear" not in plan.outputs[1].conditions
    p.submit(
        hf.SubjectReferences(subject_id=woman, presentation="turnaround", selection=hf.Selection(rounds=1))
    )
    run_all(p)
    prompts = [c.prompt for c in fake.asked if "quality judge" in c.prompt]
    back_prompt = next(q for q in prompts if "to show: Back " in q)
    front_prompt = next(q for q in prompts if "to show: Front " in q)
    assert "- identity_from_behind:" in back_prompt and "- identity:" not in back_prompt
    assert "- identity:" in front_prompt and "identity_from_behind" not in front_prompt


def test_references_use_neutral_light_whatever_the_style_pack(ws: hf.Workspace) -> None:
    p = ws.create_project("Epic", style_pack="historical-epic")  # its mood lighting is dramatic side light
    hero = p.add_subject("character", "Rostam", description="a champion").id
    lights = {o.prompt_inputs["lighting"] for o in p.plan(hf.SubjectReferences(subject_id=hero)).outputs}
    assert lights == {"even soft neutral studio lighting, plain light grey background."}
    p.update(defaults={"presets": {"lighting": "golden-hour"}})  # chosen on purpose: kept
    lights = {o.prompt_inputs["lighting"] for o in p.plan(hf.SubjectReferences(subject_id=hero)).outputs}
    assert lights == {"golden hour sunlight, low warm light, long soft shadows, rim light."}


def test_rear_scenes_and_subject_variations(tmp_path: Path) -> None:
    from hone_frame.testing import sample_workspace

    fake = FakeModels()
    p = sample_workspace(tmp_path / "ws", models=fake)
    scene = p.save_scene(hf.Scene(name="Leaving", refs=[hf.SceneRef(subject_id="char_001")], camera="rear"))
    shot = p.plan(hf.SceneShot(scene_id=scene.id)).outputs[0]
    assert "rear" in shot.conditions
    grid = p.plan(hf.Variations(subject_id="char_001", axes={"camera": ["rear", "front"]})).outputs
    assert ["rear" in o.conditions for o in grid] == [True, False]
    p.submit(hf.SceneShot(scene_id=scene.id, selection=hf.Selection(rounds=1)))
    run_all(p)
    judged = next(c.prompt for c in fake.asked if "quality judge" in c.prompt)
    assert "- identity_from_behind:" in judged and "- identity:" not in judged
    front = p.save_scene(hf.Scene(name="Arriving", refs=[hf.SceneRef(subject_id="char_001")], camera="front"))
    p.submit(hf.SceneShot(scene_id=front.id, selection=hf.Selection(rounds=1)))
    run_all(p)
    control = [c.prompt for c in fake.asked if "quality judge" in c.prompt][-1]
    assert "- identity:" in control and "identity_from_behind" not in control


def test_reference_lighting_precedence_and_a_given_hero(ws: hf.Workspace) -> None:
    p = ws.create_project("Epic", style_pack="historical-epic")
    hero = p.add_subject("character", "Rostam", description="a champion").id
    p.update(defaults={"presets": {"lighting": "golden-hour"}})
    asked = hf.SubjectReferences(subject_id=hero, presets={"lighting": "moonlight"})
    assert {o.prompt_inputs["lighting"] for o in p.plan(asked).outputs} == {
        "cool blue moonlight at night, deep shadows, subtle highlights."
    }  # the request's choice beats the project's
    p.update(defaults={"presets": {}})
    image = p.import_image(_png(ws.root / "hero.png"), subject_id=hero)
    given = p.plan(hf.SubjectReferences(subject_id=hero, hero_image=image.id)).outputs
    assert given and {o.prompt_inputs["lighting"] for o in given} == {
        "even soft neutral studio lighting, plain light grey background."
    }


def _png(path: Path) -> Path:
    from PIL import Image

    Image.new("RGB", (32, 48), "#888888").save(path)
    return path
