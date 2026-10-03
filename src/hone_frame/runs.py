"""Run records and views (design §8.6, §9.1): `run.json`, output records, control, statuses."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

import hone_flow as fk
from pydantic import Field

from hone_frame._files import now, read_json, write_json
from hone_frame.errors import HoneFrameError, NotFound
from hone_frame.events import estimate, observed, plan_units, read_events, usage
from hone_frame.records import Record
from hone_frame.requests import Plan

if TYPE_CHECKING:
    from hone_frame.store import ProjectStore
    from hone_frame.workspace import Workspace

OutputStatus = Literal[
    "queued", "running", "done", "needs_review", "waiting", "failed", "paused", "canceled", "replaced"
]
RunStatus = Literal["queued", "pausing", "running", "paused", "canceled", "failed", "needs_review", "done"]
ACTIVE: set[str] = set()  # runs this process is executing right now (engine.Runner)
STAGES = ("planning", "generating", "judging", "selecting", "refining", "composing", "exporting")


class StopRequested(HoneFrameError):
    """Raised at a safe boundary when the run was asked to pause or cancel (decisions D-007)."""

    def __init__(self, action: str) -> None:
        super().__init__(f"stopped: {action} requested")
        self.action = action


class WaitingForReference(HoneFrameError):
    """An output needs an accepted reference that does not exist yet (design §8.7, D-008)."""


class OutputRecord(Record):
    format_version: str = "1"
    id: str
    label: str
    kind: str
    status: OutputStatus = "queued"
    model: str = ""
    rounds_done: int = 0
    candidates: list[str] = Field(default_factory=list[str])
    selected: str | None = None
    best_available: str | None = None
    manual: bool = False
    manual_by: str | None = None
    manual_at: str | None = None
    manual_note: str = ""
    reason: str = ""
    replaced_by: dict[str, str] | None = None  # {"run", "output"}: a person asked for it again
    readings: list[str] = Field(default_factory=list[str])  # a casting hero's readings (change 0006)
    retries: int = 0
    error: str | None = None
    prompt: str = ""
    started_at: str | None = None
    ended_at: str | None = None


class RunRecord(Record):
    format_version: str = "1"
    id: str
    project: str
    title: str
    kind: str
    plan: Plan
    state: Literal["queued", "running", "finished"] = "queued"
    flow_run_id: str | None = None
    rerun_of: dict[str, str] | None = None
    then: list[dict[str, Any]] = Field(
        default_factory=list[dict[str, Any]]
    )  # requests to submit when done (0005)
    created_at: str
    started_at: str | None = None
    ended_at: str | None = None


class RunView(Record):
    id: str
    project: str
    title: str
    kind: str
    status: RunStatus
    reason: str = ""
    stage: str | None = None
    current: dict[str, Any] | None = None
    outputs: list[OutputRecord]
    accepted: list[str]
    unresolved: list[str]
    progress: dict[str, Any]
    estimate: dict[str, float] | None = None
    usage: dict[str, Any]
    created_at: str
    started_at: str | None = None
    ended_at: str | None = None
    elapsed_s: float | None = None
    profile: dict[str, Any]
    selection: dict[str, Any]
    presets: dict[str, int]
    flow_run_id: str | None = None
    rerun_of: dict[str, str] | None = None
    events: int = 0


def run_dir(store: ProjectStore, run_id: str) -> Path:
    return store.root / "runs" / run_id


def load_run(store: ProjectStore, run_id: str) -> RunRecord:
    path = run_dir(store, run_id) / "run.json"
    if not path.is_file():
        raise NotFound(f"no run {run_id!r} in project {store.id!r}")
    return RunRecord.model_validate(read_json(path))


def save_run(store: ProjectStore, run: RunRecord) -> None:
    write_json(run_dir(store, run.id) / "run.json", run.model_dump(mode="json"))


def load_output(store: ProjectStore, run_id: str, output_id: str) -> OutputRecord | None:
    path = run_dir(store, run_id) / "outputs" / f"{output_id}.json"
    return OutputRecord.model_validate(read_json(path)) if path.is_file() else None


def save_output(store: ProjectStore, run_id: str, record: OutputRecord) -> None:
    write_json(run_dir(store, run_id) / "outputs" / f"{record.id}.json", record.model_dump(mode="json"))


def outputs(store: ProjectStore, run: RunRecord) -> list[OutputRecord]:
    return [
        load_output(store, run.id, o.id) or OutputRecord(id=o.id, label=o.label, kind=o.kind, model=o.model)
        for o in run.plan.outputs
    ]


def control(store: ProjectStore, run_id: str) -> str | None:
    path = run_dir(store, run_id) / "control.json"
    return read_json(path).get("action") if path.is_file() else None


def control_message(store: ProjectStore, run_id: str) -> str:
    path = run_dir(store, run_id) / "control.json"
    return str(read_json(path).get("message") or "") if path.is_file() else ""


def set_control(store: ProjectStore, run_id: str, action: str | None, message: str = "") -> None:
    """Ask a run to `pause` or `cancel`, or to wait for the person's `approve` (change 0006)."""
    path = run_dir(store, run_id) / "control.json"
    if action is None:
        path.unlink(missing_ok=True)
    else:
        write_json(path, {"format_version": "1", "action": action, "at": now(), "message": message})


def is_live(store: ProjectStore, run: RunRecord) -> bool:
    """This process runs it, or its hone-flow lease is held by a living process (design §9.2)."""
    if run.id in ACTIVE:
        return True
    if run.flow_run_id is None:
        return False
    try:
        lease = fk.open_runs(store.workspace.root / "flows", store.id).open_run(run.flow_run_id).lease()
    except fk.errors.HoneFlowError:
        return False
    return lease is not None and lease.live


def status(store: ProjectStore, run: RunRecord, outs: list[OutputRecord]) -> tuple[RunStatus, str]:
    """The run status, first match wins (design §9.1)."""
    action = control(store, run.id)
    live = run.state == "running" and is_live(store, run)
    if action == "approve":  # a checkpoint of an approval mode (change 0006)
        message = control_message(store, run.id) or "Waiting for your approval"
        return ("pausing", message) if live else ("paused", message)
    if live:
        return ("pausing", f"will stop after the current call ({action})") if action else ("running", "")
    if run.state == "queued" and action != "cancel":
        return ("paused", "paused before it started") if action == "pause" else ("queued", "")
    if action in ("pause", "cancel"):  # a canceled queued run too
        return ("paused" if action == "pause" else "canceled"), f"{action} requested"
    if run.state == "running":
        return "paused", "interrupted: its process stopped; resume to continue"
    return _from_outputs(outs)


def _from_outputs(outs: list[OutputRecord]) -> tuple[RunStatus, str]:
    failed = [o for o in outs if o.status == "failed"]
    if failed:
        return "failed", f"{len(failed)} output(s) failed: {failed[0].error or ''}".strip()
    open_ = [o for o in outs if o.status in ("needs_review", "waiting", "paused", "queued", "running")]
    if open_:
        return "needs_review", f"{len(open_)} of {len(outs)} output(s) need review"
    return "done", ""


def view(store: ProjectStore, run: RunRecord, *, durations: dict[Any, list[float]] | None = None) -> RunView:
    outs = outputs(store, run)
    events = read_events(run_dir(store, run.id) / "events.jsonl")
    run_status, reason = status(store, run, outs)
    done = _done_per_output(events, outs)
    planned = _planned_units(run.plan, events)
    finished = sum(done[o]["generated"] + done[o]["judged"] for o in done)
    remaining = plan_units(run.plan, done) if run_status in ("running", "pausing", "queued") else {}
    est = (
        estimate(remaining, durations if durations is not None else observed(store.workspace))
        if remaining
        else None
    )
    stage = next((e.get("stage") for e in reversed(events) if e["event"] == "stage"), None)
    current = next((e for e in reversed(events) if e["event"] in ("generating", "judging")), None)
    return RunView(
        id=run.id,
        project=run.project,
        title=run.title,
        kind=run.kind,
        status=run_status,
        reason=reason,
        stage=stage if run_status in ("running", "pausing") else None,
        current=current if run_status in ("running", "pausing") else None,
        outputs=outs,
        accepted=[o.id for o in outs if o.status == "done"],
        unresolved=[o.id for o in outs if o.status not in ("done", "replaced")],
        progress={
            "done": min(finished, planned),
            "planned": planned,
            "fraction": round(min(finished / planned, 1.0), 4) if planned else 0.0,
            "current": "indeterminate" if run_status == "running" else None,
        },
        estimate=est,
        usage=usage(events),
        created_at=run.created_at,
        started_at=run.started_at,
        ended_at=run.ended_at,
        elapsed_s=_elapsed(run),
        profile=run.plan.profile.model_dump(),
        selection=run.plan.selection.model_dump(),
        presets=run.plan.presets,
        flow_run_id=run.flow_run_id,
        rerun_of=run.rerun_of,
        events=len(events),
    )


def _done_per_output(events: list[dict[str, Any]], outs: list[OutputRecord]) -> dict[str, dict[str, int]]:
    done: dict[str, dict[str, int]] = {o.id: {"generated": 0, "judged": 0, "finished": 0} for o in outs}
    for e in events:
        out = done.get(str(e.get("output")))
        if out is None:
            continue
        if e["event"] in ("generated", "candidate_failed"):
            out["generated"] += 1
        elif e["event"] in ("judged", "judge_failed"):
            out["judged"] += 1
    for o in outs:
        done[o.id]["finished"] = int(o.status in ("done", "needs_review", "failed", "replaced"))
    return done


def _planned_units(plan: Plan, events: list[dict[str, Any]]) -> int:
    """Image and judge calls; an early stop removes the skipped rounds' units (design §9.3)."""
    per_candidate = 2 if plan.selection.auto_judge and plan.profile.judge else 1
    total = plan.counts.images * per_candidate
    for e in events:
        if e["event"] == "stopped_early":
            total -= int(e.get("skipped_rounds", 0)) * plan.selection.candidates * per_candidate
    return max(total, 0)


def _elapsed(run: RunRecord) -> float | None:
    if run.started_at is None:
        return None

    def parse(stamp: str) -> datetime:
        return datetime.fromisoformat(stamp.replace("Z", "+00:00"))

    end = parse(run.ended_at) if run.ended_at else parse(now())
    return round((end - parse(run.started_at)).total_seconds(), 1)


def all_runs(store: ProjectStore) -> list[RunRecord]:
    folder = store.root / "runs"
    return (
        [
            load_run(store, p.name)
            for p in sorted(folder.iterdir(), reverse=True)
            if (p / "run.json").is_file()
        ]
        if folder.is_dir()
        else []
    )


def queue(ws: Workspace) -> list[RunView]:
    """Queued and live runs of every project, oldest first (design §2)."""
    durations = observed(ws)
    found: list[RunView] = []
    for project in ws.projects():
        store = ws.project(project.id)
        found += [view(store, r, durations=durations) for r in all_runs(store) if r.state != "finished"]
    return sorted(
        (v for v in found if v.status in ("queued", "running", "pausing")), key=lambda v: v.created_at
    )
