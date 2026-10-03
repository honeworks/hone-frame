"""Clean-up (change 0006), always the person's choice: delete the candidates that were not chosen, or a
whole variation's images. An image something still uses (a reference, a scene, a sheet) is kept."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Literal

from hone_frame.errors import InvalidRequest
from hone_frame.runs import all_runs, outputs

if TYPE_CHECKING:
    from hone_frame.store import ProjectStore

What = Literal["unchosen", "variation"]
UNCHOSEN = {"candidate", "rejected", "uncertain"}


def _unchosen(store: ProjectStore) -> list[str]:
    """Candidates of finished outputs that are neither chosen nor kept as the best available."""
    keep: set[str] = set()
    finished: set[tuple[str, str]] = set()
    for run in all_runs(store):
        for o in outputs(store, run):
            keep |= {x for x in (o.selected, o.best_available) if x}
            if o.status in ("done", "replaced", "needs_review"):
                finished.add((run.id, o.id))
    return [
        i.id
        for i in store.images()
        if i.status in UNCHOSEN and i.id not in keep and (i.run_id or "", i.output_id or "") in finished
    ]


def cleanup_candidates(store: ProjectStore, what: What, variation: str | None = None) -> list[str]:
    """The images a clean-up would delete (nothing is deleted)."""
    if what == "unchosen":
        return _unchosen(store)
    project = store.info
    if not variation:
        raise InvalidRequest("name the variation to delete")
    v = project.variation_of(variation)
    if len(project.all_variations()) < 2 or project.variation_of().id == v.id:
        raise InvalidRequest(
            "switch to another variation first; the active or only variation cannot be deleted"
        )
    return [i.id for i in store.images(variation=v.id)]


def cleanup(store: ProjectStore, what: What, variation: str | None = None) -> dict[str, Any]:
    """Delete them; an image still in use is kept and counted. Deleting a variation also removes it."""
    deleted, kept = 0, 0
    for image_id in cleanup_candidates(store, what, variation):
        if store.image_uses(image_id):
            kept += 1
            continue
        store.delete_image(image_id)
        deleted += 1
    if what == "variation" and variation:
        left = [v.model_dump() for v in store.info.all_variations() if v.id != variation]
        store.update(variations=left)
    return {"deleted": deleted, "kept_in_use": kept}
