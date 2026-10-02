"""`FakeModels`: the `Models` port without models. Images are small coloured PNGs, judges are scripted."""

from __future__ import annotations

import re
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, TypeVar

from PIL import Image
from pydantic import BaseModel

from hone_frame.judging import JudgeAnswer
from hone_frame.ports import Generated, ModelFailure, ModelInfo
from hone_frame.prompts import PlannerAnswer

T = TypeVar("T", bound=BaseModel)
Judge = Callable[[int, str, list[Path]], dict[str, Any]]
CHECK_LINE = re.compile(r"^- ([a-z_]+): ", re.M)


def judge_answer(
    prompt: str, *, fail: tuple[str, ...] = (), uncertain: tuple[str, ...] = (), overall: float = 0.8
) -> dict[str, Any]:
    """A judge answer for every check the prompt lists: pass, except those named in `fail` / `uncertain`."""
    checks: list[dict[str, Any]] = []
    for name in CHECK_LINE.findall(prompt):
        verdict = "fail" if name in fail else ("uncertain" if name in uncertain else "pass")
        checks.append(
            {
                "name": name,
                "verdict": verdict,
                "score": 0.3 if verdict == "fail" else 0.9,
                "finding": f"{name} looks {'wrong' if verdict == 'fail' else 'right'}",
            }
        )
    return {"description": "a test picture", "checks": checks, "overall": overall, "summary": "scripted"}


def _all_pass(_index: int, prompt: str, _images: list[Path]) -> dict[str, Any]:
    return judge_answer(prompt)


@dataclass
class Call:
    model: str
    prompt: str
    seed: int | None = None
    references: list[Path] = field(default_factory=list[Path])
    inputs: dict[str, Any] = field(default_factory=dict[str, Any])
    images: list[Path] = field(default_factory=list[Path])


class FakeModels:
    """Scriptable stand-in for hone-models (design §7.2).

    - `generate` writes a PNG of the requested size; `fail_generate(kind, times)` scripts failures
      (`kind` "transient" raises a transient `ModelFailure`, or a hone-models `error_kind` result).
    - `ask` answers the judge with `judge(call_index, prompt, images)` (default: every check passes,
      overall 0.8) and the planner with its draft prompt.
    - `infos` overrides what `info` says about a model (default: local, takes 3 references, vision).
    """

    def __init__(
        self,
        *,
        judge: Judge | None = None,
        infos: dict[str, ModelInfo] | None = None,
        elapsed_s: float = 2.0,
        delay_s: float = 0.0,
    ) -> None:
        self.judge: Judge = judge or _all_pass
        self.infos = dict(infos or {})
        self.elapsed_s = elapsed_s
        self.delay_s = delay_s
        self.generated: list[Call] = []
        self.asked: list[Call] = []
        self._fail: list[str] = []
        self._fail_ask: list[str] = []
        self._lock = threading.Lock()

    def fail_generate(self, kind: str = "transient", times: int = 1) -> None:
        self._fail += [kind] * times

    def fail_ask(self, times: int = 1) -> None:
        self._fail_ask += ["transient"] * times

    def generate(
        self,
        model_id: str,
        prompt: str,
        *,
        out: Path,
        seed: int,
        references: list[Path],
        inputs: dict[str, Any],
    ) -> Generated:
        with self._lock:
            self.generated.append(Call(model_id, prompt, seed, list(references), dict(inputs)))
            failure = self._fail.pop(0) if self._fail else None
        if self.delay_s:
            time.sleep(self.delay_s)
        if failure == "transient":
            raise ModelFailure(f"{model_id}: scripted transient failure", transient=True)
        if failure is not None:
            return Generated(path=None, seed=seed, error=f"scripted {failure}", error_kind=failure)
        width, height = (int(v) for v in str(inputs.get("size") or "64x64").split("x"))
        colour = (seed % 256, (seed // 256) % 256, (seed // 65536) % 256)
        Image.new("RGB", (max(width // 16, 8), max(height // 16, 8)), colour).save(out, format="PNG")
        return Generated(path=out, seed=seed, elapsed_s=self.elapsed_s, job_id=f"fake-{len(self.generated)}")

    def ask(self, model_id: str, prompt: str, *, images: list[Path], schema: type[T], think: bool) -> T:
        with self._lock:
            self.asked.append(Call(model_id, prompt, images=list(images)))
            index = len(self.asked) - 1
            failure = self._fail_ask.pop(0) if self._fail_ask else None
        if failure:
            raise ModelFailure(f"{model_id}: scripted judge failure", transient=True)
        if schema is PlannerAnswer:
            draft = prompt.split("Draft prompt:\n", 1)[-1].split("\n", 1)[0]
            return schema.model_validate({"prompt": draft, "negative": None})
        if schema is JudgeAnswer:
            judged = sum(1 for c in self.asked[: index + 1] if "quality judge" in c.prompt) - 1
            return schema.model_validate(self.judge(judged, prompt, list(images)))
        raise ModelFailure(f"FakeModels cannot answer {schema.__name__}", transient=False)

    def info(self, model_id: str) -> ModelInfo:
        if model_id in self.infos:
            return self.infos[model_id]
        kind = "chat" if model_id.startswith(("gemma", "qwen2.5vl", "qwen3")) else "image"
        return ModelInfo(
            id=model_id,
            kind=kind,
            local=True,
            installed="yes",
            max_references=3,
            vision=True if kind == "chat" else None,
            prompt_guide="plain sentences",
        )

    def available(self, kind: str) -> list[ModelInfo]:
        ids = {
            "image": ["z-image-turbo", "flux.2-klein-4b", "qwen-image-edit-2511"],
            "chat": ["gemma4-12b", "qwen2.5vl-7b"],
        }.get(kind, [])
        return [self.info(i) for i in ids]

    @property
    def image_calls(self) -> int:
        return len(self.generated)
