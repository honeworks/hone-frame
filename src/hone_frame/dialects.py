"""Prompt dialects (design §8.8, change 0002): how a prompt is written for a model and a task (mode)."""

from __future__ import annotations

import fnmatch
import tomllib
from importlib import resources
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from hone_frame.errors import HoneFrameError

Mode = Literal["generate", "view", "compose"]
SECTIONS = (
    "camera_phrase", "shot", "view", "subject", "outfit", "features", "keep", "scene", "roles", "action",
    "expression", "pose", "gaze", "state", "frame", "background", "lighting", "style_lead", "style_close",
    "text_refs", "note", "fixes",
)  # fmt: skip
REQUIRED = {"camera_phrase", "view", "keep", "subject", "scene", "fixes"}  # never dropped for the budget


class ModeRules(BaseModel):
    model_config = ConfigDict(extra="forbid")
    sections: list[str]
    max_words: int = Field(ge=10, le=1000)
    style: Literal["full", "short"] = "full"
    rules: str = ""


class Dialect(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = ""
    models: list[str]
    summary: str = ""
    camera_phrase: str | None = None
    generate: ModeRules
    view: ModeRules | None = None
    compose: ModeRules | None = None

    def matches(self, model_id: str) -> bool:
        return any(fnmatch.fnmatchcase(model_id, pattern) for pattern in self.models)

    def rules_for(self, mode: Mode) -> ModeRules:
        """The mode's rules; a dialect without rules for `view` or `compose` writes those like `generate`."""
        return getattr(self, mode) or self.generate


class Dialects:
    """The shipped dialects, overridden or extended by `<home>/prompting.toml` (same names win)."""

    def __init__(self, home: Path | None = None) -> None:
        shipped = (resources.files("hone_frame") / "data" / "prompting.toml").read_text(encoding="utf-8")
        found = _parse(shipped, "prompting.toml")
        user = home / "prompting.toml" if home is not None else None
        if user is not None and user.is_file():
            own = _parse(user.read_text(encoding="utf-8"), str(user))
            found = {**own, **{k: v for k, v in found.items() if k not in own}}  # the user's first
        self.all = found

    def for_model(self, model_id: str) -> Dialect:
        generic = self.all.get("generic")
        for dialect in self.all.values():
            if dialect.name != "generic" and dialect.matches(model_id):
                return dialect
        if generic is None:
            raise HoneFrameError("no prompt dialect matches and no 'generic' dialect is defined")
        return generic


def _parse(text: str, origin: str) -> dict[str, Dialect]:
    try:
        rows: dict[str, Any] = tomllib.loads(text).get("dialects", {})
        found = {name: Dialect.model_validate({**row, "name": name}) for name, row in rows.items()}
    except (tomllib.TOMLDecodeError, ValidationError) as exc:
        raise HoneFrameError(f"prompt dialects in {origin} are not valid: {exc}") from exc
    for dialect in found.values():
        for mode in ("generate", "view", "compose"):
            rules: ModeRules | None = getattr(dialect, mode)
            unknown = sorted(set(rules.sections) - set(SECTIONS)) if rules else []
            if unknown:
                raise HoneFrameError(
                    f"dialect {dialect.name!r} in {origin}, mode {mode}: unknown sections {unknown}; "
                    f"use {list(SECTIONS)}"
                )
    return found
