"""One candidate image (design §8.2, §8.4): its seed, the inputs the model gets, how a result is
checked, and the record it is stored with."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from hone_frame.judging import findings
from hone_frame.ports import Generated, ModelFailure
from hone_frame.records import Generation, ImageRecord, RefUse
from hone_frame.requests import PlannedOutput, PlannedRef, ResolvedProfile

RETRY_KINDS = {"out_of_memory", "failed", "no_output", None}


class CandidateRefused(Exception):
    """The model refused or rejected this one candidate's input; the output goes on (design §8.4)."""


def seed_for(*parts: object) -> int:
    return int(hashlib.sha256(":".join(map(str, parts)).encode()).hexdigest()[:8], 16)


def model_inputs(
    out: PlannedOutput,
    profile: ResolvedProfile,
    negative: str | None,
    refs: list[Path],
    *,
    camera_in_prompt: bool = False,
) -> tuple[dict[str, Any], list[Path]]:
    """The named inputs and reference files of one image call; an upscale sends its draft as `image`. When
    the dialect writes the camera phrase into the prompt, `camera_angle` is not sent as well (0002)."""
    inputs: dict[str, Any] = dict(profile.settings) | {"size": out.size}
    if negative := (negative or out.prompt_inputs.get("negative")):
        inputs["negative"] = negative
    if (angle := out.prompt_inputs.get("camera_angle")) and not camera_in_prompt:
        inputs["camera_angle"] = angle
    if out.mode == "upscale":
        if not refs:
            raise ModelFailure(
                f"{out.label}: an upscale needs its draft image as a reference; plan it with "
                "hf.Promote(image_id=..., operation='upscale')",
                transient=False,
            )
        inputs["image"], refs = refs[0], []
    return inputs, refs


def checked(result: Generated, model: str) -> Generated:
    """A job without a file: retried when transient (OOM, failed, no output), else a refused candidate."""
    if result.error is None and result.path is not None:
        return result
    message = f"{model}: {result.error or 'no output'} ({result.error_kind})"
    if result.error_kind in RETRY_KINDS:
        raise ModelFailure(message, transient=True)
    raise CandidateRefused(message)


def image_fields(
    run_id: str,
    out: PlannedOutput,
    profile: ResolvedProfile,
    refs: list[PlannedRef],
    *,
    slot: tuple[int, int],
    prompt: str,
    negative: str | None,
    result: Generated,
    dialect: tuple[str, str] | None = None,
    variation: str = "",
) -> dict[str, Any]:
    """The `ImageRecord` fields of a stored candidate (design §4.3)."""
    generation = Generation(
        model=out.model,
        prompt=prompt,
        negative=negative or out.prompt_inputs.get("negative"),
        inputs={"size": out.size, **profile.settings},
        references=[RefUse(image_id=r.image_id, role=r.role) for r in refs],
        seed=result.seed,
        job_id=result.job_id,
        elapsed_s=result.elapsed_s,
        cost_usd=result.cost_usd,
        cost_estimated=result.cost_estimated,
        dialect=dialect[0] if dialect else None,
        mode=dialect[1] if dialect else None,
    )
    return {
        "subjects": out.subjects,
        "label": out.label,
        "run_id": run_id,
        "output_id": out.id,
        "round": slot[0],
        "candidate": slot[1],
        "parent": out.parent,
        "generation": generation,
        "status": "candidate",
        "profile": profile.id,
        "source": "promoted" if out.parent else "generated",
        "pack": out.pack,
        "item": out.item,
        "variation": variation or None,
    }


def round_findings(images: list[ImageRecord]) -> list[str]:
    """The best judged candidate's unmet required checks: what the next round must fix (sequential)."""
    judged = [i for i in images if i.evaluation is not None]
    if not judged:
        return []
    best = max(judged, key=lambda i: i.evaluation.overall if i.evaluation else 0.0)
    return findings(best.evaluation)
