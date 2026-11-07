"""Per-character bitmap glyphs (PUA) — compose Thai sentences without Thai Unicode fonts.

Console-safe path: each Thai (or Latin) character → one PUA DefineFont3 glyph.
w3strings store a sequence of PUA codes; Flash lays them out LTR by advance.

Combining marks (สระ/วรรณยุกต์) use advance=0 and negative left bearing so ink
sits over the previous consonant — same model as a normal outline font.

Tone marks after an above-vowel (ิ่, กี่, …) use a separate raised PUA glyph —
Flash has no Thai OpenType shaping, so we encode the high form explicitly.
"""
from __future__ import annotations

import unicodedata
from dataclasses import dataclass, field

from PIL import Image, ImageDraw

from .render import _pil_font
from .swf_bits import BitWriter, bits_needed
from .swf_bitmap_glyph import (
    EM,
    PREVIEW_SIZE_BASE,
    _encode_bounds,
    em_height_for_size,
    glyph_y0,
    inject_glyphs,
    mask_to_glyph_shape,
    pua_code,
    rgba_to_mask,
)


_THAI_MARKS = set("ัิีึืฺุู็่้๊๋์ํ๎")
# Above vowels that push a following tone mark higher (Thai typography).
ABOVE_VOWELS = set("ัิีึื็ํ")
TONE_MARKS = set("่้๊๋")


def is_combining_mark(ch: str) -> bool:
    if not ch:
        return False
    if ch in _THAI_MARKS:
        return True
    return unicodedata.category(ch) in ("Mn", "Me")


def is_tone_mark(ch: str) -> bool:
    return ch in TONE_MARKS


def tone_raise_px(size: int, weight: str = "Bold") -> int:
    """How many px to lift a tone when it sits on an above-vowel (Sarabun metrics).

    Adds extra air above the shaped delta — menu TextFields downscale glyphs and
    1-bit scanline packing eats small gaps (ิ่ looked fused at bare delta).
    """
    font = _pil_font(weight, size)
    try:
        bare = font.getbbox("ก่", anchor="ls")
        high = font.getbbox("กิ่", anchor="ls")
        shaped = max(1, int(round(bare[1] - high[1])))
    except TypeError:
        shaped = max(1, int(round(size * 0.28)))
    # ~+40% + small pad so tone and above-vowel stay separated after EM scale.
    return max(shaped + 1, int(round(shaped * 1.45 + size * 0.06)))


@dataclass(frozen=True)
class CharCell:
    ch: str
    image: Image.Image
    advance_px: int
    pen_x_px: int
    raised: bool = False


@dataclass
class CharAtlas:
    """PUA assignment: base chars + optional raised tone variants."""

    base: dict[str, int] = field(default_factory=dict)
    high_tone: dict[str, int] = field(default_factory=dict)  # ่ → PUA for raised form

    def code_for(self, ch: str, *, raised: bool = False) -> int | None:
        if raised and ch in self.high_tone:
            return self.high_tone[ch]
        return self.base.get(ch)

    @property
    def glyph_count(self) -> int:
        return len(self.base) + len(self.high_tone)


def render_char_cell(
    ch: str,
    *,
    size: int = PREVIEW_SIZE_BASE,
    weight: str = "Bold",
    raised: bool = False,
) -> CharCell:
    """Render one character into a shared metrics cell (extra headroom for high tones)."""
    if ch == "\n":
        ch = " "
    font = _pil_font(weight, size)
    ascent, descent = font.getmetrics()
    descent = abs(int(descent))
    ascent = int(ascent)
    # Always reserve headroom so raised tones are not clipped; baseline stays fixed.
    headroom = tone_raise_px(size, weight) + 2
    raise_px = tone_raise_px(size, weight) if raised else 0
    cell_h = max(1, headroom + ascent + descent + 2)
    baseline = headroom + ascent

    mark = is_combining_mark(ch)
    raw_adv = float(font.getlength(ch)) if ch else 0.0
    advance_px = 0 if mark else max(1, int(round(raw_adv)))

    draw_y = baseline - (raise_px if raised and is_tone_mark(ch) else 0)

    try:
        left, top, right, bottom = font.getbbox(ch, anchor="ls")
    except TypeError:
        left, top, right, bottom = font.getbbox(ch)
        top -= ascent
        bottom -= ascent

    # When raised, ink moves up — expand vertical measure for width calc only via left/right.
    x0 = min(0, int(left)) - 2
    x1 = max(advance_px if not mark else 0, int(right)) + 2
    if x1 <= x0:
        x1 = x0 + 1
    width = x1 - x0
    pen_x = -x0

    img = Image.new("RGBA", (width, cell_h), (0, 0, 0, 0))
    if ch.strip() or ch == " ":
        draw = ImageDraw.Draw(img)
        try:
            draw.text((pen_x, draw_y), ch, font=font, fill=(255, 255, 255, 255), anchor="ls")
        except TypeError:
            draw.text((pen_x + left, draw_y - ascent), ch, font=font, fill=(255, 255, 255, 255))

    return CharCell(ch=ch, image=img, advance_px=advance_px, pen_x_px=pen_x, raised=raised)


def is_thai_char(ch: str) -> bool:
    """Thai block or explicit mark set (for charset / encode routing)."""
    if not ch:
        return False
    o = ord(ch)
    return 0x0E00 <= o <= 0x0E7F or ch in _THAI_MARKS


def collect_charset(texts: list[str]) -> list[str]:
    """Unique Thai characters only — ASCII/Latin stay as vanilla font glyphs."""
    seen: dict[str, None] = {}
    for text in texts:
        for ch in text:
            if ch == "\n":
                continue
            if is_thai_char(ch) and ch not in seen:
                seen[ch] = None
    return list(seen)


def build_char_atlas(texts: list[str], *, always_high_tones: bool = False) -> CharAtlas:
    """Assign PUA codes; add raised tone glyphs when needed (or always for full packs)."""
    chars = collect_charset(texts)
    atlas = CharAtlas()
    i = 0
    for ch in chars:
        atlas.base[ch] = pua_code(i)
        i += 1
    tones_used = [c for c in chars if c in TONE_MARKS]
    need_high = always_high_tones and bool(tones_used)
    if not need_high:
        for text in texts:
            prev = ""
            for ch in text:
                if ch in TONE_MARKS and prev in ABOVE_VOWELS:
                    need_high = True
                    break
                prev = ch
            if need_high:
                break
    if need_high:
        for ch in tones_used:
            atlas.high_tone[ch] = pua_code(i)
            i += 1
    return atlas


def build_char_map(texts: list[str]) -> dict[str, int]:
    """Back-compat: base char → PUA only (no high tones)."""
    return dict(build_char_atlas(texts).base)


def encode_thai(text: str, atlas: CharAtlas | dict[str, int]) -> str:
    """Thai → PUA; non-Thai (ASCII/Latin/punct) passed through for vanilla glyphs.

    Tones after above-vowels use raised PUA glyphs when the atlas has them.
    """
    if isinstance(atlas, dict):
        atlas = CharAtlas(base=atlas)
    out: list[str] = []
    prev = ""
    for ch in text:
        if ch == "\n":
            ch = " "
        raised = bool(ch in TONE_MARKS and prev in ABOVE_VOWELS and ch in atlas.high_tone)
        code = atlas.code_for(ch, raised=raised)
        if code is not None:
            out.append(chr(code))
        elif not is_thai_char(ch):
            out.append(ch)
        # unknown Thai codepoint: drop (should have been in atlas)
        prev = ch
    return "".join(out) if out else " "


def cell_to_glyph(
    cell: CharCell,
    *,
    scale: float,
    em_height: int,
    y_lift: int = 0,
) -> tuple[bytes, int, bytes]:
    mask = rgba_to_mask(cell.image)
    advance_em = 0 if cell.advance_px == 0 else max(1, int(round(cell.advance_px * scale)))
    return _mask_with_pen_origin(
        mask,
        pen_x_px=cell.pen_x_px,
        scale=scale,
        advance=advance_em,
        em_height=em_height,
        y_lift=y_lift,
    )


def _mask_with_pen_origin(
    mask: Image.Image,
    *,
    pen_x_px: int,
    scale: float,
    advance: int,
    em_height: int,
    y_lift: int = 0,
) -> tuple[bytes, int, bytes]:
    if mask.mode != "1":
        mask = mask.convert("L").point(lambda p: 255 if p > 16 else 0, mode="1")
    w_px, h_px = mask.size
    if w_px < 1 or h_px < 1:
        return mask_to_glyph_shape(mask, em_height=em_height, scale=scale, advance=max(1, advance) or 1)

    glyph_h = max(1, int(round(h_px * scale)))
    y0 = glyph_y0(glyph_h, em_height, y_lift=y_lift)
    advance = max(0, min(32767, int(advance)))

    bw = BitWriter()
    bw.u(4, 1)
    bw.u(4, 0)
    pixels = mask.load()
    min_x, min_y = 0, y0 + glyph_h
    max_x, max_y = 0, y0
    touched = False

    row_step = max(1, int(round(1 / scale))) if scale < 1 else 1
    for row in range(0, h_px, row_step):
        y = y0 + int(round(row * scale))
        y2 = y0 + int(round(min(h_px, row + row_step) * scale))
        if y2 <= y:
            y2 = y + 1
        col = 0
        while col < w_px:
            while col < w_px and pixels[col, row] == 0:
                col += 1
            if col >= w_px:
                break
            start = col
            while col < w_px and pixels[col, row] != 0:
                col += 1
            x = int(round((start - pen_x_px) * scale))
            x2 = int(round((col - pen_x_px) * scale))
            if x2 <= x:
                x2 = x + 1
            bw.u(1, 0)
            bw.u(1, 0)
            bw.u(1, 0)
            bw.u(1, 1)
            bw.u(1, 0)
            bw.u(1, 1)
            nbits = max(bits_needed(x), bits_needed(y), 1)
            bw.u(5, nbits)
            bw.s(nbits, x)
            bw.s(nbits, y)
            bw.u(1, 1)

            def edge(dx: int = 0, dy: int = 0) -> None:
                bw.u(1, 1)
                bw.u(1, 1)
                n = max(bits_needed(dx), bits_needed(dy), 1)
                bw.u(4, n - 2)
                if dx and dy:
                    bw.u(1, 1)
                    bw.s(n, dx)
                    bw.s(n, dy)
                else:
                    bw.u(1, 0)
                    if dy:
                        bw.u(1, 1)
                        bw.s(n, dy)
                    else:
                        bw.u(1, 0)
                        bw.s(n, dx)

            edge(dx=x2 - x)
            edge(dy=y2 - y)
            edge(dx=-(x2 - x))
            edge(dy=-(y2 - y))
            min_x = x if not touched else min(min_x, x)
            max_x = x2 if not touched else max(max_x, x2)
            min_y = min(min_y, y)
            max_y = max(max_y, y2)
            touched = True

    bw.u(1, 0)
    bw.u(5, 0)
    shape = bw.bytes()
    if not touched:
        from .swf_bitmap_glyph import EMPTY_RECT, EMPTY_SHAPE

        return EMPTY_SHAPE, advance, EMPTY_RECT
    bound_r = max(max_x, advance if advance else max_x)
    bounds = _encode_bounds(min_x, min_y, bound_r, max_y)
    return shape, advance, bounds


def char_em_height(size: int, em_scale: float = 1.0) -> int:
    """EM height for char fonts — allows above the sentence-glyph 1.15·EM clamp."""
    base = em_height_for_size(size)
    raw = int(round(base * float(em_scale)))
    return max(int(EM * 0.35), min(int(EM * 1.45), raw))


def build_char_font_glyphs(
    atlas: CharAtlas | dict[str, int],
    *,
    size: int = PREVIEW_SIZE_BASE,
    weight: str = "Bold",
    y_lift: int = 0,
    em_scale: float = 1.0,
) -> dict[int, tuple[bytes, int, bytes]]:
    if isinstance(atlas, dict):
        atlas = CharAtlas(base=atlas)
    em_h = char_em_height(size, em_scale=em_scale)
    sample = render_char_cell("ก", size=size, weight=weight)
    scale = em_h / max(1, sample.image.height)
    glyphs: dict[int, tuple[bytes, int, bytes]] = {}
    for ch, code in atlas.base.items():
        cell = render_char_cell(ch, size=size, weight=weight, raised=False)
        glyphs[code] = cell_to_glyph(cell, scale=scale, em_height=em_h, y_lift=y_lift)
    for ch, code in atlas.high_tone.items():
        cell = render_char_cell(ch, size=size, weight=weight, raised=True)
        glyphs[code] = cell_to_glyph(cell, scale=scale, em_height=em_h, y_lift=y_lift)
    return glyphs


def inject_char_font(
    redswf: bytes,
    atlas: CharAtlas | dict[str, int],
    *,
    size: int = PREVIEW_SIZE_BASE,
    weight: str = "Bold",
    y_lift: int = 0,
    font_index: int | None = None,
    em_scale: float = 1.0,
) -> bytes:
    glyphs = build_char_font_glyphs(
        atlas, size=size, weight=weight, y_lift=y_lift, em_scale=em_scale
    )
    return inject_glyphs(redswf, glyphs, font_index=font_index)


def preview_encoded(
    text: str,
    atlas: CharAtlas | dict[str, int],
    *,
    size: int = 48,
    weight: str = "Bold",
) -> Image.Image:
    """Composite char cells with high-tone selection — offline stacking check."""
    if isinstance(atlas, dict):
        atlas = CharAtlas(base=atlas)
    cells: list[CharCell] = []
    prev = ""
    for ch in text:
        if ch == "\n":
            ch = " "
        raised = bool(ch in TONE_MARKS and prev in ABOVE_VOWELS and ch in atlas.high_tone)
        cells.append(render_char_cell(ch, size=size, weight=weight, raised=raised))
        prev = ch
    if not cells:
        return Image.new("RGBA", (8, 8), (0, 0, 0, 0))
    h = cells[0].image.height
    pen = 0
    placements: list[tuple[int, CharCell]] = []
    for cell in cells:
        placements.append((pen - cell.pen_x_px, cell))
        pen += cell.advance_px
    width = max(pen + 4, max(x + c.image.width for x, c in placements))
    canvas = Image.new("RGBA", (max(1, width), h), (0, 0, 0, 0))
    for x, cell in placements:
        canvas.alpha_composite(cell.image, (max(0, x), 0))
    return canvas
