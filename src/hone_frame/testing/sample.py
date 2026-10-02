"""`sample_workspace`: the brief's "Morning at home" project, with fake models (tests, examples, demos)."""

from __future__ import annotations

from pathlib import Path

from PIL import Image

from hone_frame.records import State
from hone_frame.store import ProjectStore
from hone_frame.testing.fake_models import FakeModels
from hone_frame.workspace import Workspace

SUBJECTS = [
    ("character", "Woman", "late twenties, black hair in a loose bun, cream knit sweater, warm brown eyes"),
    (
        "environment",
        "Kitchen",
        "small bright kitchen, white subway tiles, wooden open shelves, a window over the sink",
    ),
    ("asset", "Coffee cup", "speckled cream ceramic mug with a round handle"),
    ("asset", "Toothbrush", "bamboo toothbrush with white bristles"),
]


def sample_workspace(
    path: str | Path, *, models: FakeModels | None = None, with_images: bool = True
) -> ProjectStore:
    """A workspace at `path` holding "Morning at home": a woman, her kitchen, a cup and a toothbrush.

    With `with_images`, each subject gets one imported reference image (a plain colour), so scenes can
    be planned at once."""
    ws = Workspace(path, models=models or FakeModels())
    store = ws.create_project(
        "Morning at home", brief="A quiet morning routine at home.", direction="soft, natural, lived-in"
    )
    colours = ["#C9A27E", "#E8E4DA", "#D9CBB0", "#B8A07A"]
    for (kind, name, description), colour in zip(SUBJECTS, colours, strict=True):
        subject = store.add_subject(kind, name, description=description)  # pyright: ignore[reportArgumentType]
        if kind == "character":
            store.edit_subject(
                subject.id,
                states=[
                    State(name="wet", kind="condition", description="soaked by rain"),
                    State(name="pyjamas", kind="outfit", description="striped pyjamas"),
                ],
            )
        if kind == "asset" and name == "Coffee cup":
            store.edit_subject(
                subject.id, states=[State(name="full", kind="condition", description="filled with coffee")]
            )
        if with_images:
            file = Path(path) / f".sample-{subject.id}.png"
            Image.new("RGB", (96, 128), colour).save(file)
            image = store.import_image(file, subject_id=subject.id, label="Hero")
            file.unlink()
            store.edit_subject(subject.id, reference_images=[image.id])
    return store
