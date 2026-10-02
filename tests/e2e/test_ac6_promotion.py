"""AC-6: a chosen draft becomes a traceable final by an explicit operation (design §10.5)."""

from pathlib import Path
from typing import Any

import hone_frame as hf
from hone_frame.testing import FakeModels, judge_answer, sample_workspace

from .conftest import run_all


def _draft(p: hf.ProjectStore) -> str:
    scene = p.save_scene(
        hf.Scene(
            name="Coffee",
            refs=[hf.SceneRef(subject_id="char_001"), hf.SceneRef(subject_id="obj_001", role="object")],
        )
    )
    run = p.submit(hf.SceneShot(scene_id=scene.id, selection=hf.Selection(rounds=1)))
    run_all(p)
    return p.run_view(run.id).outputs[0].selected or ""


def test_refine(sample: hf.ProjectStore, fake: FakeModels) -> None:
    draft = _draft(sample)
    plan = sample.plan(hf.Promote(image_id=draft, operation="refine"))
    assert plan.profile.id == "final" and plan.outputs[0].model == "qwen-image-edit-2511"
    run = sample.submit(hf.Promote(image_id=draft, operation="refine", selection=hf.Selection(rounds=1)))
    run_all(sample)
    call = fake.generated[-1]
    assert call.references[0].name == sample.image_path(draft).name  # the draft first
    assert len(call.references) == 3 and call.prompt.startswith("Refine image 1")
    final = sample.image(sample.run_view(run.id).outputs[0].selected or "")
    assert final.parent == draft and final.source == "promoted"
    assert sample.image(draft).status == "picked"


def test_regenerate_uses_the_definition(sample: hf.ProjectStore, fake: FakeModels) -> None:
    draft = _draft(sample)
    run = sample.submit(hf.Promote(image_id=draft, operation="regenerate", selection=hf.Selection(rounds=1)))
    run_all(sample)
    final = sample.image(sample.run_view(run.id).outputs[0].selected or "")
    assert final.parent == draft and final.generation and final.generation.model == "qwen-image-edit-2511"


def test_upscale_needs_an_upscaler(sample: hf.ProjectStore) -> None:
    draft = _draft(sample)
    plan = sample.plan(hf.Promote(image_id=draft, operation="upscale"))
    assert any("no upscaler" in e for e in plan.errors)


def test_failed_refine_leaves_the_draft(tmp_path: Path) -> None:
    def judge(i: int, prompt: str, _images: list[Path]) -> dict[str, Any]:
        return judge_answer(
            prompt, fail=("preserved_composition",) if "preserved_composition" in prompt else ()
        )

    p = sample_workspace(tmp_path, models=FakeModels(judge=judge))
    draft = _draft(p)
    before = p.image(draft)
    run = p.submit(hf.Promote(image_id=draft, operation="refine", selection=hf.Selection(rounds=1)))
    run_all(p)
    assert p.run_view(run.id).status == "needs_review"
    assert p.image(draft) == before
