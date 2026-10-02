"""The one port: how hone-frame calls models (design §7.2). The default is `HoneModels` (hone-models)."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol, TypeVar

from pydantic import BaseModel

from hone_frame.errors import HoneFrameError

T = TypeVar("T", bound=BaseModel)


class ModelFailure(HoneFrameError):
    """A model call that did not give a usable answer. `transient` failures are retried (design §8.4)."""

    def __init__(self, message: str, *, transient: bool) -> None:
        super().__init__(message)
        self.transient = transient


@dataclass(frozen=True)
class ModelInfo:
    """What a model is and takes, as far as the registry declares it (unknown is `None`)."""

    id: str
    kind: str  # chat | image | ...
    local: bool
    installed: str = "unknown"  # yes | no | unknown
    available: bool = True  # False: disabled, or certainly not installed
    max_references: int | None = None
    inputs: tuple[str, ...] = ()
    features: tuple[str, ...] = ()
    sizes: tuple[str, ...] = ()
    vision: bool | None = None
    prompt_guide: str = ""
    note: str = ""


@dataclass(frozen=True)
class Generated:
    """One image job (hone-models' `MediaResult`): a file, or `error` with `error_kind`."""

    path: Path | None
    seed: int | None = None
    elapsed_s: float | None = None
    job_id: str | None = None
    cost_usd: float | None = None
    cost_estimated: bool = False
    error: str | None = None
    error_kind: str | None = None
    extra: dict[str, Any] = field(default_factory=dict[str, Any])


class Models(Protocol):
    def generate(
        self,
        model_id: str,
        prompt: str,
        *,
        out: Path,
        seed: int,
        references: list[Path],
        inputs: dict[str, Any],
    ) -> Generated: ...

    def ask(self, model_id: str, prompt: str, *, images: list[Path], schema: type[T], think: bool) -> T: ...

    def info(self, model_id: str) -> ModelInfo: ...

    def available(self, kind: str) -> list[ModelInfo]: ...
