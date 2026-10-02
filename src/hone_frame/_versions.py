"""Versioned records (scenes, sequences, sheets) and the outdated-use check (design §4.4)."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Generic, TypeVar

from hone_frame._files import next_id, now, read_json, write_json
from hone_frame.errors import NotFound
from hone_frame.records import OutdatedUse, Scene, Sequence, Sheet

if TYPE_CHECKING:
    from hone_frame.store import ProjectStore

T = TypeVar("T", Scene, Sequence, Sheet)


class Versioned(Generic[T]):
    """`<folder>/<id>.json` holds every version of one record, newest last; a version never changes."""

    def __init__(self, folder: Path, prefix: str, model: type[T]) -> None:
        self.folder = folder
        self.prefix = prefix
        self.model = model

    def save(self, record: T) -> T:
        """A new record when `record.id` is empty, else a new version of that record."""
        self.folder.mkdir(parents=True, exist_ok=True)
        if not record.id:
            new = record.model_copy(
                update={"id": next_id(self.folder, self.prefix), "version": 1, "created_at": now()}
            )
            write_json(
                self._path(new.id),
                {"format_version": "1", "id": new.id, "versions": [new.model_dump(mode="json")]},
            )
            return new
        data = read_json(self._existing(record.id))
        latest = data["versions"][-1]["version"]
        new = record.model_copy(update={"version": latest + 1, "created_at": now()})
        data["versions"].append(new.model_dump(mode="json"))
        write_json(self._path(record.id), data)
        return new

    def replace(self, record: T) -> None:
        """Rewrite one version in place: only for derived fields (a sheet's render file name)."""
        data = read_json(self._existing(record.id))
        data["versions"] = [
            record.model_dump(mode="json") if row["version"] == record.version else row
            for row in data["versions"]
        ]
        write_json(self._path(record.id), data)

    def get(self, record_id: str, version: int | None = None) -> T:
        rows = read_json(self._existing(record_id))["versions"]
        row = rows[-1] if version is None else next((r for r in rows if r["version"] == version), None)
        if row is None:
            raise NotFound(f"{record_id} has no version {version}; latest is {rows[-1]['version']}")
        return self.model.model_validate(row)

    def latest(self) -> list[T]:
        return [self.get(p.stem) for p in sorted(self.folder.glob(f"{self.prefix}_*.json"))]

    def _path(self, record_id: str) -> Path:
        return self.folder / f"{record_id}.json"

    def _existing(self, record_id: str) -> Path:
        path = self._path(record_id)
        if not path.is_file():
            raise NotFound(f"no {self.model.__name__.lower()} {record_id!r}")
        return path


def outdated_uses(store: ProjectStore, current: dict[str, int]) -> list[OutdatedUse]:
    """Every pinned subject version older than the subject's current one."""
    found: list[OutdatedUse] = []

    def check(kind: str, record_id: str, version: int, subject_id: str, used: int) -> None:
        if used < current.get(subject_id, used):
            found.append(
                OutdatedUse.model_validate(
                    {
                        "kind": kind,
                        "id": record_id,
                        "version": version,
                        "subject_id": subject_id,
                        "used_version": used,
                        "current_version": current[subject_id],
                    }
                )
            )

    scenes = store.scenes()
    for scene in scenes:
        for ref in scene.refs:
            check("scene", scene.id, scene.version, ref.subject_id, ref.version or current[ref.subject_id])
    by_scene = {s.id: s for s in scenes}
    for sequence in store.sequences():
        for ref in by_scene[sequence.scene_id].refs if sequence.scene_id in by_scene else []:
            check("sequence", sequence.id, sequence.version, ref.subject_id, ref.version or 0)
    for sheet in store.sheets():
        for image_id in sheet.recipe.images:
            for link in store.image(image_id).subjects:
                check("sheet", sheet.id, sheet.version, link.subject_id, link.version)
    return found
