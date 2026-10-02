"""AC-8: pause, cancel, resume, restart after a crash, progress and estimates (design §9)."""

import os
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import pytest

import hone_frame as hf
from hone_frame.testing import FakeModels, judge_answer

from .conftest import run_all


def _woman(ws: hf.Workspace) -> tuple[hf.ProjectStore, str]:
    p = ws.create_project("Morning at home")
    return p, p.add_subject("character", "Woman", description="black hair in a bun").id


def _pause_on_judge(store_ref: dict[str, Any], at: int, action: str = "pause") -> FakeModels:
    def judge(i: int, prompt: str, _images: list[Path]) -> dict[str, Any]:
        if i == at:
            getattr(store_ref["p"], action)(store_ref["run"])
        return judge_answer(prompt)

    return FakeModels(judge=judge)


def test_pause_then_resume_regenerates_nothing(tmp_path: Path) -> None:
    ref: dict[str, Any] = {}
    fake = _pause_on_judge(ref, at=4)  # during round 2 of the second output
    ws = hf.Workspace(tmp_path, models=fake)
    p, woman = _woman(ws)
    run = p.submit(hf.SubjectReferences(subject_id=woman, presentation="turnaround"))
    ref.update(p=p, run=run.id)
    run_all(p)
    paused = p.run_view(run.id)
    assert paused.status == "paused"
    assert fake.image_calls == 5  # the call in flight finished, then it stopped
    assert {o.status for o in paused.outputs[1:]} == {"paused"}
    with pytest.raises(hf.errors.RunStateError):
        p.pause(run.id)
    assert p.resume(run.id).status == "queued"
    run_all(p)
    done = p.run_view(run.id)
    assert done.status == "done"
    assert fake.image_calls == 15 == len(p.images())
    keys = [(i.output_id, i.round, i.candidate) for i in p.images()]
    assert len(keys) == len(set(keys))


def test_cancel_cannot_resume(tmp_path: Path) -> None:
    ref: dict[str, Any] = {}
    ws = hf.Workspace(tmp_path, models=_pause_on_judge(ref, at=0, action="cancel"))
    p, woman = _woman(ws)
    run = p.submit(hf.SubjectReferences(subject_id=woman, presentation="turnaround"))
    ref.update(p=p, run=run.id)
    run_all(p)
    assert p.run_view(run.id).status == "canceled"
    with pytest.raises(hf.errors.RunStateError, match="rerun"):
        p.resume(run.id)


def test_pause_a_queued_run(ws: hf.Workspace, fake: FakeModels) -> None:
    p, woman = _woman(ws)
    run = p.submit(hf.SubjectReferences(subject_id=woman, presentation="neutral-full-body"))
    assert p.pause(run.id).status == "paused"
    assert hf.Runner(ws).run_next() is None and fake.image_calls == 0
    p.resume(run.id)
    run_all(p)
    assert p.run_view(run.id).status == "done"


CHILD = """
import sys
import hone_frame as hf
from hone_frame.testing import FakeModels
ws = hf.Workspace(sys.argv[1], models=FakeModels(delay_s=0.4))
hf.Runner(ws).run_next()
"""


def test_restart_after_a_killed_process(tmp_path: Path) -> None:
    ws = hf.Workspace(tmp_path / "ws", models=FakeModels())
    p, woman = _woman(ws)
    run = p.submit(hf.SubjectReferences(subject_id=woman, presentation="turnaround"))
    child = subprocess.Popen([sys.executable, "-c", CHILD, str(ws.root)])
    deadline = time.monotonic() + 30
    while len(p.images()) < 4 and time.monotonic() < deadline:
        time.sleep(0.05)
    os.kill(child.pid, signal.SIGKILL)
    child.wait()
    before = len(p.images())
    assert 4 <= before < 15
    assert p.run_view(run.id).status == "paused"  # interrupted
    assert "interrupted" in p.run_view(run.id).reason
    fake = FakeModels()
    again = hf.Workspace(tmp_path / "ws", models=fake)
    assert hf.Runner(again).recover() == [run.id]
    run_all(again.project(p.id))
    view = again.project(p.id).run_view(run.id)
    assert view.status == "done"
    assert len(p.images()) == 15 and fake.image_calls == 15 - before
    keys = [(i.output_id, i.round, i.candidate) for i in p.images()]
    assert len(keys) == len(set(keys))


def test_estimates_need_evidence(ws: hf.Workspace) -> None:
    p, woman = _woman(ws)
    req = hf.SubjectReferences(subject_id=woman, presentation="neutral-full-body")
    assert p.plan(req).estimate is None  # "Estimating"
    p.submit(req)
    run_all(p)
    other = p.add_subject("character", "Neighbour", description="grey beard")
    estimate = p.plan(hf.SubjectReferences(subject_id=other.id, presentation="neutral-full-body")).estimate
    assert estimate is not None
    assert 0 < estimate["low_s"] <= estimate["high_s"]
    bigger = p.plan(hf.SubjectReferences(subject_id=other.id, presentation="turnaround")).estimate
    assert bigger is None  # the editor model has no observations yet


def test_progress_while_running(tmp_path: Path) -> None:
    seen: list[dict[str, Any]] = []
    ref: dict[str, Any] = {}

    def judge(i: int, prompt: str, _images: list[Path]) -> dict[str, Any]:
        seen.append(ref["p"].run_view(ref["run"]).model_dump())
        return judge_answer(prompt)

    ws = hf.Workspace(tmp_path, models=FakeModels(judge=judge))
    p, woman = _woman(ws)
    run = p.submit(hf.SubjectReferences(subject_id=woman, presentation="neutral-full-body"))
    ref.update(p=p, run=run.id)
    run_all(p)
    assert [s["status"] for s in seen] == ["running"] * 3
    assert [s["progress"]["done"] for s in seen] == [1, 3, 5]
    assert seen[0]["progress"]["planned"] == 6 and seen[0]["progress"]["current"] == "indeterminate"
    assert seen[1]["stage"] == "judging" and seen[1]["current"]["round"] == 2
