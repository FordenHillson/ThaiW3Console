"""Spike 6: full Thai translation via per-character PUA glyphs.

Loads ThaiW3Setup translations.json.gz, encodes every matched en.w3strings id as
a PUA sequence, injects a small Thai bitmap charset into fonts_en.redswf, installs
mods/modThaiConsole.

Usage:
  python spikes/06_full_char_pack.py --install
  python spikes/06_full_char_pack.py --install --size 64 --em-scale 1.30
  python spikes/06_full_char_pack.py              # export only under export/spike6
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core.extra_sheet import SHEET_ID, load_extra_translations
from core.pack_char import merge_translations, pack_char_translation
from core.paths import repo_root
from core.setup_translations import find_setup_translations


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--install", action="store_true")
    ap.add_argument("--game", type=Path, default=None)
    ap.add_argument("--size", type=int, default=64)
    ap.add_argument("--em-scale", type=float, default=1.30)
    ap.add_argument("--weight", default="Bold")
    ap.add_argument("--y-lift", type=int, default=0)
    ap.add_argument("--refresh-extra", action="store_true", help="re-download extra Google Sheet")
    ap.add_argument("--no-extra", action="store_true", help="skip supplementary sheet")
    ap.add_argument("--no-layout", action="store_true", help="skip panel leading / left-align patch")
    args = ap.parse_args()

    src = find_setup_translations()
    if src is None:
        print("ERROR: ThaiW3Setup translations.json.gz not found")
        return 1
    print(f"translations: {src}")

    t0 = time.perf_counter()
    if not args.no_extra:
        extra = load_extra_translations(force=args.refresh_extra)
        print(
            f"extra sheet: {SHEET_ID} → {len(extra.thai):,} ids "
            f"({extra.source}, tabs={extra.by_tab})"
        )

    by_id = merge_translations(
        game=args.game,
        force_menu=True,
        use_extra_sheet=not args.no_extra,
        force_extra=args.refresh_extra,
    )
    print(f"merged Thai ids: {len(by_id):,}")
    # Spot-check skill / monster names from the extra sheet.
    for sid, label in (
        (1066845, "Muscle Memory title"),
        (1449743, "Muscle Memory desc"),
        (1176357, "Garkains"),
    ):
        th = by_id.get(sid)
        print(f"  check {label} ({sid}): {(th or '(missing)')[:80]!r}")

    out = repo_root() / "export" / "spike6"
    out.mkdir(parents=True, exist_ok=True)
    dest = None if args.install else (out / "modThaiConsole")

    def progress(stage: str, a: int, b: int) -> None:
        print(f"  [{stage}] {a:,}/{b:,}")

    path, report = pack_char_translation(
        by_id,
        game=args.game,
        dest=dest,
        size=args.size,
        weight=args.weight,
        y_lift=args.y_lift,
        em_scale=args.em_scale,
        layout_panels=not args.no_layout,
        progress=progress,
    )
    elapsed = time.perf_counter() - t0
    report["elapsed_s"] = round(elapsed, 1)
    (out / "report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    mb = report["mod_total_bytes"] / (1024 * 1024)
    font_mb = report["fonts_en_bytes"] / (1024 * 1024)
    str_mb = report["en_w3strings_bytes"] / (1024 * 1024)
    print(f"mod written: {path}")
    print(
        f"charset={report['charset_total']} "
        f"(base={report['charset_base']} high={report['charset_high_tones']}) "
        f"ids={report['ids']:,}  word_breaks={report.get('word_breaks', 0):,}  "
        f"panels={report.get('panels_restyled', 0)}"
    )
    print(f"chars: {report['chars']!r}")
    print(f"high tones: {report['high_tones']!r}")
    print(f"size: fonts_en={font_mb:.2f} MB  w3strings={str_mb:.2f} MB  total={mb:.2f} MB  ({elapsed:.1f}s)")
    print("Restart game · Text Language = English · check bestiary/skill wrapping (hair-space breaks).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
