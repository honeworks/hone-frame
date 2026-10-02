"""Submitting and controlling runs: pause, cancel, resume, retry, rerun, manual pick (design §8.5, §9.2)."""

from __future__ import annotations

import getpass
import secrets
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from hone_frame._files import now
from hone_frame.errors import InvalidRequest, NotFound, RunStateError
from hone_frame.events import EventLog, observed
from hone_frame.planning import ModelCheck, as_request, plan
from hone_frame.profiles import resolve_profile
from hone_frame.records import Selection
from hone_frame.requests import Counts, PlannedOutput, PlannedRef, RequestBase
from hone_frame.runs import (
    OutputRecord,
    RunRecord,
    RunView,
    all_runs,
    load_output,
    load_run,
    outputs,
    run_dir,
    save_output,
    save_run,
    set_control,
    view,
)

if TYPE_CHECKING:
    from hone_frame.store import ProjectStore


def new_run_id() -> str:
    return f"{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}-{secrets.token_hex(3)}"


def submit(store: ProjectStore, request: RequestBase | dict[str, Any]) -> RunView:
    """Validate, save and queue (design §6.2). Plan errors raise `InvalidRequest` with every problem."""
    request = as_request(request)
    planned = plan(store, request)
    if planned.errors:
        raise InvalidRequest("the request cannot run", planned.errors)
    run = RunRecord(
        id=new_run_id(),
        project=store.id,
        title=planned.title,
        kind=planned.kind,
        plan=planned,
        created_at=now(),
    )
    with store.lock():
        save_run(store, run)
    EventLog(run_dir(store, run.id) / "events.jsonl").write("submitted", message=planned.title)
    return view(store, run)


def pause(store: ProjectStore, run_id: str) -> RunView:
    return _ask(store, run_id, "pause", allowed=("queued", "running", "pausing"))


def cancel(store: ProjectStore, run_id: str) -> RunView:
    return _ask(store, run_id, "cancel", allowed=("queued", "running", "pausing", "paused"))


def _ask(store: ProjectStore, run_id: str, action: str, *, allowed: tuple[str, ...]) -> RunView:
    run = load_run(store, run_id)
    current = view(store, run)
    if current.status not in allowed:
        raise RunStateError(
            f"cannot {action} a run that is {current.status}; allowed when {', '.join(allowed)}"
        )
    set_control(store, run_id, action)
    return view(store, run)


def resume(store: ProjectStore, run_id: str) -> RunView:
    """Queue a paused, interrupted, failed or waiting run again; it continues where it stopped (§9.2)."""
    run = load_run(store, run_id)
    current = view(store, run)
    if current.status == "canceled":
        raise RunStateError("a canceled run cannot be resumed; rerun its outputs instead")
    if current.status in ("running", "pausing", "queued", "done"):
        raise RunStateError(f"the run is {current.status}; there is nothing to resume")
    stuck = [o for o in current.outputs if o.status in ("failed", "waiting", "paused", "queued", "running")]
    if current.status != "paused" and not stuck:
        raise RunStateError("every output has finished; pick a candidate for those that need review")
    set_control(store, run_id, None)
    with store.lock():
        save_run(store, run.model_copy(update={"state": "queued"}))
    return view(store, load_run(store, run_id))


retry = resume  # a retry is a resume of a finished run with failed or waiting outputs (design §9.2)


def rerun(
    store: ProjectStore,
    run_id: str,
    output_id: str,
    *,
    note: str = "",
    profile: str | None = None,
    selection: Selection | None = None,
) -> RunView:
    """A new run for one output (decisions D-011, D-019): the same definition, plus the person's note,
    optionally another profile and selection. The old output becomes `replaced` and keeps its images."""
    run = load_run(store, run_id)
    out = next((o for o in run.plan.outputs if o.id == output_id), None)
    if out is None:
        raise NotFound(f"run {run_id} has no output {output_id}")
    single = _redo_output(store, run, out, note)
    resolved = resolve_profile(store, RequestBase(profile=profile)) if profile else run.plan.profile
    if profile:
        errors: list[str] = []
        single = ModelCheck(store, resolved, errors, []).finish(single.model_copy(update={"model": ""}))
        if errors:
            raise InvalidRequest(f"cannot redo {out.label} with the {profile} profile", errors)
    sel = selection or run.plan.selection
    per = sel.rounds * sel.candidates
    counts = Counts(
        outputs=1,
        images=per,
        judge_calls=per if sel.auto_judge else 0,
        planner_calls=(sel.rounds if sel.strategy == "sequential" else 1) if resolved.planner else 0,
    )
    planned = run.plan.model_copy(
        update={
            "outputs": [single],
            "counts": counts,
            "sheet_layout": None,
            "profile": resolved,
            "selection": sel,
            "title": f"{run.title}: {out.label} again",
        }
    )
    new = RunRecord(
        id=new_run_id(),
        project=store.id,
        title=planned.title,
        kind=planned.kind,
        plan=planned,
        created_at=now(),
        rerun_of={"run": run_id, "output": output_id},
    )
    with store.lock():
        save_run(store, new)
        old = load_output(store, run_id, output_id)
        if old is not None and old.status not in ("running", "queued"):
            reason = f"asked again by a person in run {new.id}" + (f": {note}" if note else "")
            save_output(
                store,
                run_id,
                old.model_copy(
                    update={
                        "status": "replaced",
                        "reason": reason,
                        "replaced_by": {"run": new.id, "output": out.id},
                    }
                ),
            )
    return view(store, new)


def _redo_output(store: ProjectStore, run: RunRecord, out: PlannedOutput, note: str) -> PlannedOutput:
    """The output with its dependencies' accepted images as fixed references, and the note added."""
    refs = list(out.references)
    for dep in out.depends_on:
        record = load_output(store, run.id, dep.output)
        if record is None or record.selected is None:
            raise InvalidRequest(f"{out.label} needs an accepted {dep.output} first; pick one, then redo it")
        refs.append(PlannedRef(image_id=record.selected, role=dep.role))
    inputs = dict(out.prompt_inputs)
    if note.strip():
        inputs["note"] = " ".join(x for x in (str(inputs.get("note") or ""), note.strip()) if x)
    return out.model_copy(update={"references": refs, "depends_on": [], "prompt_inputs": inputs})


def pick(store: ProjectStore, run_id: str, output_id: str, image_id: str, *, note: str = "") -> OutputRecord:
    """A person's pick (design §8.5): the output is accepted, the image keeps its evaluation."""
    run = load_run(store, run_id)
    record = load_output(store, run_id, output_id)
    if record is None:
        raise NotFound(f"output {output_id} of run {run_id} has no candidates yet")
    if image_id not in record.candidates:
        raise InvalidRequest(
            f"{image_id} is not a candidate of {output_id}; choose one of {record.candidates}"
        )
    with store.lock():
        if record.selected and record.selected != image_id:
            store.update_image(record.selected, status="candidate")
        store.update_image(image_id, status="manual_pick")
        record = record.model_copy(
            update={
                "status": "done",
                "selected": image_id,
                "manual": True,
                "manual_by": getpass.getuser(),
                "manual_at": now(),
                "manual_note": note,
                "reason": f"picked by a person: {image_id}" + (f" ({note})" if note else ""),
                "ended_at": record.ended_at or now(),
            }
        )
        save_output(store, run_id, record)
    EventLog(run_dir(store, run.id) / "events.jsonl").write(
        "picked", output=output_id, image=image_id, manual=True, message=note or None
    )
    return record


def runs(store: ProjectStore) -> list[RunView]:
    durations = observed(store.workspace)
    return [view(store, r, durations=durations) for r in all_runs(store)]


def run_view(store: ProjectStore, run_id: str) -> RunView:
    return view(store, load_run(store, run_id))


__all__ = ["cancel", "outputs", "pause", "pick", "rerun", "resume", "retry", "run_view", "runs", "submit"]
