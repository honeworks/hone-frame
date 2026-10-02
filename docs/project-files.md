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
alone; nothing is deleted. **Download as file** on a project's page (or `export-file`) writes the
project back in the same shape, as JSON.

[`examples/projects/rostam-and-sohrab.toml`](../examples/projects/rostam-and-sohrab.toml) is a complete
example: four characters, their belongings, three places, a shared object and two scenes.

## The format

| Section | Keys |
|---|---|
| `format_version` | `"1"` |
| `[project]` | `name` (required), `brief`, `direction`, `style` (a style pack id, e.g. `historical-epic`, `clean-2d-animation`) |
| `[[characters]]` | `name`, `description`, `appearance`, `build`, `features`, `outfit`, `states` (a list of `{name, kind, description}`; kind is `outfit`, `expression`, `condition`, `lighting` or `other`) |
| `[[characters.belongings]]` | objects that belong to that character: `name`, `description`, `size`, `materials`, `colours`, `details` |
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
from hone_frame.project_file import import_file, parse
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
report = import_file(ws, parse(TEXT, "toml"))
print(report.created)  # ['project morning-at-home', 'character Mina', 'asset Mina\'s umbrella', ...]
again = import_file(ws, parse(TEXT.replace("yellow raincoat", "green raincoat"), "toml"))
assert again.updated == ["character Mina"] and not again.created
```
