"""AC-5: sheets are composed and revised from saved images without any model call (design §11)."""

import subprocess
import sys
from pathlib import Path

from PIL import Image

import hone_frame as hf
from hone_frame.testing import FakeModels


def _images(p: hf.ProjectStore, tmp: Path, n: int, size: tuple[int, int] = (300, 500)) -> list[str]:
    ids = []
    for i in range(n):
        path = tmp / f"in{i}.png"
        Image.new("RGB", size, (40 * i % 256, 90, 160)).save(path)
        ids.append(p.import_image(path, subject_id="char_001", label=f"v{i}").id)
    return ids


def test_layouts_without_models(sample: hf.ProjectStore, fake: FakeModels, tmp_path: Path) -> None:
    ids = _images(sample, tmp_path, 8)
    recipes = [
        hf.SheetRecipe(
            name="Turnaround",
            layout="four-view-turnaround",
            images=ids[:4],
            labels=["Front", "3/4", "Side", "Back"],
            palette=["#1F4FE0", "#C9A27E"],
            notes="Loose bun.",
        ),
        hf.SheetRecipe(name="Expressions", layout="expression-grid", images=ids, show_meta=True),
        hf.SheetRecipe(name="Kitchen", layout="environment-board", images=ids[:3], fit="cover"),
        hf.SheetRecipe(
            name="Before and after", layout="before-after", images=ids[:2], labels=["Before", "After"]
        ),
        hf.SheetRecipe(name="Cup", layout="object-detail-board", images=ids[:5]),
        hf.SheetRecipe(name="Frames", layout="sequence-strip", images=ids[:4]),
    ]
    for recipe in recipes:
        sheet = sample.save_sheet(recipe)
        path = sample.compose_sheet(sheet.id)
        first = path.read_bytes()
        assert sample.compose_sheet(sheet.id).read_bytes() == first
        with Image.open(path) as image:
            assert image.width > 300
    assert fake.image_calls == 0 and fake.asked == []


def test_same_bytes_in_another_process(sample: hf.ProjectStore, tmp_path: Path) -> None:
    ids = _images(sample, tmp_path, 4)
    sheet = sample.save_sheet(
        hf.SheetRecipe(name="T", layout="four-view-turnaround", images=ids, labels=list("ABCD"))
    )
    here = sample.compose_sheet(sheet.id).read_bytes()
    code = (
        "import sys, hone_frame as hf\n"
        "p = hf.Workspace(sys.argv[1]).project(sys.argv[2])\n"
        "sys.stdout.buffer.write(p.compose_sheet(sys.argv[3]).read_bytes())\n"
    )
    out = subprocess.run(
        [sys.executable, "-c", code, str(sample.workspace.root), sample.id, sheet.id],
        capture_output=True,
        check=True,
    )
    assert out.stdout == here


def test_revision_makes_a_version(sample: hf.ProjectStore, tmp_path: Path) -> None:
    ids = _images(sample, tmp_path, 4)
    sheet = sample.save_sheet(hf.SheetRecipe(name="T", layout="four-view-turnaround", images=ids))
    v1 = sample.compose_sheet(sheet.id).read_bytes()
    revised = sample.save_sheet(
        sheet.recipe.model_copy(update={"labels": list("ABCD"), "images": ids[::-1]}), sheet_id=sheet.id
    )
    assert revised.version == 2
    v2 = sample.compose_sheet(sheet.id)
    assert v2.name == "v2.png" and v2.read_bytes() != v1
    assert (v2.parent / "v1.png").read_bytes() == v1
    assert sample.sheet(sheet.id, version=1).recipe.labels == []
    assert sample.sheet(sheet.id).render == "sheets/sht_001/v2.png"


def test_large_page_does_not_upscale(sample: hf.ProjectStore, tmp_path: Path) -> None:
    ids = _images(sample, tmp_path, 1, size=(100, 100))
    sheet = sample.save_sheet(
        hf.SheetRecipe(
            name="",
            heading="",
            layout="contact-grid",
            images=ids,
            page="2000x2000",
            background="#000000",
            margin=0,
        )
    )
    with Image.open(sample.compose_sheet(sheet.id)) as image:
        assert image.size == (2000, 2000)
        box = image.convert("L").getbbox()
    assert box is not None and (box[2] - box[0], box[3] - box[1]) == (100, 100)


def test_bad_recipes(sample: hf.ProjectStore, tmp_path: Path) -> None:
    ids = _images(sample, tmp_path, 2)
    for recipe in (
        hf.SheetRecipe(name="x", images=ids, labels=["one"]),
        hf.SheetRecipe(name="x", images=ids, background="nope"),
        hf.SheetRecipe(name="x", images=ids, page="huge"),
    ):
        sheet = sample.save_sheet(recipe)
        try:
            sample.compose_sheet(sheet.id)
        except hf.errors.InvalidRequest:
            continue
        raise AssertionError(f"accepted {recipe}")
