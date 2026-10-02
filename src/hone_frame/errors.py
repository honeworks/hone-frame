"""Typed errors. Every message says what went wrong and what to do (AGENTS.md rule 3)."""

from __future__ import annotations


class HoneFrameError(RuntimeError):
    """Base class of every hone-frame error."""


class NotFound(HoneFrameError):
    """A project, subject, image, scene, sheet, run or preset that does not exist."""


class InvalidRequest(HoneFrameError):
    """A request or record that cannot be accepted; `problems` lists every reason."""

    def __init__(self, message: str, problems: list[str] | None = None) -> None:
        super().__init__(message if not problems else f"{message}: " + "; ".join(problems))
        self.problems = problems or [message]


class CapabilityProblem(InvalidRequest):
    """The chosen models cannot do what was asked (no references, no upscaler...)."""


class RunStateError(HoneFrameError):
    """A run control action that its current status does not allow."""
