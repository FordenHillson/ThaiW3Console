"""Spike 1: inject a solid-rect / short Thai mask as PUA glyph and pack a test mod.

Usage:
  python spikes/01_bitmap_glyph_swf.py [--install] [--game PATH]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core.pack_mod import SentenceEntry, pack_mod
from core.paths import repo_root
from core.render import render_sentence, preview_on_dark
from core.swf_bitmap_glyph import pua_code


# New game / Continue / Quit
ENTRIES = [
    SentenceEntry(1065947, "ทดสอบ", 0),
    SentenceEntry(1065946, "ดำเนินการต่อ", 1),
    SentenceEntry(1066024, "ออก", 2),
]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--install", action="store_true", help="write into game mods/")
    ap.add_argument("--game", type=Path, default=None)
    ap.add_argument("--size", type=int, default=48)
    args = ap.parse_args()

    out = repo_root() / "export" / "spike1"
    out.mkdir(parents=True, exist_ok=True)
    for e in ENTRIES:
        img = render_sentence(e.thai, size=args.size, weight="Bold")
        img.save(out / f"pua_{e.pua_index:04x}_{e.string_id}.png")
        preview_on_dark(e.thai, size=args.size).save(out / f"preview_{e.pua_index}.png")
        print(f"PUA U+{pua_code(e.pua_index):04X} id={e.string_id} {e.thai!r} → {img.size}")

    dest = None if args.install else (out / "modThaiConsole")
    path = pack_mod(ENTRIES, game=args.game, dest=dest, size=args.size)
    print(f"mod written: {path}")
    print("Set Text Language to English, then check main menu New game / Continue / Quit.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
