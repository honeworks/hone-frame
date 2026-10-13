"""The references one output gets when it is produced (design §8.7, §10): its fixed references plus
the accepted images of the outputs it depends on, by precedence, reduced in size."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from hone_frame.events import EventLog
from hone_frame.references import order, reduced_copy
from hone_frame.requests import PlannedOutput, PlannedRef
from hone_frame.runs import RunRecord, WaitingForReference, load_output, run_dir, save_output

if TYPE_CHECKING:
    from hone_frame.store import ProjectStore


def resolve_refs(
    store: ProjectStore, run: RunRecord, out: PlannedOutput, work: Path
) -> list[tuple[PlannedRef, Path, str]]:
    """(reference, local path, subject name) in the order the model receives them."""
    refs = list(out.references)
    for dep in out.depends_on:
        record = load_output(store, run.id, dep.output)
        chosen = record.selected if record and record.status == "done" else None
        best = record.best_available if record is not None and record.status == "needs_review" else None
        if record is not None and chosen is None and best and run.plan.request.get("use_best_available"):
            chosen = best  # an unattended run goes on from the best when nothing passed (change 0007)
            EventLog(run_dir(store, run.id) / "events.jsonl").write(
                "used_best_available", output=out.id, message=f"{record.label}: {chosen} (nothing passed)"
            )
        if chosen is None:
            label = record.label if record else dep.output
            _wait(store, run, out, f"waiting for an accepted {label} ({dep.output})")
        else:
            image = store.image(chosen)
            subject = image.subjects[0].subject_id if len(image.subjects) == 1 else None
            refs.append(PlannedRef(image_id=image.id, subject_id=subject, role=dep.role))
    limit = store.workspace.settings.max_reference_px
    named: list[tuple[PlannedRef, Path, str]] = []
    ordered = refs if out.kind == "promotion" else order(refs)  # a promotion's draft stays image 1
    for ref in ordered:
        path = reduced_copy(store.image_path(ref.image_id), work, limit)
        name = store.subject(ref.subject_id).name if ref.subject_id else ""
        named.append((ref, path, name))
    return named


def _wait(store: ProjectStore, run: RunRecord, out: PlannedOutput, reason: str) -> None:
    record = load_output(store, run.id, out.id)
    if record is not None:
        save_output(store, run.id, record.model_copy(update={"status": "waiting", "reason": reason}))
    EventLog(run_dir(store, run.id) / "events.jsonl").write("waiting", output=out.id, message=reason)
    raise WaitingForReference(reason)
