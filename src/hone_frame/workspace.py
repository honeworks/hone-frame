"""`Workspace`: the folder that holds every project, image and run (design §4.1)."""

from __future__ import annotations

import os
from functools import cached_property
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

from pydantic import Field

from hone_frame._files import now, project_lock, read_json, slug, write_json
from hone_frame.errors import InvalidRequest
from hone_frame.presets import PresetCatalog
from hone_frame.records import Project, ProjectDefaults, Record
from hone_frame.store import ProjectStore

if TYPE_CHECKING:
    from hone_frame.ports import Models
    from hone_frame.runs import RunView


class Settings(Record):
    """Workspace settings (design §12.6). Never secrets: keys live in the environment."""

    format_version: str = "1"
    theme: Literal["light", "dark", "system"] = "system"
    max_reference_px: int = Field(default=1536, ge=256, le=8192)
    port: int = 8792


class Workspace:
    """`HONE_FRAME_HOME`, else `./hone-frame`. Created on first use."""

    def __init__(self, path: str | Path | None = None, *, models: Models | None = None) -> None:
        self.root = Path(path or os.environ.get("HONE_FRAME_HOME") or "hone-frame").expanduser().resolve()
        (self.root / "projects").mkdir(parents=True, exist_ok=True)
        marker = self.root / "workspace.json"
        if marker.is_file():
            read_json(marker)  # checks format_version
        else:
            write_json(marker, {"format_version": "1", "created_at": now()})
        self._models = models

    @property
    def models(self) -> Models:
        """The `Models` port; hone-models unless the workspace was made with another (design §7.2)."""
        if self._models is None:
            from hone_frame.models import HoneModels  # noqa: PLC0415 - hone-models loads only when used

            self._models = HoneModels()
        return self._models

    @cached_property
    def presets(self) -> PresetCatalog:
        return PresetCatalog(self.root / "presets")

    @property
    def settings(self) -> Settings:
        path = self.root / "settings.json"
        return Settings.model_validate(read_json(path)) if path.is_file() else Settings()

    def save_settings(self, settings: Settings) -> None:
        write_json(self.root / "settings.json", settings.model_dump(mode="json"))

    def projects(self) -> list[Project]:
        folders = sorted(p for p in (self.root / "projects").iterdir() if (p / "project.json").is_file())
        return [Project.model_validate(read_json(p / "project.json")) for p in folders]

    def create_project(
        self,
        name: str,
        *,
        brief: str = "",
        direction: str = "",
        style_pack: str = "cinematic-realism",
        defaults: ProjectDefaults | dict[str, Any] | None = None,
    ) -> ProjectStore:
        if not name.strip():
            raise InvalidRequest("a project needs a name")
        self.presets.get("style_pack", style_pack)
        base = slug(name)
        with project_lock(self.root / "projects"):
            project_id, n = base, 1
            while (self.root / "projects" / project_id).exists():
                n += 1
                project_id = f"{base}-{n}"
            stamp = now()
            project = Project.model_validate(
                {
                    "id": project_id,
                    "name": name.strip(),
                    "brief": brief,
                    "direction": direction,
                    "style_pack": style_pack,
                    "defaults": defaults or {},
                    "created_at": stamp,
                    "updated_at": stamp,
                }
            )
            write_json(self.root / "projects" / project_id / "project.json", project.model_dump(mode="json"))
        return ProjectStore(self, project_id)

    def project(self, project_id: str) -> ProjectStore:
        return ProjectStore(self, project_id)

    def queue(self) -> list[RunView]:
        """Queued and running runs of every project, oldest first."""
        from hone_frame.runs import queue  # noqa: PLC0415 - runs imports the store, which this module imports

        return queue(self)
