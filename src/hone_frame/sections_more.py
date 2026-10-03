"""Prompt pieces added by change 0007: who the person is (from parameters), worn elements, garments, and
an object's or a place's own fields. `prompt_sections` maps them to section names."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from hone_frame.identity import identity_line, image_kind

if TYPE_CHECKING:
    from hone_frame.prompt_sections import Ctx

OBJECT_FIELDS = ("details", "materials", "colours", "scale")  # an object's own words, most telling first
PLACE_FIELDS = ("anchors", "materials")


def garments(part: dict[str, Any]) -> list[dict[str, str]]:
    """A character's garments `[{name, details}]` (change 0007), or none."""
    found: Any = dict(part.get("fields") or {}).get("garments") or []
    rows: list[dict[str, str]] = []
    for g in found:
        row: dict[str, Any] = cast("dict[str, Any]", g) if isinstance(g, dict) else {}
        rows.append(
            {"name": str(row.get("name", "")).strip(), "details": str(row.get("details", "")).strip()}
        )
    return [g for g in rows if g["name"] or g["details"]]


def garment_names(part: dict[str, Any]) -> str:
    return ", ".join(g["name"] or g["details"] for g in garments(part))


def garment_details(part: dict[str, Any]) -> str:
    return "; ".join(g["details"] or g["name"] for g in garments(part))


def own_fields(part: dict[str, Any]) -> list[str]:
    """An object's or a place's own fields as phrases (root cause B: they never reached the prompt)."""
    fields: dict[str, Any] = dict(part.get("fields") or {})
    keys = (
        OBJECT_FIELDS
        if part.get("kind") == "asset"
        else PLACE_FIELDS
        if part.get("kind") == "environment"
        else ()
    )
    return [str(fields[k]).strip().rstrip(".") for k in keys if str(fields.get(k) or "").strip()]


def identity(c: Ctx) -> str:
    """Who each person is, in the few words this kind of image needs (root cause D). In `compose` mode one
    line per character; otherwise the first subject's."""
    parts = [p for p in c.parts if p.get("kind") == "character" and p.get("params")]
    if c.mode != "compose":
        parts = parts[:1]
    kind = image_kind(c.inputs, c.faces_away)
    lines = [f"{p.get('name')}: {line}" for p in parts if (line := identity_line(dict(p["params"]), kind))]
    return ". ".join(lines)


def worn(c: Ctx) -> str:
    """Worn elements (change 0007): "wearing Zahhak's crown on his head"."""
    found: list[Any] = list(c.inputs.get("worn") or [])
    items = [str(w) for w in found]
    return ("Wearing " + "; ".join(items)) if items else ""
