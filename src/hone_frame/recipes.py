"""Recipes: a request becomes planned outputs (design §6.1). Models and reductions are `planning.py`'s."""

from __future__ import annotations

import itertools
from typing import TYPE_CHECKING, Any

from hone_frame.errors import InvalidRequest
from hone_frame.profiles import PresetChoices
from hone_frame.records import Scene, Subject, SubjectLink
from hone_frame.references import scene_refs
from hone_frame.requests import (
    CharacterPacks,
    Coverage,
    Interaction,
    PlannedOutput,
    PlannedRef,
    Promote,
    RequestBase,
    SceneShot,
    SequenceFrames,
    StatePair,
    SubjectReferences,
    Variations,
)

if TYPE_CHECKING:
    from hone_frame.store import ProjectStore

JUDGING = {
    "character": "character-identity",
    "environment": "environment-continuity",
    "asset": "object-fidelity",
}
HERO_CAMERA = {"character": "front", "environment": "establishing", "asset": "front"}
CAMERA_DATA = {"view", "faces_away", "azimuth", "elevation", "distance"}
OBJECT_FRAMING = "the whole object from end to end, centred with empty space around it, nothing cropped"
WHITE = "a plain pure white background, no scenery and no floor"  # change 0003; a pose may still use a stool
REAR_CAMERAS = {"rear"}  # views where a face is not expected: identity is judged from behind (D-020)


def view_flags(camera: str | None) -> list[str]:
    """Judging conditions that come from the camera."""
    return ["rear"] if camera in REAR_CAMERAS else []


def reference_look(kind: str) -> tuple[dict[str, Any], list[str]]:
    """A character's or object's reference image: a white background and, for a character, empty hands
    (change 0003); the prompt inputs and the judging conditions that check them. Places keep their own."""
    if kind == "environment":
        return {}, []
    hands = kind == "character"
    return {"background": WHITE, "empty_hands": hands}, ["clean_background"] + (["no_props"] if hands else [])


def reference_lighting(built: Built, request: RequestBase) -> str:
    """Reference images use neutral studio light on a plain background, whatever the style pack's mood
    lighting, unless the request or the project chose a lighting on purpose (brief §12, decisions D-021)."""
    chosen = request.presets.get("lighting") or built.choices.layers[2].get("lighting")
    return chosen or "neutral-studio"


class Built:
    """What a recipe produced: the outputs, the errors found, the presets used, an optional sheet."""

    def __init__(self, choices: PresetChoices) -> None:
        self.choices = choices
        self.outputs: list[PlannedOutput] = []
        self.errors: list[str] = []
        self.warnings: list[str] = []
        self.sheet_layout: str | None = None

    def add(self, label: str, kind: str, **fields: Any) -> PlannedOutput:
        out = PlannedOutput(id=f"o{len(self.outputs) + 1:02d}", label=label, kind=kind, **fields)
        self.outputs.append(out)
        return out


def build(store: ProjectStore, request: RequestBase) -> Built:
    from hone_frame.recipes_packs import character_packs  # noqa: PLC0415 - imports this module
    from hone_frame.recipes_scenes import (  # noqa: PLC0415 - that module imports this one
        promote_outputs,
        sequence_outputs,
        state_pair_outputs,
        variation_outputs,
    )
    from hone_frame.recipes_subjects import (  # noqa: PLC0415 - imports this module
        interaction,
        subject_references,
    )

    scene = _scene_of(store, request)
    built = Built(PresetChoices(store, request, scene.overrides if scene else None))
    if isinstance(request, SubjectReferences):
        subject_references(store, request, built)
    elif isinstance(request, SceneShot | Coverage):
        _scene_shots(store, request, scene, built)
    elif isinstance(request, Interaction):
        interaction(store, request, built)
    elif isinstance(request, StatePair):
        state_pair_outputs(store, request, scene, built)
    elif isinstance(request, SequenceFrames):
        sequence_outputs(store, request, built)
    elif isinstance(request, Variations):
        variation_outputs(store, request, scene, built)
    elif isinstance(request, Promote):
        promote_outputs(store, request, built)
    elif isinstance(request, CharacterPacks):
        character_packs(store, request, built)
    return built


def _scene_shots(
    store: ProjectStore, request: SceneShot | Coverage, scene: Scene | None, built: Built
) -> None:
    if scene is None:
        raise InvalidRequest("a scene shot needs a scene")
    cameras = request.cameras if isinstance(request, Coverage) else [scene.camera]
    for camera in cameras:
        scene_output(
            store,
            scene,
            built,
            label=(camera or scene.name) if isinstance(request, Coverage) else scene.name,
            camera=camera,
            seed_group="coverage" if isinstance(request, Coverage) else None,
        )


def _scene_of(store: ProjectStore, request: RequestBase) -> Scene | None:
    if isinstance(request, SceneShot):
        return store.scene(request.scene_id, request.scene_version)
    scene_id = getattr(request, "scene_id", None)
    if isinstance(request, SequenceFrames):
        scene_id = store.sequence(request.sequence_id).scene_id
    return store.scene(scene_id) if scene_id else None


# ------------------------------------------------------------------------------------------- prompts


def fragment(choices: PresetChoices, category: str, value: str | None) -> str:
    """The words of a preset (camera: its prefix; others: suffix); free text stays as it is."""
    if not value:
        return ""
    preset = choices.get(category, value)
    if preset is None:
        return value
    return (preset.prompt.prefix if category == "camera" else preset.prompt.suffix).strip()


def base_inputs(
    choices: PresetChoices,
    request: RequestBase,
    *,
    who: list[tuple[Subject, str | None]] | None = None,
    **values: Any,
) -> dict[str, Any]:
    """The prompt material of one output: preset wording, the camera's data, the style's forms and, for
    `who` (subject, state), the structured parts the dialects use (§8.8)."""
    pack = choices.get("style_pack")
    lighting = values.pop("lighting", None) or choices.choice("lighting")
    camera = values.pop("camera", None)
    camera_preset = choices.get("camera", camera) if camera else None
    inputs: dict[str, Any] = {
        "style_prefix": pack.prompt.prefix if pack else "",
        "style_suffix": pack.prompt.suffix if pack else "",
        "negative": ", ".join(
            x
            for x in [pack.prompt.negative if pack else "", *(n for s, _ in who or [] for n in s.never)]
            if x
        ),
        "lighting": fragment(choices, "lighting", lighting),
        "camera": fragment(choices, "camera", camera),
        "camera_angle": camera_preset.values.get("camera_angle") if camera_preset else None,
        "camera_values": {
            k: v for k, v in (camera_preset.values if camera_preset else {}).items() if k in CAMERA_DATA
        },
        "style": {
            "prefix": pack.prompt.prefix,
            "suffix": pack.prompt.suffix,
            "short": pack.values.get("short", ""),
            "dialects": pack.values.get("dialects", {}),
            "direction": choices.variation.direction,
        }
        if pack
        else {},
        "subject_parts": [subject_part(s, state) for s, state in who or []],
        "look": choices.look,
        "expression": fragment(choices, "expression", values.pop("expression", None)),
        "pose": fragment(choices, "pose", values.pop("pose", None)),
        "note": request.note,
    }
    return inputs | {k: v for k, v in values.items() if v not in (None, "")}


def subject_part(subject: Subject, state: str | None = None) -> dict[str, Any]:
    found = subject.state(state)
    return {
        "name": subject.name,
        "kind": subject.kind,
        "description": subject.description,
        "fields": dict(subject.fields),
        "state": (found.description or found.name) if found else state,
        "must": list(subject.must),
        "never": list(subject.never),
    }


def scene_conditions(store: ProjectStore, refs: list[PlannedRef], states: bool) -> list[str]:
    roles = {r.role for r in refs}
    flags = [f"{role}_ref" for role in ("identity", "object", "environment") if role in roles]
    kinds = {store.subject(r.subject_id).kind for r in refs if r.subject_id}
    return flags + (["character"] if "character" in kinds else []) + (["state"] if states else [])


def scene_output(
    store: ProjectStore,
    scene: Scene,
    built: Built,
    *,
    label: str,
    camera: str | None,
    seed_group: str | None = None,
    extra: dict[str, Any] | None = None,
    kind: str = "scene",
    judging: str = "scene-fidelity",
) -> PlannedOutput:
    refs, errors = scene_refs(store, scene, built.choices.variation.id)
    built.errors += errors
    who = [(store.subject(r.subject_id, r.version), r.state) for r in scene.refs]
    request = RequestBase()
    values: dict[str, Any] = {
        "description": scene.description,
        "action": scene.action,
        "framing": scene.framing,
        "gaze": scene.gaze,
        "camera": camera,
        "expression": scene.expression,
        "pose": scene.pose,
        "lighting": scene.lighting,
        "notes": scene.notes,
    } | (extra or {})
    links = [SubjectLink(subject_id=r.subject_id, version=r.version or 1) for r in scene.refs]
    has_state = any(r.state for r in scene.refs) or bool(values.get("state"))
    return built.add(
        label,
        kind,
        subjects=links,
        references=refs,
        judging=judging,
        seed_group=seed_group,
        conditions=scene_conditions(store, refs, has_state) + view_flags(camera),
        prompt_inputs=base_inputs(built.choices, request, who=who, **values),
    )


def product(axes: dict[str, list[str]]) -> list[dict[str, str]]:
    names = list(axes)
    return [dict(zip(names, combo, strict=True)) for combo in itertools.product(*(axes[n] for n in names))]
