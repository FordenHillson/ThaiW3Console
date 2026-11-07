"""Gradually expand sentence-glyph coverage and install for in-game testing.

Safe ladder (after black-screen hang at 6400×3 fonts):
  8 (menu POC) → 50 → 100 → 200 → 400 → 800 → 1600 → …

Usage:
  python spikes/04_expand_ladder.py --step 100 --install
  python spikes/04_expand_ladder.py --next --install
  python spikes/04_expand_ladder.py --status
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core.bundle import iter_bundle
from core.game import en_w3strings_path, mods_dir
from core.pack_mod import MENU_POC, MOD_NAME, pack_mod
from core.paths import repo_root
from core.setup_translations import load_setup_translations, select_for_pack
from core.swf_bitmap_glyph import FONT_PATH
from core.w3strings import W3Strings

LADDER = (8, 50, 100, 200, 400, 800, 1600, 3200, 6400)
STATE_PATH = repo_root() / "export" / "spike4" / "expand_state.json"


def _load_state() -> dict:
    if STATE_PATH.is_file():
        return json.loads(STATE_PATH.read_text(encoding="utf-8"))
    return {"last_ok": 8, "last_tried": 8, "history": []}


def _save_state(state: dict) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def _fmt(n: int) -> str:
    return f"{n / 1_000_000:.2f} MB" if n >= 1_000_000 else f"{n / 1_000:.1f} KB"


def _dir_size(path: Path) -> int:
    return sum(p.stat().st_size for p in path.rglob("*") if p.is_file())


def next_step(last_ok: int) -> int | None:
    for n in LADDER:
        if n > last_ok:
            return n
    return None


def pack_step(
    n: int,
    *,
    install: bool,
    fonts: str,
    size: int,
    max_chars: int,
    game: Path | None,
) -> dict:
    tr = load_setup_translations()
    game_strings = W3Strings.load(en_w3strings_path(game), "en").strings
    if n <= len(MENU_POC):
        # Pure menu POC
        from core.pack_mod import SentenceEntry
        entries = [SentenceEntry(sid, th, i) for i, (sid, th) in enumerate(MENU_POC[:n])]
        unique = n
        ids = n
    else:
        sel = select_for_pack(
            tr.thai,
            game_ids=set(game_strings),
            game_en=game_strings,
            by_text=tr.by_text,
            force=MENU_POC,
            max_unique=n,
            max_chars=max_chars,
        )
        entries = sel.entries()
        unique = sel.unique_count
        ids = len(sel.by_id)

    font_index = 0 if fonts == "one" else None
    out = repo_root() / "export" / "spike4" / f"step_{n}"
    dest = None if install else (out / MOD_NAME)
    if dest:
        out.mkdir(parents=True, exist_ok=True)

    t0 = time.time()
    # Match menu POC metrics: one scale + one advance slot so heights/columns stay even.
    path = pack_mod(
        entries,
        game=game,
        dest=dest,
        size=size,
        weight="Bold",
        font_index=font_index,
        shared_advance=True,
        shared_scale=True,
        fit_width=False,
        align="center",
        progress=lambda d, t, s: print(f"  render {d}/{t}  {s!r}", flush=True) if d % 25 == 0 or d == t else None,
    )
    elapsed = time.time() - t0

    fonts_bytes = 0
    for bf in iter_bundle(path / "content" / "blob0.bundle", lambda name, _: name == FONT_PATH):
        fonts_bytes = len(bf.data)
        break

    report = {
        "step": n,
        "unique_glyphs": unique,
        "ids": ids,
        "fonts": fonts,
        "size": size,
        "max_chars": max_chars,
        "fonts_en_bytes": fonts_bytes,
        "mod_total_bytes": _dir_size(path),
        "elapsed_s": round(elapsed, 1),
        "mod_path": str(path),
        "menu_forced": {sid: th for sid, th in MENU_POC if sid in {e.string_id for e in entries}},
    }
    (repo_root() / "export" / "spike4").mkdir(parents=True, exist_ok=True)
    (repo_root() / "export" / "spike4" / f"step_{n}_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return report


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--step", type=int, help="exact unique-glyph count from ladder")
    ap.add_argument("--next", action="store_true", help="install next step after last_ok")
    ap.add_argument("--ok", action="store_true", help="mark last_tried as last_ok (passed in-game)")
    ap.add_argument("--status", action="store_true")
    ap.add_argument("--install", action="store_true")
    ap.add_argument("--fonts", choices=("one", "all"), default="one")
    ap.add_argument("--size", type=int, default=57, help="render→EM height (57=+10% after 52 equalized; 64 was too large)")
    ap.add_argument("--max-chars", type=int, default=40)
    ap.add_argument("--game", type=Path, default=None)
    args = ap.parse_args()

    state = _load_state()
    if args.status:
        nxt = next_step(int(state.get("last_ok", 8)))
        print(f"last_ok={state.get('last_ok')}  last_tried={state.get('last_tried')}  next={nxt}")
        print(f"ladder={list(LADDER)}")
        print(f"state={STATE_PATH}")
        return 0

    if args.ok:
        state["last_ok"] = state.get("last_tried", state.get("last_ok", 8))
        state.setdefault("history", []).append({"ok": state["last_ok"], "at": time.time()})
        _save_state(state)
        print(f"marked last_ok={state['last_ok']}  next={next_step(state['last_ok'])}")
        return 0

    if args.next:
        n = next_step(int(state.get("last_ok", 8)))
        if n is None:
            print("already at top of ladder")
            return 0
    elif args.step is not None:
        n = args.step
    else:
        n = next_step(int(state.get("last_ok", 8))) or 50

    print(f"expand step={n}  fonts={args.fonts}  size={args.size}  max_chars≤{args.max_chars}")
    if n >= 1600 and args.fonts == "all":
        print("warning: large step + all fonts previously hung the game; prefer --fonts one")

    report = pack_step(
        n,
        install=args.install,
        fonts=args.fonts,
        size=args.size,
        max_chars=args.max_chars,
        game=args.game,
    )
    state["last_tried"] = n
    state.setdefault("history", []).append({**report, "at": time.time()})
    _save_state(state)

    print("---")
    print(f"glyphs:     {report['unique_glyphs']}")
    print(f"ids:        {report['ids']}")
    print(f"fonts_en:   {_fmt(report['fonts_en_bytes'])}")
    print(f"mod total:  {_fmt(report['mod_total_bytes'])}  ({report['elapsed_s']}s)")
    print(f"path:       {report['mod_path']}")
    if args.install:
        print("Installed. Restart game (Text Language=English). If OK: python spikes/04_expand_ladder.py --ok")
        print("If hang/black: disable modThaiConsole / restore menu POC, then lower step.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
