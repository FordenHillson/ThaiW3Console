"""Render Thai sentences with Google Sarabun."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from .paths import assets_dir

DEFAULT_SIZE = 48
DEFAULT_COLOR = (255, 255, 255, 255)
PAD = 4


def sarabun_path(weight: str = "Regular") -> Path:
    path = assets_dir() / "fonts" / f"Sarabun-{weight}.ttf"
    if not path.exists():
        raise FileNotFoundError(f"missing font {path}")
    return path


@lru_cache(maxsize=8)
def _pil_font(weight: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(sarabun_path(weight)), size=size)


def render_sentence(
    text: str,
    *,
    size: int = DEFAULT_SIZE,
    color: tuple[int, int, int, int] = DEFAULT_COLOR,
    weight: str = "Bold",
    bg: tuple[int, int, int, int] | None = None,
) -> Image.Image:
    """Render one sentence to RGBA (transparent background unless ``bg`` is set)."""
    text = text.strip() or " "
    font = _pil_font(weight, size)
    bbox = font.getbbox(text)
    width = PAD * 2 + max(1, bbox[2] - bbox[0])
    height = PAD * 2 + max(1, bbox[3] - bbox[1]) + size // 6
    img = Image.new("RGBA", (width, height), bg or (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.text((PAD - bbox[0], PAD - bbox[1]), text, font=font, fill=color)
    alpha = img.split()[-1]
    box = alpha.getbbox()
    if box:
        l, t, r, b = box
        img = img.crop((max(0, l - 2), max(0, t - 2), min(img.width, r + 2), min(img.height, b + 2)))
    return img


def preview_on_dark(text: str, **kwargs) -> Image.Image:
    """Sentence on a dark menu-like background for studio preview."""
    glyph = render_sentence(text, **kwargs)
    canvas = Image.new("RGB", (max(640, glyph.width + 40), max(120, glyph.height + 40)), (22, 24, 28))
    canvas.paste(glyph, ((canvas.width - glyph.width) // 2, (canvas.height - glyph.height) // 2), glyph)
    return canvas
