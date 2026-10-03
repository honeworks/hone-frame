"""AC-29: the whole world of a variation in one go, with an estimate first; the scenes follow the last
character, since they need its accepted hero (change 0005)."""

from pathlib import Path

import hone_frame as hf
from hone_frame.events import read_events
from hone_frame.testing import FakeModels, judge_answer

from .conftest import FILE, run_all


def test_generate_everything(tmp_path: Path) -> None:
    ws = hf.Workspace(tmp_path / "ws", models=FakeModels())
    p = ws.project(ws.import_file(FILE).project)
    plan = p.world_plan(selection=hf.Selection(rounds=1))
    assert len(plan["runs"]) == 8 and plan["scenes"] == 2 and plan["images"] > 100
    assert plan["estimate_s"] == round(plan["images"] * plan["seconds_per_image"])
    started = p.generate_world(selection=hf.Selection(rounds=1))
    assert len(started["runs"]) == 8 and started["scenes_after"] == 2
    run_all(p)
    titles = [r.title for r in p.runs()]
    assert "Duel" in titles and "Gordafarid unmasked" in titles  # queued after the characters
    duel = next(r for r in p.runs() if r.title == "Duel")
    assert duel.status in ("done", "needs_review")


def test_follow_ups_only_after_a_usable_run(tmp_path: Path) -> None:
    fake = FakeModels()
    ws = hf.Workspace(tmp_path / "ws", models=fake)
    p = ws.project(ws.import_file(FILE).project)
    from hone_frame.world_runs import set_follow_up

    scene = p.scenes()[0].id
    failing = p.submit(
        hf.CharacterPacks(subject_id="char_002", packs=["hero"], selection=hf.Selection(rounds=1))
    )
    set_follow_up(p, failing.id, [hf.SceneShot(scene_id=scene).model_dump(mode="json")])
    fake.fail_generate("transient", times=50)
    run_all(p)
    assert p.run_view(failing.id).status == "failed"
    assert not [r for r in p.runs() if r.kind == "scene"]  # a failed run queues nothing
    skipped = [
        e
        for e in read_events(p.root / "runs" / failing.id / "events.jsonl")
        if e["event"] == "follow_up_skipped"
    ]
    assert skipped
    reviewing = FakeModels(judge=lambda _i, prompt, _im: judge_answer(prompt, fail=("view",)))
    ws2 = hf.Workspace(tmp_path / "ws2", models=reviewing)
    q = ws2.project(ws2.import_file(FILE).project)
    review = q.submit(
        hf.CharacterPacks(subject_id="char_001", packs=["hero"], selection=hf.Selection(rounds=1))
    )
    set_follow_up(q, review.id, [hf.SceneShot(scene_id=q.scenes()[0].id).model_dump(mode="json")])
    run_all(q)
    assert q.run_view(review.id).status == "needs_review"
    tried = [
        e for e in read_events(q.root / "runs" / review.id / "events.jsonl") if e["event"] == "follow_up"
    ]
    assert tried and tried[0]["message"].startswith("not queued")  # tried: a run that needs review is usable
