# Scenes and the advanced requests

A **scene** names its subjects explicitly; each reference has a **role**: `identity`, `object`,
`environment`, `outfit`, `pose`, `expression`, `composition`, `lighting` or `style` (design §10).
Nothing that is not selected is sent, and the plan shows the exact references in order.

```python
import tempfile
from pathlib import Path

import hone_frame as hf
from hone_frame.testing import FakeModels, sample_workspace

project = sample_workspace(Path(tempfile.mkdtemp()) / "studio", models=FakeModels())
scene = project.save_scene(
    hf.Scene(
        name="Coffee scene",
        description="She holds the cup by the window.",
        refs=[
            hf.SceneRef(subject_id="char_001", role="identity"),
            hf.SceneRef(subject_id="env_001", role="environment"),
            hf.SceneRef(subject_id="obj_001", role="object"),
        ],
        camera="medium",
        expression="focused",
        lighting="soft-daylight",
    )
)
plan = project.plan(hf.SceneShot(scene_id=scene.id))
print([(r.subject_id, r.role) for r in plan.outputs[0].references])
print(plan.warnings)  # e.g. references left out when the model takes fewer
```

- **Precedence:** identity, object, environment, outfit, pose, expression, composition, lighting, style.
  When the model takes fewer references (`max_references`), the lowest ones are dropped, with a warning,
  and described in words instead. A model that takes none gets everything as words ("text only: weaker
  control").
- References larger than `settings.max_reference_px` (1536 px) are reduced in the run's work folder. The
  originals are never changed.

## Coverage, interactions, state pairs, sequences, grids

```python
one = hf.Selection(rounds=1)
requests = [
    hf.Coverage(scene_id=scene.id, cameras=["wide", "close-up", "reverse"], selection=one),
    hf.Interaction(character_id="char_001", asset_id="obj_001", action="hold-cup", selection=one),
    hf.StatePair(subject_id="obj_001", state="empty-full", selection=one),
]
for request in requests:
    print(request.kind, [o.label for o in project.plan(request).outputs])

sequence = project.save_sequence(
    hf.Sequence(
        name="Sip", scene_id=scene.id, frames=[hf.Frame(id="reach"), hf.Frame(id="grip"), hf.Frame(id="lift")]
    )
)
print([o.label for o in project.plan(hf.SequenceFrames(sequence_id=sequence.id)).outputs])
grid = project.plan(
    hf.Variations(
        scene_id=scene.id, axes={"expression": ["happy", "tired"], "lighting": ["dawn", "moonlight"]}
    )
)
print(grid.counts.outputs, "cells")
```

- **Coverage** shares the scene's references and seed; only the camera changes.
- **State pairs** share the seed; the "after" output also takes the accepted "before" image as its
  composition reference.
- **Sequences** keep the stable identity references on every frame and add the previous frame for
  continuity, so drift does not accumulate.

## Promotion: draft to final

```python
project.submit(hf.SceneShot(scene_id=scene.id, selection=one))
hf.Runner(project.workspace).run_next()
draft = project.runs()[0].outputs[0].selected
refine = project.plan(hf.Promote(image_id=draft or "", operation="refine"))
print(refine.profile.id, refine.outputs[0].model, [r.role for r in refine.outputs[0].references])
```

`refine` gives the Final editor the draft first, then the draft's own references. `regenerate` runs the
saved definition with the Final profile. `upscale` needs an upscaler model; without one the plan says
so. The new image records its `parent`, and a failed promotion never touches the draft.
