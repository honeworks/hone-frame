"""Prompts (design §8.2, §8.8): written for the model's dialect, the task (mode) and the style; the
planner may rewrite them within the dialect's rules, and its answer is checked."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel

from hone_frame.dialects import REQUIRED, Dialect, Mode
from hone_frame.prompt_sections import ROLE_WORDS, SECTION, Ctx
from hone_frame.requests import PlannedOutput, PlannedRef

OPERATIONS = {
    "refine": "Refine image 1: keep its composition, subjects, pose and camera exactly; improve detail, "
    "sharpness and finish.",
    "upscale": "Upscale image 1 faithfully, adding no new content.",
}
SUBJECT_KINDS = {"character", "environment", "asset"}


class PlannerAnswer(BaseModel):
    prompt: str
    negative: str | None = None


@dataclass(frozen=True)
class Composed:
    text: str
    dialect: str
    mode: str
    max_words: int
    camera_phrase: str
    asked: tuple[str, ...] = ()  # the words of what this image exists to show; a rewrite must keep them
    over_budget: bool = False  # even the shortest form is longer than `max_words`: it is sent anyway


# What a person or a pack asked for: never dropped to fit the budget (change 0004). The prompt is
# shortened by the compact `keep` first, then by optional sections; if it still does not fit, it is
# sent longer than the budget rather than without what it is for.
ASKED = ("pose", "expression", "outfit", "state", "action", "gaze", "note")


def mode_for(out: PlannedOutput, refs: list[tuple[PlannedRef, str]]) -> Mode:
    """`generate` when the model gets no image; `view` for the same subject again; `compose` otherwise."""
    if not refs:
        return "generate"
    return "view" if out.kind in SUBJECT_KINDS else "compose"


def compose(
    out: PlannedOutput, refs: list[tuple[PlannedRef, str]], findings: list[str], dialect: Dialect
) -> Composed:
    """The prompt for this output, written the dialect's way for its mode (change 0002)."""
    p = out.prompt_inputs
    if p.get("fixed_prompt"):  # a pose-library mannequin: one fixed wording for every model (0005)
        fixes = ("Fix from the last attempt: " + "; ".join(findings)) if findings else ""
        return Composed(_join([p["fixed_prompt"], fixes]), dialect.name, "fixed", 0, "")
    if p.get("prompt_override"):  # a promotion keeps its own wording (0001)
        head = OPERATIONS.get(str(p.get("operation")), "")
        fixes = ("Fix from the last attempt: " + "; ".join(findings)) if findings else ""
        text = _join([head, str(p["prompt_override"]), _roles(refs[1:], start=2), fixes])
        return Composed(text, dialect.name, "promotion", 0, "")
    mode = mode_for(out, refs)
    rules = dialect.rules_for(mode)
    ctx = Ctx(out, refs, findings, dialect, mode, rules.style, dict(p))
    pieces = [(name, SECTION[name](ctx).strip()) for name in rules.sections]
    if _words(" ".join(t for _, t in pieces)) > rules.max_words:
        ctx.compact = True  # the reference image shows the clothes: name them, do not list them
        pieces = [(name, SECTION[name](ctx).strip()) for name in rules.sections]
    kept = _fit(pieces, rules.max_words)
    text = _join([t for _, t in kept])
    phrase = SECTION["camera_phrase"](ctx) if "camera_phrase" in rules.sections else ""
    asked = tuple(str(p[k]) for k in ASKED if p.get(k) and str(p[k]).lower() in text.lower())  # raw words
    over = _words(text) > rules.max_words
    return Composed(text, dialect.name, mode, rules.max_words, phrase, asked, over)


# what goes first when a prompt is over its budget; required sections never go (§8.8)
DROP_FIRST = (
    "style_close", "text_refs", "frame", "gaze", "features", "style_lead", "background", "state", "action",
    "pose", "expression", "outfit", "shot", "note", "lighting",
)  # fmt: skip  # `roles` is required since change 0007 (cause C)


def _fit(pieces: list[tuple[str, str]], max_words: int) -> list[tuple[str, str]]:
    """Drop optional pieces, least important first, until the prompt fits (required ones always stay)."""
    kept = [p for p in pieces if p[1]]
    for name in (*DROP_FIRST, *(n for n, _ in reversed(kept))):
        if _words(" ".join(t for _, t in kept)) <= max_words:
            break
        if name not in REQUIRED and name not in ASKED:
            kept = [p for p in kept if p[0] != name]
    return kept


def planner_prompt(out: PlannedOutput, draft: Composed, dialect: Dialect, findings: list[str]) -> str:
    """What the planner gets: the dialect's rules for this mode, the budget and the composed draft."""
    rules = dialect.rules_for(draft.mode)  # pyright: ignore[reportArgumentType]
    lines = [
        "You write the prompt for an image model. Keep every fact in the draft; invent nothing new.",
        f"Image model family: {dialect.summary or dialect.name}.",
        f"Task: {draft.mode} ({out.label}, {out.kind}).",
        f"Rules: {rules.rules or 'plain descriptive English.'} At most {rules.max_words} words.",
        "Refer to reference images by number exactly as the draft does.",
        f"Draft prompt:\n{draft.text}",
    ]
    if draft.asked:
        lines.append("This image exists to show the following; keep these words: " + "; ".join(draft.asked))
    if findings:
        lines.append(
            "A judge found these problems in the last attempt; the prompt must fix them: "
            + "; ".join(findings)
        )
    lines.append('Return JSON: {"prompt": "...", "negative": "..." or null}.')
    return "\n".join(lines)


def planner_problem(answer: str, draft: Composed) -> str | None:
    """Why the planner's prompt cannot be used (None when it can): too long, the camera phrase lost, or the
    reference images no longer named."""
    limit = max(draft.max_words * 1.25, _words(draft.text) * 1.1)  # a long draft may stay about as long
    if draft.max_words and _words(answer) > limit:
        return f"{_words(answer)} words, over the {draft.max_words}-word budget"
    if draft.camera_phrase and draft.camera_phrase not in answer:
        return f"the camera phrase {draft.camera_phrase!r} was lost"
    if "image 1" in draft.text.lower() and "image 1" not in answer.lower():
        return "the reference images are no longer named"
    for asked in draft.asked:
        rest = draft.text.lower().replace(asked.lower(), " ")
        if not kept_words(asked, answer, common=rest):
            return f"what the image is for was dropped ({asked!r})"
    return None


def kept_words(phrase: str, answer: str, *, common: str = "") -> bool:
    """Whether `answer` still says `phrase`: most of its content words (four letters or more) appear.
    Words that the rest of the draft (`common`) also has prove nothing and are not counted."""
    words = set(re.findall(r"[a-z]{4,}", phrase.lower())) - set(re.findall(r"[a-z]{4,}", common))
    if not words:
        return True
    found = sum(1 for w in words if w in answer.lower())
    return found >= max(1, round(0.6 * len(words)))


def _roles(refs: list[tuple[PlannedRef, str]], start: int = 1) -> str:
    sentences = [
        ROLE_WORDS[r.role].format(name=name or "the subject", n=i) for i, (r, name) in enumerate(refs, start)
    ]
    return ("Reference images: " + "; ".join(sentences)) if sentences else ""


def _words(text: str) -> int:
    return len(text.split())


def _join(parts: list[Any]) -> str:
    cleaned = [str(x).strip().rstrip(".,;") for x in parts if x and str(x).strip()]
    return ". ".join(c[0].upper() + c[1:] for c in cleaned) + "."
