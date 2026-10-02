"""AC-19: the character model sheet is composed from the accepted pack images without a model call
(change 0003)."""

import pytest
from PIL import Image

import hone_frame as hf
from hone_frame.characters import model_sheet_recipe
from hone_frame.errors import HoneFrameError
from hone_frame.testing import FakeModels

from ._characters import ONE, rostam
from .conftest import run_all


def test_model_sheet_from_accepted_images(ws: hf.Workspace, fake: FakeModels) -> None:
    p = rostam(ws)
    with pytest.raises(HoneFrameError, match="generate them first"):
        model_sheet_recipe(p, "char_001")
    p.submit(hf.CharacterPacks(subject_id="char_001", packs=["turnaround", "expressions"], selection=ONE))
    run_all(p)
    calls = len(fake.generated) + len(fake.asked)
    recipe = model_sheet_recipe(p, "char_001")
    assert recipe.labels[:5] == ["Hero", "Front", "3/4", "Side", "Back"] and recipe.columns == 5
    assert recipe.labels[5:] == [
        "Neutral",
        "Happy",
        "Sad",
        "Angry",
        "Surprised",
        "Afraid",
        "Determined",
        "Thinking",
    ]
    assert "Appearance: weathered face" in recipe.notes
    path = p.compose_sheet(p.save_sheet(recipe).id)
    with Image.open(path) as sheet:
        assert sheet.width > 5 * 440 and sheet.height > 760 + 2 * 300
    assert len(fake.generated) + len(fake.asked) == calls  # no model was called
