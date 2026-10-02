"""AC-20: the dashboard API serves the project home and the character page, and its actions: generate
assets, regenerate a pack, add an item, choose a candidate on an accepted item (change 0003)."""

import json
import urllib.error
import urllib.request
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

import hone_frame as hf
from hone_frame.dashboard import Dashboard
from hone_frame.testing import FakeModels

from ._characters import rostam
from .conftest import run_all

ONE = {"rounds": 1, "candidates": 2}


@pytest.fixture
def served(tmp_path: Path) -> Iterator[tuple[hf.ProjectStore, str]]:
    store = rostam(hf.Workspace(tmp_path / "ws", models=FakeModels()))
    dashboard = Dashboard(store.workspace, port=0, runner=False).start()
    yield store, dashboard.url.rstrip("/") + "/api/projects/" + store.id
    dashboard.close()


def call(url: str, method: str = "GET", body: Any = None) -> tuple[int, Any]:
    data = json.dumps(body).encode() if body is not None else None
    request = urllib.request.Request(  # noqa: S310 - our own local test server
        url, data=data, method=method, headers={"Content-Type": "application/json"} if data else {}
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:  # noqa: S310 - http://127.0.0.1 only
            return response.status, json.loads(response.read())
    except urllib.error.HTTPError as error:
        return error.code, json.loads(error.read() or b"{}")


def _item(page: dict[str, Any], pack: str, item: str) -> dict[str, Any]:
    row = next(r for r in page["packs"] if r["id"] == pack)
    return next(i for i in row["items"] if i["item"] == item)


def test_home_and_character_page(served: tuple[hf.ProjectStore, str]) -> None:
    _, base = served
    status, home = call(base + "/home")
    assert status == 200 and [c["name"] for c in home["characters"]] == ["Rostam"]
    assert [w["name"] for w in home["world"]] == ["White Fortress"]
    status, page = call(base + "/characters/char_001")
    assert status == 200 and page["hero"] is None
    assert _item(page, "expressions", "Happy")["status"] == "not_made"
    status, runs = call(base + "/world/generate", "POST", {"selection": ONE})
    assert status == 200 and len(runs) == 1


def test_generate_regenerate_add_and_choose(served: tuple[hf.ProjectStore, str]) -> None:
    store, base = served
    status, run = call(
        base + "/characters/char_001/generate", "POST", {"packs": ["turnaround"], "selection": ONE}
    )
    assert status == 200, run
    run_all(store)
    _, page = call(base + "/characters/char_001")
    back = _item(page, "turnaround", "Back")
    assert page["hero"] is not None and back["image"] is not None and len(back["candidates"]) == 2
    other = next(c["id"] for c in back["candidates"] if c["id"] != back["selected"])
    status, _ = call(
        base.replace(f"/projects/{store.id}", f"/runs/{store.id}") + f"/{back['run']}/pick",
        "POST",
        {"output": back["output"], "image": other},
    )
    assert status == 200
    _, page = call(base + "/characters/char_001")
    assert _item(page, "turnaround", "Back")["image"]["id"] == other  # the person overrules the judge
    status, again = call(
        base + "/characters/char_001/generate",
        "POST",
        {"packs": ["outfits"], "custom": {"outfits": ["party clothing"]}, "selection": ONE},
    )
    assert status == 200 and again["outputs"] == 2  # Feast and the new item; no hero
    run_all(store)
    _, page = call(base + "/characters/char_001")
    assert _item(page, "outfits", "party clothing")["status"] == "done"
    status, sheet = call(base + "/characters/char_001/sheet", "POST", {})
    assert status == 200 and sheet["url"].endswith(".png")
    _, page = call(base + "/characters/char_001")
    assert page["sheet"]["recipe"]["layout"] == "character-model-sheet"


def test_scene_save_suggests_belongings(served: tuple[hf.ProjectStore, str]) -> None:
    _, base = served
    body = {"name": "Duel", "description": "Rostam swings his mace", "refs": [{"subject_id": "char_001"}]}
    status, scene = call(base + "/scenes", "POST", body | {"suggest": True})
    assert status == 200 and [r["subject_id"] for r in scene["refs"]] == ["char_001", "obj_001"]
    assert scene["refs"][1]["suggested"] is True
