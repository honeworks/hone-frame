"""What the dashboard shows, computed from the workspace (design §12.4, §12.5). Only real data: a value
that was never measured is None and the page says so."""

from __future__ import annotations

import statistics
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from hone_frame.events import observed, read_events
from hone_frame.records import ImageRecord
from hone_frame.runs import RunRecord, RunView, load_run, run_dir, view

if TYPE_CHECKING:
    from hone_frame.store import ProjectStore
    from hone_frame.workspace import Workspace


def image_card(store: ProjectStore, record: ImageRecord) -> dict[str, Any]:
    evaluation = record.evaluation
    return {
        "id": record.id,
        "url": f"/files/{store.id}/images/{record.file}",
        "width": record.width,
        "height": record.height,
        "status": record.status,
        "label": record.label,
        "kind": record.kind,
        "subjects": [s.subject_id for s in record.subjects],
        "model": record.generation.model if record.generation else None,
        "seed": record.generation.seed if record.generation else None,
        "job_id": record.generation.job_id if record.generation else None,
        "run_id": record.run_id,
        "output_id": record.output_id,
        "round": record.round,
        "candidate": record.candidate,
        "parent": record.parent,
        "created_at": record.created_at,
        "passed": evaluation.passed if evaluation else None,
        "overall": evaluation.overall if evaluation else None,
    }


def today() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%d")


def overview(store: ProjectStore) -> dict[str, Any]:
    """Four metrics, the live queue, recent images (brief §14). No invented numbers."""
    day = today()
    events = [e for r in _run_ids(store) for e in read_events(run_dir(store, r) / "events.jsonl")]
    generated = [e for e in events if e.get("event") == "generated" and str(e.get("at", "")).startswith(day)]
    durations = [float(e["duration_s"]) for e in generated if e.get("duration_s") is not None]
    gpu = [float(e["duration_s"]) for e in generated if e.get("local") and e.get("duration_s") is not None]
    queue = store.workspace.queue()
    images = store.images()
    return {
        "metrics": {
            "images_today": len(generated) if events else None,
            "queued": sum(1 for v in queue if v.status == "queued"),
            "running": sum(1 for v in queue if v.status in ("running", "pausing")),
            "median_render_s": round(statistics.median(durations), 1) if durations else None,
            "gpu_s_today": round(sum(gpu), 1) if gpu else None,
        },
        "queue": [run_summary(v) for v in queue],
        "recent": [image_card(store, r) for r in images[-12:][::-1]],
        "counts": {k: len(store.subjects(k)) for k in ("character", "environment", "asset")}
        | {"images": len(images), "scenes": len(store.scenes()), "sheets": len(store.sheets())},
    }


def _run_ids(store: ProjectStore) -> list[str]:
    folder = store.root / "runs"
    return sorted(p.name for p in folder.iterdir() if p.is_dir()) if folder.is_dir() else []


def run_summary(v: RunView) -> dict[str, Any]:
    current = v.current or {}
    return {
        "id": v.id,
        "project": v.project,
        "title": v.title,
        "kind": v.kind,
        "status": v.status,
        "reason": v.reason,
        "progress": v.progress,
        "estimate": v.estimate,
        "elapsed_s": v.elapsed_s,
        "created_at": v.created_at,
        "profile": v.profile.get("id"),
        "model": current.get("model"),
        "size": v.profile.get("size"),
        "round": current.get("round"),
        "rounds": v.selection.get("rounds"),
        "outputs": len(v.outputs),
        "accepted": len(v.accepted),
    }


def run_page(store: ProjectStore, run_id: str, since: int) -> dict[str, Any]:
    """Everything the run page needs (the first mockup), plus the events after line `since`."""
    run = load_run(store, run_id)
    v = view(store, run)
    events = read_events(run_dir(store, run.id) / "events.jsonl")
    ids = {i for o in v.outputs for i in o.candidates}
    images = {
        i.id: image_card(store, i) | {"evaluation": i.evaluation.model_dump() if i.evaluation else None}
        for i in store.images()
        if i.id in ids
    }
    return {
        "run": v.model_dump(mode="json"),
        "summary": run_summary(v),
        "plan": run.plan.model_dump(mode="json"),
        "stages": stages(run, events, v.status),
        "activity": activity(events[since:]),
        "next": len(events),
        "images": images,
        "current": current_task(run, v, events),
    }


def stages(run: RunRecord, events: list[dict[str, Any]], status: str) -> list[dict[str, Any]]:
    """Only the applicable stages, each with its state and the time spent in it (brief §15)."""
    names = ["planning", "generating"]
    names += ["judging"] if run.plan.selection.auto_judge else []
    names += ["selecting"] + (["composing"] if run.plan.sheet_layout else [])
    marks = [(str(e["at"]), str(e["stage"])) for e in events if e["event"] == "stage"]
    end = next((str(e["at"]) for e in reversed(events) if e["event"] == "run_finished"), None)
    spent: dict[str, float] = {}
    for (at, stage), nxt in zip(marks, [*marks[1:], (end, "")], strict=True):
        if nxt[0]:
            spent[stage] = spent.get(stage, 0.0) + _seconds(at, nxt[0])
    latest = marks[-1][1] if marks else None
    live = status in ("running", "pausing")
    at = names.index(latest) if live and latest in names else None
    rows: list[dict[str, Any]] = []
    for n, name in enumerate(names):
        if at is not None:  # while live: the pipeline of the output being worked on
            state = "done" if n < at else ("running" if n == at else "waiting")
        else:
            state = "done" if name in spent or name == latest else "waiting"
        rows.append({"name": name, "state": state, "seconds": round(spent.get(name, 0.0), 1) or None})
    return rows


def current_task(run: RunRecord, v: RunView, events: list[dict[str, Any]]) -> dict[str, Any] | None:
    """The output being worked on: round x of y, its candidate slots (mockup 1, "Current task")."""
    last = next(
        (e for e in reversed(events) if e["event"] in ("generating", "judging", "output_started")), None
    )
    if last is None:
        return None
    output_id = str(last.get("output"))
    out = next((o for o in v.outputs if o.id == output_id), None)
    if out is None:
        return None
    rnd = int(last.get("round") or max(out.rounds_done, 1))
    sel = run.plan.selection
    slots = [
        {"round": r, "candidate": c} for r in range(1, sel.rounds + 1) for c in range(1, sel.candidates + 1)
    ]
    return {
        "output": output_id,
        "label": out.label,
        "round": rnd,
        "rounds": sel.rounds,
        "candidates": sel.candidates,
        "model": last.get("model") or out.model,
        "status": out.status,
        "images": out.candidates,
        "slots": slots,
        "now": {"round": last.get("round"), "candidate": last.get("candidate"), "event": last["event"]},
    }


TITLES = {
    "submitted": "Queued",
    "run_started": "Started",
    "run_finished": "Finished",
    "output_started": "Started output",
    "planned": "Prompt ready",
    "generated": "Generated candidate",
    "judged": "Judged candidate",
    "retry": "Retrying",
    "planner_failed": "Planner failed",
    "judge_failed": "Judge failed",
    "candidate_failed": "Candidate failed",
    "waiting": "Waiting",
    "picked": "Selected",
    "stopped": "Stopping",
    "stopped_early": "Stopped early",
    "model_info_unavailable": "Model details unavailable",
    "output_finished": "Finished output",
}


def activity(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """The activity lines: stage marks are left out (the pipeline shows them)."""
    return [describe(e) for e in events if e.get("event") != "stage"]


def describe(e: dict[str, Any]) -> dict[str, Any]:
    """One readable activity line (mockup 1, "Live activity")."""
    kind = str(e.get("event"))
    detail = _detail(e)
    tone = (
        "danger"
        if kind.endswith("failed")
        else ("success" if kind in ("picked", "run_finished") else "muted")
    )
    if kind == "judged":
        tone = "success" if e.get("passed") else "warning"
    if kind in ("generating", "judging", "stage"):
        tone = "accent"
    return {
        "at": e.get("at"),
        "event": kind,
        "title": _title(e),
        "detail": detail,
        "tone": tone,
        "output": e.get("output"),
    }


def _title(e: dict[str, Any]) -> str:
    kind = str(e.get("event"))
    if kind == "stage":
        return str(e.get("stage", "")).capitalize()
    if kind in ("generating", "judging"):
        verb = "Generating" if kind == "generating" else "Judging"
        return f"{verb} {e.get('label', '')}, round {e.get('round')}".strip()
    return TITLES.get(kind, kind.replace("_", " ").capitalize())


def _detail(e: dict[str, Any]) -> str:
    kind = str(e.get("event"))
    if kind == "generated":
        return f"{e.get('image')} · {e.get('model')} · {e.get('duration_s')} s"
    if kind == "judged":
        verdict = "passed" if e.get("passed") else "did not pass"
        findings = "; ".join(e.get("findings") or [])
        return f"{e.get('image')} {verdict} · overall {e.get('overall')}" + (
            f" · {findings}" if findings else ""
        )
    if kind in ("generating", "judging"):
        return f"{e.get('output')} · candidate {e.get('candidate')} · {e.get('model')}"
    text = str(e.get("message") or e.get("output") or "")
    return text if len(text) <= 160 else text[:157] + "…"


def _seconds(start: str, end: str) -> float:
    def parse(stamp: str) -> datetime:
        return datetime.fromisoformat(stamp.replace("Z", "+00:00"))

    return max((parse(end) - parse(start)).total_seconds(), 0.0)


def model_latency(ws: Workspace) -> dict[str, float]:
    """The median observed duration per model, from every run's events (Models view)."""
    per_model: dict[str, list[float]] = {}
    for (model, _size), values in observed(ws).items():
        per_model.setdefault(model, []).extend(values)
    return {m: round(statistics.median(v), 1) for m, v in per_model.items() if v}
