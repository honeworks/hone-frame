"""AC-17: character assets have an owner and become action items; world assets have none, and the project's
generate-assets covers those without an accepted image (change 0003)."""

import hone_frame as hf
from hone_frame.characters import character_page, world, world_requests

from ._characters import ONE, rostam
from .conftest import run_all


def test_owned_and_world_assets(ws: hf.Workspace) -> None:
    p = rostam(ws)
    page = character_page(p, "char_001")
    assert [a["name"] for a in page["assets"]] == ["Mace"]
    actions = next(row for row in page["packs"] if row["id"] == "actions")
    assert [i["item"] for i in actions["items"]] == ["Mace"]
    assert [w["name"] for w in world(p)] == ["White Fortress"]


def test_world_generate_covers_those_without_an_image(ws: hf.Workspace) -> None:
    p = rostam(ws)
    assert [r.subject_id for r in world_requests(p, None)] == ["env_001"]
    run = p.submit(world_requests(p, None)[0].model_copy(update={"selection": ONE}))
    run_all(p)
    assert p.run_view(run.id).status == "done"
    assert world_requests(p, None) == []
