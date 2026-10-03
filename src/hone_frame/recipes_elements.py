"""Worn elements and action poses (change 0007).

A worn element (a crown, an armlet) is an owned object with `worn = true` and `worn_on`. It gets its own
hero and views like a belonging, is never an action, and appears in the owner's images as a line
("Zahhak's crown on his head"); its hero is a reference image only in full-figure views that are not
poses, when the model has a free slot. An action names how the belonging is used (`use_pose`), and the
pose library's mannequin shows the pose.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from hone_frame.recipes_packs import accepted_hero, owned_assets
from hone_frame.records import Subject

if TYPE_CHECKING:
    from hone_frame.store import ProjectStore

HEAD = ("head", "neck", "brow", "forehead", "ear", "face")
DEFAULT_USE = {"long": "both arms raised high overhead, the hands closed together around an empty grip"}


def is_worn(asset: Subject) -> bool:
    return bool(asset.fields.get("worn"))


def worn_elements(store: ProjectStore, character: Subject) -> list[Subject]:
    return [a for a in owned_assets(store, character.id) if is_worn(a)]


def worn_lines(store: ProjectStore, character: Subject, close_up: bool) -> list[str]:
    """The worn elements a picture shows, as lines; a close-up only those on the head or neck."""
    lines: list[str] = []
    for a in worn_elements(store, character):
        where = str(a.fields.get("worn_on") or "").strip()
        if close_up and not any(w in where.lower() for w in HEAD):
            continue
        lines.append(f"{a.name} on {where}" if where else a.name)
    return lines


def element_reference(store: ProjectStore, character: Subject, variation: str) -> tuple[Subject, str] | None:
    """The first worn element with an accepted hero, to pass as a reference image."""
    for a in worn_elements(store, character):
        if image := accepted_hero(store, a.id, variation):
            return a, image
    return None


def use_pose(asset: Subject) -> str:
    """How an action holds the belonging: its own `use_pose`, or the default for its shape."""
    own = str(asset.fields.get("use_pose") or "").strip()
    return own or DEFAULT_USE.get(str(asset.fields.get("shape") or ""), "")


def action_text(character: Subject, asset: Subject) -> str:
    """The action sentence: "<name>, <use pose>, with <belonging>: <what it is>"."""
    pose = use_pose(asset)
    about = f"{asset.name}: {asset.description}".rstrip(": ")
    size = str(asset.fields.get("scale") or "").strip()
    holding = (
        f"{character.name}, {pose}, with {about}" if pose else f"{character.name} holds and uses {about}"
    )
    return ", ".join(x for x in (holding, size) if x)


def mannequin_pose(asset: Subject) -> str:
    """The pose the mannequin shows for an action: the use pose without the object."""
    return use_pose(asset)


def element_fields(spec: dict[str, Any]) -> dict[str, Any]:
    return {k: spec[k] for k in ("worn",) if k in spec}
