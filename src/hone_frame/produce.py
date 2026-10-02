"""Producing one output (design §8.2): rounds of candidates, judging, retries, and the pick."""

from __future__ import annotations

import hashlib
import time
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any, TypeVar

from hone_frame._files import now
from hone_frame.events import EventLog
from hone_frame.judging import checks_for, evaluate, findings
from hone_frame.pick import pick
from hone_frame.ports import Generated, ModelFailure
from hone_frame.produce_refs import resolve_refs
from hone_frame.prompts import PlannerAnswer, planner_prompt, template_prompt
from hone_frame.records import Generation, ImageRecord, RefUse
from hone_frame.requests import PlannedOutput, PlannedRef
from hone_frame.runs import OutputRecord, RunRecord, StopRequested, control, load_output, run_dir, save_output

if TYPE_CHECKING:
    from hone_frame.store import ProjectStore

T = TypeVar("T")
RETRY_KINDS = {"out_of_memory", "failed", "no_output", None}


class CandidateRefused(Exception):
    """The model refused or rejected this one candidate's input; the output goes on (design §8.4)."""


def seed_for(*parts: object) -> int:
    return int(hashlib.sha256(":".join(map(str, parts)).encode()).hexdigest()[:8], 16)


class Producer:
    """§8.2 for one output of one run. Re-entrant: stored candidates are never made again."""

    def __init__(self, store: ProjectStore, run: RunRecord, out: PlannedOutput, seed: int) -> None:
        self.store, self.run, self.out = store, run, out
        self.plan = run.plan
        self.selection = run.plan.selection
        self.profile = run.plan.profile
        self.models = store.workspace.models
        self.seed = seed_for(run.id, out.seed_group) if out.seed_group else seed
        self.folder = run_dir(store, run.id)
        self.log = EventLog(self.folder / "events.jsonl")
        self.record = load_output(store, run.id, out.id) or OutputRecord(
            id=out.id, label=out.label, kind=out.kind, model=out.model
        )
        self.refs: list[tuple[PlannedRef, Path, str]] = []
        self.negative: str | None = None

    def run_output(self) -> OutputRecord:
        if self.record.status == "done":
            return self.record  # accepted earlier (a manual pick, or a previous call)
        self._save(status="running", started_at=self.record.started_at or now(), error=None, reason="")
        self.log.write("output_started", output=self.out.id, label=self.out.label)
        try:
            self._check()
            self.refs = resolve_refs(self.store, self.run, self.out, self.folder / "work")
            self._rounds()
            self._pick()
        except StopRequested as stop:
            self._save(status="paused" if stop.action == "pause" else "canceled", reason=str(stop))
            raise
        except ModelFailure as exc:
            self._save(
                status="failed", error=str(exc), reason="technical failure after retries", ended_at=now()
            )
            self.log.write("output_finished", output=self.out.id, status="failed", message=str(exc))
            raise
        self.log.write(
            "output_finished", output=self.out.id, status=self.record.status, message=self.record.reason
        )
        return self.record

    # ------------------------------------------------------------------------------------------ rounds

    def _rounds(self) -> None:
        stored = {
            (i.round, i.candidate): i
            for i in self.store.images()
            if i.run_id == self.run.id and i.output_id == self.out.id
        }
        found: list[str] = []
        for r in range(1, self.selection.rounds + 1):
            missing = [c for c in range(1, self.selection.candidates + 1) if (r, c) not in stored]
            prompt = self._prompt(found) if missing else self.record.prompt
            round_images: list[ImageRecord] = []
            for c in range(1, self.selection.candidates + 1):
                image = stored.get((r, c)) or self._candidate(r, c, prompt)
                if image is None:
                    continue
                if self.selection.auto_judge and image.evaluation is None and self.profile.judge:
                    image = self._judge(image)
                round_images.append(image)
            self._save(rounds_done=r, candidates=self._all_candidates())
            if self.selection.stop == "stop_on_pass" and any(
                i.evaluation and i.evaluation.passed for i in round_images
            ):
                if r < self.selection.rounds:
                    self.log.write(
                        "stopped_early", output=self.out.id, round=r, skipped_rounds=self.selection.rounds - r
                    )
                return
            if self.selection.strategy == "sequential":
                found = _round_findings(round_images)

    def _prompt(self, found: list[str]) -> str:
        self._check()
        self.log.write("stage", stage="planning", output=self.out.id)
        named = [(ref, name) for ref, _, name in self.refs]
        template = template_prompt(self.out, named, found)
        prompt = template
        if self.profile.planner and not self.out.prompt_inputs.get("prompt_override"):
            guide = self._guide()
            try:
                answer = self._retrying(
                    "planner",
                    lambda: self.models.ask(
                        self.profile.planner or "",
                        planner_prompt(self.out, template, guide, found),
                        images=[],
                        schema=PlannerAnswer,
                        think=self.profile.planner_think,
                    ),
                )
                prompt = answer.prompt.strip() or template
                self.negative = answer.negative
            except ModelFailure as exc:
                self.log.write(
                    "planner_failed", output=self.out.id, message=f"{exc}; the template prompt is used"
                )
        self._save(prompt=prompt)
        self.log.write("planned", output=self.out.id, message=prompt)
        return prompt

    def _guide(self) -> str:
        try:
            return self.models.info(self.out.model).prompt_guide
        except Exception:
            return ""

    def _candidate(self, r: int, c: int, prompt: str) -> ImageRecord | None:
        self.log.write("stage", stage="generating", output=self.out.id)
        self.log.write(
            "generating",
            output=self.out.id,
            round=r,
            candidate=c,
            model=self.out.model,
            label=self.out.label,
            rounds=self.selection.rounds,
        )
        seed = seed_for(self.seed, r, c)
        out = self.folder / "work" / f"{self.out.id}-r{r}c{c}.png"
        out.parent.mkdir(parents=True, exist_ok=True)
        started = time.monotonic()
        try:
            result = self._retrying("generate", lambda: self._generate(prompt, out, seed))
        except CandidateRefused as exc:
            self.log.write("candidate_failed", output=self.out.id, round=r, candidate=c, message=str(exc))
            return None
        path = result.path or out  # _generate guarantees a file
        image = self.store.add_image(path, **self._image_fields(r, c, prompt, result))
        path.unlink(missing_ok=True)
        local = self._local(self.out.model)
        self.log.write(
            "generated",
            output=self.out.id,
            round=r,
            candidate=c,
            model=self.out.model,
            size=self.out.size,
            image=image.id,
            local=local,
            cost_usd=result.cost_usd,
            cost_estimated=result.cost_estimated or None,
            job_id=result.job_id,
            seed=seed,
            duration_s=round(result.elapsed_s or time.monotonic() - started, 3),
        )
        self._save(candidates=[*self._all_candidates()])
        return image

    def _generate(self, prompt: str, out: Path, seed: int) -> Generated:
        refs = [p for _, p, _ in self.refs]
        inputs: dict[str, Any] = dict(self.profile.settings) | {"size": self.out.size}
        if negative := (self.negative or self.out.prompt_inputs.get("negative")):
            inputs["negative"] = negative
        if angle := self.out.prompt_inputs.get("camera_angle"):
            inputs["camera_angle"] = angle
        if self.out.mode == "upscale":
            inputs["image"], refs = refs[0], []
        result = self.models.generate(
            self.out.model, prompt, out=out, seed=seed, references=refs, inputs=inputs
        )
        if result.error is not None or result.path is None:
            message = f"{self.out.model}: {result.error or 'no output'} ({result.error_kind})"
            if result.error_kind in RETRY_KINDS:
                raise ModelFailure(message, transient=True)
            raise CandidateRefused(message)
        return result

    def _image_fields(self, r: int, c: int, prompt: str, result: Generated) -> dict[str, Any]:
        used = [RefUse(image_id=ref.image_id, role=ref.role) for ref, _, _ in self.refs]
        generation = Generation(
            model=self.out.model,
            prompt=prompt,
            negative=self.negative or self.out.prompt_inputs.get("negative"),
            inputs={"size": self.out.size, **self.profile.settings},
            references=used,
            seed=result.seed,
            job_id=result.job_id,
            elapsed_s=result.elapsed_s,
            cost_usd=result.cost_usd,
            cost_estimated=result.cost_estimated,
        )
        return {
            "subjects": self.out.subjects,
            "label": self.out.label,
            "run_id": self.run.id,
            "output_id": self.out.id,
            "round": r,
            "candidate": c,
            "parent": self.out.parent,
            "generation": generation,
            "status": "candidate",
            "profile": self.profile.id,
            "source": "promoted" if self.out.parent else "generated",
        }

    # ---------------------------------------------------------------------------------- judge and pick

    def _judge(self, image: ImageRecord) -> ImageRecord:
        self.log.write("stage", stage="judging", output=self.out.id)
        self.log.write(
            "judging",
            output=self.out.id,
            round=image.round,
            candidate=image.candidate,
            model=self.profile.judge,
            image=image.id,
            label=self.out.label,
        )
        checks = checks_for(self.store.workspace.presets, self.out)
        refs = [
            p for ref, p, _ in self.refs if ref.role in ("identity", "object", "environment", "composition")
        ]
        started = time.monotonic()
        try:
            evaluation = self._retrying(
                "judge",
                lambda: evaluate(
                    self.models,
                    judge=self.profile.judge or "",
                    think=self.profile.judge_think,
                    out=self.out,
                    checks=checks,
                    candidate=self.store.image_path(image.id),
                    references=refs,
                    prompt=image.generation.prompt if image.generation else "",
                ),
            )
        except ModelFailure as exc:
            self.log.write("judge_failed", output=self.out.id, image=image.id, message=str(exc))
            return image
        status = "candidate" if evaluation.passed else ("uncertain" if evaluation.uncertain else "rejected")
        image = self.store.update_image(image.id, evaluation=evaluation, status=status)
        self.log.write(
            "judged",
            output=self.out.id,
            round=image.round,
            candidate=image.candidate,
            image=image.id,
            model=self.profile.judge,
            passed=evaluation.passed,
            overall=evaluation.overall,
            message=evaluation.summary,
            duration_s=round(time.monotonic() - started, 3),
            findings=findings(evaluation),
        )
        return image

    def _pick(self) -> None:
        self._check()
        self.log.write("stage", stage="selecting", output=self.out.id)
        images = [self.store.image(i) for i in self._all_candidates()]
        if not self.selection.auto_pick:
            _, best, _ = pick(images, self.folder / "select.jsonl")
            self._finish("needs_review", None, best, "manual pick: choose a candidate")
            return
        winner, best, reason = pick(images, self.folder / "select.jsonl")
        if winner is not None:
            self.store.update_image(winner.id, status="picked")
        self._finish("done" if winner else "needs_review", winner, best, reason)

    def _finish(self, status: str, winner: ImageRecord | None, best: ImageRecord | None, reason: str) -> None:
        if best is not None:
            self.store.update_image(best.id, status="best_available")
        self._save(
            status=status,
            selected=winner.id if winner else None,
            best_available=best.id if best else None,
            reason=reason,
            ended_at=now(),
        )
        self.log.write("picked", output=self.out.id, image=winner.id if winner else None, message=reason)

    # --------------------------------------------------------------------------------------- helpers

    def _retrying(self, what: str, call: Callable[[], T]) -> T:
        for attempt in range(self.selection.technical_retries + 1):
            self._check()
            try:
                return call()
            except ModelFailure as exc:
                if not exc.transient or attempt == self.selection.technical_retries:
                    raise
                self._save(retries=self.record.retries + 1)
                self.log.write("retry", output=self.out.id, what=what, attempt=attempt + 1, message=str(exc))
        raise AssertionError("unreachable")  # pragma: no cover

    def _check(self) -> None:
        action = control(self.store, self.run.id)
        if action in ("pause", "cancel"):
            self.log.write("stopped", output=self.out.id, message=action)
            raise StopRequested(action)

    def _local(self, model_id: str) -> bool | None:
        try:
            return self.models.info(model_id).local
        except Exception:
            return None

    def _all_candidates(self) -> list[str]:
        mine = [i for i in self.store.images() if i.run_id == self.run.id and i.output_id == self.out.id]
        return [i.id for i in sorted(mine, key=lambda i: (i.round or 0, i.candidate or 0))]

    def _save(self, **fields: Any) -> None:
        self.record = self.record.model_copy(update=fields)
        save_output(self.store, self.run.id, self.record)


def _round_findings(images: list[ImageRecord]) -> list[str]:
    judged = [i for i in images if i.evaluation is not None]
    if not judged:
        return []
    best = max(judged, key=lambda i: i.evaluation.overall if i.evaluation else 0.0)
    return findings(best.evaluation)
