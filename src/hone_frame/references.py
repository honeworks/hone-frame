"""Reference roles, precedence, reduction and size limits (design §10)."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from PIL import Image

from hone_frame.records import ROLE_ORDER, Scene, SceneRef
from hone_frame.requests import PlannedRef

if TYPE_CHECKING:
    from hone_frame.store import ProjectStore

ACCEPTED = ("picked", "manual_pick", "imported")


def subject_images(store: ProjectStore, subject_id: str, image_ids: list[str] | None = None) -> list[str]:
    """The images a reference to this subject uses (design §10.1): the ones given, else the subject's
    chosen references, else its accepted hero, else its first accepted image."""
    if image_ids:
        return list(image_ids)
    subject = store.subject(subject_id)
    if subject.reference_images:
        return list(subject.reference_images)
    accepted = [
        r for r in store.images(subject_id=subject_id) if r.status in ACCEPTED and len(r.subjects) == 1
    ]
    heroes = [r for r in accepted if r.label.lower() == "hero"]
    if heroes:
        return [heroes[-1].id]
    return [accepted[0].id] if accepted else []


def scene_refs(store: ProjectStore, scene: Scene) -> tuple[list[PlannedRef], list[str]]:
    """Every reference of a scene, one per image, and the errors (a ref without a usable image)."""
    refs: list[PlannedRef] = []
    errors: list[str] = []
    for ref in scene.refs:
        planned = ref_images(store, ref)
        if not planned:
            name = store.subject(ref.subject_id).name
            errors.append(
                f"{name} ({ref.subject_id}) has no accepted image to use as its {ref.role} reference"
            )
        refs += planned
    return refs, errors


def ref_images(store: ProjectStore, ref: SceneRef) -> list[PlannedRef]:
    version = ref.version or store.subject(ref.subject_id).version
    return [
        PlannedRef(image_id=i, subject_id=ref.subject_id, version=version, role=ref.role)
        for i in subject_images(store, ref.subject_id, ref.image_ids)
    ]


def order(refs: list[PlannedRef]) -> list[PlannedRef]:
    """By role precedence; within a role, the order given (design §10.2)."""
    return sorted(refs, key=lambda r: ROLE_ORDER.index(r.role))


def reduce(
    store: ProjectStore, refs: list[PlannedRef], max_references: int | None, *, keep_order: bool = False
) -> tuple[list[PlannedRef], list[str], list[str]]:
    """Keep what the model takes; the rest become words. Returns (kept, text refs, warnings).
    `keep_order` is for promotions, whose draft must stay image 1."""
    ordered = list(refs) if keep_order else order(refs)
    limit = len(ordered) if max_references is None else max(max_references, 0)
    kept, dropped = ordered[:limit], ordered[limit:]
    words = [describe(store, r) for r in dropped]
    warnings = [
        f"reference {r.image_id} ({r.role}) left out: the model takes {limit}; described in words"
        for r in dropped
    ]
    return kept, words, warnings


def describe(store: ProjectStore, ref: PlannedRef) -> str:
    if ref.subject_id is None:
        return f"{ref.role}: image {ref.image_id}"
    subject = store.subject(ref.subject_id, ref.version)
    return f"{subject.name} ({subject.kind}, {ref.role}): {subject.description}".rstrip(": ")


def reduced_copy(source: Path, work: Path, max_px: int) -> Path:
    """`source`, or a copy in `work` whose long side is at most `max_px` (design §10.3)."""
    with Image.open(source) as picture:
        if max(picture.size) <= max_px:
            return source
        copy = picture.convert("RGB")
    copy.thumbnail((max_px, max_px), Image.Resampling.LANCZOS)
    work.mkdir(parents=True, exist_ok=True)
    target = work / f"{source.stem}-{max_px}.png"
    copy.save(target, format="PNG")
    return target
