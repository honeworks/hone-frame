"""The dashboard API's variation and whole-world routes (change 0005)."""

from __future__ import annotations

from typing import Any

from hone_frame._dashboard_api import ID, P, api, json_body
from hone_frame._dashboard_data import image_card
from hone_frame.characters import belonging_row, variation_id
from hone_frame.cleanup import cleanup, cleanup_candidates
from hone_frame.recipes_packs import accepted_hero
from hone_frame.records import Selection
from hone_frame.workspace import Workspace
from hone_frame.world_runs import generate_world, world_plan


def _variations(ws: Workspace, project_id: str) -> dict[str, Any]:
    info = ws.project(project_id).info
    return {
        "active": info.variation_of().id,
        "variations": [v.model_dump(mode="json") for v in info.all_variations()],
        "look": info.look_guide,
    }


@api("GET", P + "/variations")
def variations(ws: Workspace, project_id: str, **_: Any) -> dict[str, Any]:
    return _variations(ws, project_id)


@api("POST", P + "/variations")
def add_variation(ws: Workspace, project_id: str, *, body: Any, **_: Any) -> dict[str, Any]:
    data = json_body(body)
    ws.project(project_id).add_variation(
        str(data.get("name", "")),
        style_pack=str(data.get("style_pack") or "cinematic-realism"),
        direction=str(data.get("direction", "")),
        active=bool(data.get("active", True)),
    )
    return _variations(ws, project_id)


@api("PATCH", P + "/variations/" + ID)
def edit_variation(ws: Workspace, project_id: str, variation: str, *, body: Any, **_: Any) -> dict[str, Any]:
    ws.project(project_id).edit_variation(variation, **json_body(body))
    return _variations(ws, project_id)


@api("POST", P + "/variations/" + ID + "/use")
def use_variation(ws: Workspace, project_id: str, variation: str, **_: Any) -> dict[str, Any]:
    ws.project(project_id).use_variation(variation)
    return _variations(ws, project_id)


def _selection(data: dict[str, Any]) -> Selection | None:
    rounds = data.get("rounds")
    return Selection(rounds=int(rounds)) if rounds else None


@api("POST", P + "/world/plan")
def plan_world(ws: Workspace, project_id: str, *, body: Any, **_: Any) -> dict[str, Any]:
    data = json_body(body) if body is not None else {}
    store = ws.project(project_id)
    return world_plan(store, data.get("variation") or None, profile=str(data.get("profile") or ""),
                      selection=_selection(data))  # fmt: skip


@api("POST", P + "/world/generate-all")
def generate_all(ws: Workspace, project_id: str, *, body: Any, **_: Any) -> dict[str, Any]:
    data = json_body(body) if body is not None else {}
    store = ws.project(project_id)
    return generate_world(store, data.get("variation") or None, profile=str(data.get("profile") or ""),
                          selection=_selection(data))  # fmt: skip


@api("GET", P + "/objects/" + ID)
def object_row(ws: Workspace, project_id: str, subject_id: str, **_: Any) -> dict[str, Any]:
    """An object's hero and views in the active variation, as a page section (change 0005)."""
    store = ws.project(project_id)
    return belonging_row(store, store.subject(subject_id), variation_id(store, None))


@api("GET", P + "/subjects/" + ID + "/compare")
def compare(ws: Workspace, project_id: str, subject_id: str, **_: Any) -> list[dict[str, Any]]:
    """The subject's accepted hero in every variation, side by side."""
    store = ws.project(project_id)
    rows: list[dict[str, Any]] = []
    for v in store.info.all_variations():
        hero = accepted_hero(store, subject_id, variation_id(store, v.id))
        card = image_card(store, store.image(hero)) if hero else None
        rows.append({"variation": v.model_dump(mode="json"), "hero": card})
    return rows


@api("POST", P + "/cleanup")
def clean_up(ws: Workspace, project_id: str, *, body: Any, **_: Any) -> dict[str, Any]:
    """`{"what": "unchosen" | "variation", "variation", "dry_run"}`: what a clean-up deletes, or do it."""
    data = json_body(body)
    store = ws.project(project_id)
    what = "variation" if data.get("what") == "variation" else "unchosen"
    variation = str(data.get("variation") or "") or None
    if data.get("dry_run"):
        return {"images": len(cleanup_candidates(store, what, variation))}
    return cleanup(store, what, variation)
