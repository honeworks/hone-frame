# Project files

A whole project in one TOML or JSON file: its details, characters with their states and belongings, the
world's places and objects, and scenes (change 0004). Import it from the dashboard (**Projects → Import
a project file**, or **Import a file** on a project's page) or the command line:

```text
hone-frame import examples/projects/rostam-and-sohrab.toml
hone-frame export-file rostam-and-sohrab rostam.json
```

Everything is matched **by name**. Importing a file again after editing it creates what is new, gives
what changed a new version (earlier images keep the version they were made from) and leaves the rest
alone; nothing is deleted. Only what the file gives is changed: a key left out of the file (a field, a
character's states, a scene's framing or notes, the project's brief or style) keeps its value. **Download as file** on a project's page (or `export-file`) writes the
project back in the same shape, as JSON.

[`examples/projects/rostam-and-sohrab.toml`](../examples/projects/rostam-and-sohrab.toml) is a complete
example: four characters, their belongings, three places, a shared object and two scenes.

## The format

| Section | Keys |
|---|---|
| `format_version` | `"1"` |
| `[project]` | `name` (required), `brief`, `direction`, `style` (the first variation's style pack, e.g. `historical-epic`), `look` (the world's look guide: what things look like, in concrete sentences), `variations` (more ways of drawing it: a list of `{name, style, direction}`) |
| `[[characters]]` | `name`, `description`, `appearance`, `build`, `features`, `outfit`, `must` and `never` (lists: what every image always or never shows), `states` (a list of `{name, kind, description}`; kind is `outfit`, `expression`, `condition`, `lighting` or `other`) |
| `[[characters.belongings]]` | objects that belong to that character: `name`, `description`, `size`, `materials`, `colours`, `details`, `must`, `never` |
| `[[places]]` | `name`, `description`, `anchors`, `materials`, `viewpoints`, `recurring_objects` |
| `[[objects]]` | shared objects (no owner), with the belongings' keys |
| `[[scenes]]` | `name`, `description`, `action`, `camera`, `expression`, `pose`, `lighting` (preset ids or words), and the names in `characters`, `places` and `objects` (world objects or belongings) |

Unknown keys are refused with their place in the file, so a typo never goes unnoticed. Names must be
unique in a file. Put objects a character carries in `belongings`, not in `features` or `outfit`:
reference images are drawn with empty hands, and the plan warns when a description puts something in
the character's hands.

```python
import tempfile
from pathlib import Path

import hone_frame as hf
from hone_frame.testing import FakeModels

TEXT = """
format_version = "1"
[project]
name = "Morning at home"
style = "clean-2d-animation"

[[characters]]
name = "Mina"
description = "a girl of eight"
outfit = "yellow raincoat, red boots"
states = [{ name = "Wet", kind = "condition", description = "soaked by the rain" }]

[[characters.belongings]]
name = "Mina's umbrella"
description = "a small red umbrella"

[[places]]
name = "Kitchen"
description = "a small sunny kitchen"

[[scenes]]
name = "Breakfast"
description = "Mina eats breakfast in the kitchen"
characters = ["Mina"]
places = ["Kitchen"]
"""

ws = hf.Workspace(Path(tempfile.mkdtemp()) / "studio", models=FakeModels())
path = Path(tempfile.mkdtemp()) / "morning.toml"
path.write_text(TEXT)
report = ws.import_file(path)
print(report.created)  # ['project morning-at-home', 'character Mina', 'asset Mina\'s umbrella', ...]
path.write_text(TEXT.replace("yellow raincoat", "green raincoat"))
again = ws.import_file(path)
assert again.updated == ["character Mina"] and not again.created
```
