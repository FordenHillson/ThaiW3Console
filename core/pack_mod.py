"""Build and install modThaiConsole (fonts + w3strings with PUA sentence glyphs)."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PIL import Image

from .bundle import BundleFile, write_bundle
from .custom_art import load_custom
from .game import en_w3strings_path, extract_fonts_en, mods_dir
from .metastore import BundleLayout, build_metastore
from .render import render_sentence
from .swf_bitmap_glyph import (
    PREVIEW_SIZE_BASE,
    em_height_for_size,
    inject_mask_glyphs,
    pua_code,
    rgba_to_mask,
)
from .w3strings import W3Strings

MOD_NAME = "modThaiConsole"


@dataclass
class SentenceEntry:
    string_id: int
    thai: str
    pua_index: int

    @property
    def code(self) -> int:
        return pua_code(self.pua_index)


def build_fonts(
    entries: list[SentenceEntry],
    game: Path | None = None,
    size: int = PREVIEW_SIZE_BASE,
    weight: str = "Bold",
    y_lift: int = 0,
) -> bytes:
    """Pack glyphs: custom PNG from assets/custom/<id>.png wins over Sarabun."""
    redswf = extract_fonts_en(game)
    images: dict[int, Image.Image] = {}
    for e in entries:
        custom = load_custom(e.string_id)
        img = custom if custom is not None else render_sentence(e.thai, size=size, weight=weight)
        images[e.code] = rgba_to_mask(img)
    return inject_mask_glyphs(
        redswf,
        images,
        font_index=None,
        em_height=em_height_for_size(size),
        y_lift=y_lift,
    )


def build_w3strings(entries: list[SentenceEntry], game: Path | None = None, language: str = "en") -> bytes:
    src = en_w3strings_path(game) if language == "en" else game_root_strings(game, language)
    w = W3Strings.load(src, language)
    for e in entries:
        w.strings[e.string_id] = chr(e.code)
    return w.build()


def game_root_strings(game: Path | None, language: str) -> Path:
    from .game import game_root
    return game_root(game) / "content" / "content0" / f"{language}.w3strings"


def write_mod_content(content_dir: Path, files: list[BundleFile]) -> None:
    content_dir.mkdir(parents=True, exist_ok=True)
    size, data_offset, entries = write_bundle(content_dir / "blob0.bundle", files)
    meta = build_metastore(BundleLayout("blob0.bundle", size, data_offset, entries))
    (content_dir / "metadata.store").write_bytes(meta)


def pack_mod(
    entries: list[SentenceEntry],
    *,
    game: Path | None = None,
    dest: Path | None = None,
    size: int = PREVIEW_SIZE_BASE,
    weight: str = "Bold",
    y_lift: int = 0,
    language: str = "en",
    loose_strings: bool = True,
) -> Path:
    """Write mods/modThaiConsole and return its path.

    ``size`` is the studio preview size and also drives in-game glyph EM height.
    ``y_lift`` shifts glyphs up in EM units (fixes ชิดล่าง in menu boxes).
    """
    from .swf_bitmap_glyph import FONT_PATH

    fonts = build_fonts(entries, game=game, size=size, weight=weight, y_lift=y_lift)
    strings = build_w3strings(entries, game=game, language=language)
    files = [
        BundleFile(FONT_PATH, fonts),
        BundleFile(f"{language}.w3strings", strings),
    ]
    root = dest or (mods_dir(game) / MOD_NAME)
    if root.exists():
        import shutil
        shutil.rmtree(root)
    write_mod_content(root / "content", files)
    # Remastered also picks up loose language files next to the bundle.
    if loose_strings:
        (root / "content" / f"{language}.w3strings").write_bytes(strings)
    return root


# Main-menu string ids confirmed in-game (ASCII marker test, 2026-11-07).
# Menu shows Title Case English but Flash uppercases for display.
MENU_POC = [
    (1083486, "เล่นเกมต่อ"),      # Continue  (was THAI-CONT2)
    (1083488, "เริ่มเกมใหม่"),    # New game  (was THAI-NEW3)
    (1066020, "โหลดเกม"),         # Load game (was THAI-LOAD)
    (1066021, "ตัวเลือก"),        # Settings  (was THAI-SET)
    (1236547, "ม็อด"),            # Mods
    (1469941, "ไฮไลต์แพตช์"),     # Patch Highlights
    (1066066, "เครดิต"),          # Credits
    (401380, "ออก"),              # Exit
]
