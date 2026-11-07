"""Browse every per-character PUA glyph used by modThaiConsole.

Rebuilds the same charset as the full pack (Setup + extra sheet), renders each
glyph cell, and shows a scrollable grid + sample sentence composites.

Usage:
  launch_glyph_preview.bat
  python devtools/preview_glyphs.py
  python devtools/preview_glyphs.py --export export/glyph_preview
"""
from __future__ import annotations

import argparse
import sys
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from PIL import Image, ImageDraw, ImageTk

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.char_glyphs import (
    CharAtlas,
    build_char_atlas,
    encode_thai,
    is_combining_mark,
    preview_encoded,
    render_char_cell,
)
from core.pack_char import merge_translations
from core.paths import repo_root
from core.swf_bitmap_glyph import PREVIEW_SIZE_BASE
from core.thai_wrap import prepare


SAMPLES = [
    "กล้ามเนื้อจดจำ",
    "หลังจากหลบหลีกหรือกลิ้งตัวสำเร็จ",
    "กาเควน",
    "เล่นเกมต่อ",
    "จุดอ่อน",
    "เลเวลปัจจุบัน",
    "POINTS ที่ใช้ได้",
]


def build_mod_atlas(*, offline: bool = False) -> tuple[CharAtlas, dict]:
    """Charset identical to full pack (all Thai chars that appear in merged strings)."""
    info: dict = {"ids": 0, "source": "merge_translations"}
    try:
        by_id = merge_translations(force_menu=True, use_extra_sheet=not offline)
        info["ids"] = len(by_id)
        atlas = build_char_atlas(list(by_id.values()), always_high_tones=True)
    except Exception as exc:
        # Fallback: samples only so the tool still opens.
        atlas = build_char_atlas(SAMPLES, always_high_tones=True)
        info["source"] = f"samples-only ({exc})"
    return atlas, info


def glyph_entries(atlas: CharAtlas) -> list[tuple[str, int, bool]]:
    """(label_char, pua_code, raised) in display order."""
    rows: list[tuple[str, int, bool]] = []
    for ch, code in sorted(atlas.base.items(), key=lambda kv: kv[1]):
        rows.append((ch, code, False))
    for ch, code in sorted(atlas.high_tone.items(), key=lambda kv: kv[1]):
        rows.append((ch, code, True))
    return rows


def cell_tile(
    ch: str,
    code: int,
    *,
    raised: bool,
    size: int,
    weight: str,
    tile: int = 72,
) -> Image.Image:
    cell = render_char_cell(ch, size=size, weight=weight, raised=raised)
    canvas = Image.new("RGB", (tile, tile + 22), (28, 30, 34))
    # center glyph
    x = (tile - cell.image.width) // 2
    y = (tile - cell.image.height) // 2 + 2
    canvas.paste(cell.image, (max(0, x), max(0, y)), cell.image)
    draw = ImageDraw.Draw(canvas)
    tag = f"U+{code:04X}"
    if raised:
        tag += " ↑"
    mark = " Mn" if is_combining_mark(ch) else ""
    label = f"{ch!r}{mark}" if ch.strip() else "␠"
    draw.text((4, tile + 2), f"{label} {tag}", fill=(160, 160, 160))
    # origin tick
    ox = max(0, x) + cell.pen_x_px
    if 0 <= ox < tile:
        draw.line((ox, 0, ox, tile), fill=(80, 120, 180))
    return canvas


def export_all(
    atlas: CharAtlas,
    dest: Path,
    *,
    size: int,
    weight: str,
) -> int:
    dest.mkdir(parents=True, exist_ok=True)
    entries = glyph_entries(atlas)
    cols = 10
    tile = 80
    tiles = [
        cell_tile(ch, code, raised=raised, size=size, weight=weight, tile=tile)
        for ch, code, raised in entries
    ]
    rows = (len(tiles) + cols - 1) // cols
    tw, th = tiles[0].size
    grid = Image.new("RGB", (cols * tw + 8, rows * th + 8), (18, 20, 24))
    for i, im in enumerate(tiles):
        r, c = divmod(i, cols)
        grid.paste(im, (4 + c * tw, 4 + r * th))
        ch, code, raised = entries[i]
        safe = "space" if not ch.strip() else f"{ord(ch):04X}"
        name = f"glyph_U+{code:04X}_{safe}{'_high' if raised else ''}.png"
        im.save(dest / name)
    grid.save(dest / "charset_grid.png")
    for i, text in enumerate(SAMPLES):
        img = preview_encoded(text, atlas, size=size, weight=weight)
        bg = Image.new("RGB", (max(640, img.width + 40), max(90, img.height + 40)), (22, 24, 28))
        bg.paste(img, (20, 20), img)
        bg.save(dest / f"sample_{i:02d}.png")
    return len(entries)


class GlyphPreview(tk.Tk):
    def __init__(self, *, size: int = 52, weight: str = "Bold", offline: bool = False):
        super().__init__()
        self.title("ThaiW3Console — Glyph Preview")
        self.geometry("1100x720")
        self.minsize(800, 560)
        self.render_size = size
        self.weight = weight
        self.offline = offline
        self.atlas: CharAtlas | None = None
        self._photos: list[ImageTk.PhotoImage] = []
        self._tiles: list[Image.Image] = []
        self._entries: list[tuple[str, int, bool]] = []

        top = ttk.Frame(self, padding=8)
        top.pack(fill="x")
        ttk.Button(top, text="โหลด charset จากม็อด", command=self.reload).pack(side="left")
        ttk.Button(top, text="Export PNG ทั้งหมด", command=self.do_export).pack(side="left", padx=6)
        ttk.Button(top, text="เปิดโฟลเดอร์ export", command=self.open_export_dir).pack(side="left")
        ttk.Label(top, text="ขนาด").pack(side="left", padx=(12, 2))
        self.size_var = tk.IntVar(value=size)
        sp = ttk.Spinbox(top, from_=32, to=96, width=4, textvariable=self.size_var, command=self.reload)
        sp.pack(side="left")
        self.status = ttk.Label(top, text="")
        self.status.pack(side="right")

        paned = ttk.Panedwindow(self, orient="horizontal")
        paned.pack(fill="both", expand=True, padx=8, pady=4)

        left = ttk.Frame(paned)
        right = ttk.Frame(paned)
        paned.add(left, weight=3)
        paned.add(right, weight=2)

        # scrollable glyph grid
        wrap = ttk.Frame(left)
        wrap.pack(fill="both", expand=True)
        self.canvas = tk.Canvas(wrap, bg="#1c1e22", highlightthickness=0)
        sb = ttk.Scrollbar(wrap, orient="vertical", command=self.canvas.yview)
        self.grid_frame = ttk.Frame(self.canvas)
        self.grid_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")),
        )
        self.canvas.create_window((0, 0), window=self.grid_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=sb.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        self.canvas.bind_all("<MouseWheel>", self._on_wheel)

        # detail + samples
        self.detail = ttk.Label(right, text="คลิก glyph เพื่อดูรายละเอียด", wraplength=360)
        self.detail.pack(anchor="w", padx=4, pady=4)
        self.big = ttk.Label(right)
        self.big.pack(anchor="w", padx=4, pady=4)
        ttk.Separator(right).pack(fill="x", pady=8)
        ttk.Label(right, text="ตัวอย่างประโยค").pack(anchor="w", padx=4)
        self.sample_box = ttk.Frame(right)
        self.sample_box.pack(fill="both", expand=True, padx=4, pady=4)

        self.reload()

    def _on_wheel(self, event):
        self.canvas.yview_scroll(int(-event.delta / 120), "units")

    def reload(self):
        self.render_size = int(self.size_var.get())
        self.status.config(text="กำลังโหลด…")
        self.update_idletasks()
        try:
            self.atlas, info = build_mod_atlas(offline=self.offline)
        except Exception as exc:
            messagebox.showerror("โหลดไม่สำเร็จ", str(exc))
            return
        self._entries = glyph_entries(self.atlas)
        self._rebuild_grid()
        self._rebuild_samples()
        self.status.config(
            text=f"glyphs={len(self._entries)}  base={len(self.atlas.base)}  "
            f"high={len(self.atlas.high_tone)}  ids≈{info.get('ids', '?')}  ({info.get('source')})"
        )

    def _rebuild_grid(self):
        for w in self.grid_frame.winfo_children():
            w.destroy()
        self._photos.clear()
        self._tiles = []
        cols = 8
        for i, (ch, code, raised) in enumerate(self._entries):
            tile = cell_tile(
                ch, code, raised=raised, size=self.render_size, weight=self.weight, tile=70
            )
            self._tiles.append(tile)
            photo = ImageTk.PhotoImage(tile)
            self._photos.append(photo)
            btn = tk.Button(
                self.grid_frame,
                image=photo,
                bd=0,
                bg="#1c1e22",
                activebackground="#2a2e36",
                command=lambda idx=i: self.show_detail(idx),
            )
            r, c = divmod(i, cols)
            btn.grid(row=r, column=c, padx=2, pady=2)

    def _rebuild_samples(self):
        for w in self.sample_box.winfo_children():
            w.destroy()
        assert self.atlas is not None
        for text in SAMPLES:
            prepared = prepare(text)
            img = preview_encoded(prepared, self.atlas, size=self.render_size, weight=self.weight)
            # scale down if very wide
            max_w = 360
            if img.width > max_w:
                ratio = max_w / img.width
                img = img.resize((max_w, max(1, int(img.height * ratio))), Image.Resampling.NEAREST)
            bg = Image.new("RGB", (img.width + 16, img.height + 28), (22, 24, 28))
            bg.paste(img, (8, 20), img)
            draw = ImageDraw.Draw(bg)
            draw.text((8, 2), text[:40], fill=(140, 140, 140))
            photo = ImageTk.PhotoImage(bg)
            self._photos.append(photo)
            ttk.Label(self.sample_box, image=photo).pack(anchor="w", pady=3)

    def show_detail(self, idx: int):
        ch, code, raised = self._entries[idx]
        cell = render_char_cell(ch, size=self.render_size * 2, weight=self.weight, raised=raised)
        big = Image.new("RGB", (max(200, cell.image.width + 40), max(160, cell.image.height + 40)), (22, 24, 28))
        big.paste(cell.image, (20, 20), cell.image)
        photo = ImageTk.PhotoImage(big)
        self._photos.append(photo)
        self.big.configure(image=photo)
        enc = encode_thai(ch, self.atlas) if self.atlas else ""
        self.detail.config(
            text=(
                f"ตัวอักษร: {ch!r}  ({'วรรณยุกต์ยกสูง' if raised else 'ปกติ'})\n"
                f"PUA: U+{code:04X}   Unicode: U+{ord(ch):04X}\n"
                f"advance={cell.advance_px}px  pen_x={cell.pen_x_px}  "
                f"mark={is_combining_mark(ch)}\n"
                f"encode → {enc!r}"
            )
        )

    def do_export(self):
        if not self.atlas:
            return
        dest = filedialog.askdirectory(
            initialdir=str(repo_root() / "export" / "glyph_preview"),
            title="โฟลเดอร์สำหรับ export PNG",
        )
        if not dest:
            return
        n = export_all(self.atlas, Path(dest), size=self.render_size, weight=self.weight)
        messagebox.showinfo("Export", f"บันทึก {n} glyphs + grid + samples\n→ {dest}")

    def open_export_dir(self):
        path = repo_root() / "export" / "glyph_preview"
        path.mkdir(parents=True, exist_ok=True)
        import os

        os.startfile(path)  # noqa: S606 — Windows explorer


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--export", type=Path, default=None, help="export PNGs then exit (no GUI)")
    ap.add_argument("--size", type=int, default=PREVIEW_SIZE_BASE)
    ap.add_argument("--weight", default="Bold")
    ap.add_argument("--offline", action="store_true")
    args = ap.parse_args()

    if args.export is not None:
        atlas, info = build_mod_atlas(offline=args.offline)
        n = export_all(atlas, args.export, size=args.size, weight=args.weight)
        print(f"exported {n} glyphs → {args.export}  ({info})")
        return 0

    app = GlyphPreview(size=args.size, weight=args.weight, offline=args.offline)
    app.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
