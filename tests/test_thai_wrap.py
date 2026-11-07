from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core.thai_wrap import BREAK, prepare


def test_wrap_inserts_hair_spaces():
    text = "เกราลด์พบวิญญาณของผู้หญิง"
    out = prepare(text)
    assert BREAK in out
    assert out.replace(BREAK, "") == text or out.replace(BREAK, "").rstrip("\u00a0") == text


def test_short_menu_still_ok():
    assert "ออก" in prepare("ออก")


def test_mixed_english_preserved():
    text = "Geralt พบ Anabelle ที่ Fyke Isle"
    out = prepare(text)
    assert "Geralt" in out
    assert "Anabelle" in out
    assert "Fyke" in out
