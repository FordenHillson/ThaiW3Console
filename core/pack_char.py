"""Pack modThaiConsole using per-character PUA glyphs (full-translation path)."""
from __future__ import annotations

import shutil
from pathlib import Path

from .bundle import BundleFile, write_bundle
from .char_glyphs import CharAtlas, build_char_atlas, encode_thai, inject_char_font
from .game import en_w3strings_path, extract_fonts_en, mods_dir
from .metastore import BundleLayout, build_metastore
from .pack_mod import MENU_POC, MOD_NAME
from .extra_sheet import load_extra_translations
from .setup_translations import has_thai, load_setup_translations, normalize_en, strip_tags
from .swf_bitmap_glyph import FONT_PATH, PREVIEW_SIZE_BASE, add_empty_glyph
from .thai_wrap import BREAK, prepare
from .w3strings import W3Strings


def merge_translations(
    *,
    game: Path | None = None,
    force_menu: bool = True,
    use_extra_sheet: bool = True,
    force_extra: bool = False,
) -> dict[int, str]:
    """Thai strings keyed by game ``en.w3strings`` ids.

    Layer order: Setup cache → EN→TH fallback → extra Google Sheet (names + backlog)
    → MENU_POC holes. Extra sheet wins on conflict (newer proper names / skill blurbs).
    """
    setup = load_setup_translations()
    w = W3Strings.load(en_w3strings_path(game), "en")
    game_ids = set(w.strings)
    merged: dict[int, str] = {}

    for sid, text in setup.thai.items():
        if sid not in game_ids:
            continue
        t = strip_tags(text)
        if t and has_thai(t):
            merged[sid] = t

    for sid, en in w.strings.items():
        if sid in merged:
            continue
        th = setup.by_text.get(normalize_en(en))
        if th and has_thai(th):
            merged[sid] = th

    if use_extra_sheet:
        extra = load_extra_translations(force=force_extra)
        for sid, text in extra.thai.items():
            if sid not in game_ids:
                continue
            t = strip_tags(text)
            if t and has_thai(t):
                merged[sid] = t

    if force_menu:
        for sid, fallback in MENU_POC:
            if sid in game_ids and sid not in merged:
                merged[sid] = fallback

    return merged


def pack_char_translation(
    by_id: dict[int, str],
    *,
    game: Path | None = None,
    dest: Path | None = None,
    size: int = PREVIEW_SIZE_BASE,
    weight: str = "Bold",
    y_lift: int = 0,
    em_scale: float = 1.30,
    layout_panels: bool = True,
    progress=None,
) -> tuple[Path, dict]:
    """Build fonts + encoded en.w3strings (+ optional panel leading) and write mod."""
    texts = list(by_id.values())
    atlas = build_char_atlas(texts, always_high_tones=True)
    if progress:
        progress("atlas", atlas.glyph_count, len(by_id))

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
    # Hair-space word breaks need a zero-width glyph or Scaleform draws a gap.
    fonts = add_empty_glyph(fonts, ord(BREAK))
    if progress:
        progress("fonts", len(fonts), atlas.glyph_count)

    src = en_w3strings_path(game)
    w = W3Strings.load(src, "en")
    n = len(by_id)
    wrap_breaks = 0
    for i, (sid, text) in enumerate(sorted(by_id.items())):
        prepared = prepare(text)
        wrap_breaks += prepared.count(BREAK)
        w.strings[sid] = encode_thai(prepared, atlas)
        if progress and (i % 5000 == 0 or i + 1 == n):
            progress("strings", i + 1, n)
    strings = w.build()

    files = [
        BundleFile(FONT_PATH, fonts),
        BundleFile("en.w3strings", strings),
    ]
    panels_n = 0
    if layout_panels:
        from .panel_layout import panel_files

        def panel_progress(a, b, name=""):
            if progress:
                progress("panels", a, b)

        panels = panel_files(game, progress=panel_progress)
        files.extend(panels)
        panels_n = len(panels)
        if progress:
            progress("panels_done", panels_n, panels_n)

    root = dest or (mods_dir(game) / MOD_NAME)
    if root.exists():
        shutil.rmtree(root)
    content = root / "content"
    content.mkdir(parents=True, exist_ok=True)
    size_b, data_off, entries = write_bundle(content / "blob0.bundle", files)
    (content / "metadata.store").write_bytes(
        build_metastore(BundleLayout("blob0.bundle", size_b, data_off, entries))
    )
    (content / "en.w3strings").write_bytes(strings)

    report = {
        "ids": len(by_id),
        "charset_base": len(atlas.base),
        "charset_high_tones": len(atlas.high_tone),
        "charset_total": atlas.glyph_count,
        "chars": "".join(sorted(atlas.base)),
        "high_tones": "".join(sorted(atlas.high_tone)),
        "word_breaks": wrap_breaks,
        "panels_restyled": panels_n,
        "size": size,
        "em_scale": em_scale,
        "weight": weight,
        "fonts_en_bytes": len(fonts),
        "en_w3strings_bytes": len(strings),
        "mod_total_bytes": sum(f.stat().st_size for f in content.rglob("*") if f.is_file()),
        "mod_path": str(root),
        "sample": _samples(by_id, atlas),
    }
    return root, report


def _samples(by_id: dict[int, str], atlas: CharAtlas, n: int = 12) -> list[dict]:
    from .pack_mod import MENU_POC

    rows = []
    for sid, _ in MENU_POC:
        if sid in by_id:
            th = by_id[sid]
            prepared = prepare(th)
            rows.append(
                {
                    "id": sid,
                    "thai": th,
                    "wrapped": prepared.replace(BREAK, "|"),
                    "encoded": encode_thai(prepared, atlas)[:80],
                }
            )
    for sid in sorted(by_id)[:n]:
        if any(r["id"] == sid for r in rows):
            continue
        th = by_id[sid]
        prepared = prepare(th)
        rows.append(
            {
                "id": sid,
                "thai": th[:60],
                "wrapped": prepared.replace(BREAK, "|")[:80],
                "encoded": encode_thai(prepared, atlas)[:40],
            }
        )
        if len(rows) >= n:
            break
    return rows
