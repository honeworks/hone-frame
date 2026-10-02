"""Exports (design §11.3): zip files with images and machine-readable descriptions, never secrets."""

from __future__ import annotations

import json
import re
import zipfile
from pathlib import Path
from typing import TYPE_CHECKING, Any

from hone_frame.errors import InvalidRequest
from hone_frame.references import order, scene_refs
from hone_frame.runs import all_runs, outputs

if TYPE_CHECKING:
    from hone_frame.store import ProjectStore

SKIP = re.compile(r"(^|/)(work/|control\.json$|\.lock$|\..*\.tmp$)")


def _zip(out: Path) -> zipfile.ZipFile:
    out.parent.mkdir(parents=True, exist_ok=True)
    return zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED)


def _json(data: Any) -> str:
    return json.dumps(data, indent=2, ensure_ascii=False) + "\n"


def _safe(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "x"


def export_sheet(store: ProjectStore, sheet_id: str, out: Path, *, sources: bool = False) -> Path:
    sheet = store.sheet(sheet_id)
    png = store.compose_sheet(sheet.id, sheet.version)
    with _zip(out) as archive:
        archive.write(png, "sheet.png")
        records = [store.image(i).model_dump(mode="json") for i in sheet.recipe.images]
        archive.writestr("sheet.json", _json({"sheet": sheet.model_dump(mode="json"), "images": records}))
        if sources:
            for image_id in sheet.recipe.images:
                path = store.image_path(image_id)
                archive.write(path, f"images/{path.name}")
    return out


def export_pack(store: ProjectStore, scene_id: str, out: Path) -> Path:
    """Only what the scene selected, in reference order, with roles and subject versions (brief §6)."""
    scene = store.scene(scene_id)
    refs, errors = scene_refs(store, scene)
    if errors:
        raise InvalidRequest("the scene's references are not complete", errors)
    rows: list[dict[str, Any]] = []
    with _zip(out) as archive:
        for n, ref in enumerate(order(refs), start=1):
            path = store.image_path(ref.image_id)
            subject = store.subject(ref.subject_id or "", ref.version)
            name = f"images/{n:02d}-{_safe(subject.name)}-{ref.role}{path.suffix}"
            archive.write(path, name)
            rows.append(
                {
                    "file": name,
                    "role": ref.role,
                    "subject": subject.model_dump(mode="json"),
                    "image": store.image(ref.image_id).model_dump(mode="json"),
                }
            )
        archive.writestr("pack.json", _json({"scene": scene.model_dump(mode="json"), "references": rows}))
    return out


def export_sequence(store: ProjectStore, sequence_id: str, out: Path) -> Path:
    """Numbered frames in order: each frame's accepted image from the latest run of the sequence."""
    sequence = store.sequence(sequence_id)
    run = next((r for r in all_runs(store) if r.plan.request.get("sequence_id") == sequence_id), None)
    if run is None:
        raise InvalidRequest(f"sequence {sequence_id} has not been generated yet")
    frames: list[dict[str, Any]] = []
    with _zip(out) as archive:
        for n, (frame, record) in enumerate(zip(sequence.frames, outputs(store, run), strict=False), start=1):
            if record.selected is None:
                raise InvalidRequest(f"frame {n} ({frame.id}) has no accepted image yet; pick one first")
            path = store.image_path(record.selected)
            name = f"frames/{n:02d}{path.suffix}"
            archive.write(path, name)
            frames.append(
                {
                    "n": n,
                    "file": name,
                    "frame": frame.model_dump(mode="json"),
                    "image": store.image(record.selected).model_dump(mode="json"),
                }
            )
        archive.writestr(
            "sequence.json",
            _json({"sequence": sequence.model_dump(mode="json"), "run": run.id, "frames": frames}),
        )
    return out


def export_project(store: ProjectStore, out: Path) -> Path:
    """The project folder's records and images, without work files and control files (design §11.3)."""
    with _zip(out) as archive:
        for path in sorted(store.root.rglob("*")):
            relative = path.relative_to(store.root).as_posix()
            if path.is_file() and not SKIP.search(relative):
                archive.write(path, f"{store.id}/{relative}")
    return out
