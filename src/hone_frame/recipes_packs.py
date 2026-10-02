"""Character packs (change 0003): every reference image of one character, pack by pack, all made from one
hero. The packs and their default items are data (`data/character_packs.toml`)."""

from __future__ import annotations

import tomllib
from functools import cache
from importlib import resources
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, ConfigDict, Field

from hone_frame.errors import InvalidRequest
from hone_frame.recipes import WHITE, Built, base_inputs, reference_lighting, view_flags
from hone_frame.records import Subject, SubjectLink
from hone_frame.references import ACCEPTED
from hone_frame.requests import CharacterPacks, Dependency, PlannedOutput, PlannedRef

if TYPE_CHECKING:
    from hone_frame.store import ProjectStore

CUSTOM: dict[str, dict[str, Any]] = {  # what a person's own item text becomes, per pack's `custom`
    "camera": {"pose": "neutral-standing", "full_body": True},
    "expression": {"camera": "close-up"},
    "pose": {"camera": "front", "full_body": True},
    "outfit": {"camera": "front", "pose": "neutral-standing", "full_body": True},
    "state": {"camera": "front", "full_body": True},
    "action": {"camera": "front", "full_body": True},
}


class Pack(BaseModel):
    model_config = ConfigDict(extra="forbid")
    label: str
    description: str = ""
    custom: str | None = None
    framing: str = ""
    from_states: list[str] = Field(default_factory=list[str])
    from_assets: bool = False
    empty_hands: bool = True
    items: list[dict[str, Any]] = Field(default_factory=list[dict[str, Any]])


@cache
def packs() -> dict[str, Pack]:
    """The packs, in the order they are made."""
    text = (resources.files("hone_frame") / "data" / "character_packs.toml").read_text(encoding="utf-8")
    return {name: Pack.model_validate(row) for name, row in tomllib.loads(text)["packs"].items()}


def accepted_hero(store: ProjectStore, subject_id: str) -> str | None:
    """The character's latest accepted hero image, or None."""
    heroes = [
        i
        for i in store.images(subject_id=subject_id)
        if len(i.subjects) == 1 and i.status in ACCEPTED and (i.pack == "hero" or i.label.lower() == "hero")
    ]
    return heroes[-1].id if heroes else None


def owned_assets(store: ProjectStore, character_id: str) -> list[Subject]:
    return [s for s in store.subjects("asset") if s.owner == character_id]


def pack_items(
    store: ProjectStore, subject: Subject, name: str, extra: list[str], *, only_extra: bool = False
) -> list[dict[str, Any]]:
    """One pack's items: its defaults, one per matching state or owned asset, and the person's own."""
    pack = packs()[name]
    if only_extra:
        pack = pack.model_copy(update={"items": [], "from_states": [], "from_assets": False})
    items = [dict(i) for i in pack.items]
    for state in subject.states:
        if state.kind in pack.from_states:
            words = state.description or state.name
            key = "outfit" if state.kind == "outfit" else "state"
            items.append({"item": state.name, key: words, **CUSTOM[key]})
    if pack.from_assets:
        for asset in owned_assets(store, subject.id):
            if name == "actions":
                about = f"{asset.name}: {asset.description}".rstrip(": ")
                text = f"{subject.name} holds and uses {about}"
                items.append({"item": asset.name, "action": text, "asset_id": asset.id, **CUSTOM["action"]})
            else:
                items.append({"item": asset.name, "asset_id": asset.id})
    if extra and pack.custom is None:
        raise InvalidRequest(f"the {pack.label} pack takes no items of your own")
    kind = str(pack.custom)
    for text in extra:
        if text.strip():
            items.append({"item": text.strip(), kind: text.strip(), **CUSTOM[kind]})
    return [i | {"framing": pack.framing} if pack.framing and "framing" not in i else i for i in items]


def character_packs(store: ProjectStore, request: CharacterPacks, built: Built) -> None:
    """The hero once, then every chosen pack's items from it (change 0003). Without an accepted hero the
    hero is always the first output, whatever `packs` and `only_custom` say: nothing else can be made
    without it (D-027)."""
    subject = store.subject(request.subject_id)
    if subject.kind != "character":
        raise InvalidRequest(f"{subject.name} is a {subject.kind}; packs are made for characters")
    chosen = request.packs or list(packs())
    if unknown := sorted(set(chosen) - set(packs())) + sorted(set(request.custom) - set(packs())):
        raise InvalidRequest(f"unknown packs {unknown}; use {list(packs())}")
    if left_out := sorted(set(request.custom) - set(chosen)):
        raise InvalidRequest(
            f"items of your own for {left_out}, which are not in packs: add them or drop the items"
        )
    maker = _PackMaker(store, request, built, subject)
    hero = None if request.redraw_hero else accepted_hero(store, subject.id)
    maker.identity = maker.hero() if hero is None else {"references": [maker.ref(hero, subject, "identity")]}
    for name in [n for n in packs() if n in chosen and n != "hero"]:
        extra = request.custom.get(name, [])
        for item in pack_items(store, subject, name, extra, only_extra=request.only_custom):
            maker.item(name, item)


class _PackMaker:
    """Adds the planned outputs of one `CharacterPacks` request."""

    def __init__(self, store: ProjectStore, request: CharacterPacks, built: Built, subject: Subject) -> None:
        self.store, self.request, self.built, self.subject = store, request, built, subject
        self.lighting = reference_lighting(built, request)
        self.identity: dict[str, Any] = {}
        self.asset_outputs: dict[str, str] = {}  # asset id -> its output in this request

    def ref(self, image_id: str, subject: Subject, role: str) -> PlannedRef:
        return PlannedRef.model_validate(
            {"image_id": image_id, "subject_id": subject.id, "version": subject.version, "role": role}
        )

    def hero(self) -> dict[str, Any]:
        own = [self.ref(i, self.subject, "identity") for i in self.subject.reference_images]
        spec = {"item": "Hero", **packs()["hero"].items[0]}
        out = self._add("hero", spec, references=own, conditions=["identity_ref"] if own else [])
        return {"depends_on": [Dependency(output=out.id, role="identity")]}

    def item(self, pack: str, spec: dict[str, Any]) -> None:
        if pack == "assets":
            self._asset(spec)
            return
        fields: dict[str, Any] = {k: list(v) for k, v in self.identity.items()}
        flags = ["identity_ref", "character"] + [k for k in ("expression", "pose") if spec.get(k)]
        flags += ["state"] if spec.get("state") or spec.get("outfit") else []
        if asset_id := spec.get("asset_id"):
            asset = self.store.subject(asset_id)
            if asset_id in self.asset_outputs:
                fields.setdefault("depends_on", []).append(
                    Dependency(output=self.asset_outputs[asset_id], role="object")
                )
                flags.append("object_ref")
            elif image := accepted_hero(self.store, asset_id):
                fields.setdefault("references", []).append(self.ref(image, asset, "object"))
                flags.append("object_ref")
        self._add(pack, spec, conditions=flags, **fields)

    def _asset(self, spec: dict[str, Any]) -> None:
        asset = self.store.subject(spec["asset_id"])
        own = [self.ref(i, asset, "object") for i in asset.reference_images]
        out = self._add(
            "assets",
            {"item": asset.name, "camera": "front", "framing": "the whole object centred"},
            who=asset,
            references=own,
            conditions=["identity_ref"] if own else [],
        )
        self.asset_outputs[asset.id] = out.id

    def _add(
        self, pack: str, spec: dict[str, Any], *, who: Subject | None = None, **fields: Any
    ) -> PlannedOutput:
        subject = who or self.subject
        values = {k: v for k, v in spec.items() if k not in ("item", "asset_id", "outfit", "state")}
        empty_hands = packs()[pack].empty_hands and subject.kind == "character"
        action = pack == "actions"
        flags = list(fields.pop("conditions", [])) + view_flags(values.get("camera"))
        flags += ["clean_background"] + (["no_props"] if empty_hands else [])
        links = [SubjectLink(subject_id=subject.id, version=subject.version)]
        if action and spec.get("asset_id"):
            asset = self.store.subject(spec["asset_id"])
            links.append(SubjectLink(subject_id=asset.id, version=asset.version))
        return self.built.add(
            spec["item"],
            "interaction" if action else subject.kind,
            subjects=links,
            judging=_judging(pack, subject),
            conditions=list(dict.fromkeys(flags)),
            pack=pack,
            item=spec["item"],
            prompt_inputs=base_inputs(
                self.built.choices,
                self.request,
                who=[(subject, spec.get("state") if subject.kind == "character" else None)],
                reference=True,
                background=WHITE,
                empty_hands=empty_hands,
                outfit=spec.get("outfit"),
                state=spec.get("state"),
                lighting=self.lighting,
                **values,
            ),
            **fields,
        )


def _judging(pack: str, subject: Subject) -> str:
    if pack == "actions":
        return "interaction-plausibility"
    return "object-fidelity" if subject.kind == "asset" else "character-identity"
