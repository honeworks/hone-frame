"""Prompts (design §8.2): the template prompt, and the planner that may rewrite it for the model."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

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
OPERATIONS = {
    "refine": "Refine image 1: keep its composition, subjects, pose and camera exactly; improve detail, "
    "sharpness and finish.",
    "upscale": "Upscale image 1 faithfully, adding no new content.",
}


class PlannerAnswer(BaseModel):
    prompt: str
    negative: str | None = None


def template_prompt(out: PlannedOutput, refs: list[tuple[PlannedRef, str]], findings: list[str]) -> str:
    """The prompt built from the output's inputs (design §8.2). `refs` are (reference, subject name) in
    the order the model receives them."""
    p = out.prompt_inputs
    if p.get("prompt_override"):
        head = OPERATIONS.get(str(p.get("operation")), "")
        return _join([head, str(p["prompt_override"]), _roles(refs[1:], start=2), _fixes(findings)])
    parts = [
        p.get("style_prefix"),
        p.get("camera"),
        p.get("framing"),
        p.get("description"),
        "; ".join(p.get("subjects") or []),
        _labelled("Action", p.get("action")),
        p.get("expression"),
        p.get("pose"),
        _labelled("Gaze", p.get("gaze")),
        _labelled("State", p.get("state")),
        p.get("frame"),
        p.get("lighting"),
        p.get("notes"),
        p.get("note"),
        _roles(refs),
        _labelled("Also", "; ".join(out.text_refs)),
        _fixes(findings),
        p.get("style_suffix"),
    ]
    return _join(parts)


def planner_prompt(out: PlannedOutput, template: str, guide: str, findings: list[str]) -> str:
    """What the planner gets: the material, the model's prompt guide and the template it may improve."""
    lines = [
        "You write the prompt for an image model. Keep every fact below; do not invent new subjects or text.",
        f"Output: {out.label} ({out.kind}).",
        "The image model's own guidance on prompts: "
        + (guide or "none given; write plain descriptive English")
        + ".",
        "Mention the reference images by number exactly as the draft does.",
        f"Draft prompt:\n{template}",
    ]
    if findings:
        lines.append(
            "A judge found these problems in the last attempt; the new prompt must fix them: "
            + "; ".join(findings)
        )
    lines.append('Return JSON: {"prompt": "...", "negative": "..." or null}.')
    return "\n".join(lines)


def _roles(refs: list[tuple[PlannedRef, str]], start: int = 1) -> str:
    sentences = [
        ROLE_WORDS[r.role].format(name=name or "the subject", n=i)
        for i, (r, name) in enumerate(refs, start=start)
    ]
    return ("Reference images: " + "; ".join(sentences)) if sentences else ""


def _fixes(findings: list[str]) -> str:
    return ("Fix from the last attempt: " + "; ".join(findings)) if findings else ""


def _labelled(label: str, value: Any) -> str:
    return f"{label}: {value}" if value else ""


def _join(parts: list[Any]) -> str:
    cleaned = [str(x).strip().rstrip(".,;") for x in parts if x and str(x).strip()]
    return ". ".join(c[0].upper() + c[1:] for c in cleaned) + "."
