"""Producing one output (design §8.2): rounds of candidates, judging, retries, and the pick."""

from __future__ import annotations

import time
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any, TypeVar

from hone_frame._files import now
from hone_frame.candidates import (
    CandidateRefused,
    checked,
    image_fields,
    model_inputs,
    round_findings,
    seed_for,
)
from hone_frame.dialects import Dialect
from hone_frame.errors import NotFound
from hone_frame.events import EventLog
from hone_frame.judging import checks_for, evaluate, findings
from hone_frame.pick import decide
from hone_frame.ports import Generated, ModelFailure, ModelInfo
from hone_frame.produce_refs import resolve_refs
from hone_frame.prompts import Composed, PlannerAnswer, compose, planner_problem, planner_prompt
from hone_frame.records import ImageRecord
from hone_frame.requests import PlannedOutput, PlannedRef
from hone_frame.runs import OutputRecord, RunRecord, StopRequested, control, load_output, run_dir, save_output

if TYPE_CHECKING:
    from hone_frame.store import ProjectStore

T = TypeVar("T")


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
        self.composed: Composed | None = None
        self._infos: dict[str, ModelInfo | None] = {}

    def run_output(self) -> OutputRecord:
        if self.record.status in ("done", "replaced"):
            return self.record  # accepted earlier, or asked again in another run (D-019): never touched again
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
                found = round_findings(round_images)

    def _prompt(self, found: list[str]) -> str:
        """The prompt in the model's dialect for this mode; the planner only within its rules (§8.8)."""
        self._check()
        self.log.write("stage", stage="planning", output=self.out.id)
        dialect = self.store.workspace.dialects.for_model(self.out.model)
        draft = compose(self.out, [(ref, name) for ref, _, name in self.refs], found, dialect)
        self.composed = draft
        prompt = draft.text
        if draft.over_budget:
            self.log.write(
                "prompt_long",
                output=self.out.id,
                message=f"{len(prompt.split())} words, over the {draft.max_words}-word guide for "
                f"{draft.dialect}; sent whole rather than without what was asked",
            )
        if self.profile.planner and draft.mode not in ("promotion", "fixed"):
            prompt = self._planned(draft, dialect, found) or prompt
        self._save(prompt=prompt)
        self.log.write("planned", output=self.out.id, message=prompt, dialect=draft.dialect, mode=draft.mode)
        return prompt

    def _planned(self, draft: Composed, dialect: Dialect, found: list[str]) -> str | None:
        try:
            answer = self._retrying(
                "planner",
                lambda: self.models.ask(
                    self.profile.planner or "",
                    planner_prompt(self.out, draft, dialect, found),
                    images=[],
                    schema=PlannerAnswer,
                    think=self.profile.planner_think,
                ),
            )
        except ModelFailure as exc:
            self.log.write(
                "planner_failed", output=self.out.id, message=f"{exc}; the composed prompt is used"
            )
            return None
        text = answer.prompt.strip()
        if problem := planner_problem(text, draft):
            self.log.write(
                "planner_rejected", output=self.out.id, message=f"{problem}; the composed prompt is used"
            )
            return None
        self.negative = answer.negative
        return text

    def _info(self, model_id: str) -> ModelInfo | None:
        """What the port says about a model; when it cannot say, an event records what was left out."""
        if model_id not in self._infos:
            try:
                self._infos[model_id] = self.models.info(model_id)
            except (NotFound, ModelFailure) as exc:
                self.log.write(
                    "model_info_unavailable",
                    output=self.out.id,
                    model=model_id,
                    message=f"{exc}; its prompt guide and local flag are left out",
                )
                self._infos[model_id] = None
        return self._infos[model_id]

    def _candidate(self, r: int, c: int, prompt: str) -> ImageRecord | None:
        slot: dict[str, Any] = {"output": self.out.id, "round": r, "candidate": c, "model": self.out.model}
        self.log.write("stage", stage="generating", output=self.out.id)
        self.log.write("generating", **slot, label=self.out.label, rounds=self.selection.rounds)
        seed = seed_for(self.seed, r, c)
        out = self.folder / "work" / f"{self.out.id}-r{r}c{c}.png"
        out.parent.mkdir(parents=True, exist_ok=True)
        started = time.monotonic()
        try:
            result = self._retrying("generate", lambda: self._generate(prompt, out, seed))
        except CandidateRefused as exc:
            self.log.write("candidate_failed", **slot, message=str(exc))
            return None
        path = result.path or out  # _generate guarantees a file
        refs = [ref for ref, _, _ in self.refs]
        how = (self.composed.dialect, self.composed.mode) if self.composed else None
        fields = image_fields(
            self.run.id,
            self.out,
            self.profile,
            refs,
            slot=(r, c),
            prompt=prompt,
            dialect=how,
            negative=self.negative,
            result=result,
            variation=self.run.plan.variation,
        )
        image = self.store.add_image(path, **fields)
        path.unlink(missing_ok=True)
        info = self._info(self.out.model)
        self.log.write(
            "generated",
            **slot,
            size=self.out.size,
            image=image.id,
            seed=seed,
            job_id=result.job_id,
            local=info.local if info else None,
            cost_usd=result.cost_usd,
            cost_estimated=result.cost_estimated or None,
            duration_s=round(result.elapsed_s or time.monotonic() - started, 3),
        )
        self._save(candidates=[*self._all_candidates()])
        return image

    def _generate(self, prompt: str, out: Path, seed: int) -> Generated:
        in_prompt = bool(self.composed and self.composed.camera_phrase)
        refs_paths = [p for _, p, _ in self.refs]
        inputs, refs = model_inputs(
            self.out, self.profile, self.negative, refs_paths, camera_in_prompt=in_prompt
        )
        result = self.models.generate(
            self.out.model, prompt, out=out, seed=seed, references=refs, inputs=inputs
        )
        return checked(result, self.out.model)

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
        status, winner, best, reason = decide(
            self.store, images, self.selection.auto_pick, self.folder / "select.jsonl"
        )
        self._save(status=status, selected=winner, best_available=best, reason=reason, ended_at=now())
        self.log.write("picked", output=self.out.id, image=winner, message=reason)

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

    def _all_candidates(self) -> list[str]:
        mine = [i for i in self.store.images() if i.run_id == self.run.id and i.output_id == self.out.id]
        return [i.id for i in sorted(mine, key=lambda i: (i.round or 0, i.candidate or 0))]

    def _save(self, **fields: Any) -> None:
        self.record = self.record.model_copy(update=fields)
        save_output(self.store, self.run.id, self.record)
