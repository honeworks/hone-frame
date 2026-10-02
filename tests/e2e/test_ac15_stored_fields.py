"""AC-15: the fields change 0003 adds are stored and read back by a new workspace object, and records
written before it open with their defaults."""

import json

import hone_frame as hf
from hone_frame.testing import FakeModels

from ._characters import ONE, rostam
from .conftest import run_all


def test_new_fields_survive_a_new_workspace(ws: hf.Workspace) -> None:
    p = rostam(ws)
    p.submit(hf.CharacterPacks(subject_id="char_001", packs=["expressions"], selection=ONE))
    run_all(p)
    p.save_scene(
        hf.Scene(
            name="Duel",
            refs=[
                hf.SceneRef(subject_id="char_001"),
                hf.SceneRef(subject_id="obj_001", role="object", suggested=True),
            ],
        )
    )
    again = hf.Workspace(ws.root, models=FakeModels()).project(p.id)
    assert again.subject("obj_001").owner == "char_001"
    assert {(i.pack, i.item) for i in again.images()} >= {("hero", "Hero"), ("expressions", "Happy")}
    assert again.scenes()[0].refs[1].suggested is True


def test_records_written_before_change_0003_get_defaults(ws: hf.Workspace) -> None:
    p = rostam(ws)
    path = p.root / "subjects" / "obj_001.json"
    data = json.loads(path.read_text())
    for version in data["versions"]:
        version.pop("owner")
    path.write_text(json.dumps(data))
    image = p.import_image(_png(ws), subject_id="char_001", label="Hero")
    record = p.root / "images" / f"{image.id}.json"
    old = {k: v for k, v in json.loads(record.read_text()).items() if k not in ("pack", "item")}
    record.write_text(json.dumps(old))
    again = hf.Workspace(ws.root, models=FakeModels()).project(p.id)
    assert again.subject("obj_001").owner is None
    assert (again.image(image.id).pack, again.image(image.id).item) == (None, None)
    assert hf.SceneRef.model_validate({"subject_id": "char_001"}).suggested is False


def _png(ws: hf.Workspace):
    from PIL import Image

    path = ws.root / "hero.png"
    Image.new("RGB", (8, 8), "white").save(path)
    return path
