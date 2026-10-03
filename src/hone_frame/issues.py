"""Standard issues for "Generate again" (change 0006): each adds a fix to the new attempt's prompt and a
required check to its judging. The list is data (`data/issues.toml`)."""

from __future__ import annotations

import tomllib
from functools import cache
from importlib import resources
from typing import Any

from pydantic import BaseModel, ConfigDict

from hone_frame.errors import InvalidRequest


class Issue(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = ""
    label: str
    group: str
    fix: str
    check: str


@cache
def issues() -> dict[str, Issue]:
    text = (resources.files("hone_frame") / "data" / "issues.toml").read_text(encoding="utf-8")
    return {k: Issue.model_validate(v | {"id": k}) for k, v in tomllib.loads(text)["issues"].items()}


def chosen(ids: list[str]) -> list[Issue]:
    if unknown := sorted(set(ids) - set(issues())):
        raise InvalidRequest(f"unknown issues {unknown}; use {list(issues())}")
    return [issues()[i] for i in ids]


def issue_checks(ids: list[str]) -> list[dict[str, Any]]:
    """The judge checks of the ticked issues, required."""
    return [{"name": f"issue_{i.id}", "required": True, "question": i.check} for i in chosen(ids)]
