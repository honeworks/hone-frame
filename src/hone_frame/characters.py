"""A character's page and the project's world (change 0003): each pack's items with their accepted image,
their latest output and its candidates; the model sheet; which world assets still need references; and
which of a character's own assets a scene uses."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, Field

from hone_frame._dashboard_data import image_card
from hone_frame.errors import HoneFrameError
from hone_frame.profiles import resolve_profile
from hone_frame.recipes_packs import accepted_hero, carried_objects, owned_assets, pack_items, packs
from hone_frame.records import ImageRecord, Scene, SceneRef, SheetRecipe, Subject
from hone_frame.references import ACCEPTED
from hone_frame.requests import RequestBase, SubjectReferences
from hone_frame.runs import OutputRecord, RunView, all_runs, view
from hone_frame.sheets import MODEL_SHEET

if TYPE_CHECKING:
    from hone_frame.store import ProjectStore

LIVE = {"queued", "running", "waiting", "paused"}


def pack_of(image_pack: str | None, label: str) -> tuple[str, str] | None:
    """The (pack, item) of an image or output; older ones without a pack are matched by their label."""
    if image_pack:
        return image_pack, label
    for name, pack in packs().items():
        if any(str(i["item"]).lower() == label.lower() for i in pack.items):
            return name, next(str(i["item"]) for i in pack.items if str(i["item"]).lower() == label.lower())
    return None


def variation_id(store: ProjectStore, variation: str | None) -> str:
    """The variation asked for, or the project's active one (change 0005)."""
    return store.info.variation_of(variation or None).id


def _latest_outputs(store: ProjectStore, subject_id: str, v: str) -> dict[tuple[str, str], dict[str, Any]]:
    """Per (pack, item), the newest output made for this character in variation `v`, with its run."""
    found: dict[tuple[str, str], dict[str, Any]] = {}
    first = store.info.first_variation
    for run in all_runs(store):  # oldest first: later runs win
        if (run.plan.variation or first) != v:
            continue
        planned = [o for o in run.plan.outputs if o.subjects and o.subjects[0].subject_id == subject_id]
        if not planned:
            continue
        shown: RunView = view(store, run)
        records = {o.id: o for o in shown.outputs}
        for out in planned:
            key = pack_of(out.pack, out.item or out.label)
            record: OutputRecord | None = records.get(out.id)
            if key and record is not None and record.status != "replaced":
                found[key] = {"run": run.id, "output": record}
    return found


def _accepted(store: ProjectStore, subject_id: str, v: str) -> dict[tuple[str, str], ImageRecord]:
    found: dict[tuple[str, str], ImageRecord] = {}
    for image in store.images(subject_id=subject_id, variation=v):
        if image.status in ACCEPTED and image.subjects[0].subject_id == subject_id:
            key = pack_of(image.pack, image.item or image.label)
            if key:
                found[key] = image  # oldest first: the latest accepted wins
    return found


def _item_view(
    store: ProjectStore, key: tuple[str, str], latest: dict[str, Any] | None, accepted: ImageRecord | None
) -> dict[str, Any]:
    record: OutputRecord | None = latest["output"] if latest else None
    status = record.status if record else ("done" if accepted else "not_made")
    candidates = [store.image(i) for i in record.candidates] if record else []
    return {
        "pack": key[0],
        "item": key[1],
        "status": status,
        "reason": record.reason if record else "",
        "image": image_card(store, accepted) if accepted else None,
        "run": latest["run"] if latest else None,
        "output": record.id if record else None,
        "selected": record.selected if record else None,
        "candidates": [
            image_card(store, c) | {"evaluation": c.evaluation.model_dump() if c.evaluation else None}
            for c in candidates
        ],
    }


def character_page(store: ProjectStore, subject_id: str, variation: str | None = None) -> dict[str, Any]:
    """The character's packs in a variation: every item it should have, with what exists for it so far."""
    v = variation_id(store, variation)
    subject = store.subject(subject_id)
    latest = _latest_outputs(store, subject_id, v)
    accepted = _accepted(store, subject_id, v)
    rows: list[dict[str, Any]] = []
    for name, pack in packs().items():
        if name == "assets":
            continue  # the character's assets are their own subjects, listed below
        defaults = [
            str(i["item"])
            for i in ([{"item": "Hero"}] if name == "hero" else pack_items(store, subject, name, []))
        ]
        extra = sorted({k[1] for k in (*latest, *accepted) if k[0] == name} - set(defaults))
        items = [
            _item_view(store, (name, i), latest.get((name, i)), accepted.get((name, i)))
            for i in defaults + extra
        ]
        rows.append({"id": name, "label": pack.label, "description": pack.description,
                     "custom": pack.custom, "items": items})  # fmt: skip
    return {
        "subject": subject.model_dump(mode="json"),
        "warnings": carried_objects(subject),
        "variation": v,
        "hero": image_card(store, store.image(h)) if (h := accepted_hero(store, subject_id, v)) else None,
        "packs": rows,
        "assets": [world_card(store, a, v) for a in owned_assets(store, subject_id)],
        "sheet": _sheet_of(store, subject_id, v),
    }


def character_cards(store: ProjectStore, variation: str | None = None) -> list[dict[str, Any]]:
    """The project's characters with their hero and how many pack items are accepted in a variation."""
    v = variation_id(store, variation)
    cards: list[dict[str, Any]] = []
    for subject in store.subjects("character"):
        accepted = _accepted(store, subject.id, v)
        total = 1 + sum(
            len(pack_items(store, subject, n, [])) for n in packs() if n not in ("hero", "assets")
        )
        hero = accepted_hero(store, subject.id, v)
        cards.append(
            subject.model_dump(mode="json")
            | {
                "hero": image_card(store, store.image(hero)) if hero else None,
                "done": min(len(accepted), total),
                "total": total,
                "assets": len(owned_assets(store, subject.id)),
            }
        )
    return cards


def world_card(store: ProjectStore, subject: Subject, variation: str | None = None) -> dict[str, Any]:
    hero = accepted_hero(store, subject.id, variation_id(store, variation))
    return subject.model_dump(mode="json") | {"hero": image_card(store, store.image(hero)) if hero else None}


def world(store: ProjectStore, variation: str | None = None) -> list[dict[str, Any]]:
    """Places and objects that belong to the project, not to one character."""
    v = variation_id(store, variation)
    return [world_card(store, s, v) for s in store.subjects() if s.kind != "character" and s.owner is None]


def world_requests(
    store: ProjectStore, subject_ids: list[str] | None, variation: str | None = None
) -> list[SubjectReferences]:
    """One reference request per chosen world asset; by default those without an accepted hero."""
    v = variation_id(store, variation)
    if subject_ids is None:
        subject_ids = [s["id"] for s in world(store, v) if s["hero"] is None]
    return [SubjectReferences(subject_id=i, variation=v) for i in subject_ids]


# ------------------------------------------------------------------------------------------ model sheet


def model_sheet_recipe(store: ProjectStore, subject_id: str, variation: str | None = None) -> SheetRecipe:
    """The character model sheet from the accepted pack images: hero and turnaround, then expressions."""
    v = variation_id(store, variation)
    subject = store.subject(subject_id)
    accepted = _accepted(store, subject_id, v)
    figures = [(k, accepted[k]) for k in accepted if k[0] in ("hero", "turnaround")]
    faces = [(k, accepted[k]) for k in accepted if k[0] == "expressions"]
    if not figures:
        raise HoneFrameError(f"{subject.name} has no accepted hero or turnaround yet: generate them first")
    fields = subject.fields
    notes = [subject.description] + [
        f"{label}: {fields[key]}"
        for key, label in (
            ("appearance", "Appearance"),
            ("proportions", "Build"),
            ("features", "Distinguishing features"),
            ("outfits", "Outfit"),
        )
        if fields.get(key)
    ]
    return SheetRecipe(
        name=sheet_name(store, subject, v),
        layout=MODEL_SHEET,
        images=[i.id for _, i in figures + faces],
        labels=[k[1] for k, _ in figures + faces],
        columns=len(figures),
        heading=subject.name,
        notes="\n".join(n for n in notes if n),
    )


def sheet_name(store: ProjectStore, subject: Subject, v: str) -> str:
    """One model sheet per character and variation; the first variation keeps the plain name."""
    if v == store.info.first_variation:
        return f"{subject.name} model sheet"
    return f"{subject.name} model sheet ({store.info.variation_of(v).name})"


def _sheet_of(store: ProjectStore, subject_id: str, v: str) -> dict[str, Any] | None:
    name = sheet_name(store, store.subject(subject_id), v)
    sheet = next(
        (s for s in store.sheets() if s.recipe.name == name and s.recipe.layout == MODEL_SHEET), None
    )
    if sheet is None:
        return None
    return sheet.model_dump(mode="json") | {
        "url": f"/files/{store.id}/{sheet.render}" if sheet.render else None
    }


# ------------------------------------------------------------------------------ scene asset suggestions


class AssetChoice(BaseModel):
    use: list[str] = Field(default_factory=list[str])
    reason: str = ""


def suggest_assets(store: ProjectStore, scene: Scene) -> tuple[Scene, str]:
    """Ask the planner which of the scene's characters' own assets appear in it (change 0003); they are
    added as suggested object references. Without a planner, or when it fails, none are added."""
    kept = [r for r in scene.refs if not r.suggested]
    chars = [store.subject(r.subject_id) for r in kept if store.subject(r.subject_id).kind == "character"]
    owned = [a for c in chars for a in owned_assets(store, c.id) if all(r.subject_id != a.id for r in kept)]
    if not owned:
        return scene.model_copy(update={"refs": kept}), ""
    planner = resolve_profile(store, RequestBase()).planner
    if planner is None:
        return scene.model_copy(update={"refs": kept}), "no planner model: add the belongings yourself"
    lines = [
        f"- {a.id}: {a.name}, belongs to {store.subject(a.owner or '').name}: {a.description}" for a in owned
    ]
    prompt = (
        "A scene in a picture is described below. Which of these objects appear in it? Choose only those "
        "the description shows or clearly implies.\n"
        f"Scene: {scene.description} {scene.action}".rstrip()
        + "\nObjects:\n" + "\n".join(lines)
        + '\nReturn JSON: {"use": [ids], "reason": "one sentence"}.'
    )  # fmt: skip
    try:
        answer = store.workspace.models.ask(planner, prompt, images=[], schema=AssetChoice, think=False)
    except HoneFrameError as exc:
        return scene.model_copy(update={"refs": kept}), f"the planner could not suggest belongings: {exc}"
    ids = [a.id for a in owned if a.id in answer.use]
    added = [SceneRef(subject_id=i, role="object", suggested=True) for i in ids]
    return scene.model_copy(update={"refs": kept + added}), answer.reason
