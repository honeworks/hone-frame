"""AC-31: hero casting draws each candidate from a distinct reading of the description (change 0006); a
planner that fails leaves seeds only."""

from pathlib import Path

import hone_frame as hf
from hone_frame.testing import FakeModels

from .conftest import FILE, run_all


def test_each_candidate_is_another_reading(tmp_path: Path) -> None:
    fake = FakeModels()
    ws = hf.Workspace(tmp_path / "ws", models=fake)
    p = ws.project(ws.import_file(FILE).project)
    p.submit(
        hf.CharacterPacks(subject_id="char_001", packs=["hero"], casting=4, selection=hf.Selection(rounds=1))
    )
    run_all(p)
    heroes = [i for i in p.images(subject_id="char_001") if i.pack == "hero"]
    assert len(heroes) == 4
    prompts = sorted(h.generation.prompt for h in heroes if h.generation)
    for n, prompt in enumerate(prompts, 1):
        assert prompt.startswith(f"reading {n}: a distinct face. ")  # each candidate opens with its own


def test_the_camera_phrase_stays_first(tmp_path: Path) -> None:
    ws = hf.Workspace(tmp_path / "ws", models=FakeModels())
    p = ws.project(ws.import_file(FILE).project)
    p.submit(
        hf.CharacterPacks(
            subject_id="char_001",
            packs=["hero"],
            casting=2,
            profile="final",
            selection=hf.Selection(rounds=1),
        )
    )
    run_all(p)
    prompts = [
        i.generation.prompt for i in p.images(subject_id="char_001") if i.pack == "hero" and i.generation
    ]
    assert len(prompts) == 2 and all(t.startswith("<sks> ") and ". reading " in t for t in prompts)


def test_without_a_planner_answer_seeds_only(tmp_path: Path) -> None:
    fake = FakeModels()
    ws = hf.Workspace(tmp_path / "ws", models=fake)
    p = ws.project(ws.import_file(FILE).project)
    fake.fail_ask(10)
    p.submit(
        hf.CharacterPacks(
            subject_id="char_001", packs=["hero"], casting=3,
            selection=hf.Selection(rounds=1, auto_judge=False, auto_pick=False),
        )
    )  # fmt: skip
    run_all(p)
    heroes = [i for i in p.images(subject_id="char_001") if i.pack == "hero"]
    assert len(heroes) == 3 and not any(
        "reading" in (h.generation.prompt if h.generation else "") for h in heroes
    )
