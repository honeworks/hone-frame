"""AC-18: saving a scene asks the planner which of the characters' own assets appear; a failing planner
suggests none (change 0003)."""

import hone_frame as hf
from hone_frame.characters import suggest_assets
from hone_frame.testing import FakeModels

from ._characters import rostam


def _scene(text: str) -> hf.Scene:
    return hf.Scene(name="Duel", description=text, refs=[hf.SceneRef(subject_id="char_001")])


def test_the_planner_suggests_what_the_scene_shows(ws: hf.Workspace, fake: FakeModels) -> None:
    p = rostam(ws)
    scene, _ = suggest_assets(p, _scene("Rostam raises his mace over his head"))
    assert [(r.subject_id, r.role, r.suggested) for r in scene.refs[1:]] == [("obj_001", "object", True)]
    assert "Mace" in fake.asked[-1].prompt
    calm, _ = suggest_assets(p, _scene("Rostam sleeps under a tree"))
    assert [r.subject_id for r in calm.refs] == ["char_001"]


def test_a_failing_planner_suggests_nothing(ws: hf.Workspace, fake: FakeModels) -> None:
    p = rostam(ws)
    fake.fail_ask(1)
    scene, why = suggest_assets(p, _scene("Rostam raises his mace"))
    assert [r.subject_id for r in scene.refs] == ["char_001"] and "could not suggest" in why
