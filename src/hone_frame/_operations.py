"""The `ProjectStore` operations that live in other modules (plans, runs, sheets, exports), imported
lazily so the store module stays small and import cycles stay out."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from hone_frame.requests import Plan, RequestBase
    from hone_frame.runs import OutputRecord, RunView
    from hone_frame.store import ProjectStore


class ProjectOperations:
    """Mixed into `ProjectStore`; every method forwards to the module that implements it."""

    def plan(self, request: RequestBase | dict[str, Any]) -> Plan:
        from hone_frame.planning import plan

        return plan(self._store, request)

    def submit(self, request: RequestBase | dict[str, Any]) -> RunView:
        from hone_frame.control import submit

        return submit(self._store, request)

    def runs(self) -> list[RunView]:
        from hone_frame.control import runs

        return runs(self._store)

    def run_view(self, run_id: str) -> RunView:
        from hone_frame.control import run_view

        return run_view(self._store, run_id)

    def pause(self, run_id: str) -> RunView:
        from hone_frame.control import pause

        return pause(self._store, run_id)

    def cancel(self, run_id: str) -> RunView:
        from hone_frame.control import cancel

        return cancel(self._store, run_id)

    def resume(self, run_id: str) -> RunView:
        from hone_frame.control import resume

        return resume(self._store, run_id)

    def retry(self, run_id: str) -> RunView:
        from hone_frame.control import retry

        return retry(self._store, run_id)

    def rerun(self, run_id: str, output_id: str) -> RunView:
        from hone_frame.control import rerun

        return rerun(self._store, run_id, output_id)

    def pick(self, run_id: str, output_id: str, image_id: str, *, note: str = "") -> OutputRecord:
        from hone_frame.control import pick

        return pick(self._store, run_id, output_id, image_id, note=note)

    def compose_sheet(self, sheet_id: str, version: int | None = None) -> Path:
        from hone_frame.sheets import compose_saved

        return compose_saved(self._store, sheet_id, version)

    def export_sheet(self, sheet_id: str, out: str | Path, *, sources: bool = False) -> Path:
        from hone_frame.exports import export_sheet

        return export_sheet(self._store, sheet_id, Path(out), sources=sources)

    def export_pack(self, scene_id: str, out: str | Path) -> Path:
        from hone_frame.exports import export_pack

        return export_pack(self._store, scene_id, Path(out))

    def export_sequence(self, sequence_id: str, out: str | Path) -> Path:
        from hone_frame.exports import export_sequence

        return export_sequence(self._store, sequence_id, Path(out))

    def export_project(self, out: str | Path) -> Path:
        from hone_frame.exports import export_project

        return export_project(self._store, Path(out))

    @property
    def _store(self) -> ProjectStore:
        return self  # type: ignore[return-value]  # pyright: ignore[reportReturnType]
