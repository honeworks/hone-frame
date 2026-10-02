"""Quickstart: a character's reference images, judged and picked unattended, then a sheet.

What: one project with one character; a turnaround request (a hero plus four views, three rounds each)
runs to the end with every candidate judged and the best passing one picked; the views become a
four-view sheet composed in Python.

How: `hf.Workspace` -> `create_project` -> `add_subject` -> `plan` (the counts before anything runs) ->
`submit` -> `hf.Runner(ws).run_next()` -> `run_view` -> `save_sheet` + `compose_sheet`. `FakeModels`
stands in for hone-models, so it runs anywhere; leave `models=` out to use the real models.

Why: the work you would otherwise babysit (generate, look, retry, pick, lay out) runs on its own, keeps
every candidate and says why it picked each one.
"""

import tempfile
from pathlib import Path

import hone_frame as hf
from hone_frame.testing import FakeModels

ws = hf.Workspace(Path(tempfile.mkdtemp()) / "studio", models=FakeModels())
project = ws.create_project("Morning at home", direction="soft, natural, lived-in")
woman = project.add_subject("character", "Woman", description="late twenties, black hair in a loose bun")

request = hf.SubjectReferences(subject_id=woman.id, presentation="turnaround")
plan = project.plan(request)
print(plan.title, "-", plan.counts.outputs, "outputs,", plan.counts.images, "images planned")

run = project.submit(request)
hf.Runner(ws).run_next()
view = project.run_view(run.id)
for output in view.outputs:
    print(f"{output.label:6} {output.status:5} {output.reason}")
assert view.status == "done" and len(project.images()) == 15

views = view.outputs[1:]  # front, three-quarter, side, back
sheet = project.save_sheet(
    hf.SheetRecipe(
        name="Woman turnaround",
        layout="four-view-turnaround",
        images=[o.selected or "" for o in views],
        labels=[o.label for o in views],
    )
)
print("sheet:", project.compose_sheet(sheet.id).name)
