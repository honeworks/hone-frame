"""Picking with hone-select (design §8.5): required checks are gates, the judge's preference the score."""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import TYPE_CHECKING, Any

import hone_select as hs

from hone_frame.records import Evaluation, ImageRecord

if TYPE_CHECKING:
    from hone_frame.store import ProjectStore


class _JsonlSink:
    """hone-select's spans for a run, appended to `runs/<run>/select.jsonl` (its RecordSink port)."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def emit(self, span: Mapping[str, Any]) -> None:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(span, default=str) + "\n")
        except OSError:  # a sink never raises into the caller
            pass

    def flush(self) -> None:
        """Every span is written when it is emitted."""

    def close(self) -> None:
        """Nothing is held open."""


def pick(
    candidates: list[ImageRecord], sink_path: Path
) -> tuple[ImageRecord | None, ImageRecord | None, str]:
    """(winner, best available, reason). Earlier candidates win ties, so a later one never replaces a
    better earlier one; with no eligible candidate the winner is None (fallback "none")."""
    judged = [c for c in candidates if c.evaluation is not None]
    if not judged:
        return None, None, "no candidate has an evaluation, so none can be picked automatically"
    names = sorted({k.name for c in judged for k in c.evaluation.checks if k.required})  # pyright: ignore[reportOptionalMemberAccess]
    engine = _engine(names, sink_path)
    result = engine.select([_candidate(c, i) for i, c in enumerate(judged)])
    by_id = {c.id: c for c in judged}
    if result.winner is not None and not result.winner.rejected:
        winner = by_id[result.winner.candidate.data["image"]]
        return winner, None, f"picked {winner.id}: passed every required check, overall {_score(winner)}"
    best = _best_available(judged)
    failing = sorted(
        {
            k.name
            for c in judged
            for k in c.evaluation.checks  # pyright: ignore[reportOptionalMemberAccess]
            if k.required and k.verdict != "pass"
        }
    )
    return (
        None,
        best,
        f"no candidate passed {', '.join(failing) or 'the required checks'}; best available {best.id}",
    )


def decide(
    store: ProjectStore, images: list[ImageRecord], auto_pick: bool, sink_path: Path
) -> tuple[str, str | None, str | None, str]:
    """(output status, selected id, best-available id, reason), with the images' statuses updated."""
    winner, best, reason = pick(images, sink_path)
    if not auto_pick:
        winner, reason = None, "manual pick: choose a candidate"
    elif winner is not None:
        store.update_image(winner.id, status="picked")
    if best is not None:
        store.update_image(best.id, status="best_available")
    return (
        ("done" if winner else "needs_review"),
        winner.id if winner else None,
        best.id if best else None,
        reason,
    )


def _engine(required: list[str], sink_path: Path) -> hs.Engine:
    registry: list[Any] = [hs.gate("gate_evaluated")(lambda c: c.data["evaluated"])]  # pyright: ignore[reportUnknownLambdaType, reportUnknownMemberType]
    for name in required:
        registry.append(hs.gate(f"gate_{name}")(_passes(name)))
    registry.append(hs.scorer("overall")(lambda c: c.data["overall"]))  # pyright: ignore[reportUnknownLambdaType, reportUnknownMemberType]
    config = hs.SelectionConfig.model_validate(
        {
            "dedup": {"method": "off"},
            "score": {
                "gates": ["gate_evaluated", *(f"gate_{n}" for n in required)],
                "cascade": [{"scorers": ["overall"]}],
                "weights": {"overall": 1.0},
            },
            "select": {"policy": "argmax", "fallback": "none"},
        }
    )
    return hs.Engine(config, registry=registry, sink=_JsonlSink(sink_path), cache=None)


def _passes(name: str) -> Any:
    def gate(c: hs.Candidate) -> bool:
        return c.data["checks"].get(name) == "pass"

    return gate


def _candidate(record: ImageRecord, order: int) -> hs.Candidate:
    evaluation = record.evaluation or Evaluation()
    checks = {k.name: k.verdict for k in evaluation.checks}
    return hs.Candidate.of(
        {
            "image": record.id,
            "order": order,
            "evaluated": True,
            "checks": checks,
            "overall": evaluation.overall,
        }
    )


def _best_available(judged: list[ImageRecord]) -> ImageRecord:
    """Uncertain ones before failed ones, then by overall, then the earlier."""

    def key(c: ImageRecord) -> tuple[int, float, int]:
        e = c.evaluation or Evaluation()
        return (0 if e.uncertain else 1, -e.overall, judged.index(c))

    return min(judged, key=key)


def _score(record: ImageRecord) -> str:
    return f"{record.evaluation.overall:.2f}" if record.evaluation else "n/a"
