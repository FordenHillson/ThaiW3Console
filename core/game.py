"""Locate game files and extract fonts_en.redswf from r4gui.bundle."""
from __future__ import annotations

from pathlib import Path

from .bundle import BundleFile, iter_bundle, read_bundle
from .paths import default_game_path
from .swf_bitmap_glyph import FONT_PATH

GUI_BUNDLE = "bundles\\r4gui.bundle"


def game_root(path: Path | None = None) -> Path:
    root = path or default_game_path()
    if not (root / "content" / "content0").is_dir():
        raise FileNotFoundError(f"not a Witcher 3 install: {root}")
    return root


def gui_bundle_path(root: Path | None = None) -> Path:
    return game_root(root) / "content" / "content0" / "bundles" / "r4gui.bundle"


def extract_fonts_en(root: Path | None = None) -> bytes:
    path = gui_bundle_path(root)
    for bf in iter_bundle(path, lambda n, _: n == FONT_PATH):
        return bf.data
    raise FileNotFoundError(f"{FONT_PATH} not in {path}")


def en_w3strings_path(root: Path | None = None) -> Path:
    return game_root(root) / "content" / "content0" / "en.w3strings"


def mods_dir(root: Path | None = None) -> Path:
    return game_root(root) / "mods"
