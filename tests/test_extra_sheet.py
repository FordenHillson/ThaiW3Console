from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core.extra_sheet import parse_extra_xlsx


def test_parse_probe_xlsx():
    path = ROOT / "export" / "probe_sheet.xlsx"
    if not path.exists():
        return  # downloaded in earlier probe; skip if absent
    thai, by_tab = parse_extra_xlsx(path.read_bytes())
    assert by_tab.get("ชื่อสกิล", 0) > 0
    assert 1066845 in thai  # Muscle Memory
    assert "กล้ามเนื้อ" in thai[1066845]
    assert 1176357 in thai  # Garkains
    assert "กาเควน" in thai[1176357]
    # skill description from Untranslated
    assert 1449743 in thai
    assert "หลบ" in thai[1449743] or "โจมตี" in thai[1449743]
