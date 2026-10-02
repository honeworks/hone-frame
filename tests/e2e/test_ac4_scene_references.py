"""AC-4: a scene consumes only its selected references, with visible roles, versions and order."""

from pathlib import Path

from PIL import Image

import hone_frame as hf
from hone_frame.ports import ModelInfo
from hone_frame.testing import FakeModels

from .conftest import run_all


def _coffee(p: hf.ProjectStore) -> hf.Scene:
    by_name = {s.name: s for s in p.subjects()}
    return p.save_scene(
        hf.Scene(
            name="Coffee scene",
            description="She holds the cup and smiles at the window.",
            refs=[
                hf.SceneRef(subject_id=by_name["Coffee cup"].id, role="object"),
                hf.SceneRef(subject_id=by_name["Kitchen"].id, role="environment"),
                hf.SceneRef(subject_id=by_name["Woman"].id, role="identity"),
            ],
            camera="medium",
            expression="focused",
        )
    )


def test_only_the_selected_references(sample: hf.ProjectStore, fake: FakeModels) -> None:
    scene = _coffee(sample)
    plan = sample.plan(hf.SceneShot(scene_id=scene.id))
    out = plan.outputs[0]
    assert [(r.subject_id, r.role) for r in out.references] == [
        ("char_001", "identity"),
        ("obj_001", "object"),
        ("env_001", "environment"),
    ]
    assert all(r.version == sample.subject(r.subject_id or "").version for r in out.references)
    assert "obj_002" not in {r.subject_id for r in out.references}  # the toothbrush
    assert plan.warnings == [] and plan.errors == []
    run = sample.submit(hf.SceneShot(scene_id=scene.id, selection=hf.Selection(rounds=1)))
    run_all(sample)
    sent = fake.generated[0].references
    expected = [sample.image_path(r.image_id).name for r in out.references]
    assert [p.name for p in sent] == expected
    assert "Toothbrush" not in fake.generated[0].prompt
    image = sample.image(sample.run_view(run.id).outputs[0].candidates[0])
    assert [u.role for u in image.generation.references] == ["identity", "object", "environment"]  # pyright: ignore[reportOptionalMemberAccess]
    assert {s.subject_id for s in image.subjects} == {"char_001", "env_001", "obj_001"}


def test_reduction_and_text_only(tmp_path: Path) -> None:
    few = FakeModels(
        infos={"flux.2-klein-4b": ModelInfo(id="flux.2-klein-4b", kind="image", local=True, max_references=2)}
    )
    from hone_frame.testing import sample_workspace

    p = sample_workspace(tmp_path / "a", models=few)
    plan = p.plan(hf.SceneShot(scene_id=_coffee(p).id))
    assert [r.role for r in plan.outputs[0].references] == ["identity", "object"]
    assert any("(environment) left out" in w for w in plan.warnings)
    assert plan.outputs[0].text_refs and "Kitchen" in plan.outputs[0].text_refs[0]

    none = FakeModels(
        infos={"flux.2-klein-4b": ModelInfo(id="flux.2-klein-4b", kind="image", local=True, max_references=0)}
    )
    q = sample_workspace(tmp_path / "b", models=none)
    plan = q.plan(hf.SceneShot(scene_id=_coffee(q).id))
    assert any("text only: weaker control" in w for w in plan.warnings)
    assert plan.outputs[0].references == [] and len(plan.outputs[0].text_refs) == 3


def test_missing_image_is_a_plan_error(ws: hf.Workspace) -> None:
    p = ws.create_project("P")
    woman = p.add_subject("character", "Woman", description="x")
    scene = p.save_scene(hf.Scene(name="S", refs=[hf.SceneRef(subject_id=woman.id)]))
    plan = p.plan(hf.SceneShot(scene_id=scene.id))
    assert any("no accepted image" in e for e in plan.errors)


def test_large_reference_is_reduced_not_changed(tmp_path: Path, fake: FakeModels) -> None:
    from hone_frame.testing import sample_workspace

    p = sample_workspace(tmp_path / "ws", models=fake)
    big = tmp_path / "big.png"
    Image.new("RGB", (3000, 2000), "#abcdef").save(big)
    image = p.import_image(big, subject_id="char_001", label="Hero")
    p.edit_subject("char_001", reference_images=[image.id])
    original = p.image_path(image.id).read_bytes()
    scene = p.save_scene(hf.Scene(name="S", refs=[hf.SceneRef(subject_id="char_001")]))
    p.submit(hf.SceneShot(scene_id=scene.id, selection=hf.Selection(rounds=1)))
    run_all(p)
    sent = fake.generated[0].references[0]
    assert sent != p.image_path(image.id) and "work" not in str(p.image_path(image.id))
    assert p.image_path(image.id).read_bytes() == original
