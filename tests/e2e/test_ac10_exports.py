"""AC-10: exports hold the originals and focused reference packs, never secrets (design §11.3)."""

import json
import zipfile
from pathlib import Path

import pytest

import hone_frame as hf

from .conftest import run_all

SECRET = "sk-test-0123456789abcdefSECRET"


def test_reference_pack_is_focused(sample: hf.ProjectStore, tmp_path: Path) -> None:
    scene = sample.save_scene(
        hf.Scene(
            name="Coffee",
            refs=[hf.SceneRef(subject_id="obj_001", role="object"), hf.SceneRef(subject_id="char_001")],
        )
    )
    out = sample.export_pack(scene.id, tmp_path / "pack.zip")
    with zipfile.ZipFile(out) as z:
        names = z.namelist()
        pack = json.loads(z.read("pack.json"))
    assert names == ["images/01-woman-identity.png", "images/02-coffee-cup-object.png", "pack.json"]
    assert [r["role"] for r in pack["references"]] == ["identity", "object"]
    assert "Toothbrush" not in json.dumps(pack)


def test_sheet_and_sequence_exports(sample: hf.ProjectStore, tmp_path: Path) -> None:
    sheet = sample.save_sheet(hf.SheetRecipe(name="Refs", images=["img_0001", "img_0003"]))
    with zipfile.ZipFile(sample.export_sheet(sheet.id, tmp_path / "s.zip", sources=True)) as z:
        assert set(z.namelist()) == {"sheet.png", "sheet.json", "images/img_0001.png", "images/img_0003.png"}
    scene = sample.save_scene(hf.Scene(name="Coffee", refs=[hf.SceneRef(subject_id="char_001")]))
    seq = sample.save_sequence(
        hf.Sequence(
            name="Sip", scene_id=scene.id, frames=[hf.Frame(id="a"), hf.Frame(id="b"), hf.Frame(id="c")]
        )
    )
    with pytest.raises(hf.errors.InvalidRequest, match="not been generated"):
        sample.export_sequence(seq.id, tmp_path / "q.zip")
    sample.submit(hf.SequenceFrames(sequence_id=seq.id, selection=hf.Selection(rounds=1)))
    run_all(sample)
    with zipfile.ZipFile(sample.export_sequence(seq.id, tmp_path / "q.zip")) as z:
        assert z.namelist() == ["frames/01.png", "frames/02.png", "frames/03.png", "sequence.json"]
        frames = json.loads(z.read("sequence.json"))["frames"]
    assert [f["frame"]["id"] for f in frames] == ["a", "b", "c"]


def test_no_secret_in_any_export(
    sample: hf.ProjectStore, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", SECRET)
    scene = sample.save_scene(hf.Scene(name="Coffee", refs=[hf.SceneRef(subject_id="char_001")]))
    sample.submit(hf.SceneShot(scene_id=scene.id, selection=hf.Selection(rounds=1)))
    run_all(sample)
    sheet = sample.save_sheet(hf.SheetRecipe(name="R", images=["img_0001"]))
    files = [
        sample.export_project(tmp_path / "p.zip"),
        sample.export_pack(scene.id, tmp_path / "k.zip"),
        sample.export_sheet(sheet.id, tmp_path / "s.zip", sources=True),
    ]
    for path in files:
        with zipfile.ZipFile(path) as z:
            for name in z.namelist():
                assert SECRET.encode() not in z.read(name), name
                assert "/work/" not in name and not name.endswith("control.json")
