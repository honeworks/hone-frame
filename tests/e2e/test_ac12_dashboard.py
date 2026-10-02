"""AC-12: the dashboard serves the page and a JSON API over the real workspace (design §12)."""

import json
import urllib.error
import urllib.request
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

import hone_frame as hf
from hone_frame.dashboard import Dashboard
from hone_frame.testing import FakeModels, sample_workspace

from .conftest import run_all


@pytest.fixture
def served(tmp_path: Path) -> Iterator[tuple[hf.ProjectStore, str]]:
    store = sample_workspace(tmp_path / "ws", models=FakeModels())
    dashboard = Dashboard(store.workspace, port=0, runner=False).start()
    yield store, dashboard.url.rstrip("/")
    dashboard.close()


def call(base: str, path: str, method: str = "GET", body: Any = None) -> tuple[int, Any, dict[str, str]]:
    data = json.dumps(body).encode() if body is not None else None
    request = urllib.request.Request(  # noqa: S310 - our own local test server
        base + path, data=data, method=method, headers={"Content-Type": "application/json"} if data else {}
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:  # noqa: S310 - http://127.0.0.1 only
            raw = response.read()
            kind = response.headers.get("Content-Type", "")
            return response.status, json.loads(raw) if "json" in kind else raw, dict(response.headers)
    except urllib.error.HTTPError as error:
        return error.code, json.loads(error.read() or b"{}"), dict(error.headers)


def test_page_and_scripts(served: tuple[hf.ProjectStore, str]) -> None:
    _, base = served
    status, page, headers = call(base, "/")
    assert (
        status == 200 and b"Hone Frame" in page and "script-src 'self'" in headers["Content-Security-Policy"]
    )
    for name in (
        "app.js",
        "core.js",
        "app.css",
        "views/queue.js",
        "views/library.js",
        "views/scenes.js",
        "views/sheets.js",
        "views/create.js",
        "views/overview.js",
        "views/presets.js",
        "views/models.js",
        "views/settings.js",
        "views/projects.js",
    ):
        status, _, headers = call(base, f"/{name}")
        assert status == 200 and headers["X-Content-Type-Options"] == "nosniff", name
    assert call(base, "/queue/some/client/route")[0] == 200  # the page handles its own routes


def test_read_endpoints(served: tuple[hf.ProjectStore, str]) -> None:
    store, base = served
    p = f"/api/projects/{store.id}"
    assert call(base, "/api/workspace")[1]["projects"][0]["id"] == store.id
    assert len(call(base, "/api/presets")[1]) == 14
    models = call(base, "/api/models")[1]
    assert {m["id"] for m in models["image"]} >= {"z-image-turbo"} and "latency_s" in models["chat"][0]
    assert [s["name"] for s in call(base, f"{p}/subjects?kind=asset")[1]] == ["Coffee cup", "Toothbrush"]
    subject = call(base, f"{p}/subjects/char_001")[1]
    assert subject["versions"][0]["version"] == 1 and subject["images"][0]["url"].startswith(
        f"/files/{store.id}/"
    )
    assert len(call(base, f"{p}/images")[1]) == 4
    assert call(base, f"{p}/images/img_0001")[1]["uses"] == ["subject char_001"]
    assert call(base, f"{p}/nope")[0] == 404


def test_writes_and_runs(served: tuple[hf.ProjectStore, str]) -> None:
    store, base = served
    p = f"/api/projects/{store.id}"
    scene = call(base, f"{p}/scenes", "POST", {"name": "Coffee", "refs": [{"subject_id": "char_001"}]})[1]
    request = {"kind": "scene", "scene_id": scene["id"], "selection": {"rounds": 1}}
    plan = call(base, f"{p}/plan", "POST", request)[1]
    assert plan["counts"]["images"] == 1 and plan["outputs"][0]["references"][0]["image_id"] == "img_0001"
    bad = call(
        base,
        f"{p}/runs",
        "POST",
        {"kind": "scene", "scene_id": scene["id"], "selection": {"auto_judge": False}},
    )
    assert bad[0] == 400 and any("automatic pick" in x for x in bad[1]["problems"])
    run = call(base, f"{p}/runs", "POST", request)[1]
    paused = call(base, f"/api/runs/{store.id}/{run['id']}/pause", "POST", {})[1]
    assert paused["status"] == "paused"
    assert call(base, f"/api/runs/{store.id}/{run['id']}/pause", "POST", {})[0] == 409
    call(base, f"/api/runs/{store.id}/{run['id']}/resume", "POST", {})
    run_all(store)
    page = call(base, f"/api/runs/{store.id}/{run['id']}?since=0")[1]
    assert page["run"]["status"] == "done" and page["activity"] and page["next"] > 0
    assert [s["name"] for s in page["stages"]] == ["planning", "generating", "judging", "selecting"]
    assert call(base, f"/api/runs/{store.id}/{run['id']}?since={page['next']}")[1]["activity"] == []
    image = page["run"]["outputs"][0]["candidates"][0]
    picked = call(base, f"/api/runs/{store.id}/{run['id']}/pick", "POST", {"output": "o01", "image": image})[
        1
    ]
    assert picked["manual"] is True
    sheet = call(base, f"{p}/sheets", "POST", {"recipe": {"name": "S", "images": ["img_0001", image]}})[1]
    status, png, headers = call(base, sheet["url"])
    assert status == 200 and png[:4] == b"\x89PNG" and headers["Content-Type"] == "image/png"
    export = call(base, f"{p}/exports", "POST", {"kind": "pack", "id": scene["id"]})[1]
    status, data, headers = call(base, export["url"])
    assert status == 200 and data[:2] == b"PK" and headers["Content-Type"] == "application/zip"


def test_files_are_confined(served: tuple[hf.ProjectStore, str]) -> None:
    store, base = served
    status, _, headers = call(base, f"/files/{store.id}/images/img_0001.png")
    assert status == 200 and headers["X-Content-Type-Options"] == "nosniff"
    assert "sandbox" in headers["Content-Security-Policy"]
    for path in (
        f"/files/{store.id}/project.json",
        f"/files/{store.id}/images/img_0001.json",
        "/files/../workspace.json",
        f"/files/{store.id}/images/%2e%2e/project.json",
        "/downloads/../workspace.json",
    ):
        assert call(base, path)[0] == 404, path
    (store.root / "images" / "evil.svg").write_text("<svg onload='alert(1)'/>")
    assert call(base, f"/files/{store.id}/images/evil.svg")[0] == 404


def test_empty_workspace_has_no_invented_numbers(tmp_path: Path) -> None:
    ws = hf.Workspace(tmp_path / "empty", models=FakeModels())
    store = ws.create_project("Empty")
    dashboard = Dashboard(ws, port=0, runner=False).start()
    try:
        data = call(dashboard.url.rstrip("/"), f"/api/projects/{store.id}/overview")[1]
    finally:
        dashboard.close()
    assert data["metrics"] == {
        "images_today": None,
        "queued": 0,
        "running": 0,
        "median_render_s": None,
        "gpu_s_today": None,
    }
    assert data["recent"] == [] and data["queue"] == []


def test_runner_thread_executes_the_queue(tmp_path: Path) -> None:
    store = sample_workspace(tmp_path / "ws", models=FakeModels())
    scene = store.save_scene(hf.Scene(name="S", refs=[hf.SceneRef(subject_id="char_001")]))
    run = store.submit(hf.SceneShot(scene_id=scene.id, selection=hf.Selection(rounds=1)))
    dashboard = Dashboard(store.workspace, port=0).start()
    try:
        import time

        deadline = time.monotonic() + 20
        while store.run_view(run.id).status != "done" and time.monotonic() < deadline:
            time.sleep(0.1)
    finally:
        dashboard.close()
    assert store.run_view(run.id).status == "done"


def test_run_page_of_a_just_submitted_run(served: tuple[hf.ProjectStore, str]) -> None:
    """Regression: the page the browser opens right after Generate (no stage yet) crashed the handler."""
    store, base = served
    scene = store.save_scene(hf.Scene(name="S", refs=[hf.SceneRef(subject_id="char_001")]))
    run = store.submit(hf.SceneShot(scene_id=scene.id))
    status, page, _ = call(base, f"/api/runs/{store.id}/{run.id}?since=0")
    assert status == 200 and page["run"]["status"] == "queued"
    assert [s["state"] for s in page["stages"]] == ["waiting"] * 4


def test_an_unexpected_error_is_a_json_500(
    served: tuple[hf.ProjectStore, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    import hone_frame._dashboard_work as work

    def broken(*_: Any, **__: Any) -> Any:
        raise ValueError("boom")

    monkeypatch.setattr(work, "run_page", broken)
    store, base = served
    status, body, _ = call(base, f"/api/runs/{store.id}/nope")
    assert status == 500 and body["error"] == "internal error: ValueError: boom"
