"""The dashboard API of change 0006: generate with casting, approval and judge mode; the approvals list;
Generate again with issues; clean-up."""

from pathlib import Path

import pytest

import hone_frame as hf
from hone_frame._dashboard_api import route
from hone_frame.engine import Runner
from hone_frame.testing import FakeModels

FILE = Path(__file__).parents[2] / "examples" / "projects" / "rostam-and-sohrab.toml"


def _run_all(ws: hf.Workspace) -> None:
    runner = Runner(ws)
    while runner.run_next() is not None:
        pass


def test_options_through_the_api(tmp_path: Path) -> None:
    ws = hf.Workspace(tmp_path / "ws", models=FakeModels())
    pid = ws.import_file(FILE).project
    body = {"packs": ["turnaround"], "casting": 2, "approval": "base", "selection": {"rounds": 1}}
    run = route(ws, "POST", f"/projects/{pid}/characters/char_001/generate", {}, body)
    _run_all(ws)
    page = route(ws, "GET", f"/projects/{pid}/characters/char_001", {}, None)
    assert [a["run"] for a in page["approvals"]] == [run["id"]]
    assert route(ws, "GET", f"/projects/{pid}/home", {}, None)["approvals"][0]["run"] == run["id"]
    route(ws, "POST", f"/runs/{pid}/{run['id']}/resume", {}, {})
    _run_all(ws)
    page = route(ws, "GET", f"/projects/{pid}/characters/char_001", {}, None)
    assert not page["approvals"]
    back = next(
        i for row in page["packs"] if row["id"] == "turnaround" for i in row["items"] if i["item"] == "Back"
    )
    redo = route(
        ws, "POST", f"/runs/{pid}/{back['run']}/rerun", {}, {"output": back["output"], "issues": ["feet"]}
    )
    _run_all(ws)
    image = next(i for i in ws.project(pid).images() if i.run_id == redo["id"])
    assert image.generation and "both pointing the same way" in image.generation.prompt.lower()
    assert (
        route(ws, "POST", f"/projects/{pid}/cleanup", {}, {"what": "unchosen", "dry_run": True})["images"]
        >= 1
    )
    assert route(ws, "POST", f"/projects/{pid}/cleanup", {}, {"what": "unchosen"})["deleted"] >= 1
    issues = route(ws, "GET", "/issues", {}, None)
    assert len(issues) == 20 and {"id", "label", "group"} == set(issues[0])
    strong = {"packs": ["hero"], "judge_mode": "strong_all"}
    with pytest.raises(hf.errors.InvalidRequest) as refused:
        route(ws, "POST", f"/projects/{pid}/characters/char_002/generate", {}, strong)
    assert "no stronger judge is set" in " ".join(refused.value.problems)
