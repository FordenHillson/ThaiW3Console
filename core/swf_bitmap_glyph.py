"""Embed a rendered sentence as a DefineFont3 glyph (scanline bitmap → shape).

SWF font glyphs cannot reference DefineBitsLossless character IDs. Instead we
encode the alpha mask as filled rectangles (horizontal runs) inside the glyph
shape. One PUA codepoint maps to one whole sentence image.
"""
from __future__ import annotations

import struct
import zlib
from dataclasses import dataclass

from PIL import Image

from .swf_bits import BitWriter, bits_needed

EM = 1024 * 20  # DefineFont3 units per em
EMPTY_SHAPE = b"\x10\x00"
EMPTY_RECT = b"\x00"
CR2W_FILE_SIZES = (24, 28)
CR2W_EXPORT_SIZE = 385
CR2W_SWF_SIZE = 597
FONT_PATH = "gameplay\\gui_new\\swf\\witcher3\\fonts_en.redswf"
PUA_BASE = 0xE000


def pua_code(index: int) -> int:
    return PUA_BASE + index


# ---------------------------------------------------------------------------
# Shape encoding
# ---------------------------------------------------------------------------

def _encode_rect(x: int, y: int, w: int, h: int) -> bytes:
    """Filled axis-aligned rectangle as a font glyph shape fragment (no header)."""
    bw = BitWriter()
    # StyleChange: MoveTo + FillStyle1=1
    bw.u(1, 0)  # TypeFlag
    bw.u(1, 0)  # StateNewStyles
    bw.u(1, 0)  # StateLineStyle
    bw.u(1, 1)  # StateFillStyle1
    bw.u(1, 0)  # StateFillStyle0
    bw.u(1, 1)  # StateMoveTo
    nbits = max(bits_needed(x), bits_needed(y), 1)
    bw.u(5, nbits)
    bw.s(nbits, x)
    bw.s(nbits, y)
    bw.u(1, 1)  # FillStyle1 value (NumFillBits=1)

    def edge(dx: int = 0, dy: int = 0) -> None:
        bw.u(1, 1)  # TypeFlag edge
        bw.u(1, 1)  # Straight
        n = max(bits_needed(dx), bits_needed(dy), 1)
        bw.u(4, n - 2)
        if dx and dy:
            bw.u(1, 1)  # General
            bw.s(n, dx)
            bw.s(n, dy)
        else:
            bw.u(1, 0)  # Vert/Horiz
            if dy:
                bw.u(1, 1)
                bw.s(n, dy)
            else:
                bw.u(1, 0)
                bw.s(n, dx)

    edge(dx=w)
    edge(dy=h)
    edge(dx=-w)
    edge(dy=-h)
    # EndShape
    bw.u(1, 0)
    bw.u(5, 0)
    return bw.bytes()


def _encode_bounds(x_min: int, y_min: int, x_max: int, y_max: int) -> bytes:
    bw = BitWriter()
    n = max(bits_needed(x_min), bits_needed(y_min), bits_needed(x_max), bits_needed(y_max), 1)
    bw.u(5, n)
    bw.s(n, x_min)
    bw.s(n, x_max)
    bw.s(n, y_min)
    bw.s(n, y_max)
    return bw.bytes()


def normalize_masks(masks: list[Image.Image]) -> list[Image.Image]:
    """Pad every mask to the same height (centered). Prefer ``trim_mask`` + per-glyph scale."""
    out = []
    ready = []
    for mask in masks:
        if mask.mode != "1":
            mask = mask.convert("L").point(lambda p: 255 if p > 16 else 0, mode="1")
        ready.append(mask)
    max_h = max((m.height for m in ready), default=1)
    for mask in ready:
        if mask.height == max_h:
            out.append(mask)
            continue
        canvas = Image.new("1", (mask.width, max_h), 0)
        canvas.paste(mask, (0, (max_h - mask.height) // 2))
        out.append(canvas)
    return out


def trim_mask(mask: Image.Image, pad: int = 1) -> Image.Image:
    """Crop to ink bbox so empty padding does not change EM scale."""
    if mask.mode != "1":
        mask = mask.convert("L").point(lambda p: 255 if p > 16 else 0, mode="1")
    bbox = mask.getbbox()
    if not bbox:
        return mask
    left, top, right, bottom = bbox
    left = max(0, left - pad)
    top = max(0, top - pad)
    right = min(mask.width, right + pad)
    bottom = min(mask.height, bottom + pad)
    return mask.crop((left, top, right, bottom))


# Target glyph height in EM (~Latin capital). Menu TextFields scale by fontSize/EM,
# so a short glyph looks tiny even when advance is maxed.
TARGET_EM_HEIGHT = int(EM * 0.85)
# Studio "ขนาด" at this value packs to TARGET_EM_HEIGHT — preview and game stay in sync.
PREVIEW_SIZE_BASE = 52
PREVIEW_SIZE_MIN = 24
PREVIEW_SIZE_MAX = 96


def em_height_for_size(size: int, base: int = PREVIEW_SIZE_BASE) -> int:
    """Map studio preview size → DefineFont3 EM height (same control for preview + pack)."""
    size = max(PREVIEW_SIZE_MIN, min(PREVIEW_SIZE_MAX, int(size)))
    base = max(1, int(base))
    # size=52 → 0.85·EM; size=104 would be 1.7·EM but we clamp below.
    raw = TARGET_EM_HEIGHT * size / base
    return max(int(EM * 0.35), min(int(EM * 1.15), int(round(raw))))


def glyph_y0(glyph_h: int, em_height: int, y_lift: int = 0) -> int:
    """Top of glyph in EM (y down). Center ink in the capital band [−em_height, 0].

    Older code used ``y0 = -0.75 * glyph_h`` so ~25% hung below the baseline and
    menu labels looked ชิดล่าง. ``y_lift`` (EM units) shifts further up.
    """
    y0 = -(int(em_height) + int(glyph_h)) // 2
    return y0 - int(y_lift)


def uniform_scale(masks: list[Image.Image], em_height: int = TARGET_EM_HEIGHT) -> float:
    """One scale for the whole set — sized by height, not clamped by advance width.

    Wide sentences may draw past their SI16 advance (overhang). That is OK for
    single-PUA menu labels: there is no following character to collide with.
    """
    if not masks:
        return 1.0
    max_h = max(m.height for m in masks) or 1
    return em_height / max_h


def mask_to_glyph_shape(
    mask: Image.Image,
    em_height: int = TARGET_EM_HEIGHT,
    scale: float | None = None,
    advance: int | None = None,
    align: str = "center",
    y_lift: int = 0,
    fit_width: bool = False,
) -> tuple[bytes, int, bytes]:
    """Convert an L/'1' mask image to (shape, advance, bounds) in EM units.

    Pass a shared ``scale`` and ``advance`` so every sentence glyph has the same
    visual height and the same metrics box (menu column alignment). Ink is
    centered (or left-aligned) inside that advance slot, and vertically centered
    in the capital band with optional ``y_lift``.

    ``fit_width`` shrinks scale so the ink fits in SI16 advance (≤32767). Needed
    for UI that mixes ASCII prefixes (``3. ``) or neighbor prompts — otherwise
    center+overhang paints over ``3.`` (``3ลาก่อน``) and adjacent labels.
    """
    if mask.mode != "1":
        mask = mask.convert("L").point(lambda p: 255 if p > 16 else 0, mode="1")
    w_px, h_px = mask.size
    if w_px < 1 or h_px < 1:
        return EMPTY_SHAPE, 0, EMPTY_RECT

    if scale is None:
        scale = em_height / h_px
    if fit_width and w_px > 0:
        scale = min(scale, 32767 / w_px)
    width_em = max(1, int(round(w_px * scale)))
    if advance is None:
        advance = min(32767, width_em)
    else:
        advance = max(1, min(32767, int(advance)))
    # If advance was shared/clamped smaller than ink, still don't overhang when fitting.
    if fit_width and width_em > advance:
        scale *= advance / width_em
        width_em = advance
    if align == "center":
        x_offset = (advance - width_em) // 2
    elif align == "right":
        x_offset = advance - width_em
    else:
        x_offset = 0
    glyph_h = max(1, int(round(h_px * scale)))
    y0 = glyph_y0(glyph_h, em_height, y_lift=y_lift)

    # Merge consecutive shape records into one stream: header once, then all rects, then end.
    bw = BitWriter()
    bw.u(4, 1)  # NumFillBits
    bw.u(4, 0)  # NumLineBits

    pixels = mask.load()
    min_x, min_y = advance, y0 + glyph_h
    max_x, max_y = 0, y0

    # Skip rows when scale < 1px to keep shape size reasonable.
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
            x = int(round(start * scale)) + x_offset
            x2 = int(round(col * scale)) + x_offset
            if x2 <= x:
                x2 = x + 1
            # StyleChange MoveTo + FillStyle1
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
            min_x, max_x = min(min_x, x), max(max_x, x2)
            min_y, max_y = min(min_y, y), max(max_y, y2)

    bw.u(1, 0)
    bw.u(5, 0)
    shape = bw.bytes()
    bounds = _encode_bounds(min_x, min_y, max(max_x, advance), max_y)
    return shape, advance, bounds


def solid_rect_glyph(width_em: int = EM // 2, height_em: int = EM // 2) -> tuple[bytes, int, bytes]:
    """Simple filled rectangle for Spike 1 smoke tests."""
    y0 = -int(height_em * 0.8)
    frag = _encode_rect(0, y0, width_em, height_em)
    # frag already includes style/end; prepend fill bits header by stripping... 
    # _encode_rect returns full style records without NumFillBits. Rebuild:
    bw = BitWriter()
    bw.u(4, 1)
    bw.u(4, 0)
    # re-encode rectangle inline
    body = _encode_rect(0, y0, width_em, height_em)
    # _encode_rect ends with EndShape; use it after header
    shape = bw.bytes() + body
    bounds = _encode_bounds(0, y0, width_em, y0 + height_em)
    return shape, width_em, bounds


def rgba_to_mask(img: Image.Image, threshold: int = 16) -> Image.Image:
    if img.mode != "RGBA":
        img = img.convert("RGBA")
    alpha = img.split()[-1]
    return alpha.point(lambda p: 255 if p > threshold else 0, mode="1")


# ---------------------------------------------------------------------------
# DefineFont3 read/write (subset of ThaiW3Setup swf_font)
# ---------------------------------------------------------------------------

def _rect_len(data: bytes, pos: int) -> int:
    return (5 + 4 * (data[pos] >> 3) + 7) // 8


@dataclass
class _Font3:
    head: bytes
    flags: int
    codes: list[int]
    shapes: list[bytes]
    metrics: bytes
    advances: list[int]
    bounds: list[bytes]
    kerning: bytes

    def put(self, code: int, shape: bytes, advance: int, bounds: bytes) -> None:
        if code in self.codes:
            at = self.codes.index(code)
        else:
            at = next((i for i, c in enumerate(self.codes) if c > code), len(self.codes))
            for seq, value in ((self.codes, code), (self.shapes, b""), (self.advances, 0), (self.bounds, b"")):
                seq.insert(at, value)
        self.shapes[at] = shape
        if self.flags & 0x80:
            self.advances[at], self.bounds[at] = advance, bounds


def _read_font3(d: bytes) -> _Font3:
    flags, nl = d[2], d[4]
    p = 5 + nl
    n = struct.unpack_from("<H", d, p)[0]
    table = p + 2
    fmt, size = ("<I", 4) if flags & 0x08 else ("<H", 2)
    offsets = [struct.unpack_from(fmt, d, table + i * size)[0] for i in range(n + 1)]
    shapes = [d[table + offsets[i]:table + offsets[i + 1]] for i in range(n)]
    p = table + offsets[n]
    if not flags & 0x04:
        raise ValueError("DefineFont3 without wide codes")
    codes = list(struct.unpack_from(f"<{n}H", d, p))
    p += 2 * n
    metrics, advances, bounds = b"", [0] * n, [b""] * n
    if flags & 0x80:
        metrics = d[p:p + 6]
        p += 6
        advances = list(struct.unpack_from(f"<{n}h", d, p))
        p += 2 * n
        bounds = []
        for _ in range(n):
            ln = _rect_len(d, p)
            bounds.append(d[p:p + ln])
            p += ln
    return _Font3(d[:5 + nl], flags, codes, shapes, metrics, advances, bounds, d[p:])


def _write_font3(f: _Font3) -> bytes:
    n, flags = len(f.codes), f.flags
    wide = bool(flags & 0x08)
    if not wide and (n + 1) * 2 + sum(map(len, f.shapes)) > 0xFFFF:
        wide = True
        flags |= 0x08
    fmt, size = ("<I", 4) if wide else ("<H", 2)
    pos, table = (n + 1) * size, []
    for s in f.shapes:
        table.append(struct.pack(fmt, pos))
        pos += len(s)
    table.append(struct.pack(fmt, pos))
    layout = b""
    if flags & 0x80:
        layout = f.metrics + struct.pack(f"<{n}h", *f.advances) + b"".join(f.bounds) + f.kerning
    head = f.head[:2] + bytes([flags]) + f.head[3:] + struct.pack("<H", n)
    return head + b"".join(table) + b"".join(f.shapes) + struct.pack(f"<{n}H", *f.codes) + layout


def _swf_body_from_redswf(redswf: bytes) -> tuple[int, bytes, bool, int]:
    """Return (swf_at, uncompressed_swf_bytes, packed, stored_len)."""
    at = CR2W_SWF_SIZE + 4
    sig = redswf[at:at + 3]
    if sig not in (b"FWS", b"GFX", b"CWS", b"CFX"):
        raise ValueError("not a fonts redswf")
    stored = struct.unpack_from("<I", redswf, CR2W_SWF_SIZE)[0]
    packed = sig in (b"CWS", b"CFX")
    raw = redswf[at:at + stored]
    swf = raw[:8] + zlib.decompress(raw[8:]) if packed else raw
    return at, swf, packed, stored


def _edit_fonts(redswf: bytes, edit) -> bytes:
    at, swf, packed, stored = _swf_body_from_redswf(redswf)
    nbits = swf[8] >> 3
    p = 8 + (5 + 4 * nbits + 7) // 8 + 4
    out = [swf[8:p]]
    changed = False
    while p + 2 <= len(swf):
        code_len = struct.unpack_from("<H", swf, p)[0]
        tag, ln, hp = code_len >> 6, code_len & 0x3F, p + 2
        if ln == 0x3F:
            ln = struct.unpack_from("<I", swf, hp)[0]
            hp += 4
        body = swf[hp:hp + ln]
        new = edit(body) if tag == 75 else None
        if new is None:
            out.append(swf[p:hp + ln])
        else:
            out.append(struct.pack("<HI", (tag << 6) | 0x3F, len(new)) + new)
            changed = True
        p = hp + ln
        if tag == 0:
            break
    if not changed:
        return redswf
    body = b"".join(out)
    new_swf = swf[:4] + struct.pack("<I", len(body) + 8) + body
    if packed:
        new_swf = new_swf[:8] + zlib.compress(new_swf[8:], 9)
    delta = len(new_swf) - stored
    head = bytearray(redswf[:at])
    for off in CR2W_FILE_SIZES + (CR2W_EXPORT_SIZE, CR2W_SWF_SIZE):
        struct.pack_into("<I", head, off, struct.unpack_from("<I", head, off)[0] + delta)
    return bytes(head) + new_swf + redswf[at + stored:]


def inject_glyphs(redswf: bytes, glyphs: dict[int, tuple[bytes, int, bytes]], font_index: int | None = 0) -> bytes:
    """Insert/replace PUA glyphs into DefineFont3 tags.

    ``font_index`` None = every font; int = only the N-th DefineFont3 (0 = first).
    """
    seen = {"i": 0}

    def edit(d: bytes) -> bytes | None:
        idx = seen["i"]
        seen["i"] += 1
        if font_index is not None and idx != font_index:
            return None
        f = _read_font3(d)
        for code, (shape, advance, bounds) in sorted(glyphs.items()):
            f.put(code, shape, advance, bounds or EMPTY_RECT)
        return _write_font3(f)

    return _edit_fonts(redswf, edit)


def add_empty_glyph(redswf: bytes, code: int) -> bytes:
    """Ensure every DefineFont3 has a zero-width empty glyph for ``code`` (e.g. U+200A).

    Overwrites an existing glyph at that code so a hair-space break never draws ink.
    """

    def edit(d: bytes) -> bytes | None:
        f = _read_font3(d)
        f.put(code, EMPTY_SHAPE, 0, EMPTY_RECT)
        return _write_font3(f)

    return _edit_fonts(redswf, edit)


def pixel_scale_for_em(size: int, weight: str, em_height: int) -> float:
    """One px→EM scale for a pack render size (font metrics, not per-glyph bbox).

    Using each mask's trimmed height made สระ-tall lines shrink and short lines
    blow up (ม็อด vs ออก). A single metrics-based scale keeps font size even;
    per-sentence overrides belong on ``SentenceEntry.size`` / ``.scale``.
    """
    from .render import _pil_font

    ascent, descent = _pil_font(weight, size).getmetrics()
    ref_h = max(1, int(ascent) + abs(int(descent)))
    return em_height / ref_h


def inject_mask_glyphs(
    redswf: bytes,
    items: dict[int, Image.Image],
    font_index: int | None = 0,
    em_height: int = TARGET_EM_HEIGHT,
    align: str = "center",
    y_lift: int = 0,
    shared_advance: bool = True,
    shared_scale: bool = True,
    fit_width: bool = False,
    pixel_scale: float | None = None,
    scales: dict[int, float] | None = None,
) -> bytes:
    """Embed masks as PUA glyphs.

    Prefer ``pixel_scale`` (pack-wide) or ``scales`` (per PUA code). Fall back to
    per-mask height only when neither is set. ``shared_advance`` = one slot width.
    """
    _ = shared_scale
    codes = sorted(items)
    masks = [
        trim_mask(rgba_to_mask(items[c]) if items[c].mode != "1" else items[c])
        for c in codes
    ]
    if scales is not None:
        scale_list = [float(scales[c]) for c in codes]
    elif pixel_scale is not None:
        scale_list = [float(pixel_scale)] * len(masks)
    else:
        scale_list = [em_height / (m.height or 1) for m in masks]
    if fit_width:
        scale_list = [min(s, 32767 / (m.width or 1)) for m, s in zip(masks, scale_list)]
    widths = [max(1, int(round(m.width * s))) for m, s in zip(masks, scale_list)]
    slot = min(32767, max(widths, default=1)) if shared_advance else None
    glyphs = {
        code: mask_to_glyph_shape(
            mask,
            em_height=em_height,
            scale=s,
            advance=slot if shared_advance else min(32767, w),
            align=align,
            y_lift=y_lift,
            fit_width=fit_width,
        )
        for code, mask, s, w in zip(codes, masks, scale_list, widths)
    }
    return inject_glyphs(redswf, glyphs, font_index=font_index)
