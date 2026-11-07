"""Thai word segmentation for Scaleform line wrapping.

Scaleform only wraps at Unicode spaces; Thai has none between words. A hair space
(U+200A) counts as a space to Scaleform. We inject a zero-width glyph for it into
fonts_en so breaks do not add visible gaps (same approach as ThaiW3Setup).

Dictionary: assets/thai_words.txt.gz — union of pythainlp corpus (Apache-2.0) and
ICU thaidict (Unicode License), via ThaiW3Setup / thaiwrap.
"""
from __future__ import annotations

import gzip
import re
from functools import lru_cache

from .paths import assets_dir

BREAK = "\u200a"  # hair space
WORDS_FILE = "thai_words.txt.gz"
THAI_RUN = re.compile("[\u0e01-\u0e4e]+")
NO_BREAK_BEFORE = frozenset(
    "\u0e2f\u0e30\u0e31\u0e32\u0e33\u0e34\u0e35\u0e36\u0e37\u0e38\u0e39\u0e3a"
    "\u0e45\u0e46\u0e47\u0e48\u0e49\u0e4a\u0e4b\u0e4c\u0e4d\u0e4e"
)
NO_BREAK_AFTER = frozenset("\u0e40\u0e41\u0e42\u0e43\u0e44")
SHORT_WORD = 2
_END = ""

# Trailing mark can be clipped on right-aligned fields — pad with NBSP (Setup).
THAI_MARKS = frozenset(
    "\u0e31\u0e34\u0e35\u0e36\u0e37\u0e38\u0e39\u0e3a\u0e47\u0e48\u0e49\u0e4a\u0e4b\u0e4c\u0e4d\u0e4e"
)
NBSP = "\u00a0"


def load_words() -> set[str]:
    path = assets_dir() / WORDS_FILE
    with gzip.open(path, "rt", encoding="utf-8") as fh:
        return {w for w in (line.strip() for line in fh) if w and not w.startswith("#")}


class ThaiWrapper:
    def __init__(self, words):
        self.trie: dict = {}
        self._split = lru_cache(maxsize=200_000)(self._split_run)
        self.add_words(words)

    def add_words(self, words) -> None:
        for w in words:
            node = self.trie
            for c in w:
                node = node.setdefault(c, {})
            node[_END] = True
        self._split.cache_clear()

    def wrap(self, text: str) -> str:
        if not THAI_RUN.search(text):
            return text
        return THAI_RUN.sub(lambda m: BREAK.join(self._split(m.group())), text)

    def _split_run(self, run: str) -> tuple[str, ...]:
        n = len(run)
        ok = [
            i == 0 or i == n or (run[i] not in NO_BREAK_BEFORE and run[i - 1] not in NO_BREAK_AFTER)
            for i in range(n + 1)
        ]
        inf = (n + 1, n + 1)
        best = [inf] * (n + 1)
        prev = [(0, False)] * (n + 1)
        best[0] = (0, 0)
        for i in range(n):
            if best[i] == inf or not ok[i]:
                continue
            unknown, count = best[i]
            node, j = self.trie, i
            while j < n and run[j] in node:
                node = node[run[j]]
                j += 1
                if _END in node and ok[j] and (unknown, count + 1) < best[j]:
                    best[j], prev[j] = (unknown, count + 1), (i, True)
            j = i + 1
            while not ok[j]:
                j += 1
            if (unknown + j - i, count + 1) < best[j]:
                best[j], prev[j] = (unknown + j - i, count + 1), (i, False)
        parts: list[tuple[str, bool]] = []
        j = n
        while j > 0:
            i, word = prev[j]
            parts.append((run[i:j], word))
            j = i
        parts.reverse()
        merged: list[list] = []
        for k, (text, word) in enumerate(parts):
            near_unknown = (k > 0 and not parts[k - 1][1]) or (k + 1 < len(parts) and not parts[k + 1][1])
            unknown = not word or (len(text) <= SHORT_WORD and near_unknown)
            if merged and unknown and not merged[-1][1]:
                merged[-1][0] += text
            else:
                merged.append([text, not unknown])
        return tuple(text for text, _ in merged)


def guard_trailing_mark(text: str) -> str:
    return text + NBSP if text and text[-1] in THAI_MARKS else text


@lru_cache(maxsize=1)
def _wrapper() -> ThaiWrapper:
    return ThaiWrapper(load_words())


def prepare(text: str) -> str:
    """Insert hair-space word breaks + trailing-mark guard (ready for encode)."""
    return guard_trailing_mark(_wrapper().wrap(text))
