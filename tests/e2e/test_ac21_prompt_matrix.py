"""AC-21: every prompt hone-frame writes, checked for what can go wrong (change 0004): for every
style pack, every profile (so every image model and dialect), every character pack item and scenes,
with the realistic descriptions of examples/projects/rostam-and-sohrab.toml. A prompt must keep what its
image is for, never contradict itself, stay near its model's budget, and let the planner's rewrite
through only when it keeps what was asked."""

from __future__ import annotations

import re

import pytest

import hone_frame as hf
from hone_frame.presets import PresetCatalog
from hone_frame.prompts import ASKED, Composed, compose, planner_problem
from hone_frame.recipes import WHITE
from hone_frame.requests import PlannedOutput, PlannedRef

STYLES = [p.id for p in PresetCatalog().list("style_pack")]
PROFILES = ["draft", "standard", "final"]
CUSTOM = {
    "expressions": ["grief-stricken, eyes full of tears"],
    "poses": ["drawing a bow, the string pulled back to the cheek"],
    "outfits": ["in party clothing of red and gold silk"],
    "states": ["soaked by heavy rain"],
    "actions": ["riding a horse at full gallop"],
    "turnaround": ["from a low angle looking up"],
}


def _refs(store: hf.ProjectStore, out: PlannedOutput) -> list[tuple[PlannedRef, str]]:
    """The references the model would get: the fixed ones plus one per dependency (as at run time)."""
    found = list(out.references)
    first = out.subjects[0].subject_id if out.subjects else None
    for dep in out.depends_on:
        found.append(PlannedRef(image_id=f"img_{dep.output}", subject_id=first, role=dep.role))
    return [(r, store.subject(r.subject_id).name if r.subject_id else "") for r in found]


def _all_prompts(store: hf.ProjectStore, style: str, profile: str) -> list[tuple[PlannedOutput, Composed]]:
    store.update(style_pack=style)
    found: list[tuple[PlannedOutput, Composed]] = []
    for character in store.subjects("character"):
        request = hf.CharacterPacks(subject_id=character.id, custom=CUSTOM, profile=profile)
        plan = store.plan(request)
        assert not plan.errors, plan.errors
        for out in plan.outputs:
            dialect = store.workspace.dialects.for_model(out.model)
            found.append((out, compose(out, _refs(store, out), [], dialect)))
    return found


@pytest.mark.parametrize("profile", PROFILES)
@pytest.mark.parametrize("style", STYLES)
def test_every_pack_prompt_keeps_what_it_is_for(
    rostam_project: hf.ProjectStore, style: str, profile: str
) -> None:
    for out, composed in _all_prompts(rostam_project, style, profile):
        text, where = composed.text.lower(), f"{style}/{profile}/{out.pack}/{out.item}"
        p = out.prompt_inputs
        for key in ASKED:  # the point of the image is never cut for the budget
            if p.get(key):
                assert str(p[key]).lower().rstrip(".") in text, f"{where}: {key} {p[key]!r} lost"
        assert WHITE in text, f"{where}: no white background"
        assert ("empty hands" in text) is bool(p.get("empty_hands")), f"{where}: hands"
        if out.pack == "actions" or out.kind == "asset":
            assert "empty hands" not in text, where
        assert len(composed.text.split()) <= composed.max_words * (1.5 if composed.over_budget else 1), where
        _no_contradictions(out, composed, where)


def _no_contradictions(out: PlannedOutput, composed: Composed, where: str) -> None:
    text = composed.text.lower()
    p = out.prompt_inputs
    if "rear" in out.conditions:
        assert "face is not visible" in text, where
        assert "same face" not in text and "weathered" not in text, f"{where}: a face in a back view"
    if out.pack == "expressions":
        assert "head to feet" not in text and "whole figure" not in text, f"{where}: full body in a close-up"
        assert "close-up" in text and "boots" not in text, f"{where}: a close-up that names the feet"
    if p.get("full_body"):
        assert "head to feet" in text, f"{where}: full figure not asked"
    assert "surroundings" not in text, f"{where}: scenery asked on a white background"
    rostam = bool(out.subjects) and out.subjects[0].subject_id == "char_001" and out.kind == "character"
    if rostam and not p.get("outfit") and not p.get("state") and p.get("full_body"):
        assert "helmet" in text and "boots" in text, f"{where}: a piece of the outfit forgotten"
    if p.get("outfit"):
        assert "tiger-skin coat worn over" not in text, f"{where}: the usual outfit kept in an outfit change"
    if composed.dialect == "qwen-edit":
        assert composed.text.startswith("<sks> "), f"{where}: camera phrase not first"
    assert not re.search(r"\.\s*\.", composed.text) and composed.text.endswith("."), f"{where}: punctuation"
    sentences = [s.strip() for s in composed.text.split(". ") if s.strip()]
    assert len(sentences) == len(set(sentences)), f"{where}: a sentence repeated"


@pytest.mark.parametrize("profile", PROFILES)
def test_the_planner_cannot_drop_what_was_asked(rostam_project: hf.ProjectStore, profile: str) -> None:
    for out, composed in _all_prompts(rostam_project, "historical-epic", profile):
        assert planner_problem(composed.text, composed) is None, f"{out.item}: the draft itself is refused"
        for asked in composed.asked:
            dropped = composed.text.replace(asked, "").replace(asked[0].upper() + asked[1:], "")
            if dropped != composed.text:
                assert "was dropped" in (planner_problem(dropped, composed) or ""), f"{out.item}: {asked}"


def test_scenes_keep_their_action_pose_expression_and_notes(rostam_project: hf.ProjectStore) -> None:
    rostam, sohrab = (s.id for s in rostam_project.subjects("character")[:2])
    plain = next(s.id for s in rostam_project.subjects("environment") if s.name == "Battle plain")
    scene = rostam_project.save_scene(
        hf.Scene(
            name="Long duel",
            description="Rostam and Sohrab fight on horseback on the dusty plain at sunset " * 4,
            action="Rostam swings his mace down at Sohrab's raised spear",
            expression="determined",
            pose="a ready fighting stance, knees bent",
            gaze="the two men lock eyes",
            notes="dust hangs in the air",
            refs=[
                hf.SceneRef(subject_id=rostam),
                hf.SceneRef(subject_id=sohrab),
                hf.SceneRef(subject_id=plain, role="environment"),
            ],
            camera="wide",
        )
    )
    for profile in PROFILES:
        out = rostam_project.plan(hf.SceneShot(scene_id=scene.id, profile=profile)).outputs[0]
        composed = compose(
            out, _refs(rostam_project, out), [], rostam_project.workspace.dialects.for_model(out.model)
        )
        text = composed.text.lower()
        for words in ("swings his mace", "determined", "fighting stance", "lock eyes", "dust hangs"):
            assert words in text, f"{profile}: {words!r} lost"


def test_a_note_on_generate_again_is_never_cut(rostam_project: hf.ProjectStore) -> None:
    rostam = rostam_project.subjects("character")[0]
    out = next(
        o
        for o in rostam_project.plan(hf.CharacterPacks(subject_id=rostam.id, packs=["poses"])).outputs
        if o.item == "Running"
    )
    note = "both feet must point the same way as the body, the left arm forward"
    noted = out.model_copy(update={"prompt_inputs": out.prompt_inputs | {"note": note}})
    composed = compose(
        noted,
        _refs(rostam_project, noted),
        ["the man is standing still"],
        rostam_project.workspace.dialects.for_model(out.model),
    )
    assert (
        note in composed.text.lower()
        and "standing still" in composed.text
        and "running" in composed.text.lower()
    )


def test_objects_in_the_hands_are_reported(rostam_project: hf.ProjectStore) -> None:
    rostam = rostam_project.subjects("character")[0]
    rostam_project.edit_subject(
        rostam.id, fields=rostam.fields | {"features": "a bull-headed mace in his right hand"}
    )
    try:
        warnings = rostam_project.plan(hf.CharacterPacks(subject_id=rostam.id, packs=["poses"])).warnings
        assert any("mace" in w and "Belongings" in w for w in warnings)
    finally:
        rostam_project.edit_subject(rostam.id, fields=rostam.fields)
