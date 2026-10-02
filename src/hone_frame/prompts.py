"""Prompts (design §8.2, §8.8): written for the model's dialect, the task (mode) and the style; the
planner may rewrite them within the dialect's rules, and its answer is checked."""

from __future__ import annotations

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
    if p.get("prompt_override"):  # a promotion keeps its own wording (0001)
        head = OPERATIONS.get(str(p.get("operation")), "")
        fixes = ("Fix from the last attempt: " + "; ".join(findings)) if findings else ""
        text = _join([head, str(p["prompt_override"]), _roles(refs[1:], start=2), fixes])
        return Composed(text, dialect.name, "promotion", 0, "")
    mode = mode_for(out, refs)
    rules = dialect.rules_for(mode)
    ctx = Ctx(out, refs, findings, dialect, mode, rules.style, dict(p))
    pieces = _fit([(name, SECTION[name](ctx).strip()) for name in rules.sections], rules.max_words)
    phrase = SECTION["camera_phrase"](ctx) if "camera_phrase" in rules.sections else ""
    return Composed(_join([text for _, text in pieces]), dialect.name, mode, rules.max_words, phrase)


# what goes first when a prompt is over its budget; required sections never go (§8.8)
DROP_FIRST = (
    "style_close", "text_refs", "frame", "gaze", "features", "style_lead", "background", "state", "action",
    "pose", "expression", "outfit", "shot", "note", "lighting", "roles",
)  # fmt: skip


def _fit(pieces: list[tuple[str, str]], max_words: int) -> list[tuple[str, str]]:
    """Drop optional pieces, least important first, until the prompt fits (required ones always stay)."""
    kept = [p for p in pieces if p[1]]
    for name in (*DROP_FIRST, *(n for n, _ in reversed(kept))):
        if _words(" ".join(t for _, t in kept)) <= max_words:
            break
        if name not in REQUIRED:
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
    if draft.max_words and _words(answer) > draft.max_words * 1.25:
        return f"{_words(answer)} words, over the {draft.max_words}-word budget"
    if draft.camera_phrase and draft.camera_phrase not in answer:
        return f"the camera phrase {draft.camera_phrase!r} was lost"
    if "image 1" in draft.text.lower() and "image 1" not in answer.lower():
        return "the reference images are no longer named"
    return None


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
