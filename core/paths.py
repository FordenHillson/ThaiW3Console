from __future__ import annotations

import os
import sys
from pathlib import Path

from . import APP_NAME


def repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def assets_dir() -> Path:
    if getattr(sys, "frozen", False):
        base = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    else:
        base = repo_root()
    return base / "assets"


def cache_dir() -> Path:
    override = os.environ.get("THAIW3CONSOLE_DATA")
    if override:
        path = Path(override)
    else:
        root = Path(os.environ.get("APPDATA") or Path.home())
        path = root / APP_NAME
    path.mkdir(parents=True, exist_ok=True)
    (path / "cache").mkdir(parents=True, exist_ok=True)
    return path / "cache"


def default_game_path() -> Path:
    env = os.environ.get("WITCHER3_PATH")
    if env:
        return Path(env)
    steam = Path(r"D:\SteamLibrary\steamapps\common\The Witcher 3")
    if steam.is_dir():
        return steam
    return Path(r"C:\Program Files (x86)\Steam\steamapps\common\The Witcher 3")
