from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core.char_glyphs import (
    build_char_atlas,
    encode_thai,
    is_combining_mark,
    preview_encoded,
    render_char_cell,
)


def test_marks_detected():
    assert is_combining_mark("่")
    assert is_combining_mark("ิ")
    assert is_combining_mark("ุ")
    assert not is_combining_mark("ก")
    assert not is_combining_mark("า")
    assert not is_combining_mark("เ")


def test_mark_advance_zero():
    base = render_char_cell("ก", size=48)
    mark = render_char_cell("่", size=48)
    assert base.advance_px > 0
    assert mark.advance_px == 0
    assert mark.pen_x_px >= 0


def test_high_tone_after_sara_i():
    text = "เริ่มเกมใหม่"
    atlas = build_char_atlas([text])
    assert "่" in atlas.high_tone
    pua = encode_thai(text, atlas)
    # เ ร ิ ่ … — 4th char is raised ่, not base ่
    assert len(pua) == len(text)
    base_mai_ek = atlas.base["่"]
    high_mai_ek = atlas.high_tone["่"]
    assert ord(pua[3]) == high_mai_ek
    assert ord(pua[3]) != base_mai_ek
    # เล่น has ่ on consonant (after ล) — base form
    atlas2 = build_char_atlas(["เล่น", text])
    pua2 = encode_thai("เล่น", atlas2)
    assert ord(pua2[2]) == atlas2.base["่"]


def test_raised_cell_higher_ink():
    low = render_char_cell("่", size=60, raised=False)
    high = render_char_cell("่", size=60, raised=True)
    assert high.image.height == low.image.height

    def top_ink(img):
        px = img.split()[-1]
        for y in range(px.height):
            for x in range(px.width):
                if px.getpixel((x, y)) > 16:
                    return y
        return px.height

    assert top_ink(high.image) < top_ink(low.image)


def test_preview_composites():
    text = "เริ่ม"
    atlas = build_char_atlas([text])
    img = preview_encoded(text, atlas, size=40)
    assert img.width > 10 and img.height > 10


def test_ascii_passthrough():
    atlas = build_char_atlas(["น้ำยา Swallow"])
    pua = encode_thai("น้ำยา Swallow", atlas)
    assert "Swallow" in pua
    assert " " in pua
    assert not any(0x0E00 <= ord(c) <= 0x0E7F for c in pua)
    assert any(0xE000 <= ord(c) <= 0xF8FF for c in pua)
