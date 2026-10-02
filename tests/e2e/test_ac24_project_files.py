"""AC-24: a project file creates a project with its characters, belongings, world and scenes; imported
again after an edit it versions only what changed; bad files are refused with the place of the error
(change 0004)."""

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

import hone_frame as hf
from hone_frame._dashboard_api import route
from hone_frame.cli import app
from hone_frame.errors import InvalidRequest
from hone_frame.project_file import import_file, import_path, parse, project_file

from .conftest import FILE


def test_import_creates_everything(ws: hf.Workspace) -> None:
    report = import_path(ws, FILE)
    p = ws.project(report.project)
    assert [s.name for s in p.subjects("character")] == ["Rostam", "Sohrab", "Tahmineh", "Gordafarid"]
    rostam = p.subjects("character")[0]
    assert rostam.fields["proportions"].startswith("enormous") and rostam.fields["outfits"].startswith(
        "tiger"
    )
    assert [s.name for s in p.subjects("asset") if s.owner == rostam.id] == [
        "Rostam's mace",
        "Rostam's lasso",
    ]
    assert [s.name for s in p.subjects("asset") if s.owner is None] == ["Rakhsh"]
    duel = next(s for s in p.scenes() if s.name == "Duel")
    roles = {(p.subject(r.subject_id).name, r.role) for r in duel.refs}
    assert ("Battle plain", "environment") in roles and ("Rostam's mace", "object") in roles
    assert p.info.style_pack == "historical-epic"


def test_import_again_versions_only_what_changed(ws: hf.Workspace) -> None:
    store = ws.project(import_path(ws, FILE).project)
    data = project_file(store)
    assert import_file(ws, parse(json.dumps(data), "json")).updated == []  # a round trip changes nothing
    data["characters"][1]["build"] = "very tall"
    data["scenes"][0]["description"] = "a new description"
    again = import_file(ws, parse(json.dumps(data), "json"))
    assert again.updated == ["character Sohrab", "scene Duel"] and not again.created
    sohrab = store.subjects("character")[1]
    assert sohrab.version == 2 and store.subject(sohrab.id, 1).fields["proportions"].startswith(
        "very tall and"
    )


@pytest.mark.parametrize(
    ("text", "message"),
    [
        ("[project\n", "not valid TOML"),
        ('[project]\nname = "x"\n[[characters]]\nname = "A"\nhieght = "tall"\n', "characters.0.hieght"),
        ('[project]\nname = "x"\n[[characters]]\nname = "A"\n[[places]]\nname = "A"\n', "repeated"),
        ('[project]\nname = "x"\n[[scenes]]\nname = "S"\ncharacters = ["Nobody"]\n', "'Nobody'"),
        ('format_version = "2"\n[project]\nname = "x"\n', "format_version"),
    ],
)
def test_bad_files_say_where(ws: hf.Workspace, text: str, message: str) -> None:
    with pytest.raises(InvalidRequest) as error:
        import_file(ws, parse(text, "toml"))
    assert message in str(error.value) + " ".join(error.value.problems)


def test_the_cli_and_the_api_import(ws: hf.Workspace, tmp_path: Path) -> None:

    result = CliRunner().invoke(app, ["import", str(FILE), "--home", str(ws.root)])
    assert result.exit_code == 0 and "rostam-and-sohrab" in result.output
    out = tmp_path / "back.json"
    assert (
        CliRunner()
        .invoke(app, ["export-file", "rostam-and-sohrab", str(out), "--home", str(ws.root)])
        .exit_code
        == 0
    )
    assert json.loads(out.read_text())["project"]["name"] == "Rostam and Sohrab"


def test_the_dashboard_api_imports_and_writes_back(ws: hf.Workspace) -> None:
    report = route(ws, "POST", "/import", {}, {"text": FILE.read_text(), "format": "toml"})
    assert report["project"] == "rostam-and-sohrab" and len(report["created"]) == 15
    data = route(ws, "GET", "/projects/rostam-and-sohrab/file", {}, None)
    assert [c["name"] for c in data["characters"]][:2] == ["Rostam", "Sohrab"]
    assert data["characters"][0]["belongings"][0]["name"] == "Rostam's mace"
