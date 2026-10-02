"""The sheet compositor (design §11): Pillow only, no model call, the same bytes for the same recipe."""

from __future__ import annotations

import math
import textwrap
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from PIL import Image, ImageColor, ImageDraw, ImageFont

from hone_frame.errors import InvalidRequest
from hone_frame.records import ImageRecord, SheetRecipe

if TYPE_CHECKING:
    from hone_frame.store import ProjectStore

AUTO_CELL_WIDTH = 768
HEADING_SIZE, LABEL_SIZE, META_SIZE, NOTE_SIZE = 40, 22, 14, 18
SWATCH = 56


@dataclass(frozen=True)
class Grid:
    columns: int
    rows: int
    cell_w: int
    cell_h: int
    feature: bool  # the first image fills a row of its own, twice as tall
    label_h: int
    numbered: bool


def compose(store: ProjectStore, recipe: SheetRecipe) -> Image.Image:
    """The sheet as a Pillow image. Images are fitted into cells and never enlarged past 1:1."""
    if not recipe.images:
        raise InvalidRequest("a sheet needs at least one image")
    if recipe.labels and len(recipe.labels) != len(recipe.images):
        raise InvalidRequest(
            f"{len(recipe.labels)} labels for {len(recipe.images)} images: give one per image"
        )
    if recipe.layout == MODEL_SHEET:
        return model_sheet(store, recipe)
    records = [store.image(i) for i in recipe.images]
    grid = _grid(store, recipe, records)
    ink = _ink(recipe.background)
    heading = recipe.heading if recipe.heading is not None else recipe.name
    head_h = HEADING_SIZE + 32 if heading else 0
    grid_w = grid.columns * grid.cell_w + (grid.columns - 1) * recipe.spacing
    grid_h = _grid_height(grid, recipe.spacing)
    foot = _footer_lines(recipe, grid_w)
    foot_h = (
        (SWATCH + 40 if recipe.palette else 0)
        + len(foot) * (NOTE_SIZE + 8)
        + (32 if recipe.palette or foot else 0)
    )
    width, height = _page(recipe, grid_w + 2 * recipe.margin, head_h + grid_h + foot_h + 2 * recipe.margin)
    sheet = Image.new("RGB", (width, height), _colour(recipe.background))
    draw = ImageDraw.Draw(sheet)
    x0 = (width - grid_w) // 2
    y = recipe.margin
    if heading:
        draw.text((x0, y), heading, fill=ink, font=_font(HEADING_SIZE))
        y += head_h
    _draw_cells(store, sheet, draw, recipe=recipe, records=records, grid=grid, origin=(x0, y), ink=ink)
    y += grid_h
    _draw_footer(draw, recipe, foot, (x0, y + 32), ink)
    return sheet


def compose_saved(store: ProjectStore, sheet_id: str, version: int | None = None) -> Path:
    """Compose a saved sheet version into `sheets/<id>/v<n>.png` and record it (design §11.2)."""
    sheet = store.sheet(sheet_id, version)
    target = store.root / "sheets" / sheet.id / f"v{sheet.version}.png"
    target.parent.mkdir(parents=True, exist_ok=True)
    compose(store, sheet.recipe).save(target, format="PNG", compress_level=6)
    store.set_sheet_render(sheet, str(target.relative_to(store.root)))
    return target


def _grid(store: ProjectStore, recipe: SheetRecipe, records: list[ImageRecord]) -> Grid:
    values = store.workspace.presets.get("sheet_layout", recipe.layout).values
    n = len(records)
    feature = bool(values.get("feature_first")) and n > 1
    cells = n - 1 if feature else n
    columns = recipe.columns if recipe.columns is not None else int(values.get("columns", 4))
    if columns == 0:
        columns = max(cells, 1)
    elif columns < 0:
        columns = math.ceil(math.sqrt(max(cells, 1)))
    columns = max(1, min(columns, max(cells, 1)))
    aspect = float(values.get("cell", 1.0))
    cell_w = min(AUTO_CELL_WIDTH, max(r.width for r in records))
    numbered = values.get("label_style") == "numbered"
    label_h = (LABEL_SIZE + 12 if recipe.labels or numbered else 0) + (
        META_SIZE + 6 if recipe.show_meta else 0
    )
    return Grid(
        columns, math.ceil(cells / columns), cell_w, round(cell_w / aspect), feature, label_h, numbered
    )


def _grid_height(grid: Grid, spacing: int) -> int:
    row = grid.cell_h + grid.label_h
    feature = (2 * grid.cell_h + grid.label_h + spacing) if grid.feature else 0
    return feature + grid.rows * row + max(grid.rows - 1, 0) * spacing


def _page(recipe: SheetRecipe, need_w: int, need_h: int) -> tuple[int, int]:
    if recipe.page == "auto":
        return need_w, need_h
    try:
        w, h = (int(v) for v in recipe.page.lower().split("x"))
    except ValueError as exc:
        raise InvalidRequest(f"page must be 'auto' or 'WxH' in pixels, not {recipe.page!r}") from exc
    return max(w, need_w), max(h, need_h)  # a larger page is a larger canvas, never larger images


def _draw_cells(
    store: ProjectStore,
    sheet: Image.Image,
    draw: ImageDraw.ImageDraw,
    *,
    recipe: SheetRecipe,
    records: list[ImageRecord],
    grid: Grid,
    origin: tuple[int, int],
    ink: tuple[int, int, int],
) -> None:
    x0, y = origin
    full_w = grid.columns * grid.cell_w + (grid.columns - 1) * recipe.spacing
    for i, record in enumerate(records):
        if grid.feature and i == 0:
            box = (x0, y, full_w, 2 * grid.cell_h)
        else:
            k = i - 1 if grid.feature else i
            top = y + ((2 * grid.cell_h + grid.label_h + recipe.spacing) if grid.feature else 0)
            col, row = k % grid.columns, k // grid.columns
            box = (
                x0 + col * (grid.cell_w + recipe.spacing),
                top + row * (grid.cell_h + grid.label_h + recipe.spacing),
                grid.cell_w,
                grid.cell_h,
            )
        _place(sheet, store.root / "images" / record.file, box, recipe.fit)
        _label(draw, recipe, record, index=i, grid=grid, at=(box[0], box[1] + box[3] + 8), ink=ink)


def _place(sheet: Image.Image, path: Path, box: tuple[int, int, int, int], fit: str) -> None:
    x, y, w, h = box
    with Image.open(path) as source:
        picture: Image.Image = source.convert("RGB")
    if fit == "cover":
        scale = min(max(w / picture.width, h / picture.height), 1.0)
    else:
        scale = min(w / picture.width, h / picture.height, 1.0)
    size = (max(1, round(picture.width * scale)), max(1, round(picture.height * scale)))
    if size != picture.size:
        picture = picture.resize(size, Image.Resampling.LANCZOS)  # pyright: ignore[reportUnknownMemberType]
    left, top = max((picture.width - w) // 2, 0), max((picture.height - h) // 2, 0)
    picture = picture.crop((left, top, left + min(w, picture.width), top + min(h, picture.height)))
    sheet.paste(picture, (x + (w - picture.width) // 2, y + (h - picture.height) // 2))


def _label(
    draw: ImageDraw.ImageDraw,
    recipe: SheetRecipe,
    record: ImageRecord,
    *,
    index: int,
    grid: Grid,
    at: tuple[int, int],
    ink: tuple[int, int, int],
) -> None:
    x, y = at
    text = recipe.labels[index] if recipe.labels else ""
    if grid.numbered:
        text = f"{index + 1}  {text}".rstrip()
    if text:
        draw.text((x, y), text, fill=ink, font=_font(LABEL_SIZE))
        y += LABEL_SIZE + 12
    if recipe.show_meta:
        draw.text((x, y), f"{record.id}  {record.width} x {record.height}", fill=ink, font=_font(META_SIZE))


def _footer_lines(recipe: SheetRecipe, width: int) -> list[str]:
    chars = max(20, width // (NOTE_SIZE // 2 + 1))
    return [line for para in recipe.notes.splitlines() for line in textwrap.wrap(para, chars) or [""]]


def _draw_footer(
    draw: ImageDraw.ImageDraw,
    recipe: SheetRecipe,
    notes: list[str],
    at: tuple[int, int],
    ink: tuple[int, int, int],
) -> None:
    x, y = at
    if recipe.palette:
        for i, colour in enumerate(recipe.palette):
            left = x + i * (SWATCH + 72)
            draw.rectangle((left, y, left + SWATCH, y + SWATCH), fill=_colour(colour), outline=ink)
            draw.text((left, y + SWATCH + 6), colour.upper(), fill=ink, font=_font(META_SIZE))
        y += SWATCH + 40
    for line in notes:
        draw.text((x, y), line, fill=ink, font=_font(NOTE_SIZE))
        y += NOTE_SIZE + 8


def _colour(value: str) -> tuple[int, int, int]:
    try:
        rgb = ImageColor.getrgb(value)
    except ValueError as exc:
        raise InvalidRequest(f"{value!r} is not a colour; use a hex value such as #F4F6F9") from exc
    return rgb[0], rgb[1], rgb[2]


def _ink(background: str) -> tuple[int, int, int]:
    r, g, b = _colour(background)
    return (20, 24, 33) if 0.2126 * r + 0.7152 * g + 0.0722 * b > 140 else (238, 241, 246)


def _font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    return ImageFont.load_default(size)


# ------------------------------------------------------------------------ the character model sheet

MODEL_SHEET = "character-model-sheet"  # change 0003: full figures in a row, faces below, notes
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
    notes = _footer_lines(recipe, content_w)
    height = (
        HEADING_SIZE + 32
        + FIGURE[1] + label_h + s
        + face_rows * (FACE + label_h + s)
        + len(notes) * (NOTE_SIZE + 8) + 2 * m
    )  # fmt: skip
    sheet = Image.new("RGB", (content_w + 2 * m, height), _colour(recipe.background))
    draw = ImageDraw.Draw(sheet)
    ink = _ink(recipe.background)
    draw.text((m, m), recipe.heading or recipe.name, fill=ink, font=_font(HEADING_SIZE))
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
        draw.text((m, y), line, fill=ink, font=_font(NOTE_SIZE))
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
    _place(sheet, store.image_path(image_id), box, fit)
    if label:
        draw.text((box[0], box[1] + box[3] + 8), label, fill=ink, font=_font(LABEL_SIZE))
