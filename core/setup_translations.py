"""Load community Thai translations from a ThaiW3Setup install (bundled cache)."""
from __future__ import annotations

import gzip
import json
import re
import time
from dataclasses import dataclass
from pathlib import Path

TAG_RE = re.compile(r"<[^>]+>")
THAI_RE = re.compile(r"[\u0e00-\u0e7f]")

# Prefer sibling checkout, then common local clones.
SETUP_CANDIDATES = [
    Path(__file__).resolve().parents[2] / "ThaiW3Setup" / "assets" / "translations.json.gz",
    Path(r"D:\backup\github\ThaiW3Setup\assets\translations.json.gz"),
]


def has_thai(text: str) -> bool:
    return bool(THAI_RE.search(text))


def find_setup_translations() -> Path | None:
    for path in SETUP_CANDIDATES:
        if path.is_file():
            return path
    return None


def strip_tags(text: str) -> str:
    return TAG_RE.sub("", text).strip()


def normalize_en(text: str) -> str:
    return " ".join(text.split())


@dataclass
class SetupTranslations:
    thai: dict[int, str]
    by_text: dict[str, str]  # normalized English → Thai
    source: str
    fetched_at: float


def load_setup_translations(path: Path | None = None) -> SetupTranslations:
    """Read ThaiW3Setup ``translations.json.gz`` (format 3: strings + text)."""
    path = path or find_setup_translations()
    if path is None:
        raise FileNotFoundError("ThaiW3Setup translations.json.gz not found")
    payload = json.loads(gzip.decompress(path.read_bytes()).decode("utf-8"))
    raw = payload.get("strings") or payload.get("thai") or {}
    thai = {int(k): strip_tags(v) for k, v in raw.items() if strip_tags(str(v))}
    by_text = {
        normalize_en(k): strip_tags(v)
        for k, v in (payload.get("text") or {}).items()
        if strip_tags(str(v))
    }
    fetched = float(payload.get("fetched_at") or time.time())
    return SetupTranslations(thai=thai, by_text=by_text, source=str(path), fetched_at=fetched)


@dataclass
class Selection:
    """Chosen (string_id → thai) for packing, with unique-text → PUA index map."""

    by_id: dict[int, str]
    pua_of_text: dict[str, int]  # thai text → pua index

    @property
    def unique_count(self) -> int:
        return len(self.pua_of_text)

    def entries(self):
        from .pack_mod import SentenceEntry

        out: list[SentenceEntry] = []
        for sid, text in sorted(self.by_id.items()):
            out.append(SentenceEntry(sid, text, self.pua_of_text[text]))
        return out


def _reserve(pua_of_text: dict[str, int], by_id: dict[int, str], sid: int, text: str,
             max_unique: int) -> bool:
    """Add sid→text; allocate a new PUA slot if needed. False if no room for a new text."""
    text = text.strip()
    if not text or not has_thai(text):
        return False
    if text not in pua_of_text:
        if len(pua_of_text) >= max_unique:
            return False
        pua_of_text[text] = len(pua_of_text)
    by_id[sid] = text
    return True


def select_for_pack(
    thai: dict[int, str],
    *,
    game_ids: set[int] | None = None,
    game_en: dict[int, str] | None = None,
    by_text: dict[str, str] | None = None,
    force: list[tuple[int, str]] | None = None,
    max_unique: int = 6400,
    max_chars: int = 80,
    min_chars: int = 1,
) -> Selection:
    """Pick translated ids that exist in the game, shortest first, dedupe text for PUA.

    ``force`` (e.g. MENU_POC) is reserved first so known UI never drops out of the sheet.
    ``by_text`` fills ids that have English in-game but no id-keyed Thai.
    ``max_unique`` defaults to BMP PUA size (U+E000..U+F8FF = 6400).
    """
    pua_of_text: dict[str, int] = {}
    by_id: dict[int, str] = {}

    # 1) Forced UI fallbacks win a PUA slot even when the sheet has no id.
    for sid, text in force or ():
        if game_ids is not None and sid not in game_ids:
            continue
        _reserve(pua_of_text, by_id, sid, text, max_unique)

    # 2) Merge id-keyed sheet + English→Thai lookup into candidate list.
    merged: dict[int, str] = {}
    for sid, text in thai.items():
        t = text.strip()
        if t and has_thai(t):
            merged[sid] = t
    if by_text and game_en:
        for sid, en in game_en.items():
            if sid in merged:
                continue
            th = by_text.get(normalize_en(en))
            if th and has_thai(th):
                merged[sid] = th

    items = []
    for sid, text in merged.items():
        if game_ids is not None and sid not in game_ids:
            continue
        if sid in by_id:
            continue  # already forced
        if not (min_chars <= len(text) <= max_chars):
            continue
        items.append((len(text), sid, text))
    items.sort()  # short first

    for _, sid, text in items:
        if text not in pua_of_text and len(pua_of_text) >= max_unique:
            continue
        _reserve(pua_of_text, by_id, sid, text, max_unique)
    return Selection(by_id=by_id, pua_of_text=pua_of_text)
