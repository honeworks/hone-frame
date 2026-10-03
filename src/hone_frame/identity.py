"""Who a character is, as short words (change 0007): measurable parameters (sex, age, body, hair,
beard, permanent marks) turned into the few tokens a prompt carries for a kind of image, and
into facts the judge checks. The token choice per kind of image is data (`data/parameters.toml`)."""

from __future__ import annotations

import tomllib
from functools import cache
from importlib import resources
from typing import Any

FACE_WORDS = ("face", "cheek", "brow", "forehead", "lip", "chin", "eye", "nose", "jaw", "mouth", "ear")
BACK_WORDS = ("back", "shoulder", "neck", "nape")
BUILD_CLASS = {"slight": "slight", "lean": "slight", "average": "average", "athletic": "average",
               "heavy": "heavy", "massive": "heavy"}  # fmt: skip


@cache
def table() -> dict[str, Any]:
    text = (resources.files("hone_frame") / "data" / "parameters.toml").read_text(encoding="utf-8")
    return tomllib.loads(text)


def _marks(params: dict[str, Any]) -> list[dict[str, str]]:
    found: Any = params.get("marks") or []
    return [{k: str(v) for k, v in m.items()} for m in found if isinstance(m, dict)]  # pyright: ignore[reportUnknownVariableType, reportUnknownArgumentType]


def _mark_words(mark: dict[str, str]) -> str:
    words = mark.get("what", "")
    if mark.get("where") and mark["where"].lower() not in words.lower():
        words += f" ({mark['where']})"
    return words


def _where(mark: dict[str, str]) -> str:
    return f"{mark.get('what', '')} {mark.get('where', '')}".lower()


def tokens(params: dict[str, Any]) -> dict[str, str]:
    """Every token this character's parameters give (empty when the parameter is not set)."""
    p = {k: v for k, v in params.items() if v not in (None, "", [])}
    beard = table()["beard"].get(str(p.get("beard", "")), str(p.get("beard", "")))
    hair = " ".join(str(p[k]) for k in ("hair_length", "hair_colour") if k in p)
    hair = hair if not hair or "hair" in hair else f"{hair} hair"
    marks = _marks(p)
    return {
        "who": ", ".join(str(p[k]) for k in ("sex", "age") if k in p),
        "body": table()["body"].get(str(p.get("body", "")), str(p.get("body", ""))),
        "hair": hair,
        "beard": beard,
        "face_marks": "; ".join(_mark_words(m) for m in marks if any(w in _where(m) for w in FACE_WORDS)),
        "body_marks": "; ".join(_mark_words(m) for m in marks if not any(w in _where(m) for w in FACE_WORDS)),
        "back_marks": "; ".join(_mark_words(m) for m in marks if any(w in _where(m) for w in BACK_WORDS)),
    }


def image_kind(inputs: dict[str, Any], faces_away: bool) -> str:
    """The kind of image for the token choice: a face close-up, a figure from behind, or the whole figure."""
    camera: dict[str, Any] = dict(inputs.get("camera_values") or {})
    if faces_away:
        return "back"
    if camera.get("distance") == "close-up" and not inputs.get("full_body"):
        return "close"
    return "full"


def identity_line(params: dict[str, Any], kind: str) -> str:
    """The short words a prompt carries for this kind of image: "a man, about fifty; a full beard reaching
    the chest; two black serpents growing out of his shoulders"."""
    found = tokens(params)
    wanted: list[str] = table()["kinds"][kind]["tokens"]
    return "; ".join(found[t] for t in wanted if found.get(t))


def facts(params: dict[str, Any]) -> list[str]:
    """The parameters as facts for the judge."""
    found = tokens(params)
    return [f"{label}: {found[key]}" for key, label in (("who", "Person"), ("body", "Body"), ("hair", "Hair"),
            ("beard", "Beard")) if found.get(key)]  # fmt: skip


def mark_checks(params: dict[str, Any]) -> list[str]:
    """One required judge question per permanent mark."""
    return [_mark_words(m) for m in _marks(params)]


def build_class(params: dict[str, Any]) -> str:
    return BUILD_CLASS.get(str(params.get("body") or ""), "average")
