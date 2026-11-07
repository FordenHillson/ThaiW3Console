"""Spike 4: pack translated strings from ThaiW3Setup and measure mod size.

Default: fill BMP PUA (~6400 unique texts), shortest first (UI-like), one font.
Also prints a full-corpus size estimate from length-bucket samples.

Usage:
  python spikes/03_pack_size.py
  python spikes/03_pack_size.py --max-unique 500 --max-chars 40
  python spikes/03_pack_size.py --install --fonts all
  python spikes/03_pack_size.py --estimate-only
"""
from __future__ import annotations

import argparse
import json
import random
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core.bundle import iter_bundle
from core.game import en_w3strings_path
from core.pack_mod import MENU_POC, pack_mod
from core.paths import repo_root
from core.render import render_sentence
from core.setup_translations import load_setup_translations, select_for_pack
from core.swf_bitmap_glyph import (
    FONT_PATH,
    em_height_for_size,
    mask_to_glyph_shape,
    rgba_to_mask,
)
from core.w3strings import W3Strings

PUA_ROOM = 0xF8FF - 0xE000 + 1


def _dir_size(path: Path) -> int:
    return sum(p.stat().st_size for p in path.rglob("*") if p.is_file())


def _fmt(n: int) -> str:
    if n >= 1_000_000:
        return f"{n / 1_000_000:.2f} MB"
    if n >= 1_000:
        return f"{n / 1_000:.1f} KB"
    return f"{n} B"


def estimate_full(thai_texts: list[str], size: int, samples_per_bucket: int = 10) -> dict:
    random.seed(7)
    em_h = em_height_for_size(size)
    buckets = [
        ("UI short", 1, 15),
        ("UI/mid", 16, 40),
        ("line", 41, 100),
        ("dialogue", 101, 250),
        ("long", 251, 600),
    ]
    medians: dict[str, int] = {}
    for label, lo, hi in buckets:
        pool = [t for t in thai_texts if lo <= len(t) <= hi]
        if not pool:
            continue
        sample = pool if len(pool) <= samples_per_bucket else random.sample(pool, samples_per_bucket)
        shapes = []
        for t in sample:
            shape, _, _ = mask_to_glyph_shape(
                rgba_to_mask(render_sentence(t, size=size, weight="Regular")),
                em_height=em_h,
                align="left",
            )
            shapes.append(len(shape))
        medians[label] = int(statistics.median(shapes))
        print(f"  estimate {label:10} n={len(sample):2} shape_med={medians[label]:,} B  pool={len(pool):,}")

    total = 0
    counts = {label: 0 for label, _, _ in buckets}
    counts["overflow"] = 0
    for t in set(thai_texts):
        L = len(t)
        placed = False
        for label, lo, hi in buckets:
            if lo <= L <= hi and label in medians:
                total += medians[label]
                counts[label] += 1
                placed = True
                break
        if not placed:
            total += medians.get("long", medians.get("dialogue", 100_000))
            counts["overflow"] += 1
    return {"shape_bytes_1font": total, "counts": counts, "medians": medians}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--install", action="store_true", help="write into game mods/")
    ap.add_argument("--game", type=Path, default=None)
    ap.add_argument("--size", type=int, default=64, help="render size → EM height (larger = closer to menu POC)")
    ap.add_argument("--max-unique", type=int, default=PUA_ROOM)
    ap.add_argument("--max-chars", type=int, default=50,
                    help="skip long lines as sentence glyphs (they force tiny fit_width or huge overhang)")
    ap.add_argument("--min-chars", type=int, default=1)
    ap.add_argument("--fonts", choices=("one", "all"), default="one",
                    help="one=DefineFont3#0 only; all=every font (≈3× glyph data)")
    ap.add_argument("--estimate-only", action="store_true")
    ap.add_argument("--weight", default="Bold")
    args = ap.parse_args()

    out = repo_root() / "export" / "spike4"
    out.mkdir(parents=True, exist_ok=True)

    tr = load_setup_translations()
    print(f"ThaiW3Setup translations: {len(tr.thai):,} ids + {len(tr.by_text):,} by_text from {tr.source}")

    game_strings = W3Strings.load(en_w3strings_path(args.game), "en").strings
    game_ids = set(game_strings)
    print(f"game en.w3strings ids: {len(game_ids):,}")

    uniq_texts = list({t for t in tr.thai.values() if t})
    print(f"unique Thai texts in sheet: {len(uniq_texts):,}")
    print("Full-corpus shape estimate (sampled)…")
    est = estimate_full(uniq_texts, size=args.size)
    print(
        f"  → shapes only ≈ {_fmt(est['shape_bytes_1font'])} (1 font), "
        f"≈ {_fmt(est['shape_bytes_1font'] * 3)} (3 fonts)"
    )
    print(f"  PUA room BMP = {PUA_ROOM}; unique texts = {len(uniq_texts):,}")

    if args.estimate_only:
        report = {
            "estimate": est,
            "unique_texts": len(uniq_texts),
            "pua_room": PUA_ROOM,
            "setup_ids": len(tr.thai),
        }
        (out / "size_report.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"wrote {out / 'size_report.json'}")
        return 0

    sel = select_for_pack(
        tr.thai,
        game_ids=game_ids,
        game_en=game_strings,
        by_text=tr.by_text,
        force=MENU_POC,
        max_unique=args.max_unique,
        max_chars=args.max_chars,
        min_chars=args.min_chars,
    )
    entries = sel.entries()
    print(
        f"selected: {len(sel.by_id):,} string ids → {sel.unique_count:,} unique glyphs "
        f"(max_chars≤{args.max_chars})"
    )
    for sid, label in ((1236547, "Mods"), (1469941, "Patch Highlights")):
        print(f"  force-check {label}: {sel.by_id.get(sid)!r}")
    if not entries:
        print("nothing to pack")
        return 1

    font_index = 0 if args.fonts == "one" else None
    t0 = time.time()

    def progress(done: int, total: int, sample: str) -> None:
        print(f"  render {done}/{total}  {sample!r}", flush=True)

    dest = None if args.install else (out / "modThaiConsole")
    # Full EM height for every glyph (no fit_width): size stays even.
    # Left align so wide glyphs overhang right only — keeps "3. ลาก่อน" readable.
    # Long footers stay English via --max-chars to limit neighbor overlap.
    path = pack_mod(
        entries,
        game=args.game,
        dest=dest,
        size=args.size,
        weight=args.weight,
        font_index=font_index,
        shared_advance=False,
        shared_scale=False,
        fit_width=False,
        align="left",
        progress=progress,
    )
    elapsed = time.time() - t0

    fonts_bytes = 0
    for bf in iter_bundle(path / "content" / "blob0.bundle", lambda n, _: n == FONT_PATH):
        fonts_bytes = len(bf.data)
        (out / "fonts_en.redswf").write_bytes(bf.data)
        break
    strings_path = path / "content" / "en.w3strings"
    strings_bytes = strings_path.stat().st_size if strings_path.is_file() else 0
    bundle_bytes = (path / "content" / "blob0.bundle").stat().st_size
    total_bytes = _dir_size(path)

    report = {
        "elapsed_s": round(elapsed, 1),
        "ids": len(sel.by_id),
        "unique_glyphs": sel.unique_count,
        "max_chars": args.max_chars,
        "render_size": args.size,
        "fonts": args.fonts,
        "fonts_en_redswf_bytes": fonts_bytes,
        "en_w3strings_bytes": strings_bytes,
        "blob0_bundle_bytes": bundle_bytes,
        "mod_total_bytes": total_bytes,
        "estimate_full_1font_bytes": est["shape_bytes_1font"],
        "pua_room": PUA_ROOM,
        "unique_in_sheet": len(uniq_texts),
        "mod_path": str(path),
        "sample": [
            {"id": e.string_id, "thai": e.thai, "pua": f"U+{e.code:04X}"}
            for e in entries[:20]
        ],
    }
    (out / "size_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (out / "mapping.json").write_text(
        json.dumps(
            [{"id": e.string_id, "thai": e.thai, "pua": f"U+{e.code:04X}"} for e in entries],
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print("---")
    print(f"mod:              {path}")
    print(f"unique glyphs:    {sel.unique_count:,}")
    print(f"fonts_en.redswf:  {_fmt(fonts_bytes)}")
    print(f"en.w3strings:     {_fmt(strings_bytes)}")
    print(f"blob0.bundle:     {_fmt(bundle_bytes)}")
    print(f"mod total:        {_fmt(total_bytes)}  ({elapsed:.0f}s)")
    print(f"report:           {out / 'size_report.json'}")
    if args.fonts == "one":
        print(f"note: fonts=one → if injected into all 3 fonts ≈ {_fmt(fonts_bytes * 3)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
