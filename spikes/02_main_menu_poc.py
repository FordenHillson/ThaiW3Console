"""Spike 3: pack main-menu POC on string ids confirmed in-game.

Usage:
  python spikes/02_main_menu_poc.py --install
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core.pack_mod import MENU_POC, SentenceEntry, pack_mod
from core.paths import repo_root
from core.render import preview_on_dark, render_sentence
from core.sheet import load_translations


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--install", action="store_true")
    ap.add_argument("--game", type=Path, default=None)
    ap.add_argument("--size", type=int, default=64)
    ap.add_argument("--offline", action="store_true")
    args = ap.parse_args()

    thai: dict[int, str] = {}
    if not args.offline:
        try:
            tr = load_translations()
            thai = tr.thai
            print(f"sheet: {len(thai)} strings ({tr.source}, {tr.age_text})")
        except Exception as exc:
            print(f"sheet unavailable ({exc}); using fallbacks")

    entries: list[SentenceEntry] = []
    for i, (sid, fallback) in enumerate(MENU_POC):
        text = (thai.get(sid) or fallback).strip()
        if "<" in text:
            text = re.sub(r"<[^>]+>", "", text)
        entries.append(SentenceEntry(sid, text or fallback, i))

    out = repo_root() / "export" / "spike3"
    out.mkdir(parents=True, exist_ok=True)
    mapping = []
    for e in entries:
        render_sentence(e.thai, size=args.size).save(out / f"{e.string_id}.png")
        preview_on_dark(e.thai, size=args.size).save(out / f"{e.string_id}_preview.png")
        mapping.append({"id": e.string_id, "thai": e.thai, "pua": f"U+{e.code:04X}"})
        print(f"{e.string_id}: {e.thai!r} → U+{e.code:04X}")
    (out / "mapping.json").write_text(json.dumps(mapping, ensure_ascii=False, indent=2), encoding="utf-8")

    dest = None if args.install else (out / "modThaiConsole")
    path = pack_mod(entries, game=args.game, dest=dest, size=args.size)
    print(f"mod written: {path}")
    print("Restart game, Text Language = English, check main menu for Thai glyphs.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
