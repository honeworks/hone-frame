"""Whole-world runs (change 0005): every place, object and character of a variation, then its scenes, as
a chain of runs started once, with an estimate first. Runs follow one another in the queue; the scenes
are submitted when the last character's run finishes, since they need the accepted heroes."""

from __future__ import annotations

import statistics
from datetime import datetime
from typing import TYPE_CHECKING, Any

from hone_frame.characters import variation_id, world_requests
from hone_frame.errors import HoneFrameError
from hone_frame.events import read_events
from hone_frame.planning import plan
from hone_frame.records import Selection
from hone_frame.requests import CharacterPacks, RequestBase, SceneShot
from hone_frame.runs import all_runs, load_run, run_dir, save_run

if TYPE_CHECKING:
    from hone_frame.store import ProjectStore
    from hone_frame.workspace import Workspace

FALLBACK_S = 70.0  # seconds per image with planning and judging, measured on the reference machine


def world_requests_all(
    store: ProjectStore,
    variation: str | None = None,
    *,
    profile: str = "",
    selection: Selection | None = None,
) -> list[RequestBase]:
    """The world's places and objects without an image, then every character's packs."""
    v = variation_id(store, variation)
    common: dict[str, Any] = {"variation": v, "profile": profile, "selection": selection}
    found: list[RequestBase] = [r.model_copy(update=common) for r in world_requests(store, None, v)]
    found += [CharacterPacks(subject_id=c.id, **common) for c in store.subjects("character")]
    return found


def scene_requests(
    store: ProjectStore, variation: str, *, profile: str = "", selection: Selection | None = None
) -> list[dict[str, Any]]:
    """A shot of every scene, as requests to submit once the characters are made."""
    return [
        SceneShot(scene_id=s.id, variation=variation, profile=profile, selection=selection).model_dump(
            mode="json"
        )
        for s in store.scenes()
    ]


def world_plan(
    store: ProjectStore,
    variation: str | None = None,
    *,
    profile: str = "",
    selection: Selection | None = None,
) -> dict[str, Any]:
    """What a whole-world run would make, and how long it should take (nothing is written)."""
    v = variation_id(store, variation)
    rows: list[dict[str, Any]] = []
    for request in world_requests_all(store, v, profile=profile, selection=selection):
        planned = plan(store, request)
        counts = planned.counts
        rows.append(
            {
                "title": planned.title,
                "outputs": counts.outputs,
                "images": counts.images,
                "errors": planned.errors,
            }
        )
    scenes: list[dict[str, Any]] = []
    for request in scene_requests(store, v, profile=profile, selection=selection):
        planned = plan(store, request)  # counted now; it runs once the characters are made
        problems = [e for e in planned.errors if "no accepted image" not in e]  # heroes come first
        scenes.append({"title": planned.title, "images": planned.counts.images, "errors": problems})
    seconds = per_image_seconds(store.workspace)
    images = sum(r["images"] for r in rows) + sum(r["images"] for r in scenes)
    return {
        "variation": v,
        "runs": rows,
        "scenes": len(scenes),
        "scene_runs": scenes,
        "images": images,
        "seconds_per_image": round(seconds, 1),
        "estimate_s": round(images * seconds),
        "measured": seconds != FALLBACK_S,
    }


def generate_world(
    store: ProjectStore,
    variation: str | None = None,
    *,
    profile: str = "",
    selection: Selection | None = None,
) -> dict[str, Any]:
    """Submit the whole world of a variation; its scenes follow the last character's run."""
    v = variation_id(store, variation)
    run_ids: list[str] = []
    skipped: list[str] = []
    for request in world_requests_all(store, v, profile=profile, selection=selection):
        try:
            run_ids.append(store.submit(request).id)
        except HoneFrameError as exc:  # one subject that cannot run does not stop the world
            skipped.append(f"{request.task}: {exc}")
    scenes = scene_requests(store, v, profile=profile, selection=selection)
    if run_ids and scenes:
        set_follow_up(store, run_ids[-1], scenes)
    return {
        "variation": v,
        "runs": run_ids,
        "skipped": skipped,
        "scenes_after": len(scenes) if run_ids else 0,
    }


def per_image_seconds(ws: Workspace) -> float:
    """The median wall time of one candidate (planning, generating, judging) over finished outputs."""
    samples: list[float] = []
    for project in ws.projects():
        store = ws.project(project.id)
        for run in all_runs(store):
            started: dict[str, datetime] = {}
            for e in read_events(run_dir(store, run.id) / "events.jsonl"):
                at = datetime.fromisoformat(str(e["at"]).replace("Z", "+00:00"))
                if e["event"] == "output_started":
                    started[str(e["output"])] = at
                elif e["event"] == "output_finished" and str(e.get("output")) in started:
                    images = max(1, run.plan.selection.rounds * run.plan.selection.candidates)
                    samples.append((at - started.pop(str(e["output"]))).total_seconds() / images)
    return statistics.median(samples) if len(samples) >= 3 else FALLBACK_S


def set_follow_up(store: ProjectStore, run_id: str, requests: list[dict[str, Any]]) -> None:
    """Requests to submit when the run finishes (they need what it makes)."""
    with store.lock():
        save_run(store, load_run(store, run_id).model_copy(update={"then": requests}))


def follow_up(store: ProjectStore, run_id: str) -> list[str]:
    """Submit a finished run's follow-up requests; one that cannot run yet is reported, not raised."""
    run = load_run(store, run_id)
    messages: list[str] = []
    for request in run.then:
        try:
            messages.append(f"queued {store.submit(request).title}")
        except HoneFrameError as exc:
            messages.append(f"not queued: {exc}")
    return messages
