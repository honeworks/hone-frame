# The workspace, projects and versions

Everything lives in one folder, the **workspace** (`HONE_FRAME_HOME`, else `./hone-frame`): projects as
JSON files, images as files, runs as hone-flow run folders. There is no database, so a project can be
copied, backed up or read without hone-frame (design §4).

```python
import tempfile
from pathlib import Path

import hone_frame as hf
from hone_frame.testing import FakeModels

ws = hf.Workspace(Path(tempfile.mkdtemp()) / "studio", models=FakeModels())
project = ws.create_project(
    "Morning at home", brief="A quiet morning routine.", style_pack="cinematic-realism"
)
woman = project.add_subject(
    "character",
    "Woman",
    description="late twenties, black hair in a loose bun",
    fields={"features": ["small mole under the left eye"]},
)
kitchen = project.add_subject(
    "environment",
    "Kitchen",
    description="small bright kitchen",
    fields={"anchors": ["window over the sink", "open wooden shelves"]},
)
cup = project.add_subject("asset", "Coffee cup", description="speckled cream mug with a round handle")
print([s.id for s in project.subjects()])  # char_001, env_001, obj_001
```

## Subjects and versions

Characters, environments and assets are **subjects**, each with a description, kind-specific fields,
**states** (an outfit, an expression, wet/dry, open/closed...) and its chosen reference images. Editing a
subject writes a new version; older versions stay readable, and everything made from them keeps pointing
at them.

```python
v2 = project.edit_subject(
    woman.id, states=[hf.State(name="pyjamas", kind="outfit", description="striped pyjamas")]
)
assert v2.version == 2 and project.subject(woman.id, version=1).states == []
```

## Images

Every image is kept on its own with a full record: its subjects (at their versions), the run and round it
came from, the model, prompt, seed and references, the judge's evaluation and its status (`candidate`,
`picked`, `manual_pick`, `best_available`, `rejected`, `uncertain`, `imported`). A selection points at an
image; nothing is overwritten.

```python
from PIL import Image

Image.new("RGB", (512, 768), "#C9A27E").save("woman.png")
image = project.import_image("woman.png", subject_id=woman.id, label="Hero")
project.edit_subject(woman.id, reference_images=[image.id])
print(image.id, image.width, image.height, image.status)
assert [r.id for r in project.images(kind="character")] == [image.id]
```

A scene or sheet saved on an older subject version shows up in `project.outdated()` (the dashboard's
"Update available"); updating saves a new scene or sheet version.

## The stored format

`format_version: "1"`. Every JSON file is written atomically; readers ignore keys they do not know; a
file with a newer `format_version` is refused with "upgrade hone-frame".

```text
<home>/
  workspace.json  settings.json
  projects/<project>/project.json
    subjects/<id>.json          every version, newest last
    images/<id>.<ext> + <id>.json
    scenes/ sequences/ sheets/  versioned records; sheets/<id>/v<n>.png renders
    runs/<run>/run.json  events.jsonl  outputs/<output>.json  control.json (only while asked)
  flows/<project>/runs/<flow run>/   hone-flow run folders
  presets/*.toml                      your own preset packs (optional)
```
