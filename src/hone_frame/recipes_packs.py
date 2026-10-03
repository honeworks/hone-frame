"""Character packs (change 0003): every reference image of one character, pack by pack, all made from one
hero. The packs and their default items are data (`data/character_packs.toml`)."""

from __future__ import annotations

import re
import tomllib
from functools import cache
from importlib import resources
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, ConfigDict, Field

from hone_frame.errors import InvalidRequest
from hone_frame.pose_library import pose_reference
from hone_frame.recipes import (
    WHITE,
    Built,
    base_inputs,
    fragment,
    reference_lighting,
    view_flags,
)
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
    context: str = "short"  # "full": the item brings something new, so the world's look guide goes too (0005)
    items: list[dict[str, Any]] = Field(default_factory=list[dict[str, Any]])


CATALOGS = {"character": "character_packs.toml", "asset": "object_packs.toml"}  # objects: change 0005


@cache
def packs(kind: str = "character") -> dict[str, Pack]:
    """A kind's packs, in the order they are made: a character's, or an object's (change 0005)."""
    name = CATALOGS[kind]
    text = (resources.files("hone_frame") / "data" / name).read_text(encoding="utf-8")
    return {name: Pack.model_validate(row) for name, row in tomllib.loads(text)["packs"].items()}


def accepted_hero(store: ProjectStore, subject_id: str, variation: str | None = None) -> str | None:
    """The latest accepted hero image of a character or object in the variation (the active one by
    default, change 0005), or None."""
    v = variation or store.info.variation_of().id
    heroes = [
        i
        for i in store.images(subject_id=subject_id, variation=v)
        if len(i.subjects) == 1
        and i.status in ACCEPTED
        and (i.pack in ("hero", "assets") or i.label.lower() == "hero")  # "assets": a 0003 belonging
    ]
    return heroes[-1].id if heroes else None


def owned_assets(store: ProjectStore, character_id: str) -> list[Subject]:
    return [s for s in store.subjects("asset") if s.owner == character_id]


def pack_items(
    store: ProjectStore, subject: Subject, name: str, extra: list[str], *, only_extra: bool = False
) -> list[dict[str, Any]]:
    """One pack's items: its defaults, one per matching state or owned asset, and the person's own."""
    pack = packs(subject.kind if subject.kind in CATALOGS else "character")[name]
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
                size = str(asset.fields.get("scale") or "").strip()
                about = ", ".join(x for x in (f"{asset.name}: {asset.description}".rstrip(": "), size) if x)
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
    if subject.kind == "asset":  # an object: its own packs (change 0005)
        from hone_frame.recipes_objects import object_packs  # noqa: PLC0415 - that module imports this one

        object_packs(store, request, built)
        return
    if subject.kind != "character":
        raise InvalidRequest(f"{subject.name} is a {subject.kind}; packs are made for characters and objects")
    chosen = request.packs or list(packs())
    if unknown := sorted(set(chosen) - set(packs())) + sorted(set(request.custom) - set(packs())):
        raise InvalidRequest(f"unknown packs {unknown}; use {list(packs())}")
    if left_out := sorted(set(request.custom) - set(chosen)):
        raise InvalidRequest(
            f"items of your own for {left_out}, which are not in packs: add them or drop the items"
        )
    built.warnings += carried_objects(subject) + unstable_features(subject)
    maker = _PackMaker(store, request, built, subject)
    hero = None if request.redraw_hero else accepted_hero(store, subject.id, built.choices.variation.id)
    maker.identity = maker.hero() if hero is None else {"references": [maker.ref(hero, subject, "identity")]}
    for name in [n for n in packs() if n in chosen and n != "hero"]:
        extra = request.custom.get(name, [])
        for item in pack_items(store, subject, name, extra, only_extra=request.only_custom):
            maker.item(name, item)


HELD = re.compile(
    r"\b(sword|mace|spear|lance|bow|arrows?|axe|dagger|knife|shield|staff|club|lasso|whip|torch|cup|"
    r"holding|holds|carries|carrying|wields|wielding|in (?:his|her|their) (?:right |left )?hands?)\b",
    re.I,
)


SMALL_MARKS = re.compile(
    r"\b(beauty marks?|moles?|freckles?|birthmarks?|tattoos?|scars?|dimples?|piercings?|warts?|"
    r"small marks?|spots?|tear marks?)\b",
    re.I,
)


def unstable_features(subject: Subject) -> list[str]:
    """Warnings for small marks the image models cannot keep in place from image to image (change 0005:
    a beauty mark moved from the cheek to the chin to the forehead): keep it with an exact position and
    size and an Always-shown entry, or remove it."""
    found: list[str] = []
    for key, label in (("appearance", "appearance"), ("features", "distinguishing features")):
        if match := SMALL_MARKS.search(str(subject.fields.get(key) or "")):
            found.append(
                f"{subject.name}'s {label} mention {match.group(0)!r}: small marks drift between images "
                "(another place, another size, or gone). If it matters, give its exact place and size "
                "(e.g. 'a small dark mole just above the left corner of the upper lip') and add it to "
                "Always shown; otherwise remove it"
            )
    return found


def carried_objects(subject: Subject) -> list[str]:
    """Warnings for a description that puts an object in the character's hands: reference images are
    drawn with empty hands, so the prompt would contradict itself (change 0004)."""
    found: list[str] = []
    for key, label in (("features", "distinguishing features"), ("outfits", "default outfit")):
        if match := HELD.search(str(subject.fields.get(key) or "")):
            found.append(
                f"{subject.name}'s {label} mention {match.group(0)!r}: reference images show empty hands, "
                "so carried objects belong in Belongings; move it there"
            )
    return found


class _PackMaker:
    """Adds the planned outputs of one `CharacterPacks` request."""

    def __init__(self, store: ProjectStore, request: CharacterPacks, built: Built, subject: Subject) -> None:
        self.store, self.request, self.built, self.subject = store, request, built, subject
        self.lighting = reference_lighting(built, request)
        self.identity: dict[str, Any] = {}
        self.asset_outputs: dict[str, str] = {}  # asset id -> its output in this request
        self.mannequins: dict[str, str] = {}  # pose -> its mannequin's output in this request

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
        if pack == "poses" and spec.get("pose"):  # the mannequin of the pose library (change 0005)
            words = fragment(self.built.choices, "pose", str(spec["pose"]))
            for k, v in pose_reference(self.store, self.built, words, self.mannequins).items():
                fields.setdefault(k, []).extend(v)
        if asset_id := spec.get("asset_id"):  # an action: its belonging is the object reference
            v = self.built.choices.variation.id
            image = None if asset_id in self.asset_outputs else accepted_hero(self.store, asset_id, v)
            if image:
                fields.setdefault("references", []).append(
                    self.ref(image, self.store.subject(asset_id), "object")
                )
            else:  # made first in this request, and the action waits for it (change 0004)
                if asset_id not in self.asset_outputs:
                    self._asset({"asset_id": asset_id})
                dep = Dependency(output=self.asset_outputs[asset_id], role="object")
                fields.setdefault("depends_on", []).append(dep)
            flags.append("object_ref")
        self._add(pack, spec, conditions=flags, **fields)

    def _asset(self, spec: dict[str, Any]) -> None:
        """A belonging's whole object pack, before the actions that use it (change 0005): its hero
        (unless one is accepted) and its views."""
        from hone_frame.recipes_objects import add_object  # noqa: PLC0415 - that module imports this one

        asset = self.store.subject(spec["asset_id"])
        hero = accepted_hero(self.store, asset.id, self.built.choices.variation.id)
        if out := add_object(self.store, self.built, self.request, asset, hero=hero):
            self.asset_outputs[asset.id] = out

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
                context=packs()[pack].context,
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
