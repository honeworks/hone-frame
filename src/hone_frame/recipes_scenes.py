"""Scene recipes (design §6.1, §10.5): state pairs, sequences, variation grids and promotion."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from hone_frame._files import read_json
from hone_frame.errors import InvalidRequest, NotFound
from hone_frame.recipes import JUDGING, Built, base_inputs, product, scene_output, subject_text, view_flags
from hone_frame.records import Scene, SubjectLink
from hone_frame.references import subject_images
from hone_frame.requests import (
    Dependency,
    PlannedOutput,
    PlannedRef,
    Promote,
    SequenceFrames,
    StatePair,
    Variations,
)

if TYPE_CHECKING:
    from hone_frame.store import ProjectStore

AXES = {"outfit", "expression", "lighting", "camera", "state", "style", "pose"}


def state_pair_outputs(store: ProjectStore, request: StatePair, scene: Scene | None, built: Built) -> None:
    preset = built.choices.get("state", request.state)
    if preset is None:
        raise InvalidRequest(f"unknown state preset {request.state!r}")
    before, after = preset.values["before"], preset.values["after"]
    group = "pair" if request.same_framing else None
    first: PlannedOutput | None = None
    for name, words in ((before, preset.values["before_prompt"]), (after, preset.values["after_prompt"])):
        label = f"{name.capitalize()}"
        deps = [Dependency(output=first.id, role="composition")] if first and request.same_framing else []
        if scene is not None:
            out = scene_output(
                store,
                scene,
                built,
                label=label,
                camera=scene.camera,
                seed_group=group,
                extra={"state": words},
            )
        elif request.subject_id:
            out = _subject_output(
                store,
                request.subject_id,
                built,
                request=request,
                label=label,
                extra={"state": words},
                group=group,
            )
        else:
            raise InvalidRequest("a state pair needs a subject_id or a scene_id")
        out.depends_on = deps
        out.conditions = sorted({*out.conditions, "state"})
        first = first or out


def sequence_outputs(store: ProjectStore, request: SequenceFrames, built: Built) -> None:
    sequence = store.sequence(request.sequence_id)
    scene = store.scene(sequence.scene_id)
    previous: PlannedOutput | None = None
    for n, frame in enumerate(sequence.frames, start=1):
        change = (
            f"from {frame.start_state} to {frame.end_state}" if frame.start_state or frame.end_state else ""
        )
        out = scene_output(
            store,
            scene,
            built,
            label=f"{n}. {frame.description or frame.id}",
            camera=scene.camera,
            kind="sequence_frame",
            judging="sequence-continuity",
            extra={
                "description": f"{scene.description} {frame.description}".strip(),
                "action": frame.change,
                "state": change,
                "frame": f"frame {n} of {len(sequence.frames)}",
            },
        )
        if previous is not None and frame.use_previous:
            out.depends_on = [Dependency(output=previous.id, role="composition")]
            out.conditions = sorted({*out.conditions, "previous"})
        if change:
            out.conditions = sorted({*out.conditions, "state"})
        previous = out


def variation_outputs(store: ProjectStore, request: Variations, scene: Scene | None, built: Built) -> None:
    if unknown := sorted(set(request.axes) - AXES):
        raise InvalidRequest(f"unknown variation axes {unknown}; use {sorted(AXES)}")
    for combo in product(request.axes):
        label = " · ".join(f"{k}: {v}" for k, v in combo.items())
        extra = _axis_values(built, combo)
        if scene is not None:
            scene_output(
                store,
                scene,
                built,
                label=label,
                camera=extra.pop("camera", scene.camera),
                seed_group="grid",
                extra=extra,
            )
        elif request.subject_id:
            _subject_output(
                store, request.subject_id, built, request=request, label=label, extra=extra, group="grid"
            )
        else:
            raise InvalidRequest("a variation grid needs a scene_id or a subject_id")


def _axis_values(built: Built, combo: dict[str, str]) -> dict[str, Any]:
    extra: dict[str, Any] = {
        k: v for k, v in combo.items() if k in {"camera", "lighting", "expression", "pose"}
    }
    states = [combo[k] for k in ("outfit", "state") if k in combo]
    if states:
        extra["state"] = ", ".join(states)
    if "style" in combo:
        pack = built.choices.get("style_pack", combo["style"])
        if pack is not None:
            extra |= {"style_prefix": pack.prompt.prefix, "style_suffix": pack.prompt.suffix}
    return extra


def _subject_output(
    store: ProjectStore,
    subject_id: str,
    built: Built,
    *,
    request: Any,
    label: str,
    extra: dict[str, Any],
    group: str | None,
) -> PlannedOutput:
    subject = store.subject(subject_id)
    role = (
        "environment"
        if subject.kind == "environment"
        else ("object" if subject.kind == "asset" else "identity")
    )
    images = subject_images(store, subject.id)
    if not images:
        built.errors.append(
            f"{subject.name} ({subject.id}) has no accepted image yet: make its references first"
        )
    refs = [PlannedRef(image_id=i, subject_id=subject.id, version=subject.version, role=role) for i in images]
    flags = ["identity_ref"] + (["character"] if subject.kind == "character" else [])
    flags += [k for k in ("expression", "pose", "state") if extra.get(k)]
    flags += view_flags(extra.get("camera", "front"))
    return built.add(
        label,
        subject.kind,
        subjects=[SubjectLink(subject_id=subject.id, version=subject.version)],
        references=refs,
        judging=JUDGING[subject.kind],
        seed_group=group,
        conditions=flags,
        prompt_inputs=base_inputs(
            built.choices,
            request,
            subjects=[subject_text(subject)],
            camera=extra.pop("camera", "front"),
            **extra,
        ),
    )


def promote_outputs(store: ProjectStore, request: Promote, built: Built) -> None:
    image = store.image(request.image_id)
    if request.operation == "regenerate":
        used = [
            PlannedRef(image_id=r.image_id, role=r.role)  # pyright: ignore[reportArgumentType]
            for r in (image.generation.references if image.generation else [])
        ]
        planned = _planned_of(store, image.run_id, image.output_id)
        built.outputs.append(
            planned.model_copy(
                update={
                    "id": "o01",
                    "parent": image.id,
                    "depends_on": [],
                    "references": used or planned.references,
                }
            )
        )
        return
    if image.generation is None:
        raise InvalidRequest(
            f"{image.id} was not generated here: only generated images can be {request.operation}d"
        )
    refs = [PlannedRef(image_id=image.id, role="composition")]
    if request.operation == "refine":
        refs += [PlannedRef(image_id=r.image_id, role=r.role) for r in image.generation.references]  # pyright: ignore[reportArgumentType]
    kind = image.kind if image.kind != "scene" else "scene"
    built.add(
        f"{request.operation.capitalize()} {image.id}",
        "promotion",
        subjects=image.subjects,
        references=refs,
        judging=JUDGING.get(kind, "scene-fidelity"),
        parent=image.id,
        mode="upscale" if request.operation == "upscale" else "generate",
        conditions=["preserve", *(["identity_ref"] if len(refs) > 1 else [])],
        prompt_inputs={
            "prompt_override": image.generation.prompt,
            "operation": request.operation,
            "negative": image.generation.negative or "",
        },
    )


def _planned_of(store: ProjectStore, run_id: str | None, output_id: str | None) -> PlannedOutput:
    path = store.root / "runs" / str(run_id) / "run.json"
    if not run_id or not output_id or not path.is_file():
        raise InvalidRequest(
            "only an image made by a run here can be regenerated (its definition is in the run)"
        )
    for row in read_json(path)["plan"]["outputs"]:
        if row["id"] == output_id:
            return PlannedOutput.model_validate(row)
    raise NotFound(f"run {run_id} has no output {output_id}")
