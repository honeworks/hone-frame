"""AC-1: a fresh installation offers useful presets before the first project exists (design §5)."""

from pathlib import Path

import pytest

import hone_frame as hf
from hone_frame.presets import CATEGORIES

EXPECTED = {
    "style_pack": {
        "cinematic-realism",
        "illustrated-storybook",
        "clean-2d-animation",
        "cel-shaded-animation",
        "inked-comic",
        "painterly-fantasy",
        "stylised-3d",
        "miniature-stop-motion",
        "historical-epic",
        "product-studio",
    },
    "camera": {
        "establishing",
        "wide",
        "medium",
        "close-up",
        "extreme-close-up",
        "detail",
        "front",
        "profile",
        "rear",
        "three-quarter",
        "overhead",
        "low-angle",
        "reverse",
        "pov",
    },
    "profile": {"draft", "standard", "final", "custom"},
    "selection": {"batch-then-judge", "sequential-judge-refine", "all-rounds", "stop-on-pass", "manual-pick"},
    "sheet_layout": {
        "four-view-turnaround",
        "expression-grid",
        "pose-grid",
        "object-detail-board",
        "environment-board",
        "before-after",
        "sequence-strip",
        "contact-grid",
    },
}
MODEL_WORDS = ("gpt", "sora", "flux", "qwen", "gemma", "z-image", "claude", "openai")


def test_catalogue_without_a_project() -> None:
    catalog = hf.presets()
    assert catalog.categories() == list(CATEGORIES)
    assert len(CATEGORIES) == 14
    for category, ids in EXPECTED.items():
        assert {p.id for p in catalog.list(category)} == ids, category
    for category in CATEGORIES:
        presets = catalog.list(category)
        assert presets, category
        for preset in presets:
            assert preset.description.strip()
            assert preset.version >= 1
            assert isinstance(preset.subject_kinds, list)


def test_only_profiles_name_models() -> None:
    catalog = hf.presets()
    for category in CATEGORIES:
        if category == "profile":
            continue
        for preset in catalog.list(category):
            text = preset.model_dump_json().lower()
            assert not any(word in text for word in MODEL_WORDS), (category, preset.id)


def test_shipped_profiles_are_local_models() -> None:
    hosted = ("gpt-image", "sora", "openai", "litellm")
    for preset in hf.presets().list("profile"):
        models = [v for k, v in preset.values.items() if k in {"planner", "generator", "editor", "judge"}]
        assert models and not any(h in str(m) for m in models for h in hosted)


def test_defaults() -> None:
    catalog = hf.presets()
    assert catalog.default("style_pack") == "cinematic-realism"
    pack = catalog.get("style_pack", "cinematic-realism")
    assert pack.values["lighting"] == "neutral-studio"
    assert pack.values["sheet_layout"] == "four-view-turnaround"


def test_presets_filter_by_subject_kind() -> None:
    catalog = hf.presets()
    assert all(p.applies_to("character") for p in catalog.list("expression", kind="character"))
    assert catalog.list("expression", kind="asset") == []


def test_user_pack_is_merged(tmp_path: Path) -> None:
    ws = hf.Workspace(tmp_path)
    (tmp_path / "presets").mkdir()
    (tmp_path / "presets" / "mine.toml").write_text(
        '[[presets]]\nid = "noir"\ncategory = "style_pack"\nversion = 1\nname = "Noir"\n'
        'description = "Black and white, hard shadows."\n'
    )
    catalog = hf.Workspace(tmp_path).presets
    assert catalog.get("style_pack", "noir").builtin is False
    assert len(catalog.list("style_pack")) == 11
    assert ws.presets.get("style_pack", "cinematic-realism").builtin


def test_bad_user_pack_is_refused(tmp_path: Path) -> None:
    (tmp_path / "presets").mkdir()
    (tmp_path / "presets" / "bad.toml").write_text(
        '[[presets]]\nid = "x"\ncategory = "nope"\nversion = 1\nname = "X"\ndescription = "x"\n'
    )
    with pytest.raises(hf.errors.HoneFrameError, match="unknown category"):
        _ = hf.Workspace(tmp_path).presets


def test_unknown_preset_names_the_choices() -> None:
    with pytest.raises(hf.errors.NotFound, match="cinematic-realism"):
        hf.presets().get("style_pack", "nope")


def test_runs_record_preset_versions(tmp_path: Path) -> None:
    from hone_frame.testing import FakeModels

    ws = hf.Workspace(tmp_path, models=FakeModels())
    p = ws.create_project("P", style_pack="inked-comic")
    woman = p.add_subject("character", "Woman", description="x")
    run = p.submit(hf.SubjectReferences(subject_id=woman.id))
    assert run.presets["style_pack:inked-comic"] == 1
    assert run.presets["profile:draft"] == 1 and run.presets["judging:character-identity"] == 1
    (tmp_path / "presets").mkdir()
    (tmp_path / "presets" / "v2.toml").write_text(
        '[[presets]]\nid = "inked-comic"\ncategory = "style_pack"\nversion = 2\nname = "Inked"\n'
        'description = "changed"\n'
    )
    again = hf.Workspace(tmp_path, models=FakeModels()).project(p.id)
    assert again.run_view(run.id).presets["style_pack:inked-comic"] == 1
    assert again.info.style_pack == "inked-comic"
