"""AC-15: one request makes a whole character from one hero; packs can be left out, items added, and a
second request reuses the accepted hero (change 0003)."""

import hone_frame as hf
from hone_frame.recipes_packs import packs

from ._characters import ONE, rostam
from .conftest import run_all


def test_every_pack_from_one_hero(ws: hf.Workspace) -> None:
    p = rostam(ws)
    plan = p.plan(hf.CharacterPacks(subject_id="char_001"))
    assert not plan.errors
    hero, *rest = plan.outputs
    assert (hero.pack, hero.item, hero.depends_on) == ("hero", "Hero", [])
    assert [o.pack for o in rest if o.pack == "hero"] == []
    assert all(o.depends_on[0].output == hero.id for o in rest if o.pack != "assets")
    assert {o.pack for o in plan.outputs} == set(packs()) - {"states"}  # Rostam has no other states
    assert [o.item for o in rest if o.pack == "outfits"] == ["Feast"]
    assert [o.item for o in rest if o.pack == "actions"] == ["Mace"]
    action = next(o for o in rest if o.pack == "actions")
    mace = next(o for o in rest if o.pack == "assets")
    assert {d.output for d in action.depends_on} == {hero.id, mace.id}  # the belonging as an object


def test_the_accepted_hero_is_never_redrawn(ws: hf.Workspace) -> None:
    p = rostam(ws)
    first = p.submit(hf.CharacterPacks(subject_id="char_001", packs=["turnaround"], selection=ONE))
    run_all(p)
    hero_image = next(o for o in p.run_view(first.id).outputs if o.label == "Hero").selected
    images = p.images(subject_id="char_001")
    assert {(i.pack, i.item) for i in images if len(i.subjects) == 1} >= {
        ("hero", "Hero"),
        ("turnaround", "Back"),
    }
    second = p.plan(hf.CharacterPacks(subject_id="char_001", packs=["expressions"]))
    assert all(o.pack == "expressions" for o in second.outputs)  # no hero this time
    assert all(o.references[0].image_id == hero_image for o in second.outputs)
    redraw = p.plan(hf.CharacterPacks(subject_id="char_001", packs=["hero"], redraw_hero=True))
    assert [(o.pack, o.item) for o in redraw.outputs] == [("hero", "Hero")]


def test_packs_left_out_and_items_added(ws: hf.Workspace) -> None:
    p = rostam(ws)
    plan = p.plan(
        hf.CharacterPacks(
            subject_id="char_001",
            packs=["outfits", "poses"],
            custom={"outfits": ["party clothing"], "poses": ["drawing a bow"]},
        )
    )
    assert {o.pack for o in plan.outputs} == {"hero", "outfits", "poses"}
    party = next(o for o in plan.outputs if o.item == "party clothing")
    assert party.pack == "outfits" and party.prompt_inputs["outfit"] == "party clothing"
    assert next(o for o in plan.outputs if o.item == "drawing a bow").prompt_inputs["pose"] == "drawing a bow"


def test_bad_requests_are_named(ws: hf.Workspace) -> None:
    p = rostam(ws)
    assert (
        "unknown packs ['props']"
        in p.plan(hf.CharacterPacks(subject_id="char_001", packs=["props"])).errors[0]
    )
    assert (
        "takes no items"
        in p.plan(hf.CharacterPacks(subject_id="char_001", custom={"assets": ["a shield"]})).errors[0]
    )
    assert "packs are made for characters" in p.plan(hf.CharacterPacks(subject_id="obj_001")).errors[0]


def test_custom_items_need_their_pack(ws: hf.Workspace) -> None:
    p = rostam(ws)
    request = hf.CharacterPacks(subject_id="char_001", packs=["poses"], custom={"outfits": ["a cloak"]})
    assert "not in packs" in p.plan(request).errors[0]


def test_without_an_accepted_hero_the_hero_always_comes_first(ws: hf.Workspace) -> None:
    p = rostam(ws)
    only = hf.CharacterPacks(
        subject_id="char_001", packs=["poses"], custom={"poses": ["bowing"]}, only_custom=True
    )
    assert [(o.pack, o.item) for o in p.plan(only).outputs] == [("hero", "Hero"), ("poses", "bowing")]
