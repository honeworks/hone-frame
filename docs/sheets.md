# Sheets and exports

A sheet is a saved **recipe** (layout, images, labels, columns, page, fit, palette, notes) over exact
image ids, composed with Pillow, with no model call (design §11). The same recipe and images give the
same bytes, and a larger page is a larger canvas: images are never enlarged.

```python
import tempfile
import zipfile
from pathlib import Path

from PIL import Image

import hone_frame as hf
from hone_frame.testing import FakeModels, sample_workspace

folder = Path(tempfile.mkdtemp())
project = sample_workspace(folder / "studio", models=FakeModels())
ids = []
for n in range(4):
    Image.new("RGB", (600, 1000), (60 * n, 120, 160)).save(folder / f"v{n}.png")
    ids.append(project.import_image(folder / f"v{n}.png", subject_id="char_001").id)

sheet = project.save_sheet(
    hf.SheetRecipe(
        name="Woman turnaround",
        layout="four-view-turnaround",
        images=ids,
        labels=["Front", "3/4", "Side", "Back"],
        palette=["#1F4FE0"],
    )
)
png = project.compose_sheet(sheet.id)
print(png.name, Image.open(png).size)
```

Layouts: `four-view-turnaround`, `expression-grid`, `pose-grid`, `object-detail-board`,
`environment-board`, `before-after`, `sequence-strip`, `contact-grid`. Saving a changed recipe with
`sheet_id=` makes a new version; earlier renders stay.

## Exports

| Call | The zip holds |
|---|---|
| `export_sheet(id, out, sources=True)` | `sheet.png`, `sheet.json` (recipe and image records), the original images |
| `export_pack(scene_id, out)` | only the scene's references, `images/<nn>-<subject>-<role>.<ext>`, and `pack.json` |
| `export_sequence(id, out)` | `frames/<nn>.<ext>` in order and `sequence.json` |
| `export_project(out)` | the project's records and images, without work files |

```python
scene = project.save_scene(
    hf.Scene(
        name="Coffee",
        refs=[hf.SceneRef(subject_id="char_001"), hf.SceneRef(subject_id="obj_001", role="object")],
    )
)
pack = project.export_pack(scene.id, folder / "pack.zip")
print(zipfile.ZipFile(pack).namelist())
```

API keys live in the environment and never reach a record, so they never reach an export.
