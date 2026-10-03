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


SCENE_KEYS = ("description", "action", "camera", "expression", "pose", "lighting")


class _In(BaseModel):
    model_config = ConfigDict(extra="forbid")


class StateIn(_In):
    name: str
    kind: StateKind = "other"
    description: str = ""


class ObjectIn(_In):
    name: str
    description: str = ""
    must: list[str] = Field(default_factory=list[str])
    never: list[str] = Field(default_factory=list[str])
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
    must: list[str] = Field(default_factory=list[str])  # always shown (change 0005)
    never: list[str] = Field(default_factory=list[str])  # never shown
    states: list[StateIn] = Field(default_factory=list[StateIn])
    belongings: list[ObjectIn] = Field(default_factory=list[ObjectIn])


class PlaceIn(_In):
    name: str
    description: str = ""
    must: list[str] = Field(default_factory=list[str])
    never: list[str] = Field(default_factory=list[str])
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


class VariationIn(_In):
    name: str
    style: str  # a style_pack preset id
    direction: str = ""  # how this variation is drawn, in a few words


class ProjectIn(_In):
    name: str
    brief: str = ""
    direction: str = ""
    style: str = "cinematic-realism"  # the first variation's style pack; for a new project only when omitted
    look: str = ""  # the world's look guide (change 0005)
    variations: list[VariationIn] = Field(default_factory=list[VariationIn])  # more ways of drawing it


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
    kind = path.suffix.lstrip(".").lower()
    if kind not in ("toml", "json"):
        raise InvalidRequest(f"{path.name}: a project file ends in .toml or .json")
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise InvalidRequest(f"cannot read the project file {path}: {exc.strerror or exc}") from exc
    return import_file(ws, parse(text, kind))


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
    """Create the project, or update only what the file gives (a key left out keeps its value)."""
    styles = [x.id for x in ws.presets.list("style_pack")]
    if p.style not in styles:
        raise InvalidRequest(f"project style {p.style!r} is not a style pack; use one of {styles}")
    existing = next((x for x in ws.projects() if x.name == p.name), None)
    if existing is None:
        store = ws.create_project(p.name, brief=p.brief, direction=p.direction, style_pack=p.style)
        if p.look:
            store.update(look=p.look)
        _variations(store, p.variations, styles)
        return store, True
    given = p.model_dump(exclude_unset=True)
    keys = (("brief", "brief"), ("direction", "direction"), ("style", "style_pack"), ("look", "look"))
    wanted = {k: given[key] for key, k in keys if key in given}
    store = ws.project(existing.id)
    if any(getattr(existing, k) != v for k, v in wanted.items()):
        store.update(**wanted)
    _variations(store, p.variations, styles)
    return store, False


def _variations(store: ProjectStore, wanted: list[VariationIn], styles: list[str]) -> None:
    """Add the file's variations that are missing (by name) and update those that changed."""
    for w in wanted:
        if w.style not in styles:
            raise InvalidRequest(
                f"variation {w.name!r}: style {w.style!r} is not a style pack; use one of {styles}"
            )
        found = next((v for v in store.info.all_variations() if v.name == w.name), None)
        if found is None:
            store.add_variation(w.name, style_pack=w.style, direction=w.direction, active=False)
        elif (found.style_pack, found.direction) != (w.style, w.direction):
            store.edit_variation(found.id, style_pack=w.style, direction=w.direction)


def _fields(item: BaseModel, mapping: dict[str, str]) -> dict[str, str]:
    """The subject fields the file gives (a key left out of the file is not touched)."""
    values = item.model_dump(exclude_unset=True)
    return {field: str(values[key]).strip() for key, field in mapping.items() if key in values}


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
    given = item.model_dump(exclude_unset=True)
    found = next((s for s in store.subjects(kind) if s.name == item.name), None)
    label = f"{kind} {item.name}"
    wanted: dict[str, Any] = {
        "fields": (dict(found.fields) if found else {}) | fields,
        "owner": owner,
    }
    if "description" in given or found is None:
        wanted["description"] = item.description
    for key in ("must", "never"):
        if key in given or found is None:
            wanted[key] = list(getattr(item, key, []))
    if states is not None and ("states" in given or found is None):
        wanted["states"] = [s.model_dump() for s in states]
    if found is None:
        report.created.append(label)
        return store.add_subject(kind, item.name, **wanted)  # pyright: ignore[reportArgumentType]
    now = found.model_dump(include=set(wanted))
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
    given = s.model_dump(exclude_unset=True)
    update: dict[str, Any] = {k: given[k] for k in SCENE_KEYS if k in given}
    if found is None:
        store.save_scene(Scene(name=s.name, refs=refs, **update))
        report.created.append(f"scene {s.name}")
        return
    if {"characters", "places", "objects"} & set(given):  # the file's references; suggested ones stay
        kept = [r for r in found.refs if r.suggested and r.subject_id not in {x.subject_id for x in refs}]
        if [(r.subject_id, r.role) for r in found.refs if not r.suggested] != [
            (r.subject_id, r.role) for r in refs
        ]:
            update["refs"] = refs + kept
    if all(getattr(found, k) == v for k, v in update.items()):
        report.unchanged.append(f"scene {s.name}")
        return
    store.save_scene(found.model_copy(update=update))
    report.updated.append(f"scene {s.name}")


def project_file(store: ProjectStore) -> dict[str, Any]:
    """The project in the project-file shape, ready to edit and import again."""
    info = store.info
    subjects = store.subjects()
    names = {s.id: s.name for s in subjects}

    def keyed(subject: Subject, mapping: dict[str, str]) -> dict[str, Any]:
        out: dict[str, Any] = {"name": subject.name, "description": subject.description}
        out |= {key: str(subject.fields[f]) for key, f in mapping.items() if subject.fields.get(f)}
        out |= {key: list(getattr(subject, key)) for key in ("must", "never") if getattr(subject, key)}
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
            "look": info.look,
            "variations": [
                {"name": v.name, "style": v.style_pack, "direction": v.direction} for v in info.variations
            ],
        },
        "characters": characters,
        "places": [keyed(p, PLACE) for p in subjects if p.kind == "environment"],
        "objects": [keyed(o, OBJECT) for o in subjects if o.kind == "asset" and o.owner is None],
        "scenes": scenes,
    }
