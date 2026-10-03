"""Options chosen when generation starts (change 0006): approval checkpoints, where a run waits for the
person, and the stronger judge for the images that matter or for all."""

from __future__ import annotations

from typing import TYPE_CHECKING

from hone_frame.runs import RunRecord, set_control

if TYPE_CHECKING:
    from hone_frame.events import EventLog
    from hone_frame.requests import Plan, PlannedOutput
    from hone_frame.store import ProjectStore


def judge_for(store: ProjectStore, plan: Plan, default: str | None, out: PlannedOutput) -> str | None:
    """The profile's judge, or the workspace's stronger judge when the plan asks for it for every output,
    or for the outputs others are made from."""
    strong = store.workspace.settings.strong_judge
    base = any(d.output == out.id for o in plan.outputs for d in o.depends_on)
    if strong and (plan.judge_mode == "strong_all" or (plan.judge_mode == "strong_base" and base)):
        return strong
    return default


def checkpoint(store: ProjectStore, run: RunRecord, out: PlannedOutput, log: EventLog) -> None:
    """After a checkpoint output, ask the person before going on: the run stops before the next output,
    and Approve (resume) lets it continue."""
    plan = run.plan
    if out.id not in plan.checkpoints or plan.outputs[-1].id == out.id:
        return
    message = f"Waiting for your approval: {out.label} and what came before it"
    set_control(store, run.id, "approve", message)
    log.write("approval_needed", output=out.id, message=message)
