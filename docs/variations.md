# Variations, the look guide and the whole world

A project is a **world**: its characters, places, objects, scenes and **look guide**. A **variation** is
one way of drawing that world: a style pack and a few style notes (change 0005). Every image belongs to
one variation, so each variation has its own hero of each character; switching variations never mixes
their images. A project made before variations has one, `main`, from its style pack, and its older
images belong to it.

The **look guide** says what things in the world look like: culture, period, costume, armour, materials,
buildings, in concrete sentences you could check in a picture. Labels ("Sasanian") and tags barely
change a picture; described things do. It goes into every prompt that draws something new (a hero, an
object, an outfit, a scene); an edit of the same character leaves it out, since the reference image
shows it. A subject's **must** list ("an onyx armlet on the right upper arm") goes into its prompts and
is checked by the judge; its **never** list ("a cape") is checked by the judge and sent as a negative to
the models that take one, never written into the prompt.

```python
import tempfile
from pathlib import Path

import hone_frame as hf
from hone_frame.testing import FakeModels

ws = hf.Workspace(Path(tempfile.mkdtemp()) / "studio", models=FakeModels())
world = ws.create_project("Rostam and Sohrab", style_pack="historical-epic")
world.update(
    look="Knee-length lamellar coats laced with red cord over silk kaftans with roundel patterns, "
    "conical segmented steel helmets with mail curtains, loose trousers gathered at the ankle."
)
sohrab = world.add_subject(
    "character",
    "Sohrab",
    description="a young warrior of seventeen",
    must=["an onyx armlet with a gold setting on the right upper arm"],
    never=["plate armour", "a cape"],
)
print([v.id for v in world.info.all_variations()])  # ['main']

flat = world.add_variation("2D animated", style_pack="clean-2d-animation", direction="thick outlines")
print(world.info.variation_of().id)  # '2d-animated': the new variation is the active one

plan = world.world_plan(selection=hf.Selection(rounds=1))
print(plan["images"], "images, about", plan["estimate_s"] // 60, "minutes")
started = world.generate_world(selection=hf.Selection(rounds=1))
print(len(started["runs"]), "runs queued; the scenes follow the last one")

world.use_variation("main")  # back to the realistic look; its images were never touched
```

**Generate everything** (the project page) is `generate_world`: one run for each place and object
without an image and for each character (all its packs), in that order, then the scenes, queued by the
last run when it finishes, since they need the accepted heroes. The estimate uses the seconds per image
measured on this machine (70 s before any run has been measured).
