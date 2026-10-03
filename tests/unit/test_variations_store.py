"""Variations and the new stored fields (change 0005): they survive reopening the workspace, a project
from before has one `main` variation, and bad input is refused with what to do."""

import json
from pathlib import Path

import pytest

import hone_frame as hf
from hone_frame._dashboard_api import route
from hone_frame.errors import InvalidRequest, NotFound
from hone_frame.testing import FakeModels

FILE = Path(__file__).parents[2] / "examples" / "projects" / "rostam-and-sohrab.toml"


def test_new_fields_survive_reopening(tmp_path: Path) -> None:
    ws = hf.Workspace(tmp_path / "ws", models=FakeModels())
    p = ws.create_project("World", style_pack="historical-epic")
    p.update(look="lamellar coats")
    v = p.add_variation("Flat", style_pack="clean-2d-animation", direction="thick lines")
    who = p.add_subject("character", "A", must=["an armlet"], never=["a cape"])
    again = hf.Workspace(tmp_path / "ws", models=FakeModels()).project(p.id)
    info = again.info
    assert info.look == "lamellar coats" and info.variation == v.id
    assert [x.id for x in info.all_variations()] == ["main", v.id]
    assert info.variation_of(v.id).direction == "thick lines"
    assert (again.subject(who.id).must, again.subject(who.id).never) == (["an armlet"], ["a cape"])


def test_a_project_from_before_has_one_main_variation(tmp_path: Path) -> None:
    ws = hf.Workspace(tmp_path / "ws", models=FakeModels())
    p = ws.create_project("Old", style_pack="inked-comic")
    data = json.loads((p.root / "project.json").read_text())
    for key in ("look", "variations", "variation"):
        data.pop(key)
    data["direction"] = "bold ink"
    (p.root / "project.json").write_text(json.dumps(data))
    old = hf.Workspace(tmp_path / "ws", models=FakeModels()).project(p.id)
    assert [(v.id, v.style_pack) for v in old.info.all_variations()] == [("main", "inked-comic")]
    assert old.info.look_guide == "bold ink"
    image = old.import_image(_png(tmp_path))
    assert old.images(variation="main") == [old.image(image.id)]  # no variation: the first one


def test_bad_variations_are_refused(tmp_path: Path) -> None:
    p = hf.Workspace(tmp_path / "ws", models=FakeModels()).create_project("W")
    with pytest.raises(InvalidRequest, match="needs a name"):
        p.add_variation(" ", style_pack="clean-2d-animation")
    with pytest.raises(NotFound):
        p.add_variation("X", style_pack="oil-paint")
    v = p.add_variation("X", style_pack="clean-2d-animation")
    with pytest.raises(InvalidRequest, match="cannot change \\['id'\\]"):
        p.edit_variation(v.id, id="y")
    with pytest.raises(InvalidRequest, match="needs a name"):
        p.edit_variation(v.id, name="")
    with pytest.raises(NotFound, match="no variation 'nope'"):
        p.edit_variation("nope", name="Z")
    with pytest.raises(NotFound, match="no variation 'nope'"):
        p.use_variation("nope")


def test_project_files_carry_look_variations_must_never(tmp_path: Path) -> None:
    ws = hf.Workspace(tmp_path / "ws", models=FakeModels())
    data = {
        "project": {"name": "W", "style": "historical-epic", "look": "lamellar coats",
                    "variations": [{"name": "Flat", "style": "clean-2d-animation", "direction": "thick"}]},
        "characters": [{"name": "A", "must": ["an armlet"], "never": ["a cape"]}],
    }  # fmt: skip
    path = tmp_path / "w.json"
    path.write_text(json.dumps(data))
    p = ws.project(ws.import_file(path).project)
    assert p.info.look == "lamellar coats" and [v.name for v in p.info.all_variations()] == ["Flat"]
    back = p.project_file()
    assert back["project"]["look"] == "lamellar coats" and back["characters"][0]["never"] == ["a cape"]
    path.write_text(json.dumps(back))
    report = ws.import_file(path)
    assert not report.created and not report.updated  # a round trip changes nothing
    assert [v.name for v in p.info.all_variations()].count("Flat") == 1
    data["project"]["variations"][0]["style"] = "oil-paint"
    path.write_text(json.dumps(data))
    with pytest.raises(InvalidRequest, match="not a style pack"):
        ws.import_file(path)
    data["project"]["variations"] = []
    data["project"]["style"] = "inked-comic"
    path.write_text(json.dumps(data))
    ws.import_file(path)
    assert p.info.all_variations()[0].style_pack == "inked-comic"  # the first variation's style


def test_dashboard_variation_and_world_routes(tmp_path: Path) -> None:
    ws = hf.Workspace(tmp_path / "ws", models=FakeModels())
    pid = ws.import_file(FILE).project
    listed = route(
        ws, "POST", f"/projects/{pid}/variations", {}, {"name": "Flat", "style_pack": "clean-2d-animation"}
    )
    assert listed["active"] == "flat" and len(listed["variations"]) == 2
    assert route(ws, "POST", f"/projects/{pid}/variations/main/use", {}, {})["active"] == "main"
    assert (
        route(ws, "PATCH", f"/projects/{pid}/variations/flat", {}, {"name": "Flat 2D"})["variations"][1][
            "name"
        ]
        == "Flat 2D"
    )
    plan = route(ws, "POST", f"/projects/{pid}/world/plan", {}, {"rounds": 1})
    assert plan["images"] > 0 and len(plan["scene_runs"]) == 2
    rows = route(ws, "GET", f"/projects/{pid}/subjects/char_001/compare", {}, None)
    assert [r["variation"]["name"] for r in rows] == ["Historical epic", "Flat 2D"] and rows[0][
        "hero"
    ] is None
    started = route(ws, "POST", f"/projects/{pid}/world/generate-all", {}, {"rounds": 1})
    assert len(started["runs"]) == 8
    obj = route(ws, "GET", f"/projects/{pid}/objects/obj_005", {}, None)
    assert [i["item"] for i in obj["items"]] == ["Hero", "Front", "Side", "Back", "Top", "Detail"]


def _png(tmp_path: Path) -> Path:
    from PIL import Image

    path = tmp_path / "x.png"
    Image.new("RGB", (8, 8), "white").save(path)
    return path


def test_scene_rows_keep_real_plan_errors_only(tmp_path: Path) -> None:
    ws = hf.Workspace(tmp_path / "ws", models=FakeModels())
    p = ws.project(ws.import_file(FILE).project)
    rows = p.world_plan()["scene_runs"]
    assert rows and all(r["errors"] == [] for r in rows)  # only missing heroes: they come first
    duel = next(s for s in p.scenes() if s.name == "Duel")
    place = next(r.subject_id for r in duel.refs if r.role == "environment")
    (p.root / "subjects" / f"{place}.json").unlink()  # its place is gone: a real plan error
    duel_row = next(r for r in p.world_plan()["scene_runs"] if place in " ".join(r["errors"]))
    assert duel_row["images"] == 0


def test_a_new_project_from_a_file_starts_with_its_first_variation(tmp_path: Path) -> None:
    ws = hf.Workspace(tmp_path / "ws", models=FakeModels())
    data = {"project": {"name": "W", "variations": [
        {"name": "Realistic", "style": "historical-epic", "direction": "warm"},
        {"name": "Flat", "style": "clean-2d-animation"}]}}  # fmt: skip
    path = tmp_path / "w.json"
    path.write_text(json.dumps(data))
    p = ws.project(ws.import_file(path).project)
    assert [(v.id, v.name, v.style_pack) for v in p.info.all_variations()] == [
        ("main", "Realistic", "historical-epic"),
        ("flat", "Flat", "clean-2d-animation"),
    ]
    assert not ws.import_file(path).updated  # importing again adds nothing


def test_a_bad_first_variation_style_creates_nothing(tmp_path: Path) -> None:
    ws = hf.Workspace(tmp_path / "ws", models=FakeModels())
    path = tmp_path / "w.json"
    path.write_text(json.dumps({"project": {"name": "W", "variations": [{"name": "A", "style": "nope"}]}}))
    with pytest.raises(InvalidRequest, match="variation style 'nope' is not a style pack"):
        ws.import_file(path)
    assert ws.projects() == []
