"""Download community Thai translations from the w3tu Google Sheets."""
from __future__ import annotations

import gzip
import io
import json
import logging
import time
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from .paths import cache_dir

log = logging.getLogger(__name__)

EXPORT_URL = "https://docs.google.com/spreadsheets/d/{id}/export?format=xlsx"
SOURCES = [
    ("1lwoUZkMQcFwl_nlzV7UG9qxij6CMc5YuJOSsMuK3ZH8", ["v3", "v4"]),
    ("1YZvH6sd3XjPcLmz5nlRVkHd2Wm1psU1KthHtwSeG3t4", ["NextGen"]),
]
CACHE_NAME = "translations.json.gz"
CACHE_MAX_AGE = 24 * 3600
USER_AGENT = "ThaiW3Console (+https://github.com/FordenHillson/ThaiW3Console)"


@dataclass
class Translations:
    thai: dict[int, str]
    source: str
    fetched_at: float

    @property
    def age_text(self) -> str:
        return time.strftime("%d/%m/%Y %H:%M", time.localtime(self.fetched_at))


def _cell_text(value) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def parse_xlsx(data: bytes, sheets: list[str]) -> dict[int, str]:
    import openpyxl

    wb = openpyxl.load_workbook(io.BytesIO(data), read_only=True, data_only=True)
    out: dict[int, str] = {}
    for name in sheets:
        if name not in wb.sheetnames:
            log.warning("sheet %s not found", name)
            continue
        for row in wb[name].iter_rows(min_row=3, max_col=5, values_only=True):
            if not row or row[0] is None or len(row) < 5:
                continue
            try:
                sid = int(str(row[0]).strip())
            except ValueError:
                continue
            thai = _cell_text(row[4]).strip()
            # strip simple font tags from sheet if present
            if thai:
                out[sid] = thai
    wb.close()
    return out


def _download(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=120) as resp:
        return resp.read()


def fetch_online() -> dict[int, str]:
    merged: dict[int, str] = {}
    for sheet_id, tabs in SOURCES:
        data = _download(EXPORT_URL.format(id=sheet_id))
        merged.update(parse_xlsx(data, tabs))
    return merged


def save_cache(thai: dict[int, str], fetched_at: float, path: Path | None = None) -> Path:
    path = path or (cache_dir() / CACHE_NAME)
    payload = {"fetched_at": fetched_at, "thai": {str(k): v for k, v in thai.items()}}
    path.write_bytes(gzip.compress(json.dumps(payload, ensure_ascii=False).encode("utf-8"), 9))
    return path


def load_cache(path: Path | None = None) -> Translations | None:
    path = path or (cache_dir() / CACHE_NAME)
    if not path.exists():
        return None
    payload = json.loads(gzip.decompress(path.read_bytes()).decode("utf-8"))
    thai = {int(k): v for k, v in payload["thai"].items()}
    return Translations(thai=thai, source=str(path), fetched_at=float(payload["fetched_at"]))


def load_translations(force: bool = False) -> Translations:
    cached = None if force else load_cache()
    if cached and (time.time() - cached.fetched_at) < CACHE_MAX_AGE:
        return cached
    try:
        thai = fetch_online()
        fetched_at = time.time()
        path = save_cache(thai, fetched_at)
        return Translations(thai=thai, source=f"online→{path}", fetched_at=fetched_at)
    except Exception as exc:
        if cached:
            log.warning("sheet fetch failed (%s); using cache", exc)
            return cached
        raise
