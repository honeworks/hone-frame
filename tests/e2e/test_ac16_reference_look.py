"""AC-16: pack items are written on a white background with empty hands (actions excepted), expressions as
face close-ups, and judged on both (change 0003)."""

import hone_frame as hf
from hone_frame.prompts import compose
from hone_frame.requests import PlannedRef
from hone_frame.testing import FakeModels

from ._characters import ONE, rostam
from .conftest import run_all

WHITE = "plain pure white background"
EMPTY = "Empty hands"


def _prompt(p: hf.ProjectStore, out: hf.PlannedOutput) -> str:
    refs = [(PlannedRef(image_id="img_0001", subject_id="char_001"), "Rostam")] if out.depends_on else []
    return compose(out, refs, [], p.workspace.dialects.for_model(out.model)).text


def test_white_background_and_empty_hands(ws: hf.Workspace) -> None:
    p = rostam(ws)
    outputs = p.plan(hf.CharacterPacks(subject_id="char_001")).outputs
    for out in outputs:
        text = _prompt(p, out)
        assert WHITE in text, out.label
        assert "clean_background" in out.conditions
        holds = out.pack == "actions" or out.kind == "asset"
        assert (EMPTY in text) is not holds and ("no_props" in out.conditions) is not holds, out.label


def test_expressions_are_face_close_ups(ws: hf.Workspace) -> None:
    p = rostam(ws)
    happy = next(o for o in p.plan(hf.CharacterPacks(subject_id="char_001")).outputs if o.item == "Happy")
    text = _prompt(p, happy)
    assert (
        "close-up of the head and shoulders" in text and "the face, head and shoulders fill the frame" in text
    )
    assert not happy.prompt_inputs.get("full_body")


def test_the_judge_checks_background_and_hands(ws: hf.Workspace, fake: FakeModels) -> None:
    p = rostam(ws)
    p.submit(hf.CharacterPacks(subject_id="char_001", packs=["turnaround"], selection=ONE))
    run_all(p)
    judged = [c.prompt for c in fake.asked if "quality judge" in c.prompt]
    assert judged and all("- clean_background:" in j and "- no_props:" in j for j in judged)
