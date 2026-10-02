# Generation: requests, plans, rounds, judging and picks

A **request** says what to make; its **plan** expands it into **outputs** (one per view, expression,
scene shot or frame) with the exact models, references and counts, before anything runs (design §6-§8).

```python
import tempfile
from pathlib import Path

import hone_frame as hf
from hone_frame.testing import FakeModels

fake = FakeModels()
ws = hf.Workspace(Path(tempfile.mkdtemp()) / "studio", models=fake)
project = ws.create_project("Morning at home")
woman = project.add_subject("character", "Woman", description="black hair in a loose bun")

request = hf.SubjectReferences(
    subject_id=woman.id,
    presentation="turnaround",
    selection=hf.Selection(rounds=3, candidates=1, auto_judge=True, auto_pick=True),
)
plan = project.plan(request)
for out in plan.outputs:
    print(out.id, out.label, out.model, "waits for", [d.output for d in out.depends_on])
print(plan.counts)  # outputs=5 images=15 judge_calls=15
```

The hero comes first; the views wait for an accepted hero and use it as their identity reference.

## Profiles

A profile names a hone-models model for each role: `planner` (writes the prompt), `generator` (no
references), `editor` (with references), `judge` (a vision model), `upscaler`. Draft, Standard and Final
ship as local models; a project can override any role, and so can a request.

```python
print(plan.profile.generator, plan.profile.editor, plan.profile.judge)
project.update(defaults={"profile": "draft", "profiles": {"draft": {"judge": "qwen3.8-27b"}}})
assert project.plan(request).profile.judge == "qwen3.8-27b"
project.update(defaults={"profile": "draft"})
```

## Selection: rounds, strategy, stopping

- **Rounds per output** (default 3) and **candidates per round** (default 1): 12 outputs × 3 × 1 = 36
  planned images.
- **Strategy:** `batch` (generate the round, judge it) or `sequential` (each round's prompt carries the
  judge's findings from the round before).
- **Stopping rule:** `all_rounds`, or `stop_on_pass`.
- **Technical retries** (default 2) for model or service failures; they never add creative rounds.

## Judging and picking

Each candidate gets one vision-model call with the checks that apply to it: identity only when there is
an identity reference, anatomy only when a character is visible, and so on. Every check returns `pass`,
`fail`, `uncertain` or `not_assessable` with a score and a finding. Required checks are gates, and the
judge's `overall` only ranks the candidates that pass all of them. The pick is made by hone-select. The
best acceptable candidate across all rounds wins, so a later one never replaces a better earlier one.
When nothing passes, the output is **Needs review** and its best candidate is kept apart as
`best_available`, not accepted.

```python
from hone_frame.testing import judge_answer


def strict(index, prompt, images):
    return judge_answer(prompt, fail=("anatomy",) if index % 2 == 0 else ())


ws2 = hf.Workspace(Path(tempfile.mkdtemp()) / "studio", models=FakeModels(judge=strict))
p2 = ws2.create_project("P")
hero = p2.add_subject("character", "Woman", description="black hair")
run = p2.submit(hf.SubjectReferences(subject_id=hero.id, presentation="neutral-full-body"))
hf.Runner(ws2).run_next()
out = p2.run_view(run.id).outputs[0]
print(out.status, out.reason)
assert out.selected == out.candidates[1]  # the only one without the anatomy failure
```

## How prompts are written

Each prompt is written for the model that draws it (its **dialect**), the task (**mode**) and the style
(design §8.8):

- **z-image-turbo, a new picture:** long and structured, shot first, every piece of clothing, a plain
  background for references, style words at the start (and, for 2D styles, at the end too).
- **FLUX.2 klein, another view of the same character:** a short edit instruction: "Show the same person
  as in image 1, from directly behind… Keep exactly the same as in image 1: … Change only what is asked."
- **Qwen-Image-Edit:** the same, opening with its camera phrase (`<sks> back view eye-level shot wide
  shot`) for the Multiple-Angles LoRA.

```python
from hone_frame.prompts import compose
from hone_frame.requests import PlannedRef

plan = project.plan(hf.SubjectReferences(subject_id=woman.id, presentation="turnaround", profile="final"))
back = next(o for o in plan.outputs if o.label == "Back")
ref = [(PlannedRef(image_id="img_0001", subject_id=woman.id, role="identity"), "Woman")]
prompt = compose(back, ref, [], project.workspace.dialects.for_model(back.model))
print(prompt.dialect, prompt.mode)
print(prompt.text)
assert prompt.text.startswith("<sks> back view")
```

To change how prompts are written for a model, add `prompting.toml` to the workspace folder with a
`[dialects.<name>]` table (the same shape as hone-frame's `data/prompting.toml`); a dialect with the same
name replaces the shipped one.
