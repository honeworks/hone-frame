"""The dashboard API's character-first routes (change 0003): the project home, characters and their packs,
the world, and generating assets."""

from __future__ import annotations

from typing import Any

from hone_frame._dashboard_api import ID, ApiError, P, api, json_body
from hone_frame._dashboard_data import overview, run_summary
from hone_frame.characters import (
    character_cards,
    character_page,
    model_sheet_recipe,
    world,
    world_requests,
)
from hone_frame.errors import HoneFrameError
from hone_frame.project_file import import_file, parse, project_file
from hone_frame.requests import CharacterPacks
from hone_frame.workspace import Workspace


@api("GET", P + "/home")
def home(ws: Workspace, project_id: str, **_: Any) -> dict[str, Any]:
    store = ws.project(project_id)
    return overview(store) | {
        "project": store.info.model_dump(mode="json"),
        "characters": character_cards(store),
        "world": world(store),
        "scenes": [s.model_dump(mode="json") for s in store.scenes()],
    }


@api("GET", P + "/characters")
def characters(ws: Workspace, project_id: str, **_: Any) -> list[dict[str, Any]]:
    return character_cards(ws.project(project_id))


@api("GET", P + "/characters/" + ID)
def character(ws: Workspace, project_id: str, subject_id: str, **_: Any) -> dict[str, Any]:
    return character_page(ws.project(project_id), subject_id)


@api("POST", P + "/characters/" + ID + "/generate")
def generate_character(
    ws: Workspace, project_id: str, subject_id: str, *, body: Any, **_: Any
) -> dict[str, Any]:
    data = json_body(body) if body is not None else {}
    request = CharacterPacks.model_validate({**data, "subject_id": subject_id})
    return run_summary(ws.project(project_id).submit(request))


@api("POST", P + "/characters/" + ID + "/sheet")
def character_sheet(ws: Workspace, project_id: str, subject_id: str, **_: Any) -> dict[str, Any]:
    store = ws.project(project_id)
    try:
        recipe = model_sheet_recipe(store, subject_id)
    except HoneFrameError as exc:
        raise ApiError(str(exc)) from exc
    same = next((s for s in store.sheets() if s.recipe.name == recipe.name), None)
    sheet = store.save_sheet(recipe, sheet_id=same.id if same else None)
    path = store.compose_sheet(sheet.id)
    return store.sheet(sheet.id).model_dump(mode="json") | {
        "url": f"/files/{store.id}/{path.relative_to(store.root)}"
    }


@api("GET", P + "/world")
def world_assets(ws: Workspace, project_id: str, **_: Any) -> list[dict[str, Any]]:
    return world(ws.project(project_id))


@api("POST", P + "/world/generate")
def generate_world(ws: Workspace, project_id: str, *, body: Any, **_: Any) -> list[dict[str, Any]]:
    store = ws.project(project_id)
    data = json_body(body) if body is not None else {}
    chosen: Any = data.get("subject_ids")
    ids = [str(i) for i in chosen] if isinstance(chosen, list) else None  # pyright: ignore[reportUnknownArgumentType, reportUnknownVariableType]
    requests = world_requests(store, ids)
    if not requests:
        raise ApiError("every world asset already has an accepted image: nothing to generate")
    return [run_summary(store.submit(r)) for r in requests]


@api("POST", "/import")
def import_project(ws: Workspace, *, body: Any, **_: Any) -> dict[str, Any]:
    """`{"text": <the file>, "format": "toml" | "json"}`: create or update a project (change 0004)."""
    data = json_body(body)
    return import_file(ws, parse(str(data.get("text", "")), str(data.get("format", "")))).model_dump()


@api("GET", P + "/file")
def export_project_file(ws: Workspace, project_id: str, **_: Any) -> dict[str, Any]:
    return project_file(ws.project(project_id))
