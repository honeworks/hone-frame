"""AC-9: unresolved quality failures stay visible; dependent work waits, unrelated work continues."""

from pathlib import Path
from typing import Any

import pytest

import hone_frame as hf
from hone_frame.testing import FakeModels, judge_answer

from .conftest import run_all


def _fail_label(label: str) -> FakeModels:
    def judge(_i: int, prompt: str, _images: list[Path]) -> dict[str, Any]:
        failing = f"to show: {label} " in prompt
        return judge_answer(prompt, fail=("view",) if failing else (), overall=0.7)

    return FakeModels(judge=judge)


def test_one_output_never_passes(tmp_path: Path) -> None:
    ws = hf.Workspace(tmp_path, models=_fail_label("Side"))
    p = ws.create_project("P")
    woman = p.add_subject("character", "Woman", description="black hair")
    run = p.submit(hf.SubjectReferences(subject_id=woman.id, presentation="turnaround"))
    run_all(p)
    view = p.run_view(run.id)
    assert view.status == "needs_review"
    assert view.accepted == ["o01", "o02", "o03", "o05"] and view.unresolved == ["o04"]
    side = view.outputs[3]
    assert side.selected is None and side.best_available in side.candidates
    assert p.image(side.best_available or "").status == "best_available"
    assert not any(p.image(c).status in ("picked", "manual_pick") for c in side.candidates)


def test_waiting_for_a_hero_while_others_continue(tmp_path: Path) -> None:
    ws = hf.Workspace(tmp_path, models=_fail_label("Hero"))
    p = ws.create_project("P")
    woman = p.add_subject("character", "Woman", description="black hair")
    cup = p.add_subject("asset", "Cup", description="mug")
    run_w = p.submit(hf.SubjectReferences(subject_id=woman.id, presentation="turnaround"))
    run_c = p.submit(hf.SubjectReferences(subject_id=cup.id, presentation="isolated-studio"))
    run_all(p)
    view = p.run_view(run_w.id)
    assert view.status == "needs_review"
    assert [o.status for o in view.outputs] == ["needs_review", "waiting", "waiting", "waiting", "waiting"]
    assert "waiting for an accepted Hero" in view.outputs[1].reason
    assert p.run_view(run_c.id).status == "done"  # unrelated work completed (an object has no "view" check)

    hero = view.outputs[0]
    failing = p.image(hero.candidates[0])
    record = p.pick(run_w.id, "o01", failing.id, note="good enough for the views")
    assert record.status == "done" and record.manual and record.manual_note == "good enough for the views"
    picked = p.image(failing.id)
    assert picked.status == "manual_pick"
    assert picked.evaluation is not None and not picked.evaluation.passed  # the findings stay
    p.retry(run_w.id)
    run_all(p)
    final = p.run_view(run_w.id)
    assert [o.status for o in final.outputs[1:]] == ["done"] * 4
    assert final.status == "done"


def test_redo_one_output_with_a_note_and_another_profile(tmp_path: Path) -> None:
    fake = _fail_label("Back")
    ws = hf.Workspace(tmp_path, models=fake)
    p = ws.create_project("P")
    woman = p.add_subject("character", "Woman", description="black hair")
    run = p.submit(hf.SubjectReferences(subject_id=woman.id, presentation="turnaround"))
    run_all(p)
    back = p.run_view(run.id).outputs[4]
    assert back.label == "Back" and back.status == "needs_review"
    redo = p.rerun(
        run.id,
        back.id,
        note="seen from directly behind, no face visible",
        profile="final",
        selection=hf.Selection(rounds=2),
    )
    old = p.run_view(run.id)
    assert old.status == "done" and old.outputs[4].status == "replaced" and old.unresolved == []
    assert old.outputs[4].replaced_by == {"run": redo.id, "output": back.id}
    assert old.outputs[4].candidates == back.candidates  # the rejected images and their findings stay
    assert redo.selection["rounds"] == 2 and redo.profile["id"] == "final"
    fake.judge = lambda _i, prompt, _images: judge_answer(prompt)  # the new attempt passes
    run_all(p)
    again = p.run_view(redo.id)
    assert again.status == "done" and len(again.outputs[0].candidates) == 2
    sent = fake.generated[-1]
    assert sent.model == "qwen-image-edit-2511" and "no face visible" in sent.prompt
    assert [r.name for r in sent.references] == [p.image_path(old.outputs[0].selected or "").name]


def test_redo_errors(tmp_path: Path) -> None:
    from hone_frame.ports import ModelInfo

    no_final = FakeModels(
        infos={
            "qwen-image-edit-2511": ModelInfo(
                id="qwen-image-edit-2511", kind="image", local=True, available=False
            )
        }
    )
    no_final.judge = _fail_label("Hero").judge
    ws = hf.Workspace(tmp_path, models=no_final)
    p = ws.create_project("P")
    woman = p.add_subject("character", "Woman", description="black hair")
    run = p.submit(hf.SubjectReferences(subject_id=woman.id, presentation="turnaround"))
    run_all(p)
    with pytest.raises(hf.errors.InvalidRequest, match="needs an accepted o01 first"):
        p.rerun(run.id, "o02")
    with pytest.raises(hf.errors.NotFound, match=r"no output o99; its outputs are \['o01'"):
        p.rerun(run.id, "o99")
    with pytest.raises(hf.errors.NotFound, match="no profile preset 'nope'"):
        p.rerun(run.id, "o01", profile="nope")
    with pytest.raises(hf.errors.InvalidRequest, match="cannot redo Hero with the final profile"):
        p.rerun(run.id, "o01", profile="final")
    again = p.rerun(run.id, "o01")
    assert again.profile["id"] == "draft" and p.run_view(again.id).selection["rounds"] == 3
    assert load_run_plan(p, again.id).counts.planner_calls == 1


def load_run_plan(p: hf.ProjectStore, run_id: str) -> hf.Plan:
    from hone_frame.runs import load_run

    return load_run(p, run_id).plan


def test_a_replaced_output_is_never_produced_again(tmp_path: Path) -> None:
    fake = _fail_label("Back")
    ws = hf.Workspace(tmp_path, models=fake)
    p = ws.create_project("P")
    a = p.add_subject("character", "A", description="a")
    run = p.submit(
        hf.SubjectReferences(
            subject_id=a.id, presentation="turnaround", selection=hf.Selection(rounds=1, technical_retries=0)
        )
    )
    fake.fail_generate("out_of_memory", times=1)  # the hero fails technically: its views wait
    run_all(p)
    assert p.run_view(run.id).status == "failed"
    p.rerun(run.id, "o01")
    assert p.run_view(run.id).outputs[0].status == "replaced"
    p.retry(run.id)
    run_all(p)
    first = p.run_view(run.id).outputs[0]
    assert first.status == "replaced" and first.replaced_by is not None


def test_redo_of_an_accepted_or_unfinished_output(tmp_path: Path) -> None:
    ws = hf.Workspace(tmp_path, models=FakeModels())
    p = ws.create_project("P")
    a = p.add_subject("character", "A", description="a")
    done = p.submit(
        hf.SubjectReferences(
            subject_id=a.id, presentation="neutral-full-body", selection=hf.Selection(rounds=1)
        )
    )
    run_all(p)
    p.rerun(done.id, "o01")  # a person wants an accepted image again: it is replaced, no longer accepted
    view = p.run_view(done.id)
    assert view.outputs[0].status == "replaced" and view.accepted == [] and view.status == "done"
    queued = p.submit(hf.SubjectReferences(subject_id=a.id, presentation="neutral-full-body"))
    p.rerun(queued.id, "o01")  # not produced yet: nothing to replace, it will still run
    assert p.run_view(queued.id).outputs[0].status == "queued"
