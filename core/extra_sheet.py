"""Supplementary Google Sheet: Untranslated backlog + proper-name tabs.

Sheet: ThaiW3Setup ข้อความที่ยังไม่แปล / ชื่อ*
https://docs.google.com/spreadsheets/d/1kIj-WNi24iy3--NLHNzcIj5szOBXoxHJGdwRQNj0etk
"""
from __future__ import annotations

import gzip
import io
import json
import logging
import re
import time
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from .paths import cache_dir
from .setup_translations import has_thai, strip_tags
from .sheet import USER_AGENT, _cell_text

log = logging.getLogger(__name__)

SHEET_ID = "1kIj-WNi24iy3--NLHNzcIj5szOBXoxHJGdwRQNj0etk"
EXPORT_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=xlsx"
CACHE_NAME = "extra_sheet.json.gz"
CACHE_MAX_AGE = 24 * 3600

# Tabs that carry Thai for game string ids.
NAME_TABS = (
    "ชื่อตัวละคร",
    "ชื่อเมือง",
    "ชื่อเควส",
    "ชื่อสกิล",
    "ชื่อมอนสเตอร์",
    "ชื่อไอเทม",
    "ชื่อการ์ดเกวนต์",
    "ชื่ออื่นๆ",
)
UNTRANSLATED_TAB = "Untranslated"

_ID_SPLIT = re.compile(r"[\s,;]+")


@dataclass
class ExtraTranslations:
    thai: dict[int, str]
    source: str
    fetched_at: float
    by_tab: dict[str, int]  # tab → how many ids contributed


def _parse_ids(raw) -> list[int]:
    text = _cell_text(raw).strip()
    if not text:
        return []
    out: list[int] = []
    for part in _ID_SPLIT.split(text):
        if not part:
            continue
        try:
            out.append(int(float(part)) if "." in part else int(part))
        except ValueError:
            continue
    return out


def _pick_thai(*candidates: str) -> str:
    for c in candidates:
        t = strip_tags(_cell_text(c)).strip()
        if t and has_thai(t):
            return t
    return ""


def parse_extra_xlsx(data: bytes) -> tuple[dict[int, str], dict[str, int]]:
    import openpyxl

    wb = openpyxl.load_workbook(io.BytesIO(data), read_only=True, data_only=True)
    thai: dict[int, str] = {}
    by_tab: dict[str, int] = {}

    # 1) Name tabs — prefer pure THAI column, then TRANSLATE.
    for name in NAME_TABS:
        if name not in wb.sheetnames:
            log.warning("extra sheet tab missing: %s", name)
            continue
        n0 = len(thai)
        for row in wb[name].iter_rows(min_row=3, max_col=5, values_only=True):
            if not row or row[0] is None:
                continue
            ids = _parse_ids(row[0])
            if not ids:
                continue
            # ID | ENGLISH | THAI | TRANSLATE | NOTE
            text = _pick_thai(row[2] if len(row) > 2 else "", row[3] if len(row) > 3 else "")
            if not text:
                continue
            for sid in ids:
                thai[sid] = text
        by_tab[name] = len(thai) - n0

    # 2) Untranslated — fill holes; คำอธิบาย always applies (skill/item blurb ids).
    if UNTRANSLATED_TAB in wb.sheetnames:
        n0 = len(thai)
        for row in wb[UNTRANSLATED_TAB].iter_rows(min_row=3, max_col=4, values_only=True):
            if not row or row[0] is None:
                continue
            ids = _parse_ids(row[0])
            if not ids:
                continue
            # ID | ENGLISH | TRANSLATE | NOTE
            text = _pick_thai(row[2] if len(row) > 2 else "")
            if not text:
                continue
            note = _cell_text(row[3] if len(row) > 3 else "")
            # Skip rows marked as better left untranslated (settings / credits).
            if "ไม่แปล" in note and "คำอธิบาย" not in note and "ชื่อสกิล" not in note:
                continue
            force = "คำอธิบาย" in note
            for sid in ids:
                if force or sid not in thai:
                    thai[sid] = text
        by_tab[UNTRANSLATED_TAB] = len(thai) - n0

    wb.close()
    return thai, by_tab


def _download() -> bytes:
    req = urllib.request.Request(EXPORT_URL, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=120) as resp:
        return resp.read()


def save_cache(thai: dict[int, str], by_tab: dict[str, int], fetched_at: float,
               path: Path | None = None) -> Path:
    path = path or (cache_dir() / CACHE_NAME)
    payload = {
        "fetched_at": fetched_at,
        "sheet_id": SHEET_ID,
        "by_tab": by_tab,
        "thai": {str(k): v for k, v in thai.items()},
    }
    path.write_bytes(gzip.compress(json.dumps(payload, ensure_ascii=False).encode("utf-8"), 9))
    return path


def load_cache(path: Path | None = None) -> ExtraTranslations | None:
    path = path or (cache_dir() / CACHE_NAME)
    if not path.exists():
        return None
    payload = json.loads(gzip.decompress(path.read_bytes()).decode("utf-8"))
    thai = {int(k): v for k, v in payload["thai"].items()}
    return ExtraTranslations(
        thai=thai,
        source=str(path),
        fetched_at=float(payload["fetched_at"]),
        by_tab=dict(payload.get("by_tab") or {}),
    )


def load_extra_translations(force: bool = False) -> ExtraTranslations:
    cached = None if force else load_cache()
    if cached and (time.time() - cached.fetched_at) < CACHE_MAX_AGE:
        return cached
    try:
        data = _download()
        thai, by_tab = parse_extra_xlsx(data)
        fetched_at = time.time()
        path = save_cache(thai, by_tab, fetched_at)
        return ExtraTranslations(
            thai=thai,
            source=f"online→{path}",
            fetched_at=fetched_at,
            by_tab=by_tab,
        )
    except Exception as exc:
        if cached:
            log.warning("extra sheet fetch failed (%s); using cache", exc)
            return cached
        raise
