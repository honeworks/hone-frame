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


BUILD_WORDS = {"slight": "a slender", "average": "a well-proportioned", "heavy": "a broad, heavy-set"}


def mannequin_prompt(pose: str, build: str = "average") -> str:
    """The mannequin's wording; its build follows the character's (change 0007), its hands stay empty so
    the edit takes the pose and not an object."""
    body = BUILD_WORDS.get(build, BUILD_WORDS["average"])
    return (
        f"A plain smooth light-grey wooden artist's mannequin, {body} figure, with no face, no hair and no "
        f"clothes, {pose}, empty hands holding nothing, seen from the front at a slight angle, the whole "
        "figure from head to feet, on a plain pure white background, even studio light."
    )


def key(pose: str) -> str:
    return " ".join(pose.lower().split()).rstrip(".")


def item_key(pose: str, build: str) -> str:
    """A mannequin per pose and build class (change 0007); the average build keeps the plain key."""
    return key(pose) if build == "average" else f"{key(pose)}|{build}"


def accepted_mannequin(store: ProjectStore, pose: str, build: str = "average") -> str | None:
    """The project's accepted mannequin image for this pose, or None (mannequins belong to no variation)."""
    wanted = item_key(pose, build)
    found = [i for i in store.images() if i.pack == PACK and i.item == wanted and i.status in ACCEPTED]
    return found[-1].id if found else None


def pose_reference(
    store: ProjectStore, built: Built, pose: str, made: dict[str, str], build: str = "average"
) -> dict[str, Any]:
    """The `pose` reference of a pose image: the accepted mannequin, or one drawn first in this request
    (`made`: mannequin key -> its output here). Nothing for the neutral standing pose."""
    if key(pose) in NEUTRAL:
        return {}
    if image := accepted_mannequin(store, pose, build):
        return {"references": [PlannedRef(image_id=image, role="pose")]}
    wanted = item_key(pose, build)
    if wanted not in made:
        made[wanted] = _add(built, pose, build).id
    return {"depends_on": [Dependency(output=made[wanted], role="pose")]}


def _add(built: Built, pose: str, build: str = "average") -> PlannedOutput:
    return built.add(
        f"Mannequin: {item_key(pose, build)}",
        "pose",
        judging="pose-reference",
        conditions=["clean_background"],
        pack=PACK,
        item=item_key(pose, build),
        prompt_inputs={
            "fixed_prompt": mannequin_prompt(pose, build),
            "pose": pose,
            "full_body": True,
            "empty_hands": True,
            "background": "a plain pure white background",
        },
    )
