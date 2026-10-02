"""Prompts written for the model's dialect, the task and the style (design §8.8, change 0002)."""

from pathlib import Path

import pytest

import hone_frame as hf
from hone_frame.candidates import model_inputs
from hone_frame.dialects import Dialects
from hone_frame.prompts import Composed, compose, planner_problem
from hone_frame.requests import PlannedRef
from hone_frame.testing import FakeModels

FACE = "thick dark beard"


@pytest.fixture
def project(tmp_path: Path) -> hf.ProjectStore:
    ws = hf.Workspace(tmp_path / "ws", models=FakeModels())
    p = ws.create_project("Rostam and Sohrab", style_pack="historical-epic")
    p.add_subject(
        "character",
        "Rostam",
        description="Rostam, son of Zal, the champion of Iran",
        fields={
            "appearance": f"weathered face, {FACE}",
            "proportions": "enormous, broad chest",
            "outfits": "tiger-hide coat over lamellar armour, brown boots",
            "features": "a bull-headed mace in his right hand",
        },
    )
    return p


def _views(p: hf.ProjectStore, profile: str) -> dict[str, Composed]:
    plan = p.plan(hf.SubjectReferences(subject_id="char_001", presentation="turnaround", profile=profile))
    ref = [(PlannedRef(image_id="img_0001", subject_id="char_001", role="identity"), "Rostam")]
    dialects = p.workspace.dialects
    return {
        o.label: compose(o, [] if o.label == "Hero" else ref, [], dialects.for_model(o.model))
        for o in plan.outputs
    }


def test_each_model_gets_its_dialect() -> None:
    d = Dialects()
    names = {
        m: d.for_model(m).name
        for m in ("z-image-turbo", "flux.2-klein-4b", "qwen-image-edit-2511", "gpt-image-1.5")
    }
    assert names == {
        "z-image-turbo": "z-image",
        "flux.2-klein-4b": "flux-klein",
        "qwen-image-edit-2511": "qwen-edit",
        "gpt-image-1.5": "generic",
    }


def test_hero_is_long_and_structured_views_are_short_edits(project: hf.ProjectStore) -> None:
    views = _views(project, "draft")
    hero, side, back = views["Hero"], views["Side"], views["Back"]
    assert (hero.dialect, hero.mode) == ("z-image", "generate") and FACE in hero.text
    assert hero.text.index("full body") < hero.text.index("tiger-hide")  # the shot first
    assert "plain light grey background" in hero.text and "architecture" not in hero.text  # a reference
    assert (side.dialect, side.mode) == ("flux-klein", "view") and side.text.startswith(
        "Show the same person"
    )
    assert "same face, hair and build" in side.text and FACE not in side.text  # an edit, not a re-description
    assert "face is not visible" in back.text and "same face" not in back.text and FACE not in back.text
    assert all(len(v.text.split()) <= 110 for v in (side, back))


def test_qwen_gets_the_camera_phrase_and_no_separate_angle(project: hf.ProjectStore) -> None:
    back = _views(project, "final")["Back"]
    assert back.dialect == "qwen-edit" and back.text.startswith("<sks> back view eye-level shot wide shot.")
    plan = project.plan(
        hf.SubjectReferences(subject_id="char_001", presentation="turnaround", profile="final")
    )
    out = next(o for o in plan.outputs if o.label == "Back")
    sent, _ = model_inputs(out, plan.profile, None, [Path("hero.png")], camera_in_prompt=True)
    assert "camera_angle" not in sent
    assert model_inputs(out, plan.profile, None, [Path("hero.png")])[0]["camera_angle"] == "back"


def test_scenes_compose_with_the_full_style(project: hf.ProjectStore) -> None:
    scene = project.save_scene(
        hf.Scene(
            name="Duel",
            description="Rostam faces his son on the plain",
            refs=[hf.SceneRef(subject_id="char_001")],
            camera="wide",
        )
    )
    out = project.plan(hf.SceneShot(scene_id=scene.id, profile="standard")).outputs[0]
    ref = [(PlannedRef(image_id="img_0001", subject_id="char_001", role="identity"), "Rostam")]
    composed = compose(out, ref, [], project.workspace.dialects.for_model(out.model))
    assert composed.mode == "compose" and composed.text.startswith("Rostam faces his son")
    assert "image 1" in composed.text


def test_a_2d_style_opens_and_closes_a_z_image_prompt(tmp_path: Path) -> None:
    ws = hf.Workspace(tmp_path, models=FakeModels())
    p = ws.create_project("Cartoon", style_pack="clean-2d-animation")
    p.add_subject("character", "Girl", description="a girl")
    hero = p.plan(hf.SubjectReferences(subject_id="char_001")).outputs[0]
    text = compose(hero, [], [], ws.dialects.for_model(hero.model)).text
    assert text.startswith("Flat 2D vector animation style") and text.endswith("crisp outlines.")


def test_the_budget_drops_optional_pieces_first(project: hf.ProjectStore) -> None:
    project.edit_subject("char_001", fields={"outfits": "armour " * 200})
    back = _views(project, "draft")["Back"]
    assert "face is not visible" in back.text and "Keep exactly the same" in back.text  # required stay


def test_planner_answers_are_checked() -> None:
    draft = Composed(
        "<sks> back view eye-level shot wide shot. Show the man from image 1.",
        "qwen-edit",
        "view",
        20,
        "<sks> back view eye-level shot wide shot",
    )
    assert planner_problem(draft.text, draft) is None
    assert "budget" in (planner_problem("word " * 40, draft) or "")
    assert "camera phrase" in (planner_problem("Show the man from image 1 from behind.", draft) or "")
    loose = Composed("Show the man from image 1.", "flux-klein", "view", 20, "")
    assert "no longer named" in (planner_problem("Show the man from behind.", loose) or "")


def test_a_workspace_dialect_wins_and_bad_sections_are_named(tmp_path: Path) -> None:
    (tmp_path / "prompting.toml").write_text(
        '[dialects.mine]\nmodels = ["gpt-image*"]\n'
        '[dialects.mine.generate]\nsections = ["subject"]\nmax_words = 50\n'
    )
    assert Dialects(tmp_path).for_model("gpt-image-1.5").name == "mine"
    (tmp_path / "prompting.toml").write_text(
        '[dialects.bad]\nmodels = ["x"]\n[dialects.bad.generate]\nsections = ["colour"]\nmax_words = 50\n'
    )
    with pytest.raises(hf.errors.HoneFrameError, match=r"unknown sections \['colour'\]"):
        Dialects(tmp_path)


@pytest.mark.parametrize(
    ("text", "message"),
    [
        ("[dialects.x\n", "not valid"),
        (
            '[dialects.x]\nmodels = ["m"]\ncolour = 1\n'
            "[dialects.x.generate]\nsections = []\nmax_words = 50\n",
            "not valid",
        ),
        (
            '[dialects.x]\nmodels = ["m"]\ncamera_phrase = "<sks> {angle}"\n'
            "[dialects.x.generate]\nsections = []\nmax_words = 50\n",
            "use only {azimuth}, {elevation} and {distance}",
        ),
    ],
)
def test_bad_workspace_dialects_are_refused(tmp_path: Path, text: str, message: str) -> None:
    (tmp_path / "prompting.toml").write_text(text)
    with pytest.raises(hf.errors.HoneFrameError, match=message.replace("{", r"\{").replace("}", r"\}")):
        Dialects(tmp_path)


@pytest.mark.parametrize("phrase", ["<sks> {azimuth.foo}", "<sks> {azimuth[x]}", "<sks> {"])
def test_any_broken_camera_phrase_is_a_typed_error(tmp_path: Path, phrase: str) -> None:
    (tmp_path / "prompting.toml").write_text(
        f'[dialects.x]\nmodels = ["m"]\ncamera_phrase = "{phrase}"\n[dialects.x.generate]\nsections = []\n'
        "max_words = 50\n"
    )
    with pytest.raises(hf.errors.HoneFrameError, match="camera_phrase"):
        Dialects(tmp_path)


def test_without_a_generic_dialect_an_unmatched_model_is_an_error(tmp_path: Path) -> None:
    dialects = Dialects()
    dialects.all.pop("generic")
    with pytest.raises(hf.errors.HoneFrameError, match="no 'generic' dialect"):
        dialects.for_model("gpt-image-1.5")
