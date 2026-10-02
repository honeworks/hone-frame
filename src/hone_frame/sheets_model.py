"""The character model sheet (change 0003): the full figures in one row, the face close-ups below, and a
text panel. Pillow only, no model call. `columns` in the recipe is how many images are full figures."""

from __future__ import annotations

import math
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

FIGURE = (440, 760)  # a full-figure cell (w, h)
FACE = 300  # a square face cell
FACES_PER_ROW = 4


def model_sheet(store: ProjectStore, recipe: SheetRecipe) -> Image.Image:
    figures = recipe.images[: recipe.columns or 0] if recipe.columns else recipe.images[:1]
    faces = recipe.images[len(figures) :]
    labels = recipe.labels or [""] * len(recipe.images)
    s, m = recipe.spacing, recipe.margin
    label_h = LABEL_SIZE + 16
    figures_w = len(figures) * FIGURE[0] + max(len(figures) - 1, 0) * s
    per_row = min(FACES_PER_ROW, len(faces)) or 1
    faces_w = per_row * FACE + (per_row - 1) * s
    content_w = max(figures_w, faces_w, 900)
    face_rows = math.ceil(len(faces) / per_row) if faces else 0
    notes = footer_lines(recipe, content_w)
    height = (
        HEADING_SIZE + 32
        + FIGURE[1] + label_h + s
        + face_rows * (FACE + label_h + s)
        + len(notes) * (NOTE_SIZE + 8) + 2 * m
    )  # fmt: skip
    sheet = Image.new("RGB", (content_w + 2 * m, height), sheet_colour(recipe.background))
    draw = ImageDraw.Draw(sheet)
    ink = sheet_ink(recipe.background)
    draw.text((m, m), recipe.heading or recipe.name, fill=ink, font=sheet_font(HEADING_SIZE))
    y = m + HEADING_SIZE + 32
    for i, image_id in enumerate(figures):
        x = m + i * (FIGURE[0] + s)
        _cell(
            store,
            sheet,
            draw=draw,
            image_id=image_id,
            box=(x, y, *FIGURE),
            label=labels[i],
            ink=ink,
            fit=recipe.fit,
        )
    y += FIGURE[1] + label_h + s
    for k, image_id in enumerate(faces):
        x = m + (k % per_row) * (FACE + s)
        top = y + (k // per_row) * (FACE + label_h + s)
        label = labels[len(figures) + k]
        _cell(
            store,
            sheet,
            draw=draw,
            image_id=image_id,
            box=(x, top, FACE, FACE),
            label=label,
            ink=ink,
            fit=recipe.fit,
        )
    y += face_rows * (FACE + label_h + s)
    for line in notes:
        draw.text((m, y), line, fill=ink, font=sheet_font(NOTE_SIZE))
        y += NOTE_SIZE + 8
    return sheet


def _cell(
    store: ProjectStore,
    sheet: Image.Image,
    *,
    draw: ImageDraw.ImageDraw,
    image_id: str,
    box: tuple[int, int, int, int],
    label: str,
    ink: tuple[int, int, int],
    fit: str,
) -> None:
    place_image(sheet, store.image_path(image_id), box, fit)
    if label:
        draw.text((box[0], box[1] + box[3] + 8), label, fill=ink, font=sheet_font(LABEL_SIZE))
