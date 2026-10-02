"""AC-11: technical retries are bounded, visible and separate from creative rounds (design §8.4)."""

import json
from pathlib import Path

import hone_frame as hf
from hone_frame.events import read_events
from hone_frame.testing import FakeModels

from .conftest import run_all


def _one(ws: hf.Workspace, **selection: object) -> tuple[hf.ProjectStore, str]:
    p = ws.create_project("P")
    woman = p.add_subject("character", "Woman", description="black hair")
    sel = hf.Selection.model_validate({"rounds": 1, **selection})
    return p, p.submit(
        hf.SubjectReferences(subject_id=woman.id, presentation="neutral-full-body", selection=sel)
    ).id


def _events(p: hf.ProjectStore, run_id: str, name: str) -> list[dict[str, object]]:
    return [e for e in read_events(p.root / "runs" / run_id / "events.jsonl") if e["event"] == name]


def test_transient_failures_then_success(ws: hf.Workspace, fake: FakeModels) -> None:
    p, run = _one(ws)
    fake.fail_generate("transient", times=2)
    run_all(p)
    view = p.run_view(run)
    assert view.status == "done"
    assert len(_events(p, run, "retry")) == 2 and view.outputs[0].retries == 2
    assert len(view.outputs[0].candidates) == 1  # no extra round
    assert view.usage["retries"] == 2


def test_out_of_retries_fails_only_that_output(tmp_path: Path) -> None:
    fake = FakeModels()
    ws = hf.Workspace(tmp_path, models=fake)
    p = ws.create_project("P")
    a = p.add_subject("character", "A", description="a")
    b = p.add_subject("character", "B", description="b")
    sel = hf.Selection(rounds=1, technical_retries=1)
    first = p.submit(hf.SubjectReferences(subject_id=a.id, presentation="neutral-full-body", selection=sel))
    second = p.submit(hf.SubjectReferences(subject_id=b.id, presentation="neutral-full-body", selection=sel))
    fake.fail_generate("out_of_memory", times=2)
    run_all(p)
    failed = p.run_view(first.id)
    assert failed.status == "failed" and failed.outputs[0].status == "failed"
    assert "out_of_memory" in (failed.outputs[0].error or "")
    assert p.run_view(second.id).status == "done"
    p.retry(first.id)
    run_all(p)
    assert p.run_view(first.id).status == "done"


def test_refused_is_not_retried(ws: hf.Workspace, fake: FakeModels) -> None:
    p, run = _one(ws, candidates=2)
    fake.fail_generate("refused", times=1)
    run_all(p)
    view = p.run_view(run)
    assert _events(p, run, "retry") == []
    assert len(_events(p, run, "candidate_failed")) == 1
    assert len(view.outputs[0].candidates) == 1 and view.status == "done"


def test_a_failing_judge_blocks_the_auto_pick(ws: hf.Workspace, fake: FakeModels) -> None:
    p, run = _one(ws, technical_retries=0)
    fake.fail_ask(times=2)  # the planner call, then the judge call
    run_all(p)
    view = p.run_view(run)
    assert len(_events(p, run, "judge_failed")) == 1 and len(_events(p, run, "planner_failed")) == 1
    assert view.outputs[0].status == "needs_review"
    assert "no candidate has an evaluation" in view.outputs[0].reason
    assert json.loads((p.root / "images" / "img_0001.json").read_text())["evaluation"] is None


class NoInfo(FakeModels):
    broken = False  # the registry breaks after the plan was made

    def info(self, model_id: str) -> hf.ModelInfo:
        if self.broken and model_id == "z-image-turbo":
            raise hf.ModelFailure("the registry could not be read", transient=False)
        return super().info(model_id)


def test_model_info_unavailable_is_recorded(tmp_path: Path) -> None:
    fake = NoInfo()
    ws = hf.Workspace(tmp_path, models=fake)
    p, run = _one(ws)
    fake.broken = True
    run_all(p)
    events = _events(p, run, "model_info_unavailable")
    assert len(events) == 1 and "registry could not be read" in str(events[0]["message"])
    view = p.run_view(run)
    assert view.status == "done"
    assert "Z-Image Turbo" in next(c.prompt for c in fake.asked if "write the prompt" in c.prompt)
    assert all("local" not in e for e in _events(p, run, "generated")) and view.usage["gpu_s"] is None
