"""Recipes: a request becomes planned outputs (design §6.1). Models and reductions are `planning.py`'s."""

from __future__ import annotations

import itertools
from typing import TYPE_CHECKING, Any

from hone_frame.errors import InvalidRequest
from hone_frame.profiles import PresetChoices
from hone_frame.records import Scene, SceneRef, Subject, SubjectLink
from hone_frame.references import ref_images, scene_refs
from hone_frame.requests import (
    Coverage,
    Dependency,
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


class Built:
    """What a recipe produced: the outputs, the errors found, the presets used, an optional sheet."""

    def __init__(self, choices: PresetChoices) -> None:
        self.choices = choices
        self.outputs: list[PlannedOutput] = []
        self.errors: list[str] = []
        self.sheet_layout: str | None = None

    def add(self, label: str, kind: str, **fields: Any) -> PlannedOutput:
        out = PlannedOutput(id=f"o{len(self.outputs) + 1:02d}", label=label, kind=kind, **fields)
        self.outputs.append(out)
        return out


def build(store: ProjectStore, request: RequestBase) -> Built:
    from hone_frame._recipes_more import (  # noqa: PLC0415 - that module imports this one
        promote_outputs,
        sequence_outputs,
        state_pair_outputs,
        variation_outputs,
    )

    scene = _scene_of(store, request)
    built = Built(PresetChoices(store, request, scene.overrides if scene else None))
    if isinstance(request, SubjectReferences):
        subject_references(store, request, built)
    elif isinstance(request, SceneShot | Coverage):
        if scene is None:
            raise InvalidRequest("a scene shot needs a scene")
        cameras = request.cameras if isinstance(request, Coverage) else [scene.camera]
        for camera in cameras:
            scene_output(
                store,
                scene,
                built,
                label=camera or scene.name,
                camera=camera,
                seed_group="coverage" if isinstance(request, Coverage) else None,
            )
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
    return built


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


def base_inputs(choices: PresetChoices, request: RequestBase, **values: Any) -> dict[str, Any]:
    pack = choices.get("style_pack")
    lighting = values.pop("lighting", None) or choices.choice("lighting")
    camera = values.pop("camera", None)
    camera_preset = choices.get("camera", camera) if camera else None
    inputs: dict[str, Any] = {
        "style_prefix": pack.prompt.prefix if pack else "",
        "style_suffix": pack.prompt.suffix if pack else "",
        "negative": pack.prompt.negative if pack else "",
        "lighting": fragment(choices, "lighting", lighting),
        "camera": fragment(choices, "camera", camera),
        "camera_angle": camera_preset.values.get("camera_angle") if camera_preset else None,
        "expression": fragment(choices, "expression", values.pop("expression", None)),
        "pose": fragment(choices, "pose", values.pop("pose", None)),
        "note": request.note,
    }
    return inputs | {k: v for k, v in values.items() if v not in (None, "")}


def subject_text(subject: Subject, state: str | None = None) -> str:
    details = "; ".join(f"{k}: {_flat(v)}" for k, v in subject.fields.items() if v)
    text = f"{subject.name} ({subject.kind}): {subject.description}" + (f"; {details}" if details else "")
    found = subject.state(state)
    if state:
        text += f"; state: {found.description or found.name if found else state}"
    return text


def _flat(value: Any) -> str:
    if isinstance(value, list | tuple):
        items: list[Any] = list(value)  # pyright: ignore[reportUnknownArgumentType]
        return ", ".join(str(v) for v in items)
    return str(value)


# ------------------------------------------------------------------------------------------ recipes


def subject_references(store: ProjectStore, request: SubjectReferences, built: Built) -> None:
    subject = store.subject(request.subject_id)
    link = SubjectLink(subject_id=subject.id, version=subject.version)
    role = (
        "environment"
        if subject.kind == "environment"
        else ("object" if subject.kind == "asset" else "identity")
    )
    common = {"subjects": [link], "judging": JUDGING[subject.kind]}
    text = subject_text(subject)
    if request.hero_image:
        store.image(request.hero_image)
        hero_ref: dict[str, Any] = {
            "references": [
                PlannedRef(
                    image_id=request.hero_image, subject_id=subject.id, version=subject.version, role=role
                )
            ]
        }
    else:
        own = [
            PlannedRef(image_id=i, subject_id=subject.id, version=subject.version, role=role)
            for i in subject.reference_images
        ]
        hero = built.add(
            "Hero",
            subject.kind,
            references=own,
            conditions=["identity_ref"] if own else [],
            **common,
            prompt_inputs=base_inputs(
                built.choices,
                request,
                subjects=[text],
                camera=HERO_CAMERA[subject.kind],
                pose="neutral-standing" if subject.kind == "character" else None,
                framing=_hero_framing(subject.kind),
            ),
        )
        hero_ref = {"depends_on": [Dependency(output=hero.id, role=role)]}
    for spec in _presentation(store, request, subject, built):
        state = spec.pop("state", None)
        label = spec.pop("label")
        built.add(
            label,
            subject.kind,
            **common,
            **hero_ref,
            conditions=_conditions(subject.kind, spec, state),
            prompt_inputs=base_inputs(
                built.choices, request, subjects=[subject_text(subject, state)], state=state, **spec
            ),
        )
    built.sheet_layout = request.sheet_layout


def _hero_framing(kind: str) -> str:
    return {
        "character": "full body from head to feet, centred, nothing cropped",
        "environment": "the whole place, its main anchors visible",
        "asset": "the whole object centred on a plain background",
    }[kind]


def _presentation(
    store: ProjectStore, request: SubjectReferences, subject: Subject, built: Built
) -> list[dict[str, Any]]:
    category = f"{subject.kind}_presentation"
    preset = built.choices.get(category, request.presentation)
    if preset is None:
        raise InvalidRequest(f"no {category} preset chosen")
    specs: list[dict[str, Any]] = [dict(o) for o in preset.values.get("outputs", [])]
    if kind := preset.values.get("from_states"):
        base = {k: preset.values[k] for k in ("camera", "pose") if k in preset.values}
        specs += [{"label": s.name, "state": s.name, **base} for s in subject.states if s.kind == kind]
    specs += [{"label": e, "expression": e, "camera": "close-up"} for e in request.expressions]
    specs += [{"label": p, "pose": p, "camera": "wide"} for p in request.poses]
    specs += [{"label": s, "state": s, "camera": "front"} for s in request.states]
    return specs


def _conditions(kind: str, spec: dict[str, Any], state: str | None) -> list[str]:
    flags = ["identity_ref"]
    flags += [k for k in ("expression", "pose") if spec.get(k)]
    flags += ["state"] if state else []
    flags += ["character"] if kind == "character" else []
    return flags


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
    refs, errors = scene_refs(store, scene)
    built.errors += errors
    texts = [subject_text(store.subject(r.subject_id, r.version), r.state) for r in scene.refs]
    request = RequestBase()
    values: dict[str, Any] = {
        "subjects": texts,
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
        conditions=scene_conditions(store, refs, has_state),
        prompt_inputs=base_inputs(built.choices, request, **values),
    )


def interaction(store: ProjectStore, request: Interaction, built: Built) -> None:
    character, asset = store.subject(request.character_id), store.subject(request.asset_id)
    preset = built.choices.get("interaction", request.action)
    action = (preset.prompt.suffix if preset else request.action).format(
        character=character.name, asset=asset.name
    )
    refs = ref_images(store, _ref(character.id, "identity")) + ref_images(store, _ref(asset.id, "object"))
    subjects = [character, asset]
    if request.environment_id:
        refs += ref_images(store, _ref(request.environment_id, "environment"))
        subjects.append(store.subject(request.environment_id))
    if request.pose_image:
        store.image(request.pose_image)
        refs.append(PlannedRef(image_id=request.pose_image, role="pose"))
    for subject in subjects:
        if not any(r.subject_id == subject.id for r in refs):
            built.errors.append(f"{subject.name} ({subject.id}) has no accepted image to use as a reference")
    built.add(
        preset.name if preset else "Interaction",
        "interaction",
        references=refs,
        subjects=[SubjectLink(subject_id=s.id, version=s.version) for s in subjects],
        judging="interaction-plausibility",
        conditions=scene_conditions(store, refs, False),
        prompt_inputs=base_inputs(
            built.choices,
            request,
            subjects=[subject_text(s) for s in subjects],
            action=action,
            pose=request.pose,
            camera="medium",
        ),
    )


def _ref(subject_id: str, role: str) -> SceneRef:
    return SceneRef.model_validate({"subject_id": subject_id, "role": role})


def product(axes: dict[str, list[str]]) -> list[dict[str, str]]:
    names = list(axes)
    return [dict(zip(names, combo, strict=True)) for combo in itertools.product(*(axes[n] for n in names))]
