"""The judge is told what was asked, from the plan; back views have their own check and other views
carry no back-view wording; the anatomy check names hands and feet (change 0004; AC-22 checks a run)."""

from pathlib import Path

import pytest

import hone_frame as hf
from hone_frame.judging import CheckAnswer, answer_schema, checks_for, judge_prompt
from hone_frame.project_file import import_path
from hone_frame.testing import FakeModels

FILE = Path(__file__).parents[2] / "examples" / "projects" / "rostam-and-sohrab.toml"


@pytest.fixture(scope="module")
def rostam_project(tmp_path_factory: pytest.TempPathFactory) -> hf.ProjectStore:
    """The realistic project of examples/projects/rostam-and-sohrab.toml."""
    ws = hf.Workspace(tmp_path_factory.mktemp("matrix") / "ws", models=FakeModels())
    return ws.project(import_path(ws, FILE).project)


def test_the_judge_is_told_what_was_asked(rostam_project: hf.ProjectStore) -> None:
    rostam = rostam_project.subjects("character")[0]
    plan = rostam_project.plan(hf.CharacterPacks(subject_id=rostam.id, packs=["poses", "turnaround"]))
    running = next(o for o in plan.outputs if o.item == "Running")
    prompt = judge_prompt(running, checks_for(rostam_project.workspace.presets, running), "a man standing", 1)
    assert "Requested pose: running fast, leaning forward" in prompt and "Requested background:" in prompt
    assert "Requested: empty hands" in prompt
    back = next(o for o in plan.outputs if o.item == "Back")
    names = [c["name"] for c in checks_for(rostam_project.workspace.presets, back)]
    assert "faces_away" in names and "identity_from_behind" in names
    side = next(o for o in plan.outputs if o.item == "Side")
    side_checks = checks_for(rostam_project.workspace.presets, side)
    assert "faces_away" not in [c["name"] for c in side_checks]
    assert all(
        "rear view" not in c["question"].lower() for c in side_checks
    )  # no back-view talk on a side view
    anatomy = next(c for c in side_checks if c["name"] == "anatomy")
    assert "foot" in anatomy["question"] and "same way as the face" in anatomy["question"]


def test_the_judge_writes_its_finding_before_its_verdict() -> None:
    schema = CheckAnswer.model_json_schema()
    assert list(schema["properties"])[:2] == ["finding", "verdict"] and schema["required"] == [
        "finding",
        "verdict",
    ]
    assert CheckAnswer.model_validate({"verdict": "pass"}).finding == ""  # read back leniently
    sent = answer_schema([{"name": "pose"}]).model_json_schema()
    assert "finding" in str(sent)


def test_object_alone_is_judged_for_objects_only(rostam_project: hf.ProjectStore) -> None:
    from hone_frame.judging import evaluate
    from hone_frame.testing import judge_answer

    plan = rostam_project.plan(hf.CharacterPacks(subject_id="char_001", packs=["actions"]))
    obj = next(o for o in plan.outputs if o.kind == "asset")
    character = next(o for o in plan.outputs if o.kind == "character")
    catalog = rostam_project.workspace.presets
    assert "object_alone" in [c["name"] for c in checks_for(catalog, obj)]
    assert "object_alone" not in [c["name"] for c in checks_for(catalog, character)]
    fails = FakeModels(judge=lambda _i, prompt, _im: judge_answer(prompt, fail=("object_alone",)))
    evaluation = evaluate(fails, judge="qwen2.5vl-7b", think=False, out=obj, checks=checks_for(catalog, obj),
                          candidate=Path(__file__), references=[], prompt="a spear")  # fmt: skip
    assert not evaluation.passed and any(
        c.name == "object_alone" and c.verdict == "fail" for c in evaluation.checks
    )
