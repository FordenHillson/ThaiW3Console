"""ThaiW3Console Studio — preview + Photoshop sync before packing into the game.

Usage:
  launch_studio.bat
  python -m studio
"""
from __future__ import annotations

import json
import sys
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk

from PIL import Image, ImageTk

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.custom_art import (
    clear_custom,
    custom_dir,
    has_custom,
    mtimes,
    png_path,
    psd_path,
    save_custom,
    save_meta,
    write_readme,
)
from core.pack_mod import MENU_POC, SentenceEntry, pack_mod
from core.paths import repo_root
from core.photoshop_link import (
    export_psd_to_png,
    find_photoshop,
    open_custom_folder,
    open_in_photoshop,
)
from core.preview_board import glyph_preview, mask_preview, menu_column_preview
from core.render import render_sentence
from core.sheet import load_translations
from core.swf_bitmap_glyph import (
    EM,
    PREVIEW_SIZE_BASE,
    PREVIEW_SIZE_MAX,
    PREVIEW_SIZE_MIN,
    em_height_for_size,
)

WATCH_MS = 700


class Studio(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("ThaiW3Console Studio — Preview / Photoshop sync")
        self.geometry("1180x760")
        self.minsize(960, 640)
        self.thai: dict[int, str] = {}
        self.rows: list[tuple[int, str, str]] = []
        self._photos: list[ImageTk.PhotoImage] = []
        self._watch: dict[str, float] = {}
        self._watch_job: str | None = None
        self._exporting_psd = False

        top = ttk.Frame(self, padding=8)
        top.pack(fill="x")
        ttk.Button(top, text="เมนู POC", command=self.load_menu_poc).pack(side="left")
        ttk.Button(top, text="โหลด Sheets", command=self.load_sheet).pack(side="left", padx=4)
        ttk.Separator(top, orient="vertical").pack(side="left", fill="y", padx=8)
        ttk.Button(top, text="Export → Photoshop", command=self.export_to_photoshop).pack(side="left")
        ttk.Button(top, text="เปิดใน Photoshop", command=self.open_photoshop).pack(side="left", padx=4)
        ttk.Button(top, text="โฟลเดอร์ PNG", command=self.open_folder).pack(side="left")
        ttk.Button(top, text="ลบ PNG รายการนี้", command=self.clear_current_custom).pack(side="left", padx=4)
        ttk.Separator(top, orient="vertical").pack(side="left", fill="y", padx=8)
        ttk.Button(top, text="Export + Install เข้าเกม", command=self.export_install).pack(side="left")
        self.status = ttk.Label(top, text="บันทึกทับ PNG ใน Photoshop → Studio sync เอง")
        self.status.pack(side="right")

        body = ttk.Panedwindow(self, orient="horizontal")
        body.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        left = ttk.Frame(body)
        right = ttk.Frame(body)
        body.add(left, weight=1)
        body.add(right, weight=3)

        ttk.Label(left, text="รายการ (● = มี PNG จาก PS)").pack(anchor="w")
        self.listbox = tk.Listbox(left, exportselection=False, font=("Segoe UI", 10))
        self.listbox.pack(fill="both", expand=True, pady=4)
        self.listbox.bind("<<ListboxSelect>>", self.on_select)

        form = ttk.Frame(right)
        form.pack(fill="x")
        ttk.Label(form, text="ID").grid(row=0, column=0, sticky="w")
        self.var_id = tk.StringVar()
        ttk.Entry(form, textvariable=self.var_id, state="readonly", width=14).grid(row=0, column=1, sticky="w")
        self.lbl_src = ttk.Label(form, text="")
        self.lbl_src.grid(row=0, column=2, sticky="w", padx=8)

        ttk.Label(form, text="ไทย").grid(row=1, column=0, sticky="nw", pady=6)
        self.txt = tk.Text(form, height=3, wrap="word", font=("Sarabun", 12))
        self.txt.grid(row=1, column=1, columnspan=2, sticky="ew", pady=6)
        self.txt.bind("<KeyRelease>", lambda _e: self.refresh_preview())

        opts = ttk.Frame(form)
        opts.grid(row=2, column=1, columnspan=2, sticky="w")
        ttk.Label(opts, text="ขนาด (พรีวิว=เกม)").pack(side="left")
        self.var_size = tk.IntVar(value=PREVIEW_SIZE_BASE)
        spin = ttk.Spinbox(
            opts, from_=PREVIEW_SIZE_MIN, to=PREVIEW_SIZE_MAX,
            textvariable=self.var_size, width=5, command=self.refresh_preview,
        )
        spin.pack(side="left", padx=4)
        spin.bind("<KeyRelease>", lambda _e: self.refresh_preview())
        ttk.Label(opts, text="น้ำหนัก").pack(side="left", padx=(10, 0))
        self.var_weight = tk.StringVar(value="Bold")
        ttk.Combobox(opts, textvariable=self.var_weight, values=["Regular", "Bold"],
                     width=8, state="readonly").pack(side="left", padx=4)
        self.var_weight.trace_add("write", lambda *_: self.refresh_preview())
        ttk.Label(opts, text="เยื้องแนวตั้ง").pack(side="left", padx=(10, 0))
        self.var_ylift = tk.IntVar(value=12)
        lift = ttk.Spinbox(
            opts, from_=-15, to=25, textvariable=self.var_ylift, width=4,
            command=self.refresh_preview,
        )
        lift.pack(side="left", padx=4)
        lift.bind("<KeyRelease>", lambda _e: self.refresh_preview())
        ttk.Label(opts, text="%EM ↑").pack(side="left")

        self.lbl_sync = ttk.Label(form, text="")
        self.lbl_sync.grid(row=3, column=1, columnspan=2, sticky="w", pady=(2, 0))
        form.columnconfigure(1, weight=1)

        previews = ttk.Notebook(right)
        previews.pack(fill="both", expand=True, pady=8)
        self.tab_menu = ttk.Frame(previews)
        self.tab_glyph = ttk.Frame(previews)
        self.tab_mask = ttk.Frame(previews)
        previews.add(self.tab_menu, text="คอลัมน์เมนู (ใกล้เกม)")
        previews.add(self.tab_glyph, text="ต้นฉบับ / PNG จาก PS")
        previews.add(self.tab_mask, text="แบบ 1-bit ในเกม")

        self.lbl_menu = tk.Label(self.tab_menu, background="#121418")
        self.lbl_menu.pack(fill="both", expand=True)
        self.lbl_glyph = tk.Label(self.tab_glyph, background="#121418")
        self.lbl_glyph.pack(fill="both", expand=True)
        self.lbl_mask = tk.Label(self.tab_mask, background="#121418")
        self.lbl_mask.pack(fill="both", expand=True)

        write_readme()
        self._watch = mtimes()
        self.load_menu_poc()
        self._schedule_watch()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _on_close(self) -> None:
        if self._watch_job is not None:
            self.after_cancel(self._watch_job)
        self.destroy()

    def set_status(self, text: str) -> None:
        self.status.configure(text=text)

    def _schedule_watch(self) -> None:
        self._watch_job = self.after(WATCH_MS, self._poll_custom_folder)

    def _poll_custom_folder(self) -> None:
        try:
            now = mtimes()
            if self._exporting_psd:
                self._watch = now
                self._schedule_watch()
                return

            changed_keys = [k for k, t in now.items() if self._watch.get(k) != t]
            changed_keys += [k for k in self._watch if k not in now]

            # PSD saved → auto export PNG via Photoshop, then preview
            psd_changed = sorted({
                int(k.split(":", 1)[1]) for k in changed_keys if k.startswith("psd:")
            })
            msgs = []
            if psd_changed:
                self._exporting_psd = True
                try:
                    for sid in psd_changed:
                        ok, msg = export_psd_to_png(psd_path(sid), png_path(sid))
                        msgs.append(("OK" if ok else "FAIL") + ": " + msg)
                        if not ok:
                            self.set_status(msg)
                finally:
                    self._exporting_psd = False
                now = mtimes()

            png_touched = any(k.startswith("png:") for k in changed_keys) or bool(psd_changed)
            self._watch = now
            if png_touched or psd_changed:
                label = ", ".join(msgs[:2]) if msgs else "PNG อัปเดต"
                self.set_status(f"Photoshop sync: {label}")
                self._reload_list_labels()
                self.refresh_preview()
        except Exception as exc:
            self._exporting_psd = False
            self.set_status(f"watch error: {exc}")
        self._schedule_watch()

    def load_sheet(self) -> None:
        try:
            self.set_status("กำลังโหลด Google Sheets...")
            self.update_idletasks()
            tr = load_translations(force=True)
            self.thai = tr.thai
            ids = [sid for sid, _ in MENU_POC] + sorted(self.thai)[:200]
            seen: set[int] = set()
            self.rows = []
            for sid in ids:
                if sid in seen or sid not in self.thai:
                    continue
                seen.add(sid)
                self.rows.append((sid, "", self.thai[sid]))
            self._reload_list()
            self.set_status(f"โหลด {len(tr.thai)} สตริง · {tr.age_text}")
        except Exception as exc:
            messagebox.showerror("Sheets", str(exc))

    def load_menu_poc(self) -> None:
        if not self.thai:
            try:
                self.thai = load_translations().thai
            except Exception:
                self.thai = {}
        self.rows = [(sid, fb, self.thai.get(sid, fb)) for sid, fb in MENU_POC]
        self._reload_list()
        self.set_status(f"เมนู POC {len(self.rows)} รายการ · โฟลเดอร์ {custom_dir()}")

    def _row_label(self, sid: int, th: str) -> str:
        mark = "● " if has_custom(sid) else "  "
        return f"{mark}{sid}  {th[:44]}"

    def _reload_list(self) -> None:
        self.listbox.delete(0, "end")
        for sid, _hint, th in self.rows:
            self.listbox.insert("end", self._row_label(sid, th))
        if self.rows:
            self.listbox.selection_set(0)
            self.on_select()

    def _reload_list_labels(self) -> None:
        sel = self.current_index()
        for i, (sid, _h, th) in enumerate(self.rows):
            if i < self.listbox.size():
                self.listbox.delete(i)
                self.listbox.insert(i, self._row_label(sid, th))
        if sel is not None:
            self.listbox.selection_set(sel)

    def current_index(self) -> int | None:
        sel = self.listbox.curselection()
        return int(sel[0]) if sel else None

    def _sync_row_text(self) -> None:
        i = self.current_index()
        if i is None:
            return
        text = self.txt.get("1.0", "end").strip() or " "
        sid, hint, _ = self.rows[i]
        self.rows[i] = (sid, hint, text)
        self.listbox.delete(i)
        self.listbox.insert(i, self._row_label(sid, text))
        self.listbox.selection_set(i)

    def on_select(self, _event=None) -> None:
        i = self.current_index()
        if i is None:
            return
        sid, _hint, th = self.rows[i]
        self.var_id.set(str(sid))
        self.txt.delete("1.0", "end")
        self.txt.insert("1.0", th)
        self.refresh_preview()

    def _pack_params(self) -> tuple[int, str, int, int]:
        try:
            size = int(self.var_size.get())
        except (TypeError, ValueError, tk.TclError):
            size = PREVIEW_SIZE_BASE
        size = max(PREVIEW_SIZE_MIN, min(PREVIEW_SIZE_MAX, size))
        weight = self.var_weight.get() or "Bold"
        try:
            pct = int(self.var_ylift.get())
        except (TypeError, ValueError, tk.TclError):
            pct = 0
        pct = max(-15, min(25, pct))
        y_lift = int(round(EM * pct / 100))
        return size, weight, y_lift, pct

    def refresh_preview(self) -> None:
        self._sync_row_text()
        text = self.txt.get("1.0", "end").strip() or " "
        size, weight, y_lift, pct = self._pack_params()
        selected = self.current_index() or 0
        lines = [th for _s, _h, th in self.rows]
        ids = [sid for sid, _h, _t in self.rows]
        sid = ids[selected] if ids else None
        em_h = em_height_for_size(size)
        src = "PNG จาก Photoshop" if sid is not None and has_custom(sid) else "Sarabun render"
        self.lbl_src.configure(text=f"แหล่ง: {src}")
        ps = find_photoshop()
        ps_lbl = ps.name if ps else "ไม่พบ Photoshop (ใช้โปรแกรมเริ่มต้น)"
        self.lbl_sync.configure(
            text=(
                f"sync: size {size}→EM {em_h} · เยื้อง ↑{pct}% · "
                f"custom {sum(1 for s in ids if has_custom(s))}/{len(ids)} · {ps_lbl}"
            )
        )
        try:
            menu = menu_column_preview(
                lines, size=size, weight=weight, selected=selected,
                y_lift_pct=pct, string_ids=ids,
            )
            glyph = glyph_preview(text, size=size, weight=weight, string_id=sid)
            gboard = Image.new("RGB", (max(480, glyph.width + 40), max(100, glyph.height + 40)), (18, 20, 24))
            gboard.paste(glyph, ((gboard.width - glyph.width) // 2, (gboard.height - glyph.height) // 2), glyph)
            mask = mask_preview(text, size=size, weight=weight, string_id=sid)
        except Exception as exc:
            self.set_status(f"พรีวิวผิดพลาด: {exc}")
            return
        self._photos = [ImageTk.PhotoImage(menu), ImageTk.PhotoImage(gboard), ImageTk.PhotoImage(mask)]
        self.lbl_menu.configure(image=self._photos[0])
        self.lbl_glyph.configure(image=self._photos[1])
        self.lbl_mask.configure(image=self._photos[2])

    def export_to_photoshop(self) -> None:
        """Write Sarabun (or keep existing custom) PNGs into assets/custom and open PS."""
        self._sync_row_text()
        size, weight, y_lift, pct = self._pack_params()
        write_readme()
        written = []
        for sid, _h, th in self.rows:
            # Seed only if missing — don't overwrite hand-edited art.
            if not has_custom(sid):
                img = render_sentence(th, size=size, weight=weight)
                save_custom(sid, img)
            written.append(png_path(sid))
        save_meta({
            "size": size, "weight": weight, "y_lift": y_lift, "y_lift_pct": pct,
            "ids": [sid for sid, _, _ in self.rows],
        })
        self._watch = mtimes()
        self._reload_list_labels()
        ok, msg = open_in_photoshop(written)
        self.refresh_preview()
        self.set_status(f"Export Photoshop: {custom_dir()}")
        messagebox.showinfo(
            "Photoshop",
            f"โฟลเดอร์ sync:\n{custom_dir()}\n\n"
            f"แนะนำ:\n"
            f"• งานเลเยอร์ → Save As เป็น <id>.psd ในโฟลเดอร์นี้ แล้ว Ctrl+S\n"
            f"  Studio จะสร้าง <id>.png ให้อัตโนมัติ\n"
            f"• หรือ Ctrl+S ทับ <id>.png โดยตรงก็ได้\n"
            f"อย่า Save As คนละชื่อ/นามสกุลอื่นโดยไม่มี .png\n\n{msg}",
        )

    def open_photoshop(self) -> None:
        self._sync_row_text()
        i = self.current_index()
        paths = []
        if i is not None:
            sid = self.rows[i][0]
            if not has_custom(sid):
                size, weight, *_ = self._pack_params()
                save_custom(sid, render_sentence(self.rows[i][2], size=size, weight=weight))
            paths = [png_path(sid)]
        else:
            paths = [png_path(sid) for sid, _, _ in self.rows if has_custom(sid)]
        ok, msg = open_in_photoshop(paths)
        self._watch = mtimes()
        self.refresh_preview()
        (messagebox.showinfo if ok else messagebox.showwarning)("Photoshop", msg)

    def open_folder(self) -> None:
        write_readme()
        open_custom_folder(custom_dir())
        self.set_status(str(custom_dir()))

    def clear_current_custom(self) -> None:
        i = self.current_index()
        if i is None:
            return
        sid = self.rows[i][0]
        if clear_custom(sid):
            self._watch = mtimes()
            self._reload_list_labels()
            self.refresh_preview()
            self.set_status(f"ลบ PNG ของ {sid} แล้ว — กลับไปใช้ Sarabun")
        else:
            messagebox.showinfo("Custom", "รายการนี้ยังไม่มี PNG จาก Photoshop")

    def export_install(self) -> None:
        self._sync_row_text()
        entries = [SentenceEntry(sid, th, i) for i, (sid, _h, th) in enumerate(self.rows) if th.strip()]
        if not entries:
            messagebox.showwarning("Export", "ไม่มีประโยค")
            return
        out = repo_root() / "export" / "studio"
        out.mkdir(parents=True, exist_ok=True)
        size, weight, y_lift, pct = self._pack_params()
        em_h = em_height_for_size(size)
        mapping = []
        for e in entries:
            mapping.append({
                "id": e.string_id,
                "thai": e.thai,
                "pua": f"U+{e.code:04X}",
                "size": size,
                "weight": weight,
                "em_height": em_h,
                "y_lift": y_lift,
                "y_lift_pct": pct,
                "custom_png": has_custom(e.string_id),
            })
            glyph_preview(e.thai, size=size, weight=weight, string_id=e.string_id).save(
                out / f"{e.string_id}.png"
            )
        (out / "mapping.json").write_text(json.dumps(mapping, ensure_ascii=False, indent=2), encoding="utf-8")
        n_custom = sum(1 for e in entries if has_custom(e.string_id))
        try:
            path = pack_mod(entries, dest=None, size=size, weight=weight, y_lift=y_lift)
            self.set_status(f"ติดตั้งแล้ว custom={n_custom}/{len(entries)}")
            messagebox.showinfo(
                "Install",
                f"เขียน mod แล้ว\n"
                f"ขนาด {size} → EM {em_h} · เยื้อง ↑{pct}%\n"
                f"ใช้ PNG จาก PS: {n_custom}/{len(entries)}\n{path}\n\n"
                f"รีสตาร์ทเกม · Text Language = English",
            )
        except Exception as exc:
            path = pack_mod(entries, dest=out / "modThaiConsole", size=size, weight=weight, y_lift=y_lift)
            messagebox.showerror("Install", f"ติดตั้งเกมไม่สำเร็จ: {exc}\nเก็บไว้ที่ {path}")


def main() -> None:
    Studio().mainloop()


if __name__ == "__main__":
    main()
