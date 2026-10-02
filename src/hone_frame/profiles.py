"""Profiles: which model plays which role (design §7.1), and the effective preset of each category."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from hone_frame.errors import NotFound
from hone_frame.presets import Preset
from hone_frame.records import Project, Selection
from hone_frame.requests import RequestBase, ResolvedProfile

if TYPE_CHECKING:
    from hone_frame.store import ProjectStore


def resolve_profile(store: ProjectStore, request: RequestBase) -> ResolvedProfile:
    """The request's profile, else the project's default, with the project's overrides applied."""
    project = store.info
    profile_id = request.profile or project.defaults.profile
    preset = store.workspace.presets.get("profile", profile_id)
    values: dict[str, Any] = dict(preset.values) | project.defaults.profiles.get(profile_id, {})
    return ResolvedProfile.model_validate({"id": profile_id, **values})


def resolve_selection(store: ProjectStore, request: RequestBase) -> Selection:
    if request.selection is not None:
        return request.selection
    if "selection" in request.presets:
        preset = store.workspace.presets.get("selection", request.presets["selection"])
        return Selection.model_validate(preset.values)
    return store.info.defaults.selection


class PresetChoices:
    """The effective preset per category: request > scene overrides > project > style pack > default."""

    def __init__(
        self, store: ProjectStore, request: RequestBase, overrides: dict[str, str] | None = None
    ) -> None:
        self.catalog = store.workspace.presets
        project: Project = store.info
        pack = self.catalog.get("style_pack", request.presets.get("style_pack") or project.style_pack)
        self.layers: list[dict[str, str]] = [
            request.presets,
            overrides or {},
            project.defaults.presets,
            {"style_pack": pack.id},
            {k: str(v) for k, v in pack.values.items()},
        ]
        self.used: dict[str, int] = {}

    def choice(self, category: str) -> str | None:
        for layer in self.layers:
            if layer.get(category):
                return layer[category]
        return self.catalog.default(category)

    def get(self, category: str, preset_id: str | None = None) -> Preset | None:
        """The preset `preset_id` (or the effective one); its version is recorded in `used`."""
        chosen = preset_id or self.choice(category)
        if not chosen:
            return None
        try:
            preset = self.catalog.get(category, chosen)
        except NotFound:
            if preset_id is not None and category in {"camera", "expression", "pose", "lighting"}:
                return None  # free text, not a preset
            raise
        self.used[f"{category}:{preset.id}"] = preset.version
        return preset
