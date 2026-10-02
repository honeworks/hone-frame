# Runs: statuses, control, progress and estimates

Every submitted request is a run: `runs/<id>/run.json` (the plan and effective settings),
`events.jsonl` (what happened), `outputs/<id>.json` (each output's candidates, pick and reason), and a
hone-flow run folder that does the execution (design §8, §9).

| Status | Meaning |
|---|---|
| Queued | submitted, waiting for the runner |
| Running / Pausing | working; pausing stops after the model call in flight |
| Paused | stopped by a pause, or left by a stopped process ("interrupted") |
| Canceled | stopped for good; rerun outputs instead |
| Failed | an output failed technically after its retries |
| Needs review | an output did not pass, or waits for an accepted reference |
| Done | every output accepted, by the judge or by a person |

```python
import tempfile
from pathlib import Path

import hone_frame as hf
from hone_frame.testing import FakeModels

ws = hf.Workspace(Path(tempfile.mkdtemp()) / "studio", models=FakeModels())
project = ws.create_project("P")
woman = project.add_subject("character", "Woman", description="black hair")
run = project.submit(hf.SubjectReferences(subject_id=woman.id, presentation="neutral-full-body"))
project.pause(run.id)  # a queued run pauses at once
assert project.run_view(run.id).status == "paused"
project.resume(run.id)
hf.Runner(ws).run_next()
view = project.run_view(run.id)
print(view.status, view.progress, view.usage)
```

- **Pause / cancel** take effect before the next model call. **Resume** and **retry** continue the
  same run, and every stored candidate is skipped, so nothing is generated twice.
- **Generate again** (`project.rerun(run, output, note=..., profile=..., selection=...)`): when every
  candidate of one output is wrong, ask for it again in a new run. The note is added to its prompt, and
  another profile can be chosen. The old output becomes "Replaced" and keeps its images and findings.
- **Manual pick:** `project.pick(run, output, image, note=...)` accepts an output by hand. The image
  keeps its evaluation, and outputs waiting for it continue on `retry`.
- **Restart:** `hf.Runner(ws).recover()` queues runs a dead process left running. The dashboard does
  this when it starts.
- **Progress** counts image and judge calls. Early stopping shrinks the plan, and the current image is
  indeterminate.
- **Estimates** are a range (25th to 75th percentile of observed durations of the same model and size,
  times the remaining calls), or `None` ("Estimating") with fewer than 3 observations.
- **Usage:** render seconds, GPU seconds of local models, and a cost only when a provider or the
  registry gives one. Local work never gets a dollar price.
