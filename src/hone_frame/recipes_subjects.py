"""Subject recipes (design §6.1): a subject's reference images (hero, then its presentation) and
character-object interactions."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from hone_frame.errors import InvalidRequest
from hone_frame.recipes import (
    HERO_CAMERA,
    OBJECT_FRAMING,
    JUDGING,
    Built,
    base_inputs,
    reference_lighting,
    reference_look,
    scene_conditions,
    view_flags,
)
from hone_frame.records import SceneRef, Subject, SubjectLink
from hone_frame.references import ref_images
from hone_frame.requests import Dependency, Interaction, PlannedRef, SubjectReferences

if TYPE_CHECKING:
    from hone_frame.store import ProjectStore


def subject_references(store: ProjectStore, request: SubjectReferences, built: Built) -> None:
    subject = store.subject(request.subject_id)
    link = SubjectLink(subject_id=subject.id, version=subject.version)
    role = (
        "environment"
        if subject.kind == "environment"
        else ("object" if subject.kind == "asset" else "identity")
    )
    common = {"subjects": [link], "judging": JUDGING[subject.kind]}
    lighting = reference_lighting(built, request)
    look, look_flags = reference_look(subject.kind)
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
            conditions=(["identity_ref"] if own else []) + look_flags,
            **common,
            prompt_inputs=base_inputs(
                built.choices,
                request,
                **look,
                who=[(subject, None)],
                full_body=subject.kind == "character",
                reference=True,
                camera=HERO_CAMERA[subject.kind],
                pose="neutral-standing" if subject.kind == "character" else None,
                framing=_hero_framing(subject.kind),
                lighting=lighting,
            ),
        )
        hero_ref = {"depends_on": [Dependency(output=hero.id, role=role)]}
    for spec in _presentation(store, request, subject, built):
        state = spec.pop("state", None)
        label = spec.pop("label")
        spec.setdefault("lighting", lighting)
        built.add(
            label,
            subject.kind,
            **common,
            **hero_ref,
            conditions=_conditions(subject.kind, spec, state) + look_flags,
            prompt_inputs=base_inputs(
                built.choices,
                request,
                **look,
                who=[(subject, state)],
                state=_state_words(subject, state),
                full_body=_full_body(subject.kind, spec),
                reference=True,
                **spec,
            ),
        )
    built.sheet_layout = request.sheet_layout


def _state_words(subject: Subject, state: str | None) -> str | None:
    found = subject.state(state)
    return (found.description or found.name) if found else state


def _full_body(kind: str, spec: dict[str, Any]) -> bool:
    """A character view that shows the whole figure (the turnaround, poses, outfits)."""
    return kind == "character" and (spec.get("pose") is not None or spec.get("camera") == "wide")


def _hero_framing(kind: str) -> str:
    return {
        "character": "full body from head to feet, centred, nothing cropped",
        "environment": "the whole place, its main anchors visible",
        "asset": OBJECT_FRAMING,
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
    return flags + view_flags(spec.get("camera"))


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
            who=[(s, None) for s in subjects],
            action=action,
            pose=request.pose,
            camera="medium",
        ),
    )


def _ref(subject_id: str, role: str) -> SceneRef:
    return SceneRef.model_validate({"subject_id": subject_id, "role": role})
