"""The pieces a prompt is made of (design §8.8, change 0002): each turns an output's inputs into one
sentence, or nothing. Dialects choose which pieces, in what order (dialects.py)."""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from hone_frame.dialects import Dialect, Mode
from hone_frame.requests import PlannedOutput, PlannedRef

ROLE_WORDS = {
    "identity": "keep the face, hair, body and clothing of {name} exactly as in image {n}",
    "object": "{name} must look exactly like the object in image {n}",
    "environment": "the place is the one in image {n} ({name})",
    "outfit": "dress {name} in the outfit shown in image {n}",
    "pose": "match the body pose shown in image {n}",
    "expression": "match the facial expression shown in image {n}",
    "composition": "keep the composition, framing and camera of image {n}",
    "lighting": "match the lighting of image {n}",
    "style": "match the art style of image {n}",
}
NOUN = {"character": "person", "environment": "place", "asset": "object"}


@dataclass
class Ctx:
    """What a section can read."""

    out: PlannedOutput
    refs: list[tuple[PlannedRef, str]]
    findings: list[str]
    dialect: Dialect
    mode: Mode
    style_form: str
    inputs: dict[str, Any] = field(default_factory=dict[str, Any])
    compact: bool = False  # over budget: `keep` names the clothes instead of listing them (change 0004)

    @property
    def parts(self) -> list[dict[str, Any]]:
        return list(self.inputs.get("subject_parts") or [])

    @property
    def camera(self) -> dict[str, Any]:
        return dict(self.inputs.get("camera_values") or {})

    @property
    def faces_away(self) -> bool:
        """Only a figure turns its back; a place or an object seen from behind has no face to hide."""
        drawn = self.parts[0].get("kind") if self.parts else None
        return bool(self.camera.get("faces_away")) and drawn not in KEPT

    @property
    def style(self) -> dict[str, Any]:
        return dict(self.inputs.get("style") or {})


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}  # pyright: ignore[reportUnknownArgumentType]


def _field(part: dict[str, Any], key: str) -> str:
    value: Any = _mapping(part.get("fields")).get(key)
    if isinstance(value, list):
        items: list[Any] = list(value)  # pyright: ignore[reportUnknownArgumentType]
        return ", ".join(str(v) for v in items)
    return str(value or "").strip().rstrip(".;, ")


def camera_phrase(c: Ctx) -> str:
    template = c.dialect.camera_phrase
    if not template:
        return ""
    cam = {"azimuth": "front view", "elevation": "eye-level shot", "distance": "medium shot"} | c.camera
    if c.inputs.get("full_body"):
        cam["distance"] = "wide shot"
    return template.format(**cam)


def shot(c: Ctx) -> str:
    words = [str(c.inputs.get("camera") or "").strip().rstrip(",")]
    if c.inputs.get("framing"):
        words.append(str(c.inputs["framing"]))
    elif c.inputs.get("full_body"):
        words.append("the whole figure from head to feet, nothing cropped")
    return ", ".join(w for w in words if w)


def view(c: Ctx) -> str:
    if not c.parts:
        return ""
    part = c.parts[0]
    noun = NOUN.get(str(part.get("kind")), "subject")
    words = str(c.inputs.get("camera") or "").strip().rstrip(",")  # a free-text view (objects, 0005)
    where = str(c.camera.get("view") or words or "from the same angle")
    lead = f"now {c.inputs['pose']}, " if _pose_leads(c) else ""  # an edit model keeps the pose it is shown
    mannequin = next((n for n, (r, _) in enumerate(c.refs, 1) if r.role == "pose"), None)
    if lead and mannequin:  # the pose library's mannequin shows it (change 0005)
        lead = f"in exactly the body pose of the wooden mannequin in image {mannequin} ({c.inputs['pose']}), "
    sentence = f"Show the same {noun} as in image 1, {part.get('name')}, {lead}{where}"
    if c.inputs.get("full_body"):
        sentence += ", the whole figure from head to feet"
    if c.inputs.get("framing"):
        sentence += f", {c.inputs['framing']}"
    if c.faces_away:
        sentence += "; the face is not visible, the figure faces away from the camera"
    return sentence


def _pose_leads(c: Ctx) -> bool:
    """A pose image (change 0004): the new pose opens the edit instruction, the first words an edit model
    weighs most, instead of following the long list of what stays the same."""
    return c.mode == "view" and c.out.pack == "poses" and bool(c.inputs.get("pose"))


def subject(c: Ctx) -> str:
    texts: list[str] = []
    for part in c.parts:
        name, about = str(part.get("name") or ""), str(part.get("description") or "").strip().rstrip(".")
        bits = [about if about.startswith(name) else f"{name}: {about}".rstrip(": ")]
        if not c.faces_away and _field(part, "appearance"):
            bits.append(_field(part, "appearance"))
        if _field(part, "proportions"):
            bits.append(_field(part, "proportions"))
        texts.append("; ".join(bits))
    return ". ".join(texts)


def outfit(c: Ctx) -> str:
    """The clothes; an outfit item (change 0003) names its own, and a view mentions only that."""
    if c.inputs.get("outfit") and c.parts:
        return f"{c.parts[0].get('name')} now wears {c.inputs['outfit']} instead of the usual clothes"
    if c.mode == "view":
        return ""
    return ". ".join(f"{p.get('name')} wears {_field(p, 'outfits')}" for p in c.parts if _field(p, "outfits"))


def features(c: Ctx) -> str:
    return ". ".join(_field(p, "features") for p in c.parts if _field(p, "features"))


def short_outfit(text: str) -> str:
    """Every piece of clothing named, without its details, so a long outfit fits a view's budget and no
    piece (a helmet) is forgotten: each comma part up to its first "with", split where another garment
    is worn over or under it ("over a tunic", not "over the hair"), six words a piece."""
    pieces: list[str] = []
    for part in text.split(","):
        bare = re.split(r"\s+with\s+", part.strip(), maxsplit=1)[0]
        pieces += [
            p for p in re.split(r"\s+(?:worn\s+(?:over|under)|(?:over|under)(?=\s+an?\s))\s+", bare) if p
        ]
    short = [" ".join(piece.split()[:6]) for piece in pieces]
    return ("the same clothes: " + ", ".join(short)) if short else "the same clothes and colours"


KEPT = {
    "environment": "the same place, buildings, materials and colours",
    "asset": "the same object, shape, materials and colours",
}


def keep(c: Ctx) -> str:
    if not c.parts:
        return ""
    part = c.parts[0]
    if part.get("kind") in KEPT:  # a person's face and clothes would walk into a place's or an object's view
        kept = [KEPT[str(part["kind"])]] + [x for x in [_field(part, "features")] if x]
        return "Keep exactly the same as in image 1: " + "; ".join(kept) + ". Change only what is asked above"
    kept = ["the same build and height, the same hair" if c.faces_away else "the same face, hair and build"]
    if c.inputs.get("outfit"):
        clothes = ""
    elif c.camera.get("distance") == "close-up" and not c.inputs.get("full_body"):
        clothes = "the same clothes and colours where they show"  # naming boots would widen a close-up
    elif c.compact:
        clothes = short_outfit(_field(part, "outfits"))
    else:
        clothes = _field(part, "outfits")
    kept += [x for x in (clothes, _field(part, "features")) if x]
    return "Keep exactly the same as in image 1: " + "; ".join(kept) + ". Change only what is asked above"


def scene(c: Ctx) -> str:
    return str(c.inputs.get("description") or "")


def roles(c: Ctx) -> str:
    sentences = [
        ROLE_WORDS[r.role].format(name=name or "the subject", n=i) for i, (r, name) in enumerate(c.refs, 1)
    ]
    return ("Reference images: " + "; ".join(sentences)) if sentences else ""


def _short_style(c: Ctx) -> bool:
    """A short prompt, or a reference image: the style's few words, without the pack's setting and mood
    (a reference stands on a plain background, whatever the style pack's scene wording)."""
    return c.style_form == "short" or bool(c.inputs.get("reference"))


def style_lead(c: Ctx) -> str:
    """The style's opening words, and the variation's own direction after them (change 0005)."""
    own = _mapping(_mapping(c.style.get("dialects")).get(c.dialect.name))
    if own.get("prefix"):
        lead = str(own["prefix"])
    else:
        lead = str(c.style.get("short") or "") if _short_style(c) else str(c.style.get("prefix") or "")
    direction = str(c.style.get("direction") or "").strip().rstrip(".")
    return ", ".join(x.strip().rstrip(".,") for x in (lead, direction) if x.strip())


def look(c: Ctx) -> str:
    """The world's look guide (change 0005): its culture, period, costume and materials in concrete words.
    An edit of the same subject leaves it out (the reference shows it) unless the item brings something
    new into the picture, like an outfit (`context` "full")."""
    if c.mode == "view" and c.inputs.get("context") != "full":
        return ""
    if c.mode != "compose" and c.parts and c.parts[0].get("kind") in ("environment", "asset"):
        return ""  # a place's or an object's own description says what it looks like; the look guide's
        # people and costumes would walk into the picture (change 0006: crowds in an empty fortress)
    return str(c.inputs.get("look") or "").strip()


def alone(c: Ctx) -> str:
    """Nobody else in a reference image (change 0006): an object alone, a character alone, a place
    empty. A look guide that describes people otherwise brings them into the picture."""
    if c.inputs.get("object_alone"):
        return "The object alone: no person, no hands, nobody holding, wearing or riding it"
    if c.inputs.get("empty_place"):
        return "The place is empty: no people, no animals, nobody in it"
    if c.inputs.get("solo") and c.parts and c.mode != "view":  # an edit of one person keeps one person
        return f"Only {c.parts[0].get('name')}, alone: no other people in the picture"
    return ""


def _items(value: Any) -> list[Any]:
    return list(value) if isinstance(value, list) else []  # pyright: ignore[reportUnknownArgumentType]


def must(c: Ctx) -> str:
    """What a subject always shows (change 0005)."""
    items = [str(m) for p in c.parts for m in _items(p.get("must"))]
    return ("Always visible: " + "; ".join(items)) if items else ""


def style_close(c: Ctx) -> str:
    own = _mapping(_mapping(c.style.get("dialects")).get(c.dialect.name))
    if own.get("suffix"):
        return str(own["suffix"])
    return "" if _short_style(c) else str(c.style.get("suffix") or "")


def _labelled(label: str, key: str) -> Callable[[Ctx], str]:
    def section(c: Ctx) -> str:
        value = c.inputs.get(key)
        return f"{label}: {value}" if label and value else str(value or "")

    return section


SECTION: dict[str, Callable[[Ctx], str]] = {
    "camera_phrase": camera_phrase,
    "shot": shot,
    "view": view,
    "subject": subject,
    "outfit": outfit,
    "features": features,
    "keep": keep,
    "scene": scene,
    "roles": roles,
    "action": _labelled("Action", "action"),
    "expression": _labelled("", "expression"),
    "pose": lambda c: "" if _pose_leads(c) else str(c.inputs.get("pose") or ""),
    "gaze": _labelled("Gaze", "gaze"),
    "state": _labelled("State", "state"),
    "frame": _labelled("", "frame"),
    "background": _labelled("", "background"),
    "look": look,
    "must": must,
    "alone": alone,
    "props": lambda c: (
        "Empty hands: no weapon, tool or object held or carried" if c.inputs.get("empty_hands") else ""
    ),
    "lighting": _labelled("", "lighting"),
    "style_lead": style_lead,
    "style_close": style_close,
    "text_refs": lambda c: ("Also: " + "; ".join(c.out.text_refs)) if c.out.text_refs else "",
    "note": lambda c: (
        str(c.inputs.get("note") or "").strip()
        + (" " + str(c.inputs.get("notes")) if c.inputs.get("notes") else "")
    ),
    "fixes": lambda c: ("Fix from the last attempt: " + "; ".join(c.findings)) if c.findings else "",
}
