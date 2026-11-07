"""Per-string custom PNG art (Photoshop) used instead of live Sarabun renders."""
from __future__ import annotations

import json
from pathlib import Path

from PIL import Image

from .paths import repo_root

CUSTOM_DIRNAME = "custom"
META_NAME = "_studio.json"


def custom_dir() -> Path:
    path = repo_root() / "assets" / CUSTOM_DIRNAME
    path.mkdir(parents=True, exist_ok=True)
    return path


def png_path(string_id: int) -> Path:
    return custom_dir() / f"{string_id}.png"


def psd_path(string_id: int) -> Path:
    return custom_dir() / f"{string_id}.psd"


def has_custom(string_id: int) -> bool:
    return png_path(string_id).is_file()


def load_custom(string_id: int) -> Image.Image | None:
    path = png_path(string_id)
    if not path.is_file():
        return None
    return Image.open(path).convert("RGBA")


def save_custom(string_id: int, image: Image.Image) -> Path:
    path = png_path(string_id)
    image.convert("RGBA").save(path, "PNG")
    return path


def clear_custom(string_id: int) -> bool:
    removed = False
    for path in (png_path(string_id), psd_path(string_id)):
        if path.is_file():
            path.unlink()
            removed = True
    return removed


def list_custom_ids() -> list[int]:
    out = set()
    for p in custom_dir().glob("*.png"):
        if p.stem.isdigit():
            out.add(int(p.stem))
    return sorted(out)


def list_psd_ids() -> list[int]:
    out = []
    for p in custom_dir().glob("*.psd"):
        if p.stem.isdigit():
            out.append(int(p.stem))
    return sorted(out)


def mtimes() -> dict[str, float]:
    """Watch keys ``png:<id>`` / ``psd:<id>`` → mtime."""
    out: dict[str, float] = {}
    for sid in list_custom_ids():
        out[f"png:{sid}"] = png_path(sid).stat().st_mtime
    for sid in list_psd_ids():
        out[f"psd:{sid}"] = psd_path(sid).stat().st_mtime
    return out


def write_readme() -> Path:
    path = custom_dir() / "README.txt"
    path.write_text(
        "ThaiW3Console — sync กับ Photoshop\n"
        "================================\n"
        "ไฟล์ที่ Studio อ่านเข้าเกม:  <id>.png   (เช่น 401380.png)\n"
        "ไฟล์ทำงานใน Photoshop:       <id>.psd  (ชั้นเลเยอร์)\n"
        "\n"
        "วิธีแนะนำ\n"
        "1) ใน Studio กด Export → Photoshop (ได้ไฟล์ .png)\n"
        "2) ใน PS: File > Save As > Photoshop (*.PSD) ชื่อเดียวกัน เช่น 401380.psd\n"
        "   เก็บในโฟลเดอร์นี้ assets/custom/\n"
        "3) แต่งเลเยอร์ใน .psd แล้ว Ctrl+S บันทึก .psd\n"
        "4) Studio จะ export .psd → .png ให้อัตโนมัติ แล้วพรีวิวเอง\n"
        "\n"
        "หรือถ้าแก้บน .png โดยตรง: Ctrl+S ทับ .png ก็ sync ได้เช่นกัน\n"
        "อย่า Save As คนละชื่อ/คนละโฟลเดอร์\n"
        "\n"
        "หมายเหตุ: glyph ในเกมเป็น 1-bit ตาม alpha\n",
        encoding="utf-8",
    )
    return path


def save_meta(data: dict) -> Path:
    path = custom_dir() / META_NAME
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return path
