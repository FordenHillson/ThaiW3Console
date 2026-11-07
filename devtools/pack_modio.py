"""Build a mod.io-ready ZIP of modThaiConsole (Private test / upload).

Usage:
  python devtools/pack_modio.py              # pack from current game install settings + custom PNG
  python devtools/pack_modio.py --from-game  # zip the already-installed mods/modThaiConsole
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core.custom_art import custom_dir
from core.game import mods_dir
from core.pack_mod import MENU_POC, MOD_NAME, SentenceEntry, pack_mod
from core.paths import repo_root
from core.sheet import load_translations


def _studio_meta() -> dict:
    path = custom_dir() / "_studio.json"
    if path.is_file():
        return json.loads(path.read_text(encoding="utf-8"))
    return {}


def _entries(offline: bool) -> list[SentenceEntry]:
    thai: dict[int, str] = {}
    if not offline:
        try:
            tr = load_translations()
            thai = tr.thai
            print(f"sheet: {len(thai)} strings ({tr.source})")
        except Exception as exc:
            print(f"sheet unavailable ({exc}); using MENU_POC fallbacks")
    out: list[SentenceEntry] = []
    for i, (sid, fallback) in enumerate(MENU_POC):
        text = (thai.get(sid) or fallback).strip()
        if "<" in text:
            text = re.sub(r"<[^>]+>", "", text)
        out.append(SentenceEntry(sid, text or fallback, i))
    return out


def zip_mod_folder(mod_root: Path, zip_path: Path) -> Path:
    """ZIP so the archive root is ``modThaiConsole/…`` (mod.io expects a mod folder)."""
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    if zip_path.exists():
        zip_path.unlink()
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(mod_root.rglob("*")):
            if path.is_file():
                arc = Path(MOD_NAME) / path.relative_to(mod_root)
                zf.write(path, arc.as_posix())
    return zip_path


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--from-game", action="store_true", help="Zip installed mods/modThaiConsole as-is")
    ap.add_argument("--offline", action="store_true")
    ap.add_argument("--game", type=Path, default=None)
    ap.add_argument("--size", type=int, default=None)
    ap.add_argument("--y-lift", type=int, default=None)
    args = ap.parse_args()

    out_dir = repo_root() / "export" / "modio"
    out_dir.mkdir(parents=True, exist_ok=True)
    zip_path = out_dir / f"{MOD_NAME}.zip"

    if args.from_game:
        mod_root = mods_dir(args.game) / MOD_NAME
        if not mod_root.is_dir():
            print(f"missing installed mod: {mod_root}")
            return 1
        print(f"source (game): {mod_root}")
    else:
        meta = _studio_meta()
        size = args.size if args.size is not None else int(meta.get("size", 68))
        y_lift = args.y_lift if args.y_lift is not None else int(meta.get("y_lift", 0))
        weight = str(meta.get("weight", "Bold"))
        entries = _entries(args.offline)
        mod_root = out_dir / MOD_NAME
        pack_mod(
            entries,
            game=args.game,
            dest=mod_root,
            size=size,
            weight=weight,
            y_lift=y_lift,
        )
        print(f"packed size={size} y_lift={y_lift} weight={weight} → {mod_root}")

    zip_mod_folder(mod_root, zip_path)
    size_mb = zip_path.stat().st_size / (1024 * 1024)
    print(f"mod.io ZIP: {zip_path} ({size_mb:.1f} MB)")
    print("Upload steps: https://mod.io/g/the-witcher-3 → Add Mod → Visibility Private → upload this ZIP")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
