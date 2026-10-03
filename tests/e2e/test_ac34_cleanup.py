"""AC-34: clean-up deletes candidates that were not chosen, or a whole variation's images, never an image
in use, and never the active variation (change 0006)."""

from pathlib import Path

import pytest

import hone_frame as hf
from hone_frame.cleanup import cleanup, cleanup_candidates
from hone_frame.errors import InvalidRequest
from hone_frame.testing import FakeModels

from .conftest import FILE, run_all


def test_unchosen_candidates_and_variations(tmp_path: Path) -> None:
    ws = hf.Workspace(tmp_path / "ws", models=FakeModels())
    p = ws.project(ws.import_file(FILE).project)
    p.submit(
        hf.CharacterPacks(
            subject_id="char_001", packs=["turnaround"], selection=hf.Selection(rounds=1, candidates=2)
        )
    )
    run_all(p)
    before = len(p.images())
    doomed = cleanup_candidates(p, "unchosen")
    assert 0 < len(doomed) < before
    assert cleanup(p, "unchosen")["deleted"] == len(doomed)
    assert all(i.status in ("picked", "manual_pick") for i in p.images(subject_id="char_001"))
    flat = p.add_variation("Flat", style_pack="clean-2d-animation")
    p.submit(hf.CharacterPacks(subject_id="char_001", packs=["hero"], selection=hf.Selection(rounds=1)))
    run_all(p)
    with pytest.raises(InvalidRequest, match="switch to another variation first"):
        cleanup(p, "variation", flat.id)
    p.use_variation("main")
    assert cleanup(p, "variation", flat.id)["deleted"] >= 1
    assert [v.id for v in p.info.all_variations()] == ["main"] and not p.images(variation=flat.id)
