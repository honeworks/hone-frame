"""The dashboard's JSON API (design §12.2): one table of routes, each a small function."""

from __future__ import annotations

import re
import tempfile
from collections.abc import Callable
from http import HTTPStatus
from pathlib import Path
from typing import Any

from hone_frame._dashboard_data import image_card, model_latency, overview, run_page, run_summary
from hone_frame.records import Scene, Sequence, SheetRecipe
from hone_frame.runs import all_runs, view
from hone_frame.store import ProjectStore
from hone_frame.workspace import Settings, Workspace

Handler = Callable[..., Any]
ROUTES: list[tuple[str, re.Pattern[str], Handler]] = []


class ApiError(Exception):
    def __init__(self, message: str, status: int = HTTPStatus.BAD_REQUEST) -> None:
        super().__init__(message)
        self.status = status


def api(method: str, pattern: str) -> Callable[[Handler], Handler]:
    def register(fn: Handler) -> Handler:
        ROUTES.append((method, re.compile("^" + pattern + "$"), fn))
        return fn

    return register


def route(ws: Workspace, method: str, path: str, query: dict[str, str], body: Any) -> Any:
    for verb, pattern, fn in ROUTES:
        match = pattern.match(path)
        if match and verb == method:
            return fn(ws, *match.groups(), query=query, body=body)
    raise ApiError(f"no API route {method} {path}", HTTPStatus.NOT_FOUND)


def _body(body: Any) -> dict[str, Any]:
    if not isinstance(body, dict):
        raise ApiError("send a JSON object")
    return body  # pyright: ignore[reportUnknownVariableType]


P = r"/projects/([a-z0-9-]+)"
ID = r"([A-Za-z0-9_-]+)"


# ------------------------------------------------------------------------------------------ workspace


@api("GET", "/workspace")
def workspace(ws: Workspace, **_: Any) -> dict[str, Any]:
    return {
        "root": str(ws.root),
        "projects": [p.model_dump(mode="json") for p in ws.projects()],
        "settings": ws.settings.model_dump(mode="json"),
        "queue": [run_summary(v) for v in ws.queue()],
    }


@api("PATCH", "/workspace/settings")
def settings(ws: Workspace, *, body: Any, **_: Any) -> dict[str, Any]:
    new = Settings.model_validate(ws.settings.model_dump() | _body(body))
    ws.save_settings(new)
    return new.model_dump(mode="json")


@api("GET", "/presets")
def presets(ws: Workspace, **_: Any) -> dict[str, Any]:
    return ws.presets.as_dict()


@api("GET", "/models")
def models(ws: Workspace, **_: Any) -> dict[str, Any]:
    latency = model_latency(ws)
    found: dict[str, Any] = {}
    for kind in ("image", "chat"):
        found[kind] = [m.__dict__ | {"latency_s": latency.get(m.id)} for m in ws.models.available(kind)]
    return found


# ------------------------------------------------------------------------------------------- projects


@api("GET", "/projects")
def projects(ws: Workspace, **_: Any) -> list[dict[str, Any]]:
    return [p.model_dump(mode="json") for p in ws.projects()]


@api("POST", "/projects")
def create_project(ws: Workspace, *, body: Any, **_: Any) -> dict[str, Any]:
    data = _body(body)
    store = ws.create_project(
        str(data.get("name", "")),
        brief=str(data.get("brief", "")),
        direction=str(data.get("direction", "")),
        style_pack=str(data.get("style_pack") or "cinematic-realism"),
    )
    return store.info.model_dump(mode="json")


@api("GET", P)
def project(ws: Workspace, project_id: str, **_: Any) -> dict[str, Any]:
    store = ws.project(project_id)
    return store.info.model_dump(mode="json") | {"outdated": [u.model_dump() for u in store.outdated()]}


@api("PATCH", P)
def update_project(ws: Workspace, project_id: str, *, body: Any, **_: Any) -> dict[str, Any]:
    return ws.project(project_id).update(**_body(body)).model_dump(mode="json")


@api("GET", P + "/overview")
def project_overview(ws: Workspace, project_id: str, **_: Any) -> dict[str, Any]:
    return overview(ws.project(project_id))


# ------------------------------------------------------------------------------------ subjects, images


def _subject_card(store: ProjectStore, subject_id: str) -> dict[str, Any]:
    subject = store.subject(subject_id)
    images = store.images(subject_id=subject_id)
    accepted = [i for i in images if i.status in ("picked", "manual_pick", "imported")]
    cover = next((i for i in images if i.id in subject.reference_images), accepted[-1] if accepted else None)
    return subject.model_dump(mode="json") | {
        "cover": image_card(store, cover) if cover else None,
        "image_count": len(images),
    }


@api("GET", P + "/subjects")
def subjects(ws: Workspace, project_id: str, *, query: dict[str, str], **_: Any) -> list[dict[str, Any]]:
    store = ws.project(project_id)
    return [_subject_card(store, s.id) for s in store.subjects(query.get("kind"))]


@api("POST", P + "/subjects")
def add_subject(ws: Workspace, project_id: str, *, body: Any, **_: Any) -> dict[str, Any]:
    data = _body(body)
    store = ws.project(project_id)
    fields = {k: v for k, v in data.items() if k not in ("kind", "name", "description")}
    subject = store.add_subject(
        data.get("kind", ""),
        str(data.get("name", "")),
        description=str(data.get("description", "")),
        **fields,
    )
    return _subject_card(store, subject.id)


@api("GET", P + "/subjects/" + ID)
def subject(ws: Workspace, project_id: str, subject_id: str, **_: Any) -> dict[str, Any]:
    store = ws.project(project_id)
    card = _subject_card(store, subject_id)
    current = store.subject(subject_id).version
    versions = [store.subject(subject_id, n).model_dump(mode="json") for n in range(1, current + 1)]
    own = [i for i in store.images(subject_id=subject_id) if len(i.subjects) == 1]  # scenes are elsewhere
    return card | {"versions": versions, "images": [image_card(store, i) for i in own]}


@api("PATCH", P + "/subjects/" + ID)
def edit_subject(ws: Workspace, project_id: str, subject_id: str, *, body: Any, **_: Any) -> dict[str, Any]:
    store = ws.project(project_id)
    store.edit_subject(subject_id, **_body(body))
    return _subject_card(store, subject_id)


@api("GET", P + "/images")
def images(ws: Workspace, project_id: str, *, query: dict[str, str], **_: Any) -> list[dict[str, Any]]:
    store = ws.project(project_id)
    found = store.images(
        kind=query.get("kind") or None,
        subject_id=query.get("subject") or None,
        status=query.get("status") or None,
        model=query.get("model") or None,
        since=query.get("since") or None,
    )
    return [image_card(store, i) for i in found[::-1]]


@api("POST", P + "/images")
def import_image(
    ws: Workspace, project_id: str, *, query: dict[str, str], body: Any, **_: Any
) -> dict[str, Any]:
    if not isinstance(body, dict) or "bytes" not in body:
        raise ApiError("send the image file as the request body")
    store = ws.project(project_id)
    suffix = Path(str(body["name"])).suffix.lower() or ".png"  # pyright: ignore[reportUnknownArgumentType]
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / f"upload{suffix}"
        path.write_bytes(body["bytes"])  # pyright: ignore[reportUnknownArgumentType]
        record = store.import_image(
            path, subject_id=query.get("subject") or None, label=query.get("label", "")
        )
    return image_card(store, record)


@api("GET", P + "/images/" + ID)
def image(ws: Workspace, project_id: str, image_id: str, **_: Any) -> dict[str, Any]:
    store = ws.project(project_id)
    record = store.image(image_id)
    return image_card(store, record) | {
        "record": record.model_dump(mode="json"),
        "uses": store.image_uses(image_id),
    }


@api("DELETE", P + "/images/" + ID)
def delete_image(ws: Workspace, project_id: str, image_id: str, **_: Any) -> dict[str, Any]:
    ws.project(project_id).delete_image(image_id)
    return {"deleted": image_id}


# --------------------------------------------------------------------------- scenes, sequences, sheets


@api("GET", P + "/scenes")
def scenes(ws: Workspace, project_id: str, **_: Any) -> list[dict[str, Any]]:
    return [s.model_dump(mode="json") for s in ws.project(project_id).scenes()]


@api("POST", P + "/scenes")
def save_scene(ws: Workspace, project_id: str, *, body: Any, **_: Any) -> dict[str, Any]:
    return ws.project(project_id).save_scene(Scene.model_validate(_body(body))).model_dump(mode="json")


@api("GET", P + "/scenes/" + ID)
def scene(ws: Workspace, project_id: str, scene_id: str, **_: Any) -> dict[str, Any]:
    store = ws.project(project_id)
    found = store.scene(scene_id)
    refs = [
        {"ref": r.model_dump(mode="json"), "subject": _subject_card(store, r.subject_id)} for r in found.refs
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
    return ws.project(project_id).save_sequence(Sequence.model_validate(_body(body))).model_dump(mode="json")


@api("GET", P + "/sheets")
def sheets(ws: Workspace, project_id: str, **_: Any) -> list[dict[str, Any]]:
    store = ws.project(project_id)
    return [
        s.model_dump(mode="json") | {"url": f"/files/{store.id}/{s.render}" if s.render else None}
        for s in store.sheets()
    ]


@api("POST", P + "/sheets")
def save_sheet(ws: Workspace, project_id: str, *, body: Any, **_: Any) -> dict[str, Any]:
    data = _body(body)
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
    return ws.project(project_id).plan(_body(body)).model_dump(mode="json")


@api("POST", P + "/runs")
def submit(ws: Workspace, project_id: str, *, body: Any, **_: Any) -> dict[str, Any]:
    return run_summary(ws.project(project_id).submit(_body(body)))


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
    data = _body(body) if body is not None else {}
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
    data = _body(body)
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
