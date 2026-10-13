"""Whole-project export: one zip with everything the workspace holds for a project — its records,
images and run records, the hone-flow run folders under `flows/` (manifests, spans, reports, produced
requests with the prompts), a queue snapshot, and a manifest naming the models used. Written best-effort
per file, so it works while the dashboard is running: a file that vanishes or is being written is listed
as skipped instead of failing the export."""

from __future__ import annotations

import json
import re
import zipfile
from pathlib import Path
from typing import TYPE_CHECKING, Any

from hone_frame._files import now
from hone_frame.errors import InvalidRequest

if TYPE_CHECKING:
    from hone_frame.store import ProjectStore

# transient files that make no sense in an archive (same rule as exports.py)
SKIP = re.compile(r"(^|/)(work/|lease\.json$|control\.json$|\.lock$|\..*\.tmp$)")


def _json(data: Any) -> str:
    return json.dumps(data, indent=2, ensure_ascii=False) + "\n"


def _tree(root: Path) -> list[Path]:
    return sorted(p for p in root.rglob("*") if p.is_file()) if root.is_dir() else []


def _add(archive: zipfile.ZipFile, path: Path, name: str) -> str | None:
    """One file into the archive; None when it could not be read just now (the dashboard may be writing)."""
    try:
        archive.write(path, name)
    except OSError:
        return path.name
    return None


def _models_used(project_dir: Path) -> dict[str, int]:
    """Model ids and how many images each generated, from the image records."""
    models: dict[str, int] = {}
    for path in (project_dir / "images").glob("img_*.json"):
        try:
            record: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
            generation: dict[str, Any] = record.get("generation") or {}
            model = str(generation.get("model") or "")
        except (OSError, json.JSONDecodeError):
            continue
        if model:
            models[model] = models.get(model, 0) + 1
    return dict(sorted(models.items()))


def _run_states(project_dir: Path) -> dict[str, list[str]]:
    states: dict[str, list[str]] = {}
    for path in sorted((project_dir / "runs").glob("*/run.json")):
        try:
            run = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        states.setdefault(run.get("state", "?"), []).append(run.get("id", path.parent.name))
    return states


def export_project(store: ProjectStore, out: Path) -> Path:
    """The whole project as one zip: `project/` (records, images, runs), `flows/` (run folders with
    spans and reports), and a `manifest.json` summary with the models used and the queue snapshot."""
    info = store.info
    out = out.expanduser()
    if out.suffix != ".zip":
        raise InvalidRequest(f"{out.name}: the export file must end in .zip")
    project_dir = store.workspace.root / "projects" / store.id
    flows_dir = store.workspace.root / "flows" / store.id
    from hone_frame.runs import queue  # noqa: PLC0415 - runs imports the store, which this module sits beside

    files: list[dict[str, Any]] = []
    skipped: list[str] = []
    out.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for top, base in ((project_dir, "project"), (flows_dir, "flows")):
            for path in _tree(top):
                rel = path.relative_to(top).as_posix()
                if SKIP.search(rel):
                    continue
                missed = _add(archive, path, f"{base}/{rel}")
                if missed:
                    skipped.append(f"{base}/{rel}")
                    continue
                files.append({"path": f"{base}/{rel}", "bytes": path.stat().st_size})
        manifest = {
            "format_version": "1",
            "exported_at": now(),
            "hone_frame_version": _version(),
            "project": {"id": store.id, "name": info.name, "created_at": info.created_at},
            "counts": {
                "subjects": len(store.subjects()),
                "scenes": len(store.scenes()),
                "images": len(list((project_dir / "images").glob("img_*.json"))),
                "run_records": len(list((project_dir / "runs").glob("*/run.json"))),
                "flow_runs": len(list(flows_dir.glob("runs/*"))) if flows_dir.is_dir() else 0,
            },
            "run_states": _run_states(project_dir),
            "models_used": _models_used(project_dir),
            "queue": [v.model_dump(mode="json") for v in queue(store.workspace)],
            "skipped_busy_files": skipped,
            "files": files,
        }
        archive.writestr("manifest.json", _json(manifest))
    return out


def _version() -> str:
    from hone_frame import __version__  # noqa: PLC0415 - cheap, but imported only when exporting

    return __version__
