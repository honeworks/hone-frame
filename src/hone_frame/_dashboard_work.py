"""The dashboard API's work routes (design §12.2): scenes, sequences, sheets, plans, runs, exports."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from hone_frame._dashboard_api import ID, ApiError, P, api, json_body, subject_card
from hone_frame._dashboard_data import image_card, run_page, run_summary
from hone_frame.records import Scene, Sequence, SheetRecipe
from hone_frame.runs import all_runs, view
from hone_frame.workspace import Workspace

# --------------------------------------------------------------------------- scenes, sequences, sheets


@api("GET", P + "/scenes")
def scenes(ws: Workspace, project_id: str, **_: Any) -> list[dict[str, Any]]:
    return [s.model_dump(mode="json") for s in ws.project(project_id).scenes()]


@api("POST", P + "/scenes")
def save_scene(ws: Workspace, project_id: str, *, body: Any, **_: Any) -> dict[str, Any]:
    return ws.project(project_id).save_scene(Scene.model_validate(json_body(body))).model_dump(mode="json")


@api("GET", P + "/scenes/" + ID)
def scene(ws: Workspace, project_id: str, scene_id: str, **_: Any) -> dict[str, Any]:
    store = ws.project(project_id)
    found = store.scene(scene_id)
    refs = [
        {"ref": r.model_dump(mode="json"), "subject": subject_card(store, r.subject_id)} for r in found.refs
    ]
    results = [
        image_card(store, i)
        for r in all_runs(store)
        if r.plan.request.get("scene_id") == scene_id
        for i in store.images()
        if i.run_id == r.id
    ]
    return found.model_dump(mode="json") | {"resolved": refs, "results": results[::-1]}


@api("GET", P + "/sequences")
def sequences(ws: Workspace, project_id: str, **_: Any) -> list[dict[str, Any]]:
    return [s.model_dump(mode="json") for s in ws.project(project_id).sequences()]


@api("POST", P + "/sequences")
def save_sequence(ws: Workspace, project_id: str, *, body: Any, **_: Any) -> dict[str, Any]:
    return (
        ws.project(project_id).save_sequence(Sequence.model_validate(json_body(body))).model_dump(mode="json")
    )


@api("GET", P + "/sheets")
def sheets(ws: Workspace, project_id: str, **_: Any) -> list[dict[str, Any]]:
    store = ws.project(project_id)
    return [
        s.model_dump(mode="json") | {"url": f"/files/{store.id}/{s.render}" if s.render else None}
        for s in store.sheets()
    ]


@api("POST", P + "/sheets")
def save_sheet(ws: Workspace, project_id: str, *, body: Any, **_: Any) -> dict[str, Any]:
    data = json_body(body)
    store = ws.project(project_id)
    sheet = store.save_sheet(
        SheetRecipe.model_validate(data.get("recipe", data)), sheet_id=data.get("id") or None
    )
    path = store.compose_sheet(sheet.id)
    return store.sheet(sheet.id).model_dump(mode="json") | {
        "url": f"/files/{store.id}/{path.relative_to(store.root)}"
    }


# ----------------------------------------------------------------------------------------------- runs


@api("POST", P + "/plan")
def plan(ws: Workspace, project_id: str, *, body: Any, **_: Any) -> dict[str, Any]:
    return ws.project(project_id).plan(json_body(body)).model_dump(mode="json")


@api("POST", P + "/runs")
def submit(ws: Workspace, project_id: str, *, body: Any, **_: Any) -> dict[str, Any]:
    return run_summary(ws.project(project_id).submit(json_body(body)))


@api("GET", "/runs")
def runs(ws: Workspace, *, query: dict[str, str], **_: Any) -> list[dict[str, Any]]:
    wanted = [query["project"]] if query.get("project") and query.get("scope") != "all" else None
    found: list[dict[str, Any]] = []
    for p in ws.projects():
        if wanted is None or p.id in wanted:
            store = ws.project(p.id)
            found += [run_summary(view(store, r)) for r in all_runs(store)]
    return sorted(found, key=lambda r: r["created_at"], reverse=True)


@api("GET", "/runs/([a-z0-9-]+)/" + ID)
def run(ws: Workspace, project_id: str, run_id: str, *, query: dict[str, str], **_: Any) -> dict[str, Any]:
    return run_page(ws.project(project_id), run_id, int(query.get("since") or 0))


@api("POST", "/runs/([a-z0-9-]+)/" + ID + "/(pause|cancel|resume|retry|rerun|pick)")
def run_action(
    ws: Workspace, project_id: str, run_id: str, action: str, *, body: Any, **_: Any
) -> dict[str, Any]:
    store = ws.project(project_id)
    data = json_body(body) if body is not None else {}
    if action == "pick":
        record = store.pick(
            run_id, str(data.get("output")), str(data.get("image")), note=str(data.get("note", ""))
        )
        return record.model_dump(mode="json")
    if action == "rerun":
        return run_summary(store.rerun(run_id, str(data.get("output"))))
    return run_summary(getattr(store, action)(run_id))


@api("POST", P + "/exports")
def export(ws: Workspace, project_id: str, *, body: Any, **_: Any) -> dict[str, Any]:
    data = json_body(body)
    store = ws.project(project_id)
    kind, item = str(data.get("kind")), str(data.get("id", ""))
    out = ws.root / "exports" / f"{store.id}-{kind}{'-' + item if item else ''}.zip"
    makers: dict[str, Callable[[], Path]] = {
        "sheet": lambda: store.export_sheet(item, out, sources=bool(data.get("sources"))),
        "pack": lambda: store.export_pack(item, out),
        "sequence": lambda: store.export_sequence(item, out),
        "project": lambda: store.export_project(out),
    }
    if kind not in makers:
        raise ApiError(f"export kind must be one of {sorted(makers)}")
    return {"file": makers[kind]().name, "url": f"/downloads/{out.name}"}
