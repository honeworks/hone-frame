"""What: imports `examples/projects/rostam-and-sohrab.toml`, a project with four characters (states and
belongings), three places, a shared object and two scenes, then imports it again after one edit.

How: `ws.import_file(path)` creates what is missing and updates what changed, matching by name;
`store.project_file()` writes the project back in the same shape.

Why: typing every character into a form for each test is slow; a file can be kept, edited and imported
again, and only what changed becomes a new version (design change 0004).
"""

import json
import tempfile
from pathlib import Path

import hone_frame as hf
from hone_frame.testing import FakeModels

FILE = Path(__file__).parent / "projects" / "rostam-and-sohrab.toml"

ws = hf.Workspace(Path(tempfile.mkdtemp()) / "studio", models=FakeModels())
report = ws.import_file(FILE)
print(f"{report.project}: created {len(report.created)}")
store = ws.project(report.project)
assert [s.name for s in store.subjects("character")] == ["Rostam", "Sohrab", "Tahmineh", "Gordafarid"]
mace = next(s for s in store.subjects("asset") if s.name == "Rostam's mace")
assert mace.owner == store.subjects("character")[0].id  # a belonging of Rostam

data = store.project_file()
data["characters"][0]["features"] = "a long old scar across his left cheek, a ring on his right hand"
edited = Path(tempfile.mkdtemp()) / "edited.json"
edited.write_text(json.dumps(data))
again = ws.import_file(edited)
print("updated:", again.updated)
assert again.updated == ["character Rostam"] and not again.created
assert store.subject(store.subjects("character")[0].id).version == 2
