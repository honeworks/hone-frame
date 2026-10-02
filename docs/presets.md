# Presets

A useful catalogue ships with the package and works before any project exists (design §5): style packs,
character / environment / asset presentations, camera, lighting, expressions, poses, interactions, state
templates, sheet layouts, generation profiles, selection recipes and judging profiles.

```python
import hone_frame as hf

catalog = hf.presets()
print(catalog.categories())
pack = catalog.get("style_pack", "cinematic-realism")
print(pack.name, "-", pack.description)
print([p.id for p in catalog.list("camera")])
assert catalog.default("style_pack") == "cinematic-realism"
```

- **Independent categories.** A style pack sets defaults for other categories (lighting, sheet layout,
  presentations); choosing a camera never changes the art style or a subject's identity.
- **Order of choice:** the request's presets, then the scene's overrides, then the project's defaults,
  then the style pack's, then the catalogue default.
- **No preset names a model.** Only profiles do, and the shipped ones are local models.
- **Versions are recorded.** Every run stores `{"category:id": version}` for the presets it used.

## Your own packs

Put TOML files in `<home>/presets/`; a preset with an existing id replaces the shipped one for that
workspace.

```python
import tempfile
from pathlib import Path

home = Path(tempfile.mkdtemp())
(home / "presets").mkdir()
(home / "presets" / "noir.toml").write_text("""
[[presets]]
id = "noir"
category = "style_pack"
version = 1
name = "Film noir"
description = "Black and white, hard shadows, rain-slick streets."
prompt = { prefix = "Film noir still, black and white,", suffix = "hard shadows, high contrast." }
values = { lighting = "dramatic-side" }
""")
assert hf.Workspace(home).presets.get("style_pack", "noir").builtin is False
```
