"""The preset catalogue (design §5): shipped TOML files plus the user's own packs."""

from __future__ import annotations

import tomllib
from importlib import resources
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from hone_frame.errors import HoneFrameError, NotFound

CATEGORIES: tuple[str, ...] = (
    "style_pack",
    "character_presentation",
    "environment_presentation",
    "asset_presentation",
    "camera",
    "lighting",
    "expression",
    "pose",
    "interaction",
    "state",
    "sheet_layout",
    "profile",
    "selection",
    "judging",
)
DEFAULTS: dict[str, str] = {
    "style_pack": "cinematic-realism",
    "lighting": "neutral-studio",
    "sheet_layout": "four-view-turnaround",
    "character_presentation": "turnaround",
    "environment_presentation": "interior-coverage",
    "asset_presentation": "four-views",
    "profile": "draft",
    "selection": "all-rounds",
}


class PromptFragments(BaseModel):
    model_config = ConfigDict(extra="forbid")
    prefix: str = ""
    suffix: str = ""
    negative: str = ""


class Preset(BaseModel):
    """One preset: structured intent, defaults, constraints and needs (design §5.2)."""

    model_config = ConfigDict(extra="forbid")
    id: str
    category: str
    version: int = Field(ge=1)
    name: str
    description: str = Field(min_length=1)
    subject_kinds: list[str] = Field(default_factory=list[str])
    prompt: PromptFragments = Field(default_factory=PromptFragments)
    values: dict[str, Any] = Field(default_factory=dict[str, Any])
    needs: list[str] = Field(default_factory=list[str])
    example: str | None = None
    builtin: bool = True

    def applies_to(self, kind: str) -> bool:
        return not self.subject_kinds or kind in self.subject_kinds


class PresetCatalog:
    """Every preset by category and id. User packs (`<home>/presets/*.toml`) add or replace presets."""

    def __init__(self, user_dir: Path | None = None) -> None:
        self._by_category: dict[str, dict[str, Preset]] = {c: {} for c in CATEGORIES}
        folder = resources.files("hone_frame") / "data" / "presets"
        for category in CATEGORIES:
            self._load(
                (folder / f"{category}.toml").read_text(encoding="utf-8"), category, f"{category}.toml"
            )
        if user_dir is not None and user_dir.is_dir():
            for path in sorted(user_dir.glob("*.toml")):
                self._load(path.read_text(encoding="utf-8"), None, str(path), builtin=False)

    def _load(self, text: str, category: str | None, origin: str, *, builtin: bool = True) -> None:
        try:
            rows: list[dict[str, Any]] = tomllib.loads(text).get("presets", [])
        except tomllib.TOMLDecodeError as exc:
            raise HoneFrameError(f"preset file {origin} is not valid TOML: {exc}") from exc
        for row in rows:
            data: dict[str, Any] = {"category": category, **row, "builtin": builtin}
            try:
                preset = Preset.model_validate(data)
            except ValidationError as exc:
                raise HoneFrameError(f"preset {row.get('id')!r} in {origin} is invalid: {exc}") from exc
            if preset.category not in self._by_category:
                raise HoneFrameError(
                    f"preset {preset.id!r} in {origin} has unknown category {preset.category!r}; "
                    f"use one of {list(CATEGORIES)}"
                )
            self._by_category[preset.category][preset.id] = preset

    def categories(self) -> list[str]:
        return list(CATEGORIES)

    def list(self, category: str, *, kind: str | None = None) -> list[Preset]:
        presets = list(self._category(category).values())
        return [p for p in presets if kind is None or p.applies_to(kind)]

    def get(self, category: str, preset_id: str) -> Preset:
        presets = self._category(category)
        if preset_id not in presets:
            raise NotFound(f"no {category} preset {preset_id!r}; available: {sorted(presets)}")
        return presets[preset_id]

    def find(self, category: str, preset_id: str | None) -> Preset | None:
        return self._category(category).get(preset_id) if preset_id else None

    def default(self, category: str) -> str | None:
        return DEFAULTS.get(category)

    def as_dict(self) -> dict[str, list[dict[str, Any]]]:
        return {c: [p.model_dump() for p in self._by_category[c].values()] for c in CATEGORIES}

    def _category(self, category: str) -> dict[str, Preset]:
        if category not in self._by_category:
            raise NotFound(f"no preset category {category!r}; available: {list(CATEGORIES)}")
        return self._by_category[category]


def presets(user_dir: Path | None = None) -> PresetCatalog:
    """The catalogue, usable before any project or workspace exists (brief §12)."""
    return PresetCatalog(user_dir)
