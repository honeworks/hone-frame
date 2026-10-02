"""AC-7: coverage, interactions, state pairs, sequences and variation grids reuse the project's
subjects and give per-output results (design §6.1)."""

import hone_frame as hf
from hone_frame.testing import FakeModels

from .conftest import run_all


def _scene(p: hf.ProjectStore) -> hf.Scene:
    return p.save_scene(
        hf.Scene(
            name="Coffee",
            description="morning coffee",
            refs=[
                hf.SceneRef(subject_id="char_001", role="identity"),
                hf.SceneRef(subject_id="env_001", role="environment"),
                hf.SceneRef(subject_id="obj_001", role="object"),
            ],
        )
    )


def test_coverage(sample: hf.ProjectStore, fake: FakeModels) -> None:
    scene = _scene(sample)
    run = sample.submit(
        hf.Coverage(
            scene_id=scene.id, cameras=["wide", "close-up", "profile"], selection=hf.Selection(rounds=1)
        )
    )
    run_all(sample)
    view = sample.run_view(run.id)
    assert [o.label for o in view.outputs] == ["wide", "close-up", "profile"]
    assert all(len(o.candidates) == 1 and o.status == "done" for o in view.outputs)
    assert "Wide shot" in fake.generated[0].prompt and "Close-up shot" in fake.generated[1].prompt
    assert len({c.seed for c in fake.generated}) == 1  # one seed group: only the camera changes


def test_interaction(sample: hf.ProjectStore, fake: FakeModels) -> None:
    run = sample.submit(
        hf.Interaction(
            character_id="char_001", asset_id="obj_001", action="hold-cup", selection=hf.Selection(rounds=1)
        )
    )
    run_all(sample)
    out = sample.run_view(run.id).outputs[0]
    image = sample.image(out.candidates[0])
    assert {s.subject_id for s in image.subjects} == {"char_001", "obj_001"}
    judge_prompt = next(c.prompt for c in fake.asked if "quality judge" in c.prompt)
    assert "- contact:" in judge_prompt and "- hand_placement:" in judge_prompt
    assert "Woman holds Coffee cup" in fake.generated[0].prompt


def test_state_pair(sample: hf.ProjectStore, fake: FakeModels) -> None:
    run = sample.submit(
        hf.StatePair(subject_id="obj_001", state="empty-full", selection=hf.Selection(rounds=1))
    )
    run_all(sample)
    before, after = sample.run_view(run.id).outputs
    assert (before.label, after.label) == ("Empty", "Full")
    assert fake.generated[0].seed == fake.generated[1].seed
    assert sample.image_path(before.selected or "").name in [p.name for p in fake.generated[1].references]
    assert "filled to the top" in fake.generated[1].prompt


def test_sequence(sample: hf.ProjectStore, fake: FakeModels) -> None:
    scene = _scene(sample)
    seq = sample.save_sequence(
        hf.Sequence(
            name="Reach",
            scene_id=scene.id,
            frames=[
                hf.Frame(id="reach", description="reaches for the cup"),
                hf.Frame(id="touch", description="touches the handle"),
                hf.Frame(id="grip", description="grips the cup"),
                hf.Frame(id="lift", description="lifts the cup"),
            ],
        )
    )
    run = sample.submit(hf.SequenceFrames(sequence_id=seq.id, selection=hf.Selection(rounds=1)))
    run_all(sample)
    view = sample.run_view(run.id)
    assert [o.status for o in view.outputs] == ["done"] * 4
    identity = sample.image_path("img_0001").name
    for n, call in enumerate(fake.generated):
        names = [p.name for p in call.references]
        assert identity in names  # the stable identity reference, every frame
        if n:
            assert sample.image_path(view.outputs[n - 1].selected or "").name in names
    rerun = sample.rerun(run.id, "o02")
    run_all(sample)
    assert sample.run_view(rerun.id).status == "done"
    assert sample.run_view(run.id).outputs[0].candidates == view.outputs[0].candidates


def test_variation_grid(sample: hf.ProjectStore) -> None:
    scene = _scene(sample)
    plan = sample.plan(
        hf.Variations(
            scene_id=scene.id,
            axes={
                "outfit": ["pyjamas", "sweater", "coat"],
                "expression": ["happy", "sad", "tired", "focused"],
                "lighting": ["soft-daylight", "moonlight"],
            },
        )
    )
    assert (plan.counts.outputs, plan.counts.images) == (24, 72)
    assert plan.outputs[0].label == "outfit: pyjamas · expression: happy · lighting: soft-daylight"
    assert len({o.label for o in plan.outputs}) == 24
