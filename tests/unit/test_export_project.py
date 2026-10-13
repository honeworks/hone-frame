"""Whole-project export (CLI `export-project`): one zip with the project's records and images, its
flow run folders, and a manifest with the models used and a queue snapshot."""

import json
import zipfile
from pathlib import Path

from typer.testing import CliRunner

import hone_frame as hf
from hone_frame.cli import app
from hone_frame.testing import FakeModels, sample_workspace

runner = CliRunner()


def _make_run(tmp_path: Path) -> hf.ProjectStore:
    """A workspace with a finished run, so there are images, a run record and a flow folder."""
    store = sample_workspace(tmp_path)
    scene = store.save_scene(hf.Scene(name="S", refs=[hf.SceneRef(subject_id="char_001")]))
    store.submit(hf.SceneShot(scene_id=scene.id, selection=hf.Selection(rounds=1)))
    hf.Runner(hf.Workspace(tmp_path, models=FakeModels())).run_next()
    return store


def test_export_project_zip(tmp_path: Path) -> None:
    store = _make_run(tmp_path)
    out = tmp_path / "whole.zip"
    got = runner.invoke(app, ["export-project", store.id, str(out), "--home", str(tmp_path)])
    assert got.exit_code == 0 and out.is_file()
    names = set(zipfile.ZipFile(out).namelist())
    assert "manifest.json" in names
    assert "project/project.json" in names
    assert any(n.startswith("project/subjects/") for n in names)
    assert any(n.startswith("project/images/") and n.endswith(".png") for n in names)
    assert any(n.startswith("project/runs/") for n in names)
    assert any(n.startswith("flows/") and n.endswith("manifest.json") for n in names)
    assert any(n.endswith("spans.jsonl") for n in names)
    manifest = json.loads(zipfile.ZipFile(out).read("manifest.json"))
    assert manifest["project"]["id"] == store.id
    assert manifest["models_used"], "the manifest names the models that generated images"
    assert "queue" in manifest and isinstance(manifest["queue"], list)


def test_export_project_defaults_and_errors(tmp_path: Path) -> None:
    store = _make_run(tmp_path)
    got = runner.invoke(app, ["export-project", store.id, "--home", str(tmp_path)])
    assert got.exit_code == 0 and (Path.cwd() / f"{store.id}-export.zip").is_file()
    (Path.cwd() / f"{store.id}-export.zip").unlink()
    got = runner.invoke(app, ["export-project", store.id, str(tmp_path / "x.tar"), "--home", str(tmp_path)])
    assert got.exit_code == 1 and "zip" in str(got.exception)
    got = runner.invoke(app, ["export-project", "nope", "--home", str(tmp_path)])
    assert got.exit_code == 1
