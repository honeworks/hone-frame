"""Object packs (change 0005): a belonging or a world object (a mace, a horse, a banner) gets a hero and
views made from it, like a character. A character's actions wait for its belongings' heroes. The packs
and items are data (`data/object_packs.toml`)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from hone_frame.errors import InvalidRequest
from hone_frame.recipes import OBJECT_FRAMING, WHITE, Built, base_inputs, reference_lighting
from hone_frame.recipes_packs import accepted_hero, pack_items, packs
from hone_frame.records import Subject, SubjectLink
from hone_frame.requests import CharacterPacks, Dependency, PlannedRef, RequestBase

if TYPE_CHECKING:
    from hone_frame.store import ProjectStore


def object_packs(store: ProjectStore, request: CharacterPacks, built: Built) -> None:
    """An object's hero (unless one is accepted, or `redraw_hero`), then its chosen packs."""
    obj = store.subject(request.subject_id)
    catalog = packs("asset")
    chosen = request.packs or list(catalog)
    if unknown := sorted(set(chosen) - set(catalog)) + sorted(set(request.custom) - set(catalog)):
        raise InvalidRequest(f"unknown packs {unknown} for an object; use {list(catalog)}")
    if left_out := sorted(set(request.custom) - set(chosen)):
        raise InvalidRequest(
            f"items of your own for {left_out}, which are not in packs: add them or drop them"
        )
    hero = None if request.redraw_hero else accepted_hero(store, obj.id, built.choices.variation.id)
    add_object(
        store,
        built,
        request,
        obj,
        chosen=chosen,
        custom=request.custom,
        only_custom=request.only_custom,
        hero=hero,
    )


def add_object(
    store: ProjectStore,
    built: Built,
    request: RequestBase,
    obj: Subject,
    *,
    chosen: list[str] | None = None,
    custom: dict[str, list[str]] | None = None,
    only_custom: bool = False,
    hero: str | None = None,
) -> str | None:
    """Add an object's hero (unless `hero`, an accepted image, is given) and its chosen packs' items.
    Returns the hero's output id in this request, or None when an accepted hero is reused."""
    catalog = packs("asset")
    chosen = chosen or list(catalog)
    maker = _ObjectMaker(built, request, obj)
    hero_output: str | None = None
    if hero is None:
        own = [maker.ref(i) for i in obj.reference_images]
        out_id = maker.add("hero", dict(catalog["hero"].items[0]), references=own)
        hero_output = out_id
        identity: dict[str, Any] = {"depends_on": [Dependency(output=out_id, role="object")]}
    else:
        identity = {"references": [maker.ref(hero)]}
    for name in [n for n in catalog if n in chosen and n != "hero"]:
        for item in pack_items(store, obj, name, (custom or {}).get(name, []), only_extra=only_custom):
            maker.add(name, item, **{k: list(v) for k, v in identity.items()})
    return hero_output


class _ObjectMaker:
    def __init__(self, built: Built, request: RequestBase, obj: Subject) -> None:
        self.built, self.request, self.obj = built, request, obj
        self.lighting = reference_lighting(built, request)

    def ref(self, image_id: str) -> PlannedRef:
        return PlannedRef(image_id=image_id, subject_id=self.obj.id, version=self.obj.version, role="object")

    def add(self, pack: str, spec: dict[str, Any], **fields: Any) -> str:
        refs = bool(fields.get("references") or fields.get("depends_on"))
        details = str(self.obj.fields.get("details") or "").strip()
        framing = (
            f"its most distinctive detail fills the frame: {details}"
            if spec.get("detail") and details
            else OBJECT_FRAMING
        )
        out = self.built.add(
            spec["item"],
            "asset",
            subjects=[SubjectLink(subject_id=self.obj.id, version=self.obj.version)],
            judging="object-fidelity",
            conditions=(["identity_ref"] if refs else []) + ["clean_background", "object_alone"],
            pack=pack,
            item=spec["item"],
            prompt_inputs=base_inputs(
                self.built.choices,
                self.request,
                who=[(self.obj, None)],
                reference=True,
                background=WHITE,
                empty_hands=False,
                object_alone=True,
                context="full" if pack == "hero" else "short",
                lighting=self.lighting,
                camera=spec.get("camera"),
                framing=framing,
            ),
            **fields,
        )
        return out.id
