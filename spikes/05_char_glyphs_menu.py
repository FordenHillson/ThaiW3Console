"""Spike 5: per-character PUA glyphs for main-menu Thai (not whole-sentence glyphs).

Renders each unique Thai letter as a DefineFont3 glyph, encodes menu strings as
PUA sequences. Combining marks use advance=0 + left overhang. Tone marks after
above-vowels use a raised PUA variant (Flash has no Thai shaping).

Usage:
  python spikes/05_char_glyphs_menu.py           # export only
  python spikes/05_char_glyphs_menu.py --install # write mods/modThaiConsole
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core.bundle import BundleFile, write_bundle
from core.char_glyphs import (
    ABOVE_VOWELS,
    TONE_MARKS,
    build_char_atlas,
    encode_thai,
    inject_char_font,
    is_combining_mark,
    preview_encoded,
    render_char_cell,
    tone_raise_px,
)
from core.game import en_w3strings_path, extract_fonts_en, mods_dir
from core.metastore import BundleLayout, build_metastore
from core.pack_mod import MENU_POC, MOD_NAME
from core.paths import repo_root
from core.swf_bitmap_glyph import FONT_PATH
from core.w3strings import W3Strings


def _menu_thai(offline: bool) -> list[tuple[int, str]]:
    thai: dict[int, str] = {}
    if not offline:
        try:
            from core.sheet import load_translations

            tr = load_translations()
            thai = tr.thai
            print(f"sheet: {len(thai)} strings ({tr.source}, {tr.age_text})")
        except Exception as exc:
            print(f"sheet unavailable ({exc}); using fallbacks")

    out: list[tuple[int, str]] = []
    for sid, fallback in MENU_POC:
        text = (thai.get(sid) or fallback).strip()
        if "<" in text:
            text = re.sub(r"<[^>]+>", "", text)
        out.append((sid, text or fallback))
    return out


def pack_char_menu(
    items: list[tuple[int, str]],
    *,
    game: Path | None,
    dest: Path | None,
    size: int,
    weight: str,
    y_lift: int,
    em_scale: float,
) -> tuple[Path, dict]:
    texts = [t for _, t in items]
    atlas = build_char_atlas(texts)
    print(
        f"charset: {atlas.glyph_count} glyphs "
        f"(base={len(atlas.base)}, high_tones={len(atlas.high_tone)})"
    )
    print(f"tone raise: {tone_raise_px(size, weight)}px @ size={size}")
    print(f"high tones: {list(atlas.high_tone)!r}  above vowels: {sorted(ABOVE_VOWELS)!r}")

    redswf = extract_fonts_en(game)
    fonts = inject_char_font(
        redswf,
        atlas,
        size=size,
        weight=weight,
        y_lift=y_lift,
        font_index=None,
        em_scale=em_scale,
    )

    src = en_w3strings_path(game)
    w = W3Strings.load(src, "en")
    encoded_rows = []
    for sid, text in items:
        pua = encode_thai(text, atlas)
        w.strings[sid] = pua
        encoded_rows.append(
            {
                "id": sid,
                "thai": text,
                "pua": " ".join(f"U+{ord(c):04X}" for c in pua),
                "n_chars": len(text),
            }
        )
    strings = w.build()

    files = [
        BundleFile(FONT_PATH, fonts),
        BundleFile("en.w3strings", strings),
    ]
    root = dest or (mods_dir(game) / MOD_NAME)
    if root.exists():
        import shutil

        shutil.rmtree(root)
    content = root / "content"
    content.mkdir(parents=True, exist_ok=True)
    size_b, data_off, entries = write_bundle(content / "blob0.bundle", files)
    (content / "metadata.store").write_bytes(
        build_metastore(BundleLayout("blob0.bundle", size_b, data_off, entries))
    )
    (content / "en.w3strings").write_bytes(strings)

    report = {
        "charset_size": atlas.glyph_count,
        "base_chars": {ch: f"U+{code:04X}" for ch, code in atlas.base.items()},
        "high_tones": {ch: f"U+{code:04X}" for ch, code in atlas.high_tone.items()},
        "size": size,
        "em_scale": em_scale,
        "menu": encoded_rows,
        "fonts_en_bytes": len(fonts),
        "en_w3strings_bytes": len(strings),
        "mod_total_bytes": sum(f.stat().st_size for f in content.rglob("*") if f.is_file()),
        "mod_path": str(root),
    }
    return root, report


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--install", action="store_true")
    ap.add_argument("--game", type=Path, default=None)
    ap.add_argument("--size", type=int, default=64)
    ap.add_argument("--em-scale", type=float, default=1.30, help="glyph EM scale vs size base (~+30%%)")
    ap.add_argument("--weight", default="Bold")
    ap.add_argument("--y-lift", type=int, default=0)
    ap.add_argument("--offline", action="store_true")
    args = ap.parse_args()

    items = _menu_thai(args.offline)
    out = repo_root() / "export" / "spike5"
    out.mkdir(parents=True, exist_ok=True)

    atlas = build_char_atlas([t for _, t in items])
    for ch, code in atlas.base.items():
        cell = render_char_cell(ch, size=args.size, weight=args.weight)
        safe = ch if ch.isprintable() and ch != " " else f"U+{ord(ch):04X}"
        cell.image.save(out / f"char_{code:04X}.png")
        print(f"  {safe!r} → U+{code:04X} adv={cell.advance_px} mark={is_combining_mark(ch)}")
    for ch, code in atlas.high_tone.items():
        cell = render_char_cell(ch, size=args.size, weight=args.weight, raised=True)
        cell.image.save(out / f"char_{code:04X}_high.png")
        print(f"  high {ch!r} → U+{code:04X} raise={tone_raise_px(args.size, args.weight)}px")

    for sid, text in items:
        preview_encoded(text, atlas, size=args.size, weight=args.weight).save(
            out / f"preview_{sid}.png"
        )
        print(f"{sid}: {text!r}")

    # Side-by-side stacking check for the known bug word.
    preview_encoded("เริ่ม", atlas, size=args.size, weight=args.weight).save(out / "stack_roem.png")

    dest = None if args.install else (out / "modThaiConsole")
    path, report = pack_char_menu(
        items,
        game=args.game,
        dest=dest,
        size=args.size,
        weight=args.weight,
        y_lift=args.y_lift,
        em_scale=args.em_scale,
    )
    (out / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    mb = report["mod_total_bytes"] / (1024 * 1024)
    font_mb = report["fonts_en_bytes"] / (1024 * 1024)
    print(f"mod written: {path}")
    print(
        f"size: fonts_en={font_mb:.2f} MB  mod_total={mb:.2f} MB  "
        f"render={args.size} em_scale={args.em_scale}"
    )
    print("Restart game · Text Language = English · check เริ่ม (ิ + ่) stacking.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
