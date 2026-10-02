"""Project files (change 0004): a whole project in one TOML or JSON file: its details, characters with
their states and belongings, the world's places and objects, and scenes. Importing a file creates what is
missing and updates what changed (a new version), matching everything by name, so the same file can be
imported again after editing it. `project_file` writes a project back in the same shape (JSON)."""

from __future__ import annotations

import json
import tomllib
from pathlib import Path
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from hone_frame.errors import InvalidRequest
from hone_frame.records import Scene, SceneRef, StateKind, Subject

if TYPE_CHECKING:
    from hone_frame.store import ProjectStore
    from hone_frame.workspace import Workspace

# file key -> the subject field it fills, per kind
CHARACTER = {"appearance": "appearance", "build": "proportions", "features": "features", "outfit": "outfits"}
PLACE = {
    "anchors": "anchors",
    "materials": "materials",
    "viewpoints": "viewpoints",
    "recurring_objects": "recurring_objects",
}
OBJECT = {"size": "scale", "materials": "materials", "colours": "colours", "details": "details"}


class _In(BaseModel):
    model_config = ConfigDict(extra="forbid")


class StateIn(_In):
    name: str
    kind: StateKind = "other"
    description: str = ""


class ObjectIn(_In):
    name: str
    description: str = ""
    size: str = ""
    materials: str = ""
    colours: str = ""
    details: str = ""


class CharacterIn(_In):
    name: str
    description: str = ""
    appearance: str = ""
    build: str = ""
    features: str = ""
    outfit: str = ""
    states: list[StateIn] = Field(default_factory=list[StateIn])
    belongings: list[ObjectIn] = Field(default_factory=list[ObjectIn])


class PlaceIn(_In):
    name: str
    description: str = ""
    anchors: str = ""
    materials: str = ""
    viewpoints: str = ""
    recurring_objects: str = ""


class SceneIn(_In):
    name: str
    description: str = ""
    action: str = ""
    camera: str | None = None
    expression: str | None = None
    pose: str | None = None
    lighting: str | None = None
    characters: list[str] = Field(default_factory=list[str])
    places: list[str] = Field(default_factory=list[str])
    objects: list[str] = Field(default_factory=list[str])  # world objects or belongings, by name


class ProjectIn(_In):
    name: str
    brief: str = ""
    direction: str = ""
    style: str = "cinematic-realism"  # a style_pack preset id


class ProjectFile(_In):
    format_version: str = "1"
    project: ProjectIn
    characters: list[CharacterIn] = Field(default_factory=list[CharacterIn])
    places: list[PlaceIn] = Field(default_factory=list[PlaceIn])
    objects: list[ObjectIn] = Field(default_factory=list[ObjectIn])
    scenes: list[SceneIn] = Field(default_factory=list[SceneIn])


class ImportReport(BaseModel):
    project: str
    created: list[str] = Field(default_factory=list[str])
    updated: list[str] = Field(default_factory=list[str])
    unchanged: list[str] = Field(default_factory=list[str])


def parse(text: str, kind: str = "") -> ProjectFile:
    """A project file from TOML or JSON text (`kind` "toml" or "json"; empty: JSON if it looks like it)."""
    as_json = kind == "json" or (not kind and text.lstrip().startswith("{"))
    try:
        data: Any = json.loads(text) if as_json else tomllib.loads(text)
    except (json.JSONDecodeError, tomllib.TOMLDecodeError) as exc:
        raise InvalidRequest(f"the project file is not valid {'JSON' if as_json else 'TOML'}: {exc}") from exc
    try:
        found = ProjectFile.model_validate(data)
    except ValidationError as exc:
        problems = [f"{'.'.join(str(x) for x in e['loc'])}: {e['msg']}" for e in exc.errors()]
        raise InvalidRequest(
            "the project file does not match the format (docs/project-files.md)", problems
        ) from exc
    if found.format_version != "1":
        raise InvalidRequest(
            f"project file format_version {found.format_version!r} is not supported; use '1'"
        )
    return found


def import_path(ws: Workspace, path: str | Path) -> ImportReport:
    path = Path(path)
    return import_file(ws, parse(path.read_text(encoding="utf-8"), path.suffix.lstrip(".").lower()))


def import_file(ws: Workspace, data: ProjectFile) -> ImportReport:
    """Create or update the project and everything in it; names match existing records."""
    _check_names(data)
    store, created = _project(ws, data.project)
    report = ImportReport(project=store.id, created=[f"project {store.id}"] if created else [])
    for c in data.characters:
        char = _subject(
            store, report, kind="character", item=c, fields=_fields(c, CHARACTER), states=c.states
        )
        for b in c.belongings:
            _subject(store, report, kind="asset", item=b, fields=_fields(b, OBJECT), owner=char.id)
    for p in data.places:
        _subject(store, report, kind="environment", item=p, fields=_fields(p, PLACE))
    for o in data.objects:
        _subject(store, report, kind="asset", item=o, fields=_fields(o, OBJECT))
    for s in data.scenes:
        _scene(store, report, s)
    return report


def _check_names(data: ProjectFile) -> None:
    names = [c.name for c in data.characters] + [b.name for c in data.characters for b in c.belongings]
    names += [p.name for p in data.places] + [o.name for o in data.objects]
    if repeated := sorted({n for n in names if names.count(n) > 1}):
        raise InvalidRequest(f"names must be unique in a project file; repeated: {repeated}")


def _project(ws: Workspace, p: ProjectIn) -> tuple[ProjectStore, bool]:
    existing = next((x for x in ws.projects() if x.name == p.name), None)
    if existing is None:
        return ws.create_project(p.name, brief=p.brief, direction=p.direction, style_pack=p.style), True
    store = ws.project(existing.id)
    if (existing.brief, existing.direction, existing.style_pack) != (p.brief, p.direction, p.style):
        store.update(brief=p.brief, direction=p.direction, style_pack=p.style)
    return store, False


def _fields(item: BaseModel, mapping: dict[str, str]) -> dict[str, str]:
    values = item.model_dump()
    return {field: str(values[key]).strip() for key, field in mapping.items() if str(values[key]).strip()}


def _subject(
    store: ProjectStore,
    report: ImportReport,
    *,
    kind: str,
    item: CharacterIn | ObjectIn | PlaceIn,
    fields: dict[str, str],
    owner: str | None = None,
    states: list[StateIn] | None = None,
) -> Subject:
    name, description = item.name, item.description
    wanted: dict[str, Any] = {
        "description": description,
        "fields": fields,
        "owner": owner,
        "states": [s.model_dump() for s in states or []],
    }
    found = next((s for s in store.subjects(kind) if s.name == name), None)
    label = f"{kind} {name}"
    if found is None:
        report.created.append(label)
        return store.add_subject(kind, name, **wanted)  # pyright: ignore[reportArgumentType]
    now = {"description": found.description, "fields": found.fields, "owner": found.owner,
           "states": [s.model_dump() for s in found.states]}  # fmt: skip
    if now == wanted:
        report.unchanged.append(label)
        return found
    report.updated.append(label)
    return store.edit_subject(found.id, **wanted)


def _scene(store: ProjectStore, report: ImportReport, s: SceneIn) -> None:
    by_name = {x.name: x for x in store.subjects()}
    refs: list[SceneRef] = []
    for names, role in ((s.characters, "identity"), (s.places, "environment"), (s.objects, "object")):
        for name in names:
            if name not in by_name:
                raise InvalidRequest(f"scene {s.name!r} names {name!r}, which is not in the project")
            refs.append(SceneRef.model_validate({"subject_id": by_name[name].id, "role": role}))
    found = next((x for x in store.scenes() if x.name == s.name), None)
    scene = Scene(
        id=found.id if found else "",
        name=s.name,
        description=s.description,
        action=s.action,
        camera=s.camera,
        expression=s.expression,
        pose=s.pose,
        lighting=s.lighting,
        refs=refs,
    )
    keys = ("description", "action", "camera", "expression", "pose", "lighting")
    same_refs = found and [(r.subject_id, r.role) for r in found.refs if not r.suggested] == [
        (r.subject_id, r.role) for r in refs
    ]
    if found and same_refs and all(getattr(found, k) == getattr(scene, k) for k in keys):
        report.unchanged.append(f"scene {s.name}")
        return
    store.save_scene(scene)
    (report.updated if found else report.created).append(f"scene {s.name}")


def project_file(store: ProjectStore) -> dict[str, Any]:
    """The project in the project-file shape, ready to edit and import again."""
    info = store.info
    subjects = store.subjects()
    names = {s.id: s.name for s in subjects}

    def keyed(subject: Subject, mapping: dict[str, str]) -> dict[str, Any]:
        out: dict[str, Any] = {"name": subject.name, "description": subject.description}
        out |= {key: str(subject.fields[f]) for key, f in mapping.items() if subject.fields.get(f)}
        return out

    characters = [
        keyed(c, CHARACTER)
        | {"states": [s.model_dump() for s in c.states]}
        | {"belongings": [keyed(a, OBJECT) for a in subjects if a.owner == c.id]}
        for c in subjects
        if c.kind == "character"
    ]
    scenes = [
        {"name": s.name, "description": s.description, "action": s.action}
        | {k: getattr(s, k) for k in ("camera", "expression", "pose", "lighting") if getattr(s, k)}
        | {
            key: [names[r.subject_id] for r in s.refs if r.role == role and r.subject_id in names]
            for key, role in (("characters", "identity"), ("places", "environment"), ("objects", "object"))
        }
        for s in store.scenes()
    ]
    return {
        "format_version": "1",
        "project": {
            "name": info.name,
            "brief": info.brief,
            "direction": info.direction,
            "style": info.style_pack,
        },
        "characters": characters,
        "places": [keyed(p, PLACE) for p in subjects if p.kind == "environment"],
        "objects": [keyed(o, OBJECT) for o in subjects if o.kind == "asset" and o.owner is None],
        "scenes": scenes,
    }
