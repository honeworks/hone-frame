"""Sheets and exports: compose, revise and export without another model call.

What: four imported images become a turnaround sheet; changing the labels makes version 2 while
version 1 stays; the same recipe always gives the same bytes; the scene's reference pack holds only
what the scene selected.

How: `import_image` -> `save_sheet(hf.SheetRecipe(...))` -> `compose_sheet` -> `save_sheet(...,
sheet_id=...)` (a new version) -> `export_sheet(sources=True)`, `export_pack(scene_id)`.

Why: a sheet is a layout of chosen images, not a generated collage: it can be re-laid out, relabelled
and exported at once, and it never invents detail.
"""

import tempfile
import zipfile
from pathlib import Path

from PIL import Image

import hone_frame as hf
from hone_frame.testing import FakeModels, sample_workspace

folder = Path(tempfile.mkdtemp())
project = sample_workspace(folder / "studio", models=FakeModels())
ids = []
for n, colour in enumerate(["#C9A27E", "#B08F70", "#977C62", "#7E6954"]):
    Image.new("RGB", (600, 1000), colour).save(folder / f"view{n}.png")
    ids.append(project.import_image(folder / f"view{n}.png", subject_id="char_001", label=f"view {n}").id)

sheet = project.save_sheet(
    hf.SheetRecipe(
        name="Woman turnaround",
        layout="four-view-turnaround",
        images=ids,
        palette=["#1F4FE0", "#C9A27E"],
        notes="Loose bun; cream sweater.",
    )
)
first = project.compose_sheet(sheet.id).read_bytes()
assert project.compose_sheet(sheet.id).read_bytes() == first  # deterministic
v2 = project.save_sheet(
    sheet.recipe.model_copy(update={"labels": ["Front", "3/4", "Side", "Back"]}), sheet_id=sheet.id
)
print(f"{sheet.id}: version {v2.version} composed to", project.compose_sheet(sheet.id).name)

archive = project.export_sheet(sheet.id, folder / "sheet.zip", sources=True)
print("sheet export:", zipfile.ZipFile(archive).namelist())

scene = project.save_scene(
    hf.Scene(
        name="Coffee",
        refs=[hf.SceneRef(subject_id="char_001"), hf.SceneRef(subject_id="obj_001", role="object")],
    )
)
pack = project.export_pack(scene.id, folder / "pack.zip")
print("reference pack:", zipfile.ZipFile(pack).namelist())
