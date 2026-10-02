"""The character model sheet (change 0003): the full figures in one row, the face close-ups below, and a
text panel. Pillow only, no model call. `columns` in the recipe is how many images are full figures."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PIL import Image, ImageDraw

from hone_frame.records import SheetRecipe
from hone_frame.sheets import (
    HEADING_SIZE,
    LABEL_SIZE,
    NOTE_SIZE,
    footer_lines,
    place_image,
    sheet_colour,
    sheet_font,
    sheet_ink,
)

if TYPE_CHECKING:
    from hone_frame.store import ProjectStore

FIGURE: tuple[int, int] = (440, 760)  # a full-figure cell (w, h)
FACE: int = 300  # a square face cell
FACES_PER_ROW = 4


def model_sheet(store: ProjectStore, recipe: SheetRecipe) -> Image.Image:
    s, m, label_h = recipe.spacing, recipe.margin, LABEL_SIZE + 16
    cells = _boxes(recipe, top=m + HEADING_SIZE + 32)
    content_w = max(900, *(x + w - m for _, (x, _, w, _) in cells))
    grid_bottom = max(y + h for _, (_, y, _, h) in cells) + label_h + s
    notes = footer_lines(recipe, content_w)
    sheet = Image.new(
        "RGB",
        (content_w + 2 * m, grid_bottom + len(notes) * (NOTE_SIZE + 8) + m),
        sheet_colour(recipe.background),
    )
    draw = ImageDraw.Draw(sheet)
    ink = sheet_ink(recipe.background)
    draw.text((m, m), recipe.heading or recipe.name, fill=ink, font=sheet_font(HEADING_SIZE))
    labels = recipe.labels or [""] * len(recipe.images)
    for (image_id, box), label in zip(cells, labels, strict=True):
        place_image(sheet, store.image_path(image_id), box, recipe.fit)
        draw.text((box[0], box[1] + box[3] + 8), label, fill=ink, font=sheet_font(LABEL_SIZE))
    y = grid_bottom
    for line in notes:
        draw.text((m, y), line, fill=ink, font=sheet_font(NOTE_SIZE))
        y += NOTE_SIZE + 8
    return sheet


def _boxes(recipe: SheetRecipe, *, top: int) -> list[tuple[str, tuple[int, int, int, int]]]:
    """Each image's cell: the first `columns` full figures in one row, then the faces, four to a row."""
    s, m, label_h = recipe.spacing, recipe.margin, LABEL_SIZE + 16
    count = recipe.columns or 1
    cells: list[tuple[str, tuple[int, int, int, int]]] = [
        (i, (m + n * (FIGURE[0] + s), top, *FIGURE)) for n, i in enumerate(recipe.images[:count])
    ]
    below = top + FIGURE[1] + label_h + s
    for k, image_id in enumerate(recipe.images[count:]):
        x = m + (k % FACES_PER_ROW) * (FACE + s)
        cells.append((image_id, (x, below + (k // FACES_PER_ROW) * (FACE + label_h + s), FACE, FACE)))
    return cells
