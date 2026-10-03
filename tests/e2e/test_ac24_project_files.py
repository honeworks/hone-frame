"""AC-24: a project file creates a project with its characters, belongings, world and scenes; imported
again after an edit it versions only what changed and keeps what the file leaves out; bad files are
refused with the place of the error (change 0004)."""

import json
from collections.abc import Mapping
from pathlib import Path

import pytest
from typer.testing import CliRunner

import hone_frame as hf
from hone_frame.cli import app
from hone_frame.errors import InvalidRequest

from .conftest import FILE


def test_import_creates_everything(ws: hf.Workspace) -> None:
    p = ws.project(ws.import_file(FILE).project)
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


def _write(tmp_path: Path, data: Mapping[str, object]) -> Path:
    path = tmp_path / "project.json"
    path.write_text(json.dumps(data))
    return path


def test_import_again_versions_only_what_changed(ws: hf.Workspace, tmp_path: Path) -> None:
    store = ws.project(ws.import_file(FILE).project)
    data = store.project_file()
    assert ws.import_file(_write(tmp_path, data)).updated == []  # a round trip changes nothing
    data["characters"][1]["build"] = "very tall"
    data["scenes"][0]["description"] = "a new description"
    again = ws.import_file(_write(tmp_path, data))
    assert again.updated == ["character Sohrab", "scene Duel"] and not again.created
    sohrab = store.subjects("character")[1]
    assert sohrab.version == 2 and store.subject(sohrab.id, 1).fields["proportions"].startswith(
        "very tall and"
    )


def test_what_the_file_leaves_out_is_kept(ws: hf.Workspace, tmp_path: Path) -> None:
    store = ws.project(ws.import_file(FILE).project)
    rostam = store.subjects("character")[0]
    store.edit_subject(rostam.id, fields=rostam.fields | {"voice": "deep"})
    duel = next(s for s in store.scenes() if s.name == "Duel")
    store.save_scene(duel.model_copy(update={"gaze": "eyes locked", "notes": "dust"}))
    store.update(brief="kept brief")
    small = {"project": {"name": "Rostam and Sohrab"},
             "characters": [{"name": "Rostam", "build": "colossal"}],
             "scenes": [{"name": "Duel", "description": "they fight"}]}  # fmt: skip
    report = ws.import_file(_write(tmp_path, small))
    assert report.updated == ["character Rostam", "scene Duel"]
    after = store.subject(rostam.id)
    assert after.fields["voice"] == "deep" and after.fields["proportions"] == "colossal"
    assert after.description == rostam.description and len(after.states) == 3
    duel = next(s for s in store.scenes() if s.name == "Duel")
    assert (duel.gaze, duel.notes, duel.description, len(duel.refs)) == (
        "eyes locked",
        "dust",
        "they fight",
        6,
    )
    assert store.info.brief == "kept brief" and store.info.style_pack == "historical-epic"


@pytest.mark.parametrize(
    ("text", "suffix", "message"),
    [
        ("[project\n", "toml", "not valid TOML"),
        (
            '[project]\nname = "x"\n[[characters]]\nname = "A"\nhieght = "tall"\n',
            "toml",
            "characters.0.hieght",
        ),
        ('[project]\nname = "x"\n[[characters]]\nname = "A"\n[[places]]\nname = "A"\n', "toml", "repeated"),
        ('[project]\nname = "x"\n[[scenes]]\nname = "S"\ncharacters = ["Nobody"]\n', "toml", "'Nobody'"),
        ('format_version = "2"\n[project]\nname = "x"\n', "toml", "format_version"),
        ('[project]\nname = "x"\nstyle = "oil-paint"\n', "toml", "not a style pack"),
        ("{}", "yaml", "ends in .toml or .json"),
    ],
)
def test_bad_files_say_where(ws: hf.Workspace, tmp_path: Path, text: str, suffix: str, message: str) -> None:
    path = tmp_path / f"bad.{suffix}"
    path.write_text(text)
    with pytest.raises(InvalidRequest) as error:
        ws.import_file(path)
    assert message in str(error.value) + " ".join(error.value.problems)
    with pytest.raises(InvalidRequest, match="cannot read"):
        ws.import_file(tmp_path / "missing.toml")


def test_the_cli_imports_and_writes_back(ws: hf.Workspace, tmp_path: Path) -> None:
    result = CliRunner().invoke(app, ["import", str(FILE), "--home", str(ws.root)])
    assert result.exit_code == 0 and "rostam-and-sohrab" in result.output
    out = tmp_path / "back.json"
    written = CliRunner().invoke(app, ["export-file", "rostam-and-sohrab", str(out), "--home", str(ws.root)])
    assert written.exit_code == 0 and json.loads(out.read_text())["project"]["name"] == "Rostam and Sohrab"


def test_scene_references_from_a_file_keep_the_suggested_ones(ws: hf.Workspace, tmp_path: Path) -> None:
    store = ws.project(ws.import_file(FILE).project)
    duel = next(s for s in store.scenes() if s.name == "Duel")
    lasso = next(s for s in store.subjects("asset") if s.name == "Rostam's lasso")
    store.save_scene(
        duel.model_copy(
            update={"refs": [*duel.refs, hf.SceneRef(subject_id=lasso.id, role="object", suggested=True)]}
        )
    )
    same = {"project": {"name": "Rostam and Sohrab"}, "scenes": [store.project_file()["scenes"][0]]}
    same["scenes"][0]["objects"] = ["Rakhsh", "Rostam's mace", "Sohrab's spear"]  # as in the file
    assert ws.import_file(_write(tmp_path, same)).unchanged == ["scene Duel"]
    same["scenes"][0]["objects"] = ["Rakhsh"]  # the file drops two objects
    assert ws.import_file(_write(tmp_path, same)).updated == ["scene Duel"]
    duel = next(s for s in store.scenes() if s.name == "Duel")
    names = [(store.subject(r.subject_id).name, r.suggested) for r in duel.refs]
    assert ("Rostam's mace", False) not in names and ("Rakhsh", False) in names
    assert ("Rostam's lasso", True) in names  # the planner's suggestion survives


def test_an_explicit_style_changes_the_project(ws: hf.Workspace, tmp_path: Path) -> None:
    store = ws.project(ws.import_file(FILE).project)
    data = {"project": {"name": "Rostam and Sohrab", "style": "clean-2d-animation"}}
    assert ws.import_file(_write(tmp_path, data)).project == store.id
    assert store.info.style_pack == "clean-2d-animation" and store.info.brief.startswith("The tragedy")
