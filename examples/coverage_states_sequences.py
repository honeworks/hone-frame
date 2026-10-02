"""Coverage, interactions, state pairs, sequences and variation grids from one project's subjects.

What: the same sample subjects give camera coverage of a scene, a character holding the cup, an
empty/full pair that shares its seed, a four-frame sequence where every frame keeps the identity
reference, and a 24-cell variation grid planned before anything runs.

How: `hf.Coverage`, `hf.Interaction`, `hf.StatePair`, `hf.SequenceFrames`, `hf.Variations` requests ->
`plan` / `submit` -> `Runner.run_next()`.

Why: every advanced request reuses the project's subjects and gives one output per view, frame or cell,
each with its own candidates and verdicts.
"""

import tempfile
from pathlib import Path

import hone_frame as hf
from hone_frame.testing import FakeModels, sample_workspace

project = sample_workspace(Path(tempfile.mkdtemp()) / "studio", models=FakeModels())
one = hf.Selection(rounds=1)
scene = project.save_scene(
    hf.Scene(
        name="Coffee",
        description="morning coffee",
        refs=[
            hf.SceneRef(subject_id="char_001"),
            hf.SceneRef(subject_id="env_001", role="environment"),
            hf.SceneRef(subject_id="obj_001", role="object"),
        ],
    )
)
sequence = project.save_sequence(
    hf.Sequence(
        name="Sip",
        scene_id=scene.id,
        frames=[
            hf.Frame(id="reach", description="reaches for the cup"),
            hf.Frame(id="touch", description="touches the handle"),
            hf.Frame(id="grip", description="grips the cup"),
            hf.Frame(id="lift", description="lifts the cup"),
        ],
    )
)

requests = [
    hf.Coverage(scene_id=scene.id, cameras=["wide", "close-up", "reverse"], selection=one),
    hf.Interaction(character_id="char_001", asset_id="obj_001", action="hold-cup", selection=one),
    hf.StatePair(subject_id="obj_001", state="empty-full", selection=one),
    hf.SequenceFrames(sequence_id=sequence.id, selection=one),
]
for request in requests:
    run = project.submit(request)
    hf.Runner(project.workspace).run_next()
    view = project.run_view(run.id)
    print(f"{request.kind:12} {view.status:5} {[o.label for o in view.outputs]}")

grid = project.plan(
    hf.Variations(
        scene_id=scene.id,
        axes={
            "outfit": ["pyjamas", "sweater", "coat"],
            "expression": ["happy", "sad", "tired", "focused"],
            "lighting": ["soft-daylight", "moonlight"],
        },
    )
)
print("variation grid:", grid.counts.outputs, "outputs,", grid.counts.images, "images planned")
