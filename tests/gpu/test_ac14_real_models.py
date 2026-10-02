"""AC-14 [real]: one hero generated with the draft profile on the GPU, planned and judged by real models.

z-image-turbo (ComfyUI) draws, gemma4-12b plans the prompt and qwen2.5vl-7b judges, all through
hone-models; the run ends `done` or `needs_review` with a real image and a real evaluation, and the chat
models are unloaded afterwards. ComfyUI is started from `HONE_COMFYUI_START` when it is not running.
Run through the machine-wide lock: `scripts/gpu-lock.sh uv run pytest -m gpu`.
"""

import os
from collections.abc import Iterator
from pathlib import Path

import hone_models as mk
import pytest
from PIL import Image

import hone_frame as hf

pytestmark = [pytest.mark.gpu, pytest.mark.ollama, pytest.mark.comfyui, pytest.mark.timeout(1800)]

PLANNER = os.environ.get("HONE_TEST_TEXT_MODEL", "gemma4-12b")
JUDGE = os.environ.get("HONE_TEST_VISION_MODEL", "qwen2.5vl-7b")


@pytest.fixture
def models(gpu_lock: None) -> Iterator[hf.HoneModels]:
    port = hf.HoneModels()
    for model_id, kind in (("z-image-turbo", "image"), (PLANNER, "chat"), (JUDGE, "chat")):
        info = port.info(model_id)
        if info.kind != kind or not info.available or info.installed == "no":
            pytest.skip(f"{model_id} is not available here ({info.note or info.installed})")
    yield port
    for model_id in (PLANNER, JUDGE):
        mk.unload(model_id)
    port.close()


def test_ac14_real_hero(tmp_path: Path, models: hf.HoneModels) -> None:
    ws = hf.Workspace(tmp_path / "studio", models=models)
    project = ws.create_project("Morning at home", direction="soft, natural, lived-in")
    project.update(defaults={"profile": "draft", "profiles": {"draft": {"planner": PLANNER, "judge": JUDGE}}})
    woman = project.add_subject(
        "character", "Woman", description="late twenties, black hair in a loose bun, cream knit sweater"
    )
    request = hf.SubjectReferences(
        subject_id=woman.id,
        presentation="neutral-full-body",
        selection=hf.Selection(rounds=1, candidates=1, technical_retries=1),
    )
    run = project.submit(request)
    hf.Runner(ws).run_next()
    view = project.run_view(run.id)
    print(view.status, view.reason, view.outputs[0].reason, view.usage)
    assert view.status in ("done", "needs_review"), view.reason
    image = project.image(view.outputs[0].candidates[0])
    with Image.open(project.image_path(image.id)) as picture:
        assert picture.size == (1024, 1024)
    assert image.generation is not None and image.generation.model == "z-image-turbo"
    assert image.evaluation is not None and image.evaluation.checks and image.evaluation.judge == JUDGE
    assert view.usage["gpu_s"] and view.usage["cost_usd"] is None


def test_ac14_real_view_from_the_hero(
    tmp_path: Path, models: hf.HoneModels, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The view after the hero goes to the editor (flux.2-klein-4b, from hone-frame's own registry file)
    with the accepted hero as its identity reference, started from a folder with no hone-models.toml."""
    monkeypatch.chdir(tmp_path)
    ws = hf.Workspace(tmp_path / "studio", models=models)
    project = ws.create_project("Morning at home")
    project.update(defaults={"profile": "draft", "profiles": {"draft": {"planner": PLANNER, "judge": JUDGE}}})
    woman = project.add_subject(
        "character",
        "Woman",
        description="late twenties, black hair in a loose bun, "
        "cream knit sweater, blue jeans, white sneakers",
    )
    one = hf.Selection(rounds=1, candidates=1, technical_retries=1)
    request = hf.SubjectReferences(
        subject_id=woman.id, presentation="neutral-full-body", expressions=["happy"], selection=one
    )
    plan = project.plan(request)
    assert [o.model for o in plan.outputs] == ["z-image-turbo", "flux.2-klein-4b"] and plan.errors == []
    run = project.submit(request)
    hf.Runner(ws).run_next()
    view = project.run_view(run.id)
    hero, happy = view.outputs
    print(view.status, [(o.label, o.status, o.reason) for o in view.outputs], view.usage)
    if hero.status != "done":
        pytest.skip(f"the judge did not accept the hero ({hero.reason}); the view could not start")
    image = project.image(happy.candidates[0])
    assert image.generation is not None and image.generation.model == "flux.2-klein-4b"
    assert [r.image_id for r in image.generation.references] == [hero.selected]
