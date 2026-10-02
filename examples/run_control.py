"""Run control: pause, resume, unresolved outputs and a manual pick, with nothing regenerated.

What: a turnaround run is paused during its second output (the call in flight finishes first), resumed
without regenerating a stored image, and a scripted judge never passes the side view, so that output
stays "Needs review" with its best candidate kept apart until a person picks one.

How: a `FakeModels` judge that pauses the run and fails one check -> `submit` -> `Runner.run_next()` ->
`run_view` (status "paused") -> `resume` -> `run_next` -> `pick(run, output, image, note=...)`.

Why: long unattended runs must be stoppable without losing work, and a failed quality check must never
look like an accepted result.
"""

import tempfile
from pathlib import Path
from typing import Any

import hone_frame as hf
from hone_frame.testing import FakeModels, judge_answer

state: dict[str, Any] = {}


def judge(index: int, prompt: str, images: list[Path]) -> dict[str, Any]:
    if index == 4:
        state["project"].pause(state["run"])  # someone presses "Pause after current"
    side = "to show: Side " in prompt
    return judge_answer(prompt, fail=("view",) if side else ())


fake = FakeModels(judge=judge)
ws = hf.Workspace(Path(tempfile.mkdtemp()) / "studio", models=fake)
project = ws.create_project("Morning at home")
woman = project.add_subject("character", "Woman", description="black hair in a loose bun")
run = project.submit(hf.SubjectReferences(subject_id=woman.id, presentation="turnaround"))
state.update(project=project, run=run.id)

hf.Runner(ws).run_next()
print("after pause:", project.run_view(run.id).status, "-", fake.image_calls, "images so far")
project.resume(run.id)
hf.Runner(ws).run_next()
view = project.run_view(run.id)
print("after resume:", view.status, "- accepted", view.accepted, "unresolved", view.unresolved)
assert fake.image_calls == 15  # nothing was generated twice

side = next(o for o in view.outputs if o.label == "Side")
record = project.pick(run.id, side.id, side.best_available or "", note="the angle is fine for our use")
print("manual pick:", record.selected, record.reason)
assert project.run_view(run.id).status == "done"
