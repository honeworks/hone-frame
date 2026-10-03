"""The hone-flow workflow of a project and the `Runner` that executes queued runs (design §8.1, §9.2)."""

from __future__ import annotations

import shutil
import threading
from typing import TYPE_CHECKING, Any

import hone_flow as fk

from hone_frame._files import now
from hone_frame.candidates import seed_for
from hone_frame.events import EventLog
from hone_frame.produce import Producer
from hone_frame.records import SheetRecipe
from hone_frame.runs import (
    ACTIVE,
    RunRecord,
    RunView,
    all_runs,
    control,
    is_live,
    load_output,
    load_run,
    outputs,
    run_dir,
    save_run,
    view,
)
from hone_frame.world_runs import follow_up

if TYPE_CHECKING:
    from hone_frame.store import ProjectStore
    from hone_frame.workspace import Workspace


def build_workflow(store: ProjectStore) -> fk.Workflow:
    """One workflow per project: `produce` per output, then `compose` (design §8.1)."""
    wf = fk.Workflow(store.id, storage=store.workspace.root / "flows", version="1", measure=("timing",))

    @wf.step(version="1", deterministic=False)
    def produce(item: fk.Item, frame_run: fk.Param[str], ctx: fk.Context) -> dict[str, Any]:  # pyright: ignore[reportUnusedFunction]
        run = load_run(store, frame_run)
        out = next(o for o in run.plan.outputs if o.id == item.id)
        return Producer(store, run, out, ctx.seed).run_output().model_dump(mode="json")

    @wf.final_step(version="1")
    def compose(produce: dict[str, dict[str, Any]], frame_run: fk.Param[str]) -> dict[str, Any]:  # pyright: ignore[reportUnusedFunction]
        return compose_requested(store, load_run(store, frame_run))

    return wf


def compose_requested(store: ProjectStore, run: RunRecord) -> dict[str, Any]:
    """The sheet the request asked for, once every output is accepted (design §8.1)."""
    layout = run.plan.sheet_layout
    if not layout:
        return {"sheet": None, "reason": "no sheet was requested"}
    outs = outputs(store, run)
    if any(o.status != "done" for o in outs):
        return {"sheet": None, "reason": "not every output is accepted; compose the sheet after review"}
    EventLog(run_dir(store, run.id) / "events.jsonl").write("stage", stage="composing")
    views = [o for o in outs if o.label != "Hero"] or outs
    recipe = SheetRecipe(
        name=run.title,
        layout=layout,
        images=[o.selected or "" for o in views],
        labels=[o.label for o in views],
    )
    sheet = store.save_sheet(recipe)
    store.compose_sheet(sheet.id)
    return {"sheet": sheet.id, "reason": "composed"}


class Runner:
    """Executes queued runs one at a time in this process (design §9.2, §12.1)."""

    def __init__(self, ws: Workspace) -> None:
        self.ws = ws

    def next_queued(self) -> tuple[ProjectStore, RunRecord] | None:
        found: list[tuple[str, ProjectStore, RunRecord]] = []
        for project in self.ws.projects():
            store = self.ws.project(project.id)
            for run in all_runs(store):
                if run.state == "queued" and control(store, run.id) is None:
                    found.append((run.created_at, store, run))
        if not found:
            return None
        _, store, run = min(found, key=lambda f: (f[0], f[2].id))
        return store, run

    def run_next(self) -> RunView | None:
        nxt = self.next_queued()
        if nxt is None:
            return None
        store, run = nxt
        execute(store, run)
        return view(store, load_run(store, run.id))

    def run_forever(self, stop: threading.Event, idle_s: float = 1.0) -> None:
        while not stop.is_set():
            if self.run_next() is None:
                stop.wait(idle_s)

    def recover(self) -> list[str]:
        """Queue again the runs a dead process left running; hone-flow takes over the lease (§9.2)."""
        recovered: list[str] = []
        for project in self.ws.projects():
            store = self.ws.project(project.id)
            for run in all_runs(store):
                if run.state == "running" and not is_live(store, run):
                    save_run(store, run.model_copy(update={"state": "queued"}))
                    recovered.append(run.id)
        return recovered


def execute(store: ProjectStore, run: RunRecord) -> None:
    """Start or resume the hone-flow run of `run`, in this process."""
    log = EventLog(run_dir(store, run.id) / "events.jsonl")
    ACTIVE.add(run.id)
    holder = {
        "run": run.model_copy(
            update={"state": "running", "started_at": run.started_at or now(), "ended_at": None}
        )
    }
    save_run(store, holder["run"])
    log.write("run_started", message=run.title, resume=bool(run.flow_run_id) or None)

    def on_event(event: dict[str, Any]) -> None:
        if event.get("event") == "run_started" and holder["run"].flow_run_id is None:
            holder["run"] = holder["run"].model_copy(update={"flow_run_id": event["run_id"]})
            save_run(store, holder["run"])

    try:
        wf = build_workflow(store)
        if run.flow_run_id:
            wf.open_run(run.flow_run_id).resume(on_event=on_event)
        else:
            items = [fk.Item(o.id) for o in run.plan.outputs]
            wf.run(
                items,
                params={"frame_run": run.id},
                seed=seed_for(run.id) % 2**31,
                label=run.title,
                on_event=on_event,
            )
    finally:
        ACTIVE.discard(run.id)
        final = load_run(store, run.id).model_copy(update={"state": "finished", "ended_at": now()})
        save_run(store, final)
        result = view(store, final)
        log.write("run_finished", message=result.status, reason=result.reason or None)
        if final.then and result.status not in ("canceled", "paused"):
            for message in follow_up(store, run.id):
                log.write("follow_up", message=message)
        if result.status == "done":
            shutil.rmtree(run_dir(store, run.id) / "work", ignore_errors=True)


def selected_of(store: ProjectStore, run_id: str, output_id: str) -> str | None:
    record = load_output(store, run_id, output_id)
    return record.selected if record else None
