"""`ProjectStore`: one project's records, versions and images (design §4).

Run, plan, sheet and export operations live in their own modules; the methods here that forward to them
import lazily, so the store stays the one object people hold.
"""

from __future__ import annotations

import hashlib
import shutil
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any

from PIL import Image

from hone_frame._files import next_id, now, project_lock, read_json, write_json
from hone_frame._operations import ProjectOperations
from hone_frame._versions import Versioned, outdated_uses
from hone_frame.errors import InvalidRequest, NotFound
from hone_frame.records import (
    ID_PREFIX,
    ImageRecord,
    OutdatedUse,
    Project,
    Scene,
    Sequence,
    Sheet,
    SheetRecipe,
    Subject,
    SubjectKind,
    SubjectLink,
)

if TYPE_CHECKING:
    from hone_frame.workspace import Workspace

IMAGE_FORMATS = {"PNG": ".png", "JPEG": ".jpg", "WEBP": ".webp"}


class ProjectStore(ProjectOperations):
    """One project folder. Every write takes the project lock (decisions D-004)."""

    def __init__(self, workspace: Workspace, project_id: str) -> None:
        self.workspace = workspace
        self.id = project_id
        self.root = workspace.root / "projects" / project_id
        if not (self.root / "project.json").is_file():
            raise NotFound(f"no project {project_id!r} in {workspace.root}; see ws.projects()")
        self._scenes = Versioned(self.root / "scenes", "scn", Scene)
        self._sequences = Versioned(self.root / "sequences", "seq", Sequence)
        self._sheets = Versioned(self.root / "sheets", "sht", Sheet)

    def lock(self) -> Any:
        return project_lock(self.root)

    # ------------------------------------------------------------------------------------------ project

    @property
    def info(self) -> Project:
        return Project.model_validate(read_json(self.root / "project.json"))

    def update(self, **fields: Any) -> Project:
        with self.lock():
            data = self.info.model_dump() | fields | {"updated_at": now()}
            project = Project.model_validate(data)
            write_json(self.root / "project.json", project.model_dump(mode="json"))
            return project

    # ----------------------------------------------------------------------------------------- subjects

    def add_subject(self, kind: SubjectKind, name: str, *, description: str = "", **fields: Any) -> Subject:
        if kind not in ID_PREFIX:
            raise InvalidRequest(f"subject kind must be one of {list(ID_PREFIX)}, not {kind!r}")
        with self.lock():
            folder = self.root / "subjects"
            folder.mkdir(exist_ok=True)
            stamp = now()
            subject = Subject.model_validate(
                {
                    "id": next_id(folder, ID_PREFIX[kind]),
                    "kind": kind,
                    "name": name,
                    "description": description,
                    "created_at": stamp,
                    "updated_at": stamp,
                    **fields,
                }
            )
            write_json(
                folder / f"{subject.id}.json",
                {"format_version": "1", "id": subject.id, "versions": [subject.model_dump(mode="json")]},
            )
            return subject

    def edit_subject(self, subject_id: str, **changes: Any) -> Subject:
        """A new version with `changes`; earlier versions stay as they were (design §4.2)."""
        with self.lock():
            path = self._subject_path(subject_id)
            data = read_json(path)
            current = Subject.model_validate(data["versions"][-1])
            fixed = {"id", "kind", "version", "created_at"}
            if bad := sorted(set(changes) & fixed):
                raise InvalidRequest(f"cannot change {bad} of a subject")
            new = Subject.model_validate(
                current.model_dump() | changes | {"version": current.version + 1, "updated_at": now()}
            )
            data["versions"].append(new.model_dump(mode="json"))
            write_json(path, data)
            return new

    def subject(self, subject_id: str, version: int | None = None) -> Subject:
        versions = read_json(self._subject_path(subject_id))["versions"]
        if version is None:
            return Subject.model_validate(versions[-1])
        for row in versions:
            if row["version"] == version:
                return Subject.model_validate(row)
        raise NotFound(
            f"subject {subject_id!r} has no version {version}; latest is {versions[-1]['version']}"
        )

    def subjects(self, kind: str | None = None) -> list[Subject]:
        folder = self.root / "subjects"
        found = [Subject.model_validate(read_json(p)["versions"][-1]) for p in sorted(folder.glob("*.json"))]
        return [s for s in found if kind is None or s.kind == kind]

    def _subject_path(self, subject_id: str) -> Path:
        path = self.root / "subjects" / f"{subject_id}.json"
        if not path.is_file():
            raise NotFound(f"no subject {subject_id!r} in project {self.id!r}")
        return path

    # ------------------------------------------------------------------------------------------- images

    def import_image(
        self, path: str | Path, *, subject_id: str | None = None, label: str = ""
    ) -> ImageRecord:
        """Copy a file into the project as an `imported` image (design §4.3)."""
        links = [self._link(subject_id)] if subject_id else []
        return self.add_image(Path(path), source="imported", status="imported", subjects=links, label=label)

    def add_image(self, path: Path, **fields: Any) -> ImageRecord:
        """Store a copy of `path` as a new image with `fields`; the original file is never changed."""
        if not path.is_file():
            raise NotFound(f"no image file {path}")
        try:
            with Image.open(path) as picture:
                width, height, fmt = picture.width, picture.height, picture.format or ""
        except OSError as exc:
            raise InvalidRequest(f"{path} is not an image Pillow can read: {exc}") from exc
        with self.lock():
            folder = self.root / "images"
            folder.mkdir(exist_ok=True)
            image_id = next_id(folder, "img", width=4)
            target = folder / f"{image_id}{IMAGE_FORMATS.get(fmt, '.png')}"
            if fmt in IMAGE_FORMATS:
                shutil.copyfile(path, target)
            else:
                with Image.open(path) as picture:
                    picture.save(target, format="PNG")
            record = ImageRecord.model_validate(
                {
                    "id": image_id,
                    "file": target.name,
                    "width": width,
                    "height": height,
                    "sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
                    "created_at": now(),
                    **fields,
                }
            )
            write_json(folder / f"{image_id}.json", record.model_dump(mode="json"))
            return record

    def update_image(self, image_id: str, **fields: Any) -> ImageRecord:
        with self.lock():
            record = ImageRecord.model_validate(self.image(image_id).model_dump() | fields)
            write_json(self.root / "images" / f"{image_id}.json", record.model_dump(mode="json"))
            return record

    def image(self, image_id: str) -> ImageRecord:
        path = self.root / "images" / f"{image_id}.json"
        if not path.is_file():
            raise NotFound(f"no image {image_id!r} in project {self.id!r}")
        return ImageRecord.model_validate(read_json(path))

    def image_path(self, image_id: str) -> Path:
        return self.root / "images" / self.image(image_id).file

    def images(
        self,
        *,
        kind: str | None = None,
        subject_id: str | None = None,
        status: str | None = None,
        model: str | None = None,
        since: str | None = None,
        variation: str | None = None,
    ) -> list[ImageRecord]:
        """Every image, oldest first, filtered as asked (design §2); `variation`: only that variation's
        (an image made before variations belongs to the first one, change 0005)."""
        folder = self.root / "images"
        found = [ImageRecord.model_validate(read_json(p)) for p in sorted(folder.glob("img_*.json"))]
        first = self.info.first_variation if variation else ""
        checks: list[Callable[[ImageRecord], bool]] = [
            lambda r: variation is None or (r.variation or first) == variation,
            lambda r: kind is None or r.kind == kind,
            lambda r: subject_id is None or any(s.subject_id == subject_id for s in r.subjects),
            lambda r: status is None or r.status == status,
            lambda r: model is None or (r.generation is not None and r.generation.model == model),
            lambda r: since is None or r.created_at >= since,
        ]
        return [r for r in found if all(check(r) for check in checks)]

    def image_uses(self, image_id: str) -> list[str]:
        """What refers to an image: subject references, scenes, sheets and runs' selections."""
        uses = [f"subject {s.id}" for s in self.subjects() if image_id in s.reference_images]
        uses += [f"scene {s.id}" for s in self.scenes() if any(image_id in r.image_ids for r in s.refs)]
        uses += [f"sheet {s.id}" for s in self.sheets() if image_id in s.recipe.images]
        uses += [f"image {r.id}" for r in self.images() if r.parent == image_id]
        return uses

    def delete_image(self, image_id: str) -> None:
        """Delete an image nobody uses; a used one is refused with its uses (design §4.3)."""
        with self.lock():
            if uses := self.image_uses(image_id):
                raise InvalidRequest(f"image {image_id} is in use", uses)
            record = self.image(image_id)
            (self.root / "images" / record.file).unlink(missing_ok=True)
            (self.root / "images" / f"{image_id}.json").unlink()

    def _link(self, subject_id: str) -> SubjectLink:
        return SubjectLink(subject_id=subject_id, version=self.subject(subject_id).version)

    # ------------------------------------------------------------------- scenes, sequences and sheets

    def save_scene(self, scene: Scene) -> Scene:
        for ref in scene.refs:
            self.subject(ref.subject_id, ref.version)  # raises NotFound for an unknown subject or version
        pinned = [
            r.model_copy(update={"version": r.version or self.subject(r.subject_id).version})
            for r in scene.refs
        ]
        with self.lock():
            return self._scenes.save(scene.model_copy(update={"refs": pinned}))

    def scene(self, scene_id: str, version: int | None = None) -> Scene:
        return self._scenes.get(scene_id, version)

    def scenes(self) -> list[Scene]:
        return self._scenes.latest()

    def save_sequence(self, sequence: Sequence) -> Sequence:
        self.scene(sequence.scene_id)
        if len({f.id for f in sequence.frames}) != len(sequence.frames):
            raise InvalidRequest("frame ids in a sequence must be unique")
        with self.lock():
            return self._sequences.save(sequence)

    def sequence(self, sequence_id: str, version: int | None = None) -> Sequence:
        return self._sequences.get(sequence_id, version)

    def sequences(self) -> list[Sequence]:
        return self._sequences.latest()

    def save_sheet(self, recipe: SheetRecipe, sheet_id: str | None = None) -> Sheet:
        """Save a sheet recipe: a new sheet, or a new version of `sheet_id` (design §11)."""
        for image_id in recipe.images:
            self.image(image_id)
        self.workspace.presets.get("sheet_layout", recipe.layout)
        with self.lock():
            return self._sheets.save(Sheet(id=sheet_id or "", recipe=recipe))

    def sheet(self, sheet_id: str, version: int | None = None) -> Sheet:
        return self._sheets.get(sheet_id, version)

    def sheets(self) -> list[Sheet]:
        return self._sheets.latest()

    def set_sheet_render(self, sheet: Sheet, render: str) -> None:
        with self.lock():
            self._sheets.replace(sheet.model_copy(update={"render": render}))

    def outdated(self) -> list[OutdatedUse]:
        """Scenes, sequences and sheets that use an older subject version (design §4.4)."""
        current = {s.id: s.version for s in self.subjects()}
        return outdated_uses(self, current)
