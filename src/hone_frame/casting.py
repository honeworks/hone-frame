"""Hero casting (change 0006): candidates of a hero that really differ. A fast distilled model draws
near-copies for the same prompt whatever the seed, so the planner writes distinct readings of the
description first (each keeps everything stated and varies only what it leaves open), and each candidate
is drawn from one. Without a planner, or when it fails, candidates differ by seed only."""

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

from hone_frame.ports import ModelFailure

if TYPE_CHECKING:
    from hone_frame.ports import Models
    from hone_frame.requests import PlannedOutput


class CastingAnswer(BaseModel):
    readings: list[str] = Field(default_factory=list[str])


def casting_prompt(out: PlannedOutput, n: int) -> str:
    parts = list(out.prompt_inputs.get("subject_parts") or [])
    about = "; ".join(f"{p.get('name')}: {p.get('description')} {p.get('fields')}" for p in parts)
    return (
        f"You are casting a character for an illustrated story. The description is: {about}\n"
        f"Write {n} distinct readings of this character, 20 to 40 words each, for an image model. Every "
        "reading keeps everything the description states and varies only what it leaves open: face shape, "
        "nose, eyes, hair and beard style, age within the stated range, build details, how the clothing is "
        "worn, colour accents not stated. Make the readings clearly different from each other.\n"
        'Return JSON: {"readings": ["...", "..."]}.'
    )


def readings(models: Models, planner: str | None, out: PlannedOutput, n: int) -> list[str]:
    """`n` readings, or [] (seeds only) without a planner or when it fails."""
    if not planner or n < 2:
        return []
    try:
        answer = models.ask(planner, casting_prompt(out, n), images=[], schema=CastingAnswer, think=False)
    except ModelFailure:
        return []
    found = [r.strip() for r in answer.readings if r.strip()]
    return found[:n] if len(found) >= 2 else []
