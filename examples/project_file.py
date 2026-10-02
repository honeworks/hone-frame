"""What: imports `examples/projects/rostam-and-sohrab.toml`, a project with four characters (states and
belongings), three places, a shared object and two scenes, then imports it again after one edit.

How: `import_path(ws, path)` creates what is missing and updates what changed, matching by name;
`project_file(store)` writes the project back in the same shape.

Why: typing every character into a form for each test is slow; a file can be kept, edited and imported
again, and only what changed becomes a new version (design change 0004).
"""

import json
import tempfile
from pathlib import Path

import hone_frame as hf
from hone_frame.project_file import import_file, import_path, parse, project_file
from hone_frame.testing import FakeModels

FILE = Path(__file__).parent / "projects" / "rostam-and-sohrab.toml"

ws = hf.Workspace(Path(tempfile.mkdtemp()) / "studio", models=FakeModels())
report = import_path(ws, FILE)
print(f"{report.project}: created {len(report.created)}")
store = ws.project(report.project)
assert [s.name for s in store.subjects("character")] == ["Rostam", "Sohrab", "Tahmineh", "Gordafarid"]
mace = next(s for s in store.subjects("asset") if s.name == "Rostam's mace")
assert mace.owner == store.subjects("character")[0].id  # a belonging of Rostam

data = project_file(store)
data["characters"][0]["features"] = "a long old scar across his left cheek, a ring on his right hand"
again = import_file(ws, parse(json.dumps(data), "json"))
print("updated:", again.updated)
assert again.updated == ["character Rostam"] and not again.created
assert store.subject(store.subjects("character")[0].id).version == 2
