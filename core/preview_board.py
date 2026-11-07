"""Compose studio previews that mirror how glyphs land in the game."""
from __future__ import annotations

from PIL import Image, ImageDraw

from .custom_art import load_custom
from .render import render_sentence
from .swf_bitmap_glyph import rgba_to_mask

MENU_BG = (18, 20, 24)
ROW_BG = (28, 30, 34)
HI_BG = (40, 44, 52)
HI_BORDER = (230, 230, 230)
TEXT_COLOR = (255, 255, 255, 255)
CUSTOM_BADGE = (80, 180, 120)


def glyph_preview(
    text: str,
    size: int = 52,
    weight: str = "Bold",
    string_id: int | None = None,
) -> Image.Image:
    """RGBA art: custom PNG if present, else Sarabun render."""
    if string_id is not None:
        custom = load_custom(string_id)
        if custom is not None:
            return custom
    return render_sentence(text, size=size, weight=weight, color=TEXT_COLOR)


def mask_preview(
    text: str,
    size: int = 52,
    weight: str = "Bold",
    string_id: int | None = None,
) -> Image.Image:
    """1-bit style preview ≈ DefineFont3 scanline glyphs."""
    rgba = glyph_preview(text, size=size, weight=weight, string_id=string_id)
    mask = rgba_to_mask(rgba)
    w, h = mask.size
    shown = mask.resize((max(1, w * 2), max(1, h * 2)), Image.NEAREST).convert("L")
    out = Image.new("RGB", (shown.width + 24, shown.height + 24), MENU_BG)
    rgb = Image.new("RGB", shown.size, (255, 255, 255))
    out.paste(rgb, (12, 12), shown)
    return out


def menu_column_preview(
    lines: list[str],
    *,
    size: int = 52,
    weight: str = "Bold",
    selected: int = 0,
    width: int = 420,
    y_lift_pct: int = 0,
    string_ids: list[int] | None = None,
) -> Image.Image:
    """Vertical menu mock; uses custom PNGs when ``string_ids`` are provided."""
    raw = []
    for i, t in enumerate(lines):
        sid = string_ids[i] if string_ids and i < len(string_ids) else None
        raw.append(glyph_preview(t or " ", size=size, weight=weight, string_id=sid))
    if not raw:
        return Image.new("RGB", (width, 120), MENU_BG)

    max_h = max(g.height for g in raw)
    glyphs = []
    for g in raw:
        if g.height == max_h:
            glyphs.append(g)
            continue
        pad = Image.new("RGBA", (g.width, max_h), (0, 0, 0, 0))
        pad.paste(g, (0, (max_h - g.height) // 2), g)
        glyphs.append(pad)

    row_h = max_h + 28
    lift_px = int(round(max_h * max(-15, min(25, y_lift_pct)) / 100))
    height = 24 + row_h * len(glyphs) + 24
    canvas = Image.new("RGB", (width, height), MENU_BG)
    draw = ImageDraw.Draw(canvas)

    for i, g in enumerate(glyphs):
        y = 24 + i * row_h
        x0, x1 = 36, width - 36
        y0, y1 = y, y + row_h - 8
        if i == selected:
            draw.rectangle([x0, y0, x1, y1], fill=HI_BG, outline=HI_BORDER, width=2)
        else:
            draw.rectangle([x0, y0, x1, y1], fill=ROW_BG)
        gx = (width - g.width) // 2
        gy = y0 + (y1 - y0 - g.height) // 2 - lift_px
        gy = max(y0 + 2, min(y1 - g.height - 2, gy))
        canvas.paste(g, (gx, gy), g)
        if string_ids and i < len(string_ids) and load_custom(string_ids[i]) is not None:
            draw.ellipse([x1 - 14, y0 + 6, x1 - 4, y0 + 16], fill=CUSTOM_BADGE)
    return canvas
