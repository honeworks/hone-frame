"""The command line (design §2): presets, projects, the queue, status and exports."""

import json
from pathlib import Path

from typer.testing import CliRunner

import hone_frame as hf
from hone_frame.cli import app
from hone_frame.testing import FakeModels, sample_workspace

runner = CliRunner()


def test_presets_and_projects(tmp_path: Path) -> None:
    out = runner.invoke(app, ["presets", "--category", "camera", "--home", str(tmp_path), "--json"])
    assert out.exit_code == 0 and len(json.loads(out.stdout)["camera"]) == 14
    sample_workspace(tmp_path)
    out = runner.invoke(app, ["projects", "--home", str(tmp_path)])
    assert out.exit_code == 0 and "morning-at-home\tMorning at home" in out.stdout


def test_queue_status_and_pack(tmp_path: Path) -> None:
    store = sample_workspace(tmp_path)
    scene = store.save_scene(hf.Scene(name="S", refs=[hf.SceneRef(subject_id="char_001")]))
    run = store.submit(hf.SceneShot(scene_id=scene.id, selection=hf.Selection(rounds=1)))
    # the CLI's workspace uses hone-models; run the queue here with fakes, then read it through the CLI
    hf.Runner(hf.Workspace(tmp_path, models=FakeModels())).run_next()
    out = runner.invoke(app, ["status", store.id, run.id, "--home", str(tmp_path), "--json"])
    assert out.exit_code == 0 and json.loads(out.stdout)["status"] == "done"
    out = runner.invoke(app, ["status", store.id, run.id, "--home", str(tmp_path)])
    assert out.stdout.startswith("S: done")
    pack = tmp_path / "pack.zip"
    out = runner.invoke(app, ["export-pack", store.id, scene.id, str(pack), "--home", str(tmp_path)])
    assert out.exit_code == 0 and pack.is_file()
    out = runner.invoke(app, ["run-queue", "--home", str(tmp_path), "--once"])
    assert out.exit_code == 0 and out.stdout == ""


def test_errors_exit_one(tmp_path: Path) -> None:
    out = runner.invoke(app, ["status", "nope", "x", "--home", str(tmp_path)])
    assert out.exit_code == 1
