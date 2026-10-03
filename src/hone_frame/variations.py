"""Variations (change 0005): several ways of drawing one world. The world (characters, places, objects,
scenes, the look guide) is shared; every generated image belongs to one variation."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from hone_frame._files import now, slug, write_json
from hone_frame.errors import InvalidRequest
from hone_frame.records import Project, Variation

if TYPE_CHECKING:
    from hone_frame.store import ProjectStore


def add_variation(
    store: ProjectStore, name: str, *, style_pack: str, direction: str = "", active: bool = True
) -> Variation:
    """A new way of drawing the world; the project's first variation keeps what was made before. With
    `active`, it becomes the one the dashboard and new requests use."""
    if not name.strip():
        raise InvalidRequest("a variation needs a name")
    store.workspace.presets.get("style_pack", style_pack)
    with store.lock():
        project = store.info
        existing = project.all_variations()
        base = slug(name)
        new_id, n = base, 1
        while any(v.id == new_id for v in existing):
            n += 1
            new_id = f"{base}-{n}"
        variation = Variation(
            id=new_id, name=name.strip(), style_pack=style_pack, direction=direction, created_at=now()
        )
        data: dict[str, Any] = project.model_dump() | {
            "variations": [v.model_dump() for v in [*existing, variation]],
            "updated_at": now(),
        }
        if active:
            data["variation"] = variation.id
        write_json(store.root / "project.json", Project.model_validate(data).model_dump(mode="json"))
    return variation


def edit_variation(store: ProjectStore, variation_id: str, **changes: Any) -> Variation:
    """Rename a variation or change its style or direction; its images keep how they were made."""
    if bad := sorted(set(changes) - {"name", "style_pack", "direction"}):
        raise InvalidRequest(f"cannot change {bad} of a variation; change its name, style_pack or direction")
    if "style_pack" in changes:
        store.workspace.presets.get("style_pack", str(changes["style_pack"]))
    with store.lock():
        project = store.info
        found = [
            v.model_copy(update=changes) if v.id == variation_id else v for v in project.all_variations()
        ]
        project.variation_of(variation_id)
        data = project.model_dump() | {"variations": [v.model_dump() for v in found], "updated_at": now()}
        write_json(store.root / "project.json", Project.model_validate(data).model_dump(mode="json"))
    return store.info.variation_of(variation_id)
