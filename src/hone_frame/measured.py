"""Measured checks (change 0007): numbers instead of the vision judge's opinion where they can be had.

- `distinct_view` (required, Pillow only): a view must not be the same picture as the subject's hero or its
  other views (the bow's and the lasso's views were near-copies). A failure skips the vision judge.
- `same_subject` (advisory): DINOv2 cosine similarity of a view to its hero, logged for calibration.
- `pose_kind` (advisory): for a pose that sits, kneels or runs, the hip, knee and ankle heights from
  ViTPose against the mannequin's.

The model checks run through hone-models (`frame-vision`, a `command` entry) on the CPU; without the tools
environment, or when the call fails, they are skipped, never failed.
"""

from __future__ import annotations

import json
import math
import os
from pathlib import Path
from typing import TYPE_CHECKING, Any

from PIL import Image

from hone_frame.ports import ModelFailure
from hone_frame.records import CheckResult, Evaluation

if TYPE_CHECKING:
    from hone_frame.produce import Producer
    from hone_frame.records import ImageRecord

DUPLICATE_BITS = 6  # under this many of 64 bits apart, two views are the same picture
VISION_MODEL = "frame-vision"
POSE_KINDS = {"sit", "kneel", "run"}


def dhash(path: Path) -> int:
    """A 64-bit difference hash: greyscale 9x8, one bit per left-right brightness step."""
    with Image.open(path) as picture:
        small = picture.convert("L").resize((9, 8), Image.Resampling.LANCZOS)  # pyright: ignore[reportUnknownMemberType]
    px = small.tobytes()
    bits = [px[r * 9 + c] > px[r * 9 + c + 1] for r in range(8) for c in range(8)]
    return sum(1 << i for i, b in enumerate(bits) if b)


def distance(a: int, b: int) -> int:
    return (a ^ b).bit_count()


def tools_ready() -> bool:
    exe = os.environ.get("HONE_FRAME_TOOLS_PYTHON", "")
    return bool(exe) and Path(exe).is_file()


def measured_checks(p: Producer, image: ImageRecord) -> list[CheckResult]:
    """The measured checks that apply to this candidate."""
    found: list[CheckResult] = []
    path = p.store.image_path(image.id)
    if p.out.prompt_inputs.get("distinct"):
        found += _distinct(p, image, path)
    if tools_ready() and (p.out.prompt_inputs.get("same_subject") or p.out.prompt_inputs.get("pose_kind")):
        found += _model_checks(p, path)
    elif p.out.prompt_inputs.get("same_subject") or p.out.prompt_inputs.get("pose_kind"):
        p.log.write("measured_skipped", output=p.out.id, message="HONE_FRAME_TOOLS_PYTHON is not set")
    return found


def _others(p: Producer, image: ImageRecord) -> list[tuple[str, Path]]:
    """The subject's hero, and its other turning views (another angle) made before this candidate; never
    views meant to look alike (a character's Front, an expression, a place's state)."""
    roles = ("object", "environment", "identity")
    found = [(name or "the reference", path) for ref, path, name in p.refs if ref.role in roles]
    subject = image.subjects[0].subject_id if image.subjects else None
    for other in p.store.images(subject_id=subject) if subject else []:
        another = other.output_id != image.output_id or other.run_id != image.run_id
        if other.id != image.id and "turn" in other.tags and another:
            found.append((other.item or other.label or other.id, p.store.image_path(other.id)))
    return found


def _distinct(p: Producer, image: ImageRecord, path: Path) -> list[CheckResult]:
    mine = dhash(path)
    closest: tuple[int, str] | None = None
    for name, other in _others(p, image):
        d = distance(mine, dhash(other))
        if closest is None or d < closest[0]:
            closest = (d, name)
    if closest is None:
        return []
    d, name = closest
    if d >= DUPLICATE_BITS:
        return [CheckResult(name="distinct_view", verdict="pass", score=round(d / 64, 3),
                            finding=f"differs from {name} ({d} of 64 bits)")]  # fmt: skip
    finding = (
        f"{p.out.label} looks the same as {name}: turn the subject to show the {p.out.label.lower()} view"
    )
    return [CheckResult(name="distinct_view", verdict="fail", score=round(d / 64, 3), finding=finding)]


def _vision(p: Producer, what: str, images: list[Path]) -> list[dict[str, Any]]:
    out = p.folder / "work" / f"{p.out.id}-vision.png"
    result = p.models.generate(VISION_MODEL, what, out=out, seed=0, references=images, inputs={})
    if result.path is None:
        raise ModelFailure(f"{VISION_MODEL}: {result.error or 'no output'}", transient=False)
    with Image.open(result.path) as picture:
        data: Any = json.loads(picture.info.get("hone-frame", "{}"))  # pyright: ignore[reportUnknownMemberType, reportUnknownArgumentType]
    result.path.unlink(missing_ok=True)
    return list(data.get("images") or [])


def _model_checks(p: Producer, path: Path) -> list[CheckResult]:
    hero = next((rp for ref, rp, _ in p.refs if ref.role in ("object", "environment", "identity")), None)
    mannequin = next((rp for ref, rp, _ in p.refs if ref.role == "pose"), None)
    found: list[CheckResult] = []
    try:
        if p.out.prompt_inputs.get("same_subject") and hero is not None:
            rows = _vision(p, "embedding", [path, hero])
            found.append(_same(rows))
        kind = str(p.out.prompt_inputs.get("pose_kind") or "")
        if kind in POSE_KINDS and mannequin is not None:
            rows = _vision(p, "keypoints", [path, mannequin])
            found.append(_pose_kind(kind, rows))
    except (ModelFailure, ValueError, KeyError, OSError) as exc:
        p.log.write("measured_skipped", output=p.out.id, message=f"{VISION_MODEL}: {exc}")
    return found


def _same(rows: list[dict[str, Any]]) -> CheckResult:
    a, b = (list(map(float, r["embedding"])) for r in rows[:2])
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    cos = dot / (math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b)) or 1.0)
    return CheckResult(name="same_subject", verdict="pass", score=round(cos, 3), required=False,
                       finding=f"similarity to the hero {cos:.2f} (logged for calibration)")  # fmt: skip


def legs(keypoints: list[list[float]]) -> tuple[float, float, float]:
    """(hip-to-knee, knee-to-ankle, body height) from COCO keypoints: 11/12 hips, 13/14 knees, 15/16
    ankles, 0 nose; heights in pixels (down is positive)."""
    y = [k[1] for k in keypoints]
    hip, knee, ankle = (y[11] + y[12]) / 2, (y[13] + y[14]) / 2, (y[15] + y[16]) / 2
    return knee - hip, ankle - knee, max(ankle - y[0], 1.0)


def _pose_kind(kind: str, rows: list[dict[str, Any]]) -> CheckResult:
    (thigh, shin, height), (m_thigh, m_shin, m_height) = (legs(r["keypoints"]) for r in rows[:2])
    mine, theirs = (thigh / height, shin / height), (m_thigh / m_height, m_shin / m_height)
    gap = abs(mine[0] - theirs[0]) + abs(mine[1] - theirs[1])
    upright = mine[0] > 0.17 and mine[1] > 0.17  # a standing figure: long thigh and shin drops
    verdict = "fail" if kind in ("sit", "kneel") and upright else ("pass" if gap < 0.15 else "uncertain")
    finding = (f"legs {mine[0]:.2f}/{mine[1]:.2f} of the height against the mannequin's "
               f"{theirs[0]:.2f}/{theirs[1]:.2f}" + ("; the figure stands" if upright else ""))  # fmt: skip
    return CheckResult(name="pose_kind", verdict=verdict, score=round(max(0.0, 1 - gap), 3), required=False,
                       finding=finding)  # fmt: skip


def failed_early(p: Producer, image: ImageRecord, measured: list[CheckResult]) -> ImageRecord | None:
    """A required measured failure: the candidate is rejected without asking the vision judge."""
    failed = [c for c in measured if c.required and c.verdict == "fail"]
    if not failed:
        return None
    summary = "; ".join(c.finding for c in failed)
    evaluation = Evaluation(checks=measured, summary=summary, judge="measured", passed=False)
    found = [c.finding for c in failed]
    p.log.write("judged", output=p.out.id, round=image.round, candidate=image.candidate, image=image.id,
                model="measured", passed=False, overall=0.0, message=summary, findings=found)  # fmt: skip
    return p.store.update_image(image.id, evaluation=evaluation, status="rejected")
