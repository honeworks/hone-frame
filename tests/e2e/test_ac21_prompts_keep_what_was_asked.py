"""AC-21: in real runs (FakeModels), every image of a whole character keeps in its prompt what it was asked
for, its white background and, unless it holds something, its empty hands, for several styles and every
profile's models; the full matrix over every style is in tests/unit/test_prompt_matrix.py (change 0004)."""

from pathlib import Path

import pytest

import hone_frame as hf
from hone_frame.testing import FakeModels

from .conftest import FILE, run_all

ASKED = ("pose", "expression", "outfit", "state", "action")
CUSTOM = {"poses": ["drawing a bow"], "outfits": ["in party clothing"], "actions": ["riding at full gallop"]}


@pytest.mark.parametrize("profile", ["draft", "standard", "final"])
@pytest.mark.parametrize("style", ["historical-epic", "clean-2d-animation"])
def test_every_image_keeps_what_it_was_asked(tmp_path: Path, style: str, profile: str) -> None:
    ws = hf.Workspace(tmp_path / "ws", models=FakeModels())
    p = ws.project(ws.import_file(FILE).project)
    p.update(style_pack=style)
    rostam = p.subjects("character")[0]
    request = hf.CharacterPacks(
        subject_id=rostam.id, custom=CUSTOM, profile=profile, selection=hf.Selection(rounds=1)
    )
    plan = p.plan(request)
    p.submit(request)
    run_all(p)
    prompts = {(i.pack, i.item): i.generation.prompt.lower() for i in p.images() if i.generation}
    checked = 0
    for out in plan.outputs:
        prompt = prompts[(out.pack, out.item)]
        for key in ASKED:
            if value := out.prompt_inputs.get(key):
                assert str(value).lower() in prompt, f"{out.item}: {key} {value!r} lost"
                checked += 1
        assert "plain pure white background" in prompt, out.item
        assert ("empty hands" in prompt) is bool(out.prompt_inputs.get("empty_hands")), out.item
    assert checked >= 20  # expressions, poses, outfits, states and actions were all looked at
