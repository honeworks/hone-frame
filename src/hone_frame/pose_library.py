"""The pose library (change 0005): a plain wooden artist's mannequin in each pose, drawn once per project
and reused as the `pose` reference of every character's pose image. An edit model keeps the pose of the
image it is shown; given the mannequin, it takes the pose from it instead (tested on FLUX.2 klein:
kneeling, running and sitting came out right only with the mannequin)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from hone_frame.references import ACCEPTED
from hone_frame.requests import Dependency, PlannedOutput, PlannedRef

if TYPE_CHECKING:
    from hone_frame.recipes import Built
    from hone_frame.store import ProjectStore

PACK = "pose-library"
NEUTRAL = {
    "standing upright in a relaxed neutral pose, arms slightly away from the body, full figure visible"
}


def mannequin_prompt(pose: str) -> str:
    return (
        "A plain smooth light-grey wooden artist's mannequin with no face, no hair and no clothes, "
        f"{pose}, seen from the front at a slight angle, the whole figure from head to feet, on a plain "
        "pure white background, even studio light."
    )


def key(pose: str) -> str:
    return " ".join(pose.lower().split()).rstrip(".")


def accepted_mannequin(store: ProjectStore, pose: str) -> str | None:
    """The project's accepted mannequin image for this pose, or None (mannequins belong to no variation)."""
    found = [i for i in store.images() if i.pack == PACK and i.item == key(pose) and i.status in ACCEPTED]
    return found[-1].id if found else None


def pose_reference(store: ProjectStore, built: Built, pose: str, made: dict[str, str]) -> dict[str, Any]:
    """The `pose` reference of a pose image: the accepted mannequin, or one drawn first in this request
    (`made`: pose key -> its output here). Nothing for the neutral standing pose."""
    if key(pose) in NEUTRAL:
        return {}
    if image := accepted_mannequin(store, pose):
        return {"references": [PlannedRef(image_id=image, role="pose")]}
    if key(pose) not in made:
        made[key(pose)] = _add(built, pose).id
    return {"depends_on": [Dependency(output=made[key(pose)], role="pose")]}


def _add(built: Built, pose: str) -> PlannedOutput:
    return built.add(
        f"Mannequin: {key(pose)}",
        "pose",
        judging="pose-reference",
        conditions=["clean_background"],
        pack=PACK,
        item=key(pose),
        prompt_inputs={
            "fixed_prompt": mannequin_prompt(pose),
            "pose": pose,
            "full_body": True,
            "background": "a plain pure white background",
        },
    )
