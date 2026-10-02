"""One candidate's inputs and result check (design §8.4, §10.5)."""

from pathlib import Path

import pytest

from hone_frame.candidates import CandidateRefused, checked, model_inputs
from hone_frame.ports import Generated, ModelFailure
from hone_frame.requests import PlannedOutput, ResolvedProfile

PROFILE = ResolvedProfile(id="final", generator="g", settings={"steps": 8})


def test_upscale_sends_the_draft_as_image() -> None:
    out = PlannedOutput(id="o01", label="Upscale", kind="promotion", mode="upscale", size="2048x2048")
    inputs, refs = model_inputs(out, PROFILE, None, [Path("draft.png"), Path("face.png")])
    assert inputs == {"steps": 8, "size": "2048x2048", "image": Path("draft.png")} and refs == []


def test_upscale_without_a_draft_fails_loudly() -> None:
    out = PlannedOutput(id="o01", label="Upscale", kind="promotion", mode="upscale")
    with pytest.raises(ModelFailure, match="needs its draft image") as raised:
        model_inputs(out, PROFILE, None, [])
    assert raised.value.transient is False


def test_result_checks() -> None:
    ok = Generated(path=Path("a.png"))
    assert checked(ok, "m") is ok
    with pytest.raises(ModelFailure):
        checked(Generated(path=None, error="CUDA out of memory", error_kind="out_of_memory"), "m")
    with pytest.raises(CandidateRefused):
        checked(Generated(path=None, error="blocked by the provider", error_kind="refused"), "m")
