"""Increase line spacing + left-align justified Thai panels (from ThaiW3Setup).

Bitmap Thai glyphs need more leading than Latin — vowels/tones collide between lines
when the game's default leading is near zero.
"""
from __future__ import annotations

import logging
import struct
import zlib
from dataclasses import dataclass
from pathlib import Path

from .abc_patch import DO_ABC, constant_sets
from .bundle import BundleFile, iter_bundle
from .cr2w_swf import fix_crcs, read_cr2w
from .game import game_root

log = logging.getLogger(__name__)

GUI_BUNDLE = "bundles\\r4gui.bundle"
STARTUP_BUNDLE = "startup.bundle"

PANELS = (
    "gameplay\\gui_new\\swf\\glossary\\",
    "gameplay\\gui_new\\swf\\journal\\",
    "gameplay\\gui_new\\swf\\overlay\\panel_overlay.redswf",
    "gameplay\\gui_new\\swf\\noticeboard\\panel_noticeboard.redswf",
    "gameplay\\gui_new\\swf\\common\\componentslib.redswf",
    "gameplay\\gui_new\\swf\\common\\panel_common.redswf",
    "gameplay\\gui_new\\swf\\character\\panel_character.redswf",
    "gameplay\\gui_new\\swf\\loading\\",
    "gameplay\\gui_new\\swf\\mainmenu\\panel_recapmovies.redswf",
    "gameplay\\gui_new\\swf\\mainmenu\\panel_startupmovies.redswf",
    "gameplay\\gui_new\\swf\\witcher3\\hud_subtitles.redswf",
)
STARTUP_PANELS = (
    "gameplay\\gui_new\\swf\\inventory\\panel_inventory.redswf",
    "gameplay\\gui_new\\swf\\popups\\popup_tutorial.redswf",
    "gameplay\\gui_new\\swf\\hud\\hud_subtitles.redswf",
    "gameplay\\gui_new\\swf\\hud\\hud_dialog.redswf",
)
ROW_PANELS = ("gameplay\\gui_new\\swf\\common\\componentslib.redswf",)
TOOLTIP_PANELS = (
    "gameplay\\gui_new\\swf\\common\\componentslib.redswf",
    "gameplay\\gui_new\\swf\\character\\panel_character.redswf",
)

DEFINE_EDIT_TEXT = 37
DEFINE_SPRITE = 39
ALIGN_LEFT, ALIGN_JUSTIFY = 0, 3
TWIPS = 20
# Setup uses 16·TWIPS; bitmap Thai (extra mark headroom) needs more air between lines.
BODY_LEADING = 22 * TWIPS
BODY_MIN_HEIGHT = 80 * TWIPS
TOOLTIP_MIN_HEIGHT = 40 * TWIPS
ROW_GAP = 8


class LayoutError(Exception):
    pass


@dataclass
class _Field:
    align: int
    text: int
    text_len: int
    height: int
    multiline: bool


def _rect_len(d: bytes | bytearray, p: int) -> int:
    return (5 + 4 * (d[p] >> 3) + 7) // 8


def _rect_height(d: bytes | bytearray, p: int) -> int:
    nbits = d[p] >> 3
    bits = int.from_bytes(d[p:p + _rect_len(d, p)], "big") >> (_rect_len(d, p) * 8 - 5 - 4 * nbits)
    mask = (1 << nbits) - 1

    def signed(v):
        return v - (1 << nbits) if v >> (nbits - 1) else v

    return signed(bits & mask) - signed((bits >> nbits) & mask)


def _tag_spans(body: bytes | bytearray, p: int, end: int):
    while p + 2 <= end:
        code_len = struct.unpack_from("<H", body, p)[0]
        p += 2
        code, ln = code_len >> 6, code_len & 0x3F
        if ln == 0x3F:
            ln = struct.unpack_from("<I", body, p)[0]
            p += 4
        yield code, p, ln
        if code == DEFINE_SPRITE:
            yield from _tag_spans(body, p + 4, p + ln)
        p += ln
        if code == 0:
            break


def _text_fields(body: bytes | bytearray) -> list[_Field]:
    found = []
    for code, start, _ln in _tag_spans(body, _rect_len(body, 0) + 4, len(body)):
        if code != DEFINE_EDIT_TEXT:
            continue
        height = _rect_height(body, start + 2)
        p = start + 2 + _rect_len(body, start + 2)
        f1, f2 = body[p], body[p + 1]
        p += 2
        if not f2 & 0x20:
            continue
        if f1 & 0x01:
            p += 2
        if f2 & 0x80:
            p = body.index(b"\0", p) + 1
        if f1 & 0x01 or f2 & 0x80:
            p += 2
        if f1 & 0x04:
            p += 4
        if f1 & 0x02:
            p += 2
        align = p
        p = body.index(b"\0", p + 9) + 1
        text_len = body.index(b"\0", p) - p if f1 & 0x80 else 0
        found.append(_Field(align, p, text_len, height, bool(f1 & 0x20)))
    return found


def wanted_leading(f: _Field, tooltips: bool = False) -> int | None:
    if f.height >= BODY_MIN_HEIGHT or (tooltips and f.multiline and f.height >= TOOLTIP_MIN_HEIGHT):
        return BODY_LEADING
    return None


def row_padding_sites(body: bytes | bytearray) -> list[int]:
    return [
        site
        for code, start, ln in _tag_spans(body, _rect_len(body, 0) + 4, len(body))
        if code == DO_ABC
        for site in constant_sets(body, start, start + ln, "itemPadding")
    ]


def _space_rows(body: bytearray) -> int:
    sites = row_padding_sites(body)
    for site in sites:
        body[site] = (min(127, struct.unpack_from("<b", body, site)[0] + ROW_GAP)) & 0xFF
    return len(sites)


def _restyle(body: bytearray, tooltips: bool = False) -> list[_Field]:
    changed = []
    for f in _text_fields(body):
        before = bytes(body[f.align:f.align + 9])
        if body[f.align] == ALIGN_JUSTIFY:
            body[f.align] = ALIGN_LEFT
        want = wanted_leading(f, tooltips)
        if want is not None:
            leading = struct.unpack_from("<h", body, f.align + 7)[0]
            struct.pack_into("<h", body, f.align + 7, max(leading, want))
        if body[f.align:f.align + 9] != before:
            changed.append(f)
    return changed


def _deflate(body: bytes) -> bytes:
    try:
        import deflate

        return deflate.zlib_compress(body, 12)
    except Exception:
        return zlib.compress(body, 9)


def restyle_panel(
    data: bytes,
    rows: bool = False,
    tooltips: bool = False,
) -> bytes | None:
    cr2w = read_cr2w(data)
    resource = next((e for e in cr2w.exports if e.cls == "CSwfResource"), None)
    if resource is None:
        raise LayoutError("no CSwfResource")
    at = data.find(b"CFX", resource.props_end, resource.offset + resource.size)
    if at < 0:
        raise LayoutError("no compressed SWF")
    inflater = zlib.decompressobj()
    body = bytearray(inflater.decompress(data[at + 8:resource.offset + resource.size]))
    stream_len = resource.offset + resource.size - at - 8 - len(inflater.unused_data)
    fields = _restyle(body, tooltips)
    spaced = _space_rows(body) if rows else 0
    if not fields and not spaced:
        return None
    stream = _deflate(bytes(body))
    if len(stream) > stream_len:
        for f in fields:
            body[f.text:f.text + f.text_len] = b" " * f.text_len
        stream = _deflate(bytes(body))
    if len(stream) > stream_len:
        raise LayoutError(f"recompressed SWF is {len(stream) - stream_len} bytes larger")
    out = bytearray(data)
    struct.pack_into("<I", out, at + 4, len(body) + 8)
    out[at + 8:at + 8 + stream_len] = stream + bytes(stream_len - len(stream))
    fix_crcs(out, cr2w, {resource.index})
    return bytes(out)


def panel_files(game: Path | None = None, progress=None) -> list[BundleFile]:
    """Restyle journal/glossary/character/tooltip panels from the local game install."""
    content0 = game_root(game) / "content" / "content0"
    files: list[BundleFile] = []
    found = [
        *iter_bundle(
            content0 / "bundles" / "r4gui.bundle",
            lambda n, _s: n.startswith(PANELS) and n.endswith(".redswf"),
        ),
        *iter_bundle(
            content0 / "bundles" / STARTUP_BUNDLE,
            lambda n, _s: n in STARTUP_PANELS,
        ),
    ]
    for i, f in enumerate(found):
        name = f.path.rsplit("\\", 1)[-1]
        if progress:
            progress(i + 1, len(found), name)
        try:
            data = restyle_panel(f.data, f.path in ROW_PANELS, f.path in TOOLTIP_PANELS)
        except (LayoutError, ValueError, struct.error) as exc:
            log.warning("panel %s left as is: %s", name, exc)
            continue
        if data is not None:
            files.append(BundleFile(f.path, data))
    return files
