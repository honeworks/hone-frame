"""How a producer writes an output's prompt (design §8.8): composed in the model's dialect, rewritten by
the planner only within its rules, and, for a casting hero, one reading per candidate (change 0006)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from hone_frame.casting import readings
from hone_frame.dialects import Dialect
from hone_frame.ports import ModelFailure
from hone_frame.prompts import Composed, PlannerAnswer, compose, planner_problem, planner_prompt

if TYPE_CHECKING:
    from hone_frame.produce import Producer


def write_prompt(self: Producer, found: list[str]) -> str:
    """The prompt in the model's dialect for this mode; the planner only within its rules (§8.8)."""
    self.check()
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
        prompt = _planned(self, draft, dialect, found) or prompt
    self.save(prompt=prompt)
    self.log.write("planned", output=self.out.id, message=prompt, dialect=draft.dialect, mode=draft.mode)
    return prompt


def _planned(self: Producer, draft: Composed, dialect: Dialect, found: list[str]) -> str | None:
    try:
        answer = self.retrying(
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
        self.log.write("planner_failed", output=self.out.id, message=f"{exc}; the composed prompt is used")
        return None
    text = answer.prompt.strip()
    if problem := planner_problem(text, draft):
        self.log.write(
            "planner_rejected", output=self.out.id, message=f"{problem}; the composed prompt is used"
        )
        return None
    self.negative = answer.negative
    return text


def cast(self: Producer, prompt: str, c: int, count: int) -> str:
    """A casting hero's candidate `c` draws from its own reading of the description (change 0006)."""
    if not self.out.prompt_inputs.get("casting"):
        return prompt
    if not self.record.readings:
        found = readings(self.models, self.profile.planner, self.out, count)
        self.save(readings=found)
        self.log.write(
            "casting", output=self.out.id, message=f"{len(found)} readings" if found else "seeds only"
        )
    if not self.record.readings:
        return prompt
    reading = self.record.readings[(c - 1) % len(self.record.readings)].strip().rstrip(".")
    phrase = self.composed.camera_phrase if self.composed else ""
    if phrase and prompt.startswith(phrase):  # a dialect's camera phrase stays first (qwen-edit)
        return f"{phrase}. {reading}. {prompt[len(phrase) :].lstrip('. ')}"
    # first, where the model weighs the words most; the prompt may run longer than its budget by it
    return f"{reading}. {prompt}"
