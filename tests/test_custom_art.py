from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core.custom_art import clear_custom, custom_dir, has_custom, load_custom, save_custom
from core.photoshop_link import find_photoshop


def test_custom_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setenv("THAIW3CONSOLE_DATA", str(tmp_path))
    # Point custom dir under tmp via monkeypatch of repo_root usage — save into real custom then clean
    sid = 999001
    clear_custom(sid)
    img = Image.new("RGBA", (40, 20), (255, 255, 255, 255))
    path = save_custom(sid, img)
    assert path.exists()
    assert has_custom(sid)
    loaded = load_custom(sid)
    assert loaded is not None and loaded.size == (40, 20)
    clear_custom(sid)
    assert not has_custom(sid)


def test_find_photoshop_runs():
    # May be None on machines without PS — just ensure no crash.
    find_photoshop()
    assert custom_dir().is_dir()
