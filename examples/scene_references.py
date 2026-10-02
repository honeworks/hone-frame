"""Scene references: a scene sends exactly what it selected, each with a role, in a visible order.

What: the sample "Morning at home" project has a woman, a kitchen, a cup and a toothbrush. The coffee
scene selects the woman (identity), the kitchen (environment) and the cup (object); the plan lists
those references in precedence order, the toothbrush is not sent, and the model received exactly them.

How: `sample_workspace` -> `save_scene(hf.Scene(refs=[hf.SceneRef(...)]))` -> `plan(hf.SceneShot(...))`
-> `submit` -> `Runner.run_next()`; `FakeModels.generated` shows what the model got.

Why: attaching everything a project has confuses models and hides what a picture was made from. Roles
and precedence make every input deliberate and every result traceable.
"""

import tempfile
from pathlib import Path

import hone_frame as hf
from hone_frame.testing import FakeModels, sample_workspace

fake = FakeModels()
project = sample_workspace(Path(tempfile.mkdtemp()) / "studio", models=fake)
by_name = {s.name: s for s in project.subjects()}
scene = project.save_scene(
    hf.Scene(
        name="Coffee scene",
        description="She holds the cup by the window and smiles.",
        refs=[
            hf.SceneRef(subject_id=by_name["Coffee cup"].id, role="object"),
            hf.SceneRef(subject_id=by_name["Woman"].id, role="identity"),
            hf.SceneRef(subject_id=by_name["Kitchen"].id, role="environment"),
        ],
        camera="medium",
        expression="focused",
    )
)

plan = project.plan(hf.SceneShot(scene_id=scene.id, selection=hf.Selection(rounds=1)))
for n, ref in enumerate(plan.outputs[0].references, start=1):
    print(f"image {n}: {project.subject(ref.subject_id or '').name} as {ref.role}")

project.submit(hf.SceneShot(scene_id=scene.id, selection=hf.Selection(rounds=1)))
hf.Runner(project.workspace).run_next()
sent = [p.name for p in fake.generated[0].references]
print("sent to the model:", sent)
assert len(sent) == 3 and "Toothbrush" not in fake.generated[0].prompt
