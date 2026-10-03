"""The project-file API routes (change 0004): import from text, write back."""

from pathlib import Path

import hone_frame as hf
from hone_frame._dashboard_api import route
from hone_frame.testing import FakeModels

FILE = Path(__file__).parents[2] / "examples" / "projects" / "rostam-and-sohrab.toml"


def test_the_dashboard_api_imports_and_writes_back(tmp_path: Path) -> None:
    ws = hf.Workspace(tmp_path / "ws", models=FakeModels())
    report = route(ws, "POST", "/import", {}, {"text": FILE.read_text(), "format": "toml"})
    assert report["project"] == "rostam-and-sohrab" and len(report["created"]) == 15
    data = route(ws, "GET", "/projects/rostam-and-sohrab/file", {}, None)
    assert [c["name"] for c in data["characters"]][:2] == ["Rostam", "Sohrab"]
    assert data["characters"][0]["belongings"][0]["name"] == "Rostam's mace"
