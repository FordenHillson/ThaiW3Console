"""Verify installed modThaiConsole has PUA glyphs and string overrides."""
from __future__ import annotations

import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core.bundle import read_bundle
from core.pack_mod import MENU_POC
from core.swf_bitmap_glyph import FONT_PATH, _read_font3, _swf_body_from_redswf, pua_code
from core.w3strings import W3Strings


def main() -> int:
    mod_dir = Path(r"D:\SteamLibrary\steamapps\common\The Witcher 3\mods\modThaiConsole\content")
    bundle = mod_dir / "blob0.bundle"
    files = {f.path: f.data for f in read_bundle(bundle)}
    print("files", sorted(files))
    w = W3Strings.parse(files["en.w3strings"], "en")
    for i, (sid, thai) in enumerate(MENU_POC):
        t = w.strings.get(sid, "")
        code = pua_code(i)
        ok = t == chr(code)
        print(f"{sid}: {t!r} expect U+{code:04X} thai={thai!r} {'OK' if ok else 'FAIL'}")

    loose = mod_dir / "en.w3strings"
    print("loose en.w3strings", loose.exists(), loose.stat().st_size if loose.exists() else 0)

    _at, swf, _packed, _stored = _swf_body_from_redswf(files[FONT_PATH])
    body = swf[8:]
    nbits = body[0] >> 3
    p = (5 + 4 * nbits + 7) // 8 + 4
    fonts = 0
    while p + 2 <= len(body):
        code_len = struct.unpack_from("<H", body, p)[0]
        p += 2
        code, ln = code_len >> 6, code_len & 0x3F
        if ln == 0x3F:
            ln = struct.unpack_from("<I", body, p)[0]
            p += 4
        d = body[p:p + ln]
        p += ln
        if code == 75:
            f = _read_font3(d)
            name = f.head[5:5 + f.head[4]].split(b"\0")[0].decode("latin-1", "replace")
            pua = [c for c in f.codes if 0xE000 <= c <= 0xE0FF]
            adv = [f.advances[f.codes.index(c)] for c in pua]
            print(f"font{fonts}", name, "pua", [hex(c) for c in pua], "adv", adv)
            fonts += 1
        if code == 0:
            break
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
