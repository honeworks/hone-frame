"""Run events (design §9.3), estimates from observed durations (§9.4, D-009) and usage (§9.5)."""

from __future__ import annotations

import json
import threading
from collections import defaultdict
from pathlib import Path
from typing import TYPE_CHECKING, Any

from hone_frame._files import now

if TYPE_CHECKING:
    from hone_frame.requests import Plan
    from hone_frame.workspace import Workspace

MIN_OBSERVATIONS = 3
KEEP_LAST = 50
_WRITE = threading.Lock()


class EventLog:
    """Appends one JSON object per line to `runs/<run>/events.jsonl`."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def write(self, event: str, **fields: Any) -> dict[str, Any]:
        row = {"at": now(), "event": event} | {k: v for k, v in fields.items() if v is not None}
        with _WRITE:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(row, ensure_ascii=False) + "\n")
        return row


def read_events(path: Path, since: int = 0) -> list[dict[str, Any]]:
    """The events from line `since` on; a half-written last line is left for the next read."""
    if not path.is_file():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines()[since:]:
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            break
    return rows


def _key(row: dict[str, Any]) -> tuple[str, str | None] | None:
    if row.get("event") == "generated" and row.get("duration_s") is not None:
        return (str(row.get("model")), row.get("size"))
    if row.get("event") == "judged" and row.get("duration_s") is not None:
        return (str(row.get("model")), None)
    return None


def observed(ws: Workspace) -> dict[tuple[str, str | None], list[float]]:
    """Durations per (model, size) from every run in the workspace, the last 50 of each."""
    found: dict[tuple[str, str | None], list[tuple[str, float]]] = defaultdict(list)
    for path in (ws.root / "projects").glob("*/runs/*/events.jsonl"):
        for row in read_events(path):
            if (key := _key(row)) is not None:
                found[key].append((str(row["at"]), float(row["duration_s"])))
    return {k: [d for _, d in sorted(v)[-KEEP_LAST:]] for k, v in found.items()}


def _quantile(values: list[float], q: float) -> float:
    ordered = sorted(values)
    position = (len(ordered) - 1) * q
    low, high = int(position), min(int(position) + 1, len(ordered) - 1)
    return ordered[low] + (ordered[high] - ordered[low]) * (position - low)


def estimate(
    units: dict[tuple[str, str | None], int], durations: dict[tuple[str, str | None], list[float]]
) -> dict[str, float] | None:
    """The remaining time as a range, or None ("Estimating") without 3 observations per needed key."""
    low = high = 0.0
    for key, count in units.items():
        if count <= 0:
            continue
        values = durations.get(key, [])
        if len(values) < MIN_OBSERVATIONS:
            return None
        low += count * _quantile(values, 0.25)
        high += count * _quantile(values, 0.75)
    return {"low_s": round(low, 1), "high_s": round(high, 1)}


def plan_units(
    plan: Plan, done: dict[str, dict[str, int]] | None = None
) -> dict[tuple[str, str | None], int]:
    """The image and judge calls a plan still needs; `done` counts per output what already happened."""
    units: dict[tuple[str, str | None], int] = defaultdict(int)
    per_output = plan.selection.rounds * plan.selection.candidates
    for out in plan.outputs:
        made = (done or {}).get(out.id, {})
        if made.get("finished"):
            continue
        units[(out.model, out.size)] += max(per_output - made.get("generated", 0), 0)
        if plan.selection.auto_judge and plan.profile.judge:
            units[(plan.profile.judge, None)] += max(per_output - made.get("judged", 0), 0)
    return dict(units)


def estimate_plan(ws: Workspace, plan: Plan) -> dict[str, float] | None:
    return estimate(plan_units(plan), observed(ws))


def usage(events: list[dict[str, Any]]) -> dict[str, Any]:
    """Render seconds, GPU seconds of local models, cost when known (never invented for local work)."""
    generated = [e for e in events if e.get("event") == "generated"]
    render = sum(float(e.get("duration_s") or 0.0) for e in generated)
    local = [float(e.get("duration_s") or 0.0) for e in generated if e.get("local")]
    costs = [e for e in generated if e.get("cost_usd") is not None]
    return {
        "images": len(generated),
        "judge_calls": sum(1 for e in events if e.get("event") == "judged"),
        "retries": sum(1 for e in events if e.get("event") == "retry"),
        "render_s": round(render, 1),
        "gpu_s": round(sum(local), 1) if local else None,
        "cost_usd": round(sum(float(e["cost_usd"]) for e in costs), 4) if costs else None,
        "cost_estimated": any(e.get("cost_estimated") for e in costs),
    }
