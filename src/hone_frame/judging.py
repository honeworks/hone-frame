"""Judging (design §8.3): the checks that apply, the judge prompt, and the verdict rules."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field, create_model

from hone_frame.ports import Models
from hone_frame.presets import PresetCatalog
from hone_frame.records import CheckResult, Evaluation
from hone_frame.requests import PlannedOutput


class CheckAnswer(BaseModel):
    verdict: Literal["pass", "fail", "uncertain", "not_assessable"]
    score: float | None = Field(default=None, ge=0.0, le=1.0)
    finding: str = ""


class JudgeAnswer(BaseModel):
    """What the judge returns; `description` first, so it looks before it decides. The schema sent to
    the judge is `answer_schema(checks)`: `checks` is an object with one required key per check, so a
    judge cannot mislabel or drop a check (decisions D-020)."""

    description: str
    checks: BaseModel  # `answer_schema` makes it a model with one CheckAnswer field per check name
    overall: float = Field(ge=0.0, le=1.0)
    summary: str = ""


def answer_schema(checks: list[dict[str, Any]]) -> type[JudgeAnswer]:
    """`JudgeAnswer` whose `checks` has exactly these check names as required keys. Field names are
    `c0`, `c1`... with the check name as the alias, so any name (from a user's pack too) is a valid key."""
    fields: dict[str, Any] = {f"c{i}": (CheckAnswer, Field(alias=c["name"])) for i, c in enumerate(checks)}
    named: Any = create_model("Checks", **fields)
    return create_model("JudgeAnswer", __base__=JudgeAnswer, checks=(named, ...))


def checks_for(catalog: PresetCatalog, out: PlannedOutput) -> list[dict[str, Any]]:
    """The judging profile's checks whose condition holds for this output (design §8.3)."""
    checks: list[dict[str, Any]] = list(catalog.get("judging", out.judging).values.get("checks", []))
    flags = set(out.conditions)
    applicable = [
        c for c in checks if (not c.get("when") or c["when"] in flags) and c.get("unless") not in flags
    ]
    if "preserve" in flags:
        applicable.append(
            {
                "name": "preserved_composition",
                "required": True,
                "question": "Does it keep the composition, subjects and pose of the image it was made from "
                "(image 2)?",
            }
        )
    return applicable


def judge_prompt(out: PlannedOutput, checks: list[dict[str, Any]], prompt: str, n_refs: int) -> str:
    refs = (
        f"Images 2 to {n_refs + 1} are the references it had to follow (in that order)."
        if n_refs
        else "There are no reference images."
    )
    lines = [
        "You are a strict visual quality judge. Image 1 is the candidate.",
        refs,
        f"It was asked to show: {out.label} ({out.kind}).",
        f"The prompt it was made from: {prompt}",
        "First describe what you actually see in image 1. Then answer every check below with a verdict "
        "(pass, fail, uncertain, not_assessable), a score from 0 to 1, and one concrete finding sentence. "
        "Use uncertain when you cannot tell; never guess a pass.",
        *(f"- {c['name']}: {c['question']}" for c in checks),
        "Then give overall (0 to 1): how good it is among acceptable candidates, and a one-line summary.",
    ]
    return "\n".join(lines)


def evaluate(
    models: Models,
    *,
    judge: str,
    think: bool,
    out: PlannedOutput,
    checks: list[dict[str, Any]],
    candidate: Path,
    references: list[Path],
    prompt: str,
) -> Evaluation:
    """One judge call (design §8.3); raises `ModelFailure` when the judge gives no usable answer."""
    images = [candidate, *references[:3]]
    answer = models.ask(
        judge,
        judge_prompt(out, checks, prompt, len(images) - 1),
        images=images,
        schema=answer_schema(checks),
        think=think,
    )
    return verdicts(answer, checks, judge)


def verdicts(answer: JudgeAnswer, checks: list[dict[str, Any]], judge: str) -> Evaluation:
    """Apply `min_score`, mark missing checks uncertain, and decide pass / uncertain (design §8.3)."""
    given = {
        name: CheckAnswer.model_validate(value)
        for name, value in answer.checks.model_dump(by_alias=True).items()
    }
    results: list[CheckResult] = []
    for check in checks:
        found = given.get(check["name"])
        if found is None:
            result = CheckResult(
                name=check["name"], verdict="uncertain", finding="the judge did not answer this check"
            )
        else:
            result = CheckResult(
                name=check["name"], verdict=found.verdict, score=found.score, finding=found.finding
            )
            floor = check.get("min_score")
            if result.verdict == "pass" and floor is not None and (result.score or 0.0) < floor:
                result = result.model_copy(
                    update={"verdict": "fail", "finding": f"score below the threshold {floor}"}
                )
        results.append(result.model_copy(update={"required": bool(check.get("required", True))}))
    required = [r for r in results if r.required]
    passed = all(r.verdict == "pass" for r in required)
    uncertain = not passed and not any(r.verdict == "fail" for r in required)
    return Evaluation(
        description=answer.description,
        checks=results,
        overall=answer.overall,
        summary=answer.summary,
        judge=judge,
        passed=passed,
        uncertain=uncertain,
    )


def findings(evaluation: Evaluation | None) -> list[str]:
    """The failed or uncertain required checks, as fixes for the next round (sequential strategy)."""
    if evaluation is None:
        return []
    return [f"{c.name}: {c.finding}" for c in evaluation.checks if c.required and c.verdict != "pass"]
