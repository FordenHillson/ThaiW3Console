from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core.render import render_sentence
from core.swf_bitmap_glyph import (
    mask_to_glyph_shape,
    normalize_masks,
    pua_code,
    rgba_to_mask,
    solid_rect_glyph,
    uniform_scale,
)


def test_render_thai_nonempty():
    img = render_sentence("เกมใหม่", size=48)
    assert img.width > 10 and img.height > 10
    assert img.mode == "RGBA"


def test_mask_to_shape():
    img = render_sentence("ทดสอบ", size=32)
    shape, advance, bounds = mask_to_glyph_shape(rgba_to_mask(img))
    assert advance > 0
    assert len(shape) > 4
    assert len(bounds) >= 1


def test_uniform_scale_and_shared_advance():
    from core.swf_bitmap_glyph import TARGET_EM_HEIGHT

    short = rgba_to_mask(render_sentence("ออก", size=48))
    long = rgba_to_mask(render_sentence("ไฮไลต์แพตช์", size=48))
    masks = normalize_masks([short, long])
    scale = uniform_scale(masks)
    slot = min(32767, max(int(round(m.width * scale)) for m in masks))
    _s1, adv_short, _ = mask_to_glyph_shape(masks[0], scale=scale, advance=slot, align="center")
    _s2, adv_long, _ = mask_to_glyph_shape(masks[1], scale=scale, advance=slot, align="center")
    assert adv_short == adv_long == slot
    assert masks[0].height == masks[1].height
    assert abs(scale * masks[0].height - TARGET_EM_HEIGHT) < 2


def test_solid_rect():
    shape, advance, bounds = solid_rect_glyph(1000, 800)
    assert advance == 1000
    assert shape[:1] == b"\x10" or shape[0] >> 4 == 1


def test_pua():
    assert pua_code(0) == 0xE000
    assert pua_code(2) == 0xE002


def test_size_syncs_em_height():
    from core.swf_bitmap_glyph import PREVIEW_SIZE_BASE, TARGET_EM_HEIGHT, em_height_for_size

    assert em_height_for_size(PREVIEW_SIZE_BASE) == TARGET_EM_HEIGHT
    assert em_height_for_size(PREVIEW_SIZE_BASE * 2) > em_height_for_size(PREVIEW_SIZE_BASE)
    assert em_height_for_size(24) < em_height_for_size(52)
