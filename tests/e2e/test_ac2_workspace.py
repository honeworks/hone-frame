"""AC-2: one project holds separately reusable, versioned subjects (design §4)."""

import json
from pathlib import Path

import pytest
from PIL import Image

import hone_frame as hf


def _png(path: Path, colour: str = "red", size: tuple[int, int] = (64, 48)) -> Path:
    Image.new("RGB", size, colour).save(path)
    return path


def _project(tmp_path: Path) -> hf.ProjectStore:
    ws = hf.Workspace(tmp_path / "ws")
    p = ws.create_project("Morning at home", brief="A quiet morning.")
    p.add_subject("character", "Woman", description="late twenties, black hair in a bun")
    p.add_subject("character", "Neighbour", description="older man, grey beard")
    p.add_subject(
        "environment", "Kitchen", description="small bright kitchen", fields={"anchors": ["window"]}
    )
    p.add_subject("asset", "Coffee cup", description="speckled cream mug")
    p.add_subject("asset", "Toothbrush", description="bamboo toothbrush")
    return p


def test_subjects_by_kind_with_readable_ids(tmp_path: Path) -> None:
    p = _project(tmp_path)
    assert p.id == "morning-at-home"
    assert [s.id for s in p.subjects("character")] == ["char_001", "char_002"]
    assert [s.id for s in p.subjects("environment")] == ["env_001"]
    assert [s.id for s in p.subjects("asset")] == ["obj_001", "obj_002"]
    assert p.subject("env_001").fields == {"anchors": ["window"]}


def test_edit_makes_a_version(tmp_path: Path) -> None:
    p = _project(tmp_path)
    new = p.edit_subject(
        "char_001", description="early thirties", states=[hf.State(name="wet", kind="condition")]
    )
    assert new.version == 2
    assert p.subject("char_001").description == "early thirties"
    assert p.subject("char_001", version=1).description == "late twenties, black hair in a bun"
    with pytest.raises(hf.errors.NotFound, match="no version 9"):
        p.subject("char_001", version=9)
    with pytest.raises(hf.errors.InvalidRequest, match="cannot change"):
        p.edit_subject("char_001", kind="asset")


def test_images_and_filters(tmp_path: Path) -> None:
    p = _project(tmp_path)
    a = p.import_image(_png(tmp_path / "a.png"), subject_id="char_001", label="front")
    b = p.import_image(_png(tmp_path / "b.png", "blue"), subject_id="obj_001")
    assert (a.id, b.id) == ("img_0001", "img_0002")
    assert a.subjects[0].subject_id == "char_001" and a.subjects[0].version == 1
    assert (a.width, a.height, a.status, a.source) == (64, 48, "imported", "imported")
    assert p.image_path(a.id).read_bytes() == (tmp_path / "a.png").read_bytes()
    assert [r.id for r in p.images(kind="character")] == [a.id]
    assert [r.id for r in p.images(kind="asset")] == [b.id]
    assert [r.id for r in p.images(subject_id="obj_001")] == [b.id]
    assert p.images(status="picked") == []
    assert p.images(model="z-image-turbo") == []


def test_outdated_uses_after_an_edit(tmp_path: Path) -> None:
    p = _project(tmp_path)
    img = p.import_image(_png(tmp_path / "a.png"), subject_id="char_001")
    scene = p.save_scene(hf.Scene(name="Coffee", refs=[hf.SceneRef(subject_id="char_001")]))
    assert scene.refs[0].version == 1 and scene.id == "scn_001"
    sheet = p.save_sheet(hf.SheetRecipe(name="Woman", images=[img.id]))
    assert p.outdated() == []
    p.edit_subject("char_001", description="changed")
    flagged = {(u.kind, u.id) for u in p.outdated()}
    assert flagged == {("scene", scene.id), ("sheet", sheet.id)}
    updated = p.save_scene(scene.model_copy(update={"refs": [hf.SceneRef(subject_id="char_001")]}))
    assert updated.version == 2 and updated.refs[0].version == 2
    assert p.scene(scene.id, version=1).refs[0].version == 1


def test_used_image_cannot_be_deleted(tmp_path: Path) -> None:
    p = _project(tmp_path)
    img = p.import_image(_png(tmp_path / "a.png"), subject_id="char_001")
    p.save_sheet(hf.SheetRecipe(name="Woman", images=[img.id]))
    with pytest.raises(hf.errors.InvalidRequest, match="sheet sht_001"):
        p.delete_image(img.id)
    other = p.import_image(_png(tmp_path / "b.png"))
    p.delete_image(other.id)
    assert [r.id for r in p.images()] == [img.id]


def test_reopen_and_format_version(tmp_path: Path) -> None:
    p = _project(tmp_path)
    again = hf.Workspace(tmp_path / "ws").project("morning-at-home")
    assert [s.name for s in again.subjects()] == [s.name for s in p.subjects()]
    assert [x.id for x in hf.Workspace(tmp_path / "ws").projects()] == ["morning-at-home"]
    second = hf.Workspace(tmp_path / "ws").create_project("Morning at home")
    assert second.id == "morning-at-home-2"
    path = tmp_path / "ws" / "projects" / "morning-at-home" / "project.json"
    data = json.loads(path.read_text())
    path.write_text(json.dumps(data | {"format_version": "9"}))
    with pytest.raises(hf.errors.HoneFrameError, match="upgrade hone-frame"):
        _ = again.info


def test_unknown_things_raise_not_found(tmp_path: Path) -> None:
    p = _project(tmp_path)
    for call in (
        lambda: p.subject("char_009"),
        lambda: p.image("img_0009"),
        lambda: p.scene("scn_009"),
        lambda: p.workspace.project("nope"),
    ):
        with pytest.raises(hf.errors.NotFound):
            call()
    with pytest.raises(hf.errors.InvalidRequest):
        p.add_subject("vehicle", "Car")  # pyright: ignore[reportArgumentType]


def test_default_workspace_is_in_the_home_folder(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("HONE_FRAME_HOME", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path / "me"))
    monkeypatch.chdir(tmp_path)
    assert hf.Workspace().root == (tmp_path / "me" / "hone-frame").resolve()
    monkeypatch.setenv("HONE_FRAME_HOME", str(tmp_path / "elsewhere"))
    assert hf.Workspace().root == (tmp_path / "elsewhere").resolve()
