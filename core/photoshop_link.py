"""Find / launch Adobe Photoshop; export PSD → PNG for Studio sync."""
from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path


def find_photoshop() -> Path | None:
    env = os.environ.get("PHOTOSHOP_EXE")
    if env and Path(env).is_file():
        return Path(env)

    roots = [
        Path(r"C:\Program Files\Adobe"),
        Path(r"C:\Program Files (x86)\Adobe"),
    ]
    hits: list[Path] = []
    for root in roots:
        if not root.is_dir():
            continue
        hits.extend(root.glob("Adobe Photoshop */Photoshop.exe"))
    hits = sorted({h.resolve() for h in hits if h.is_file()}, key=lambda p: p.as_posix(), reverse=True)
    return hits[0] if hits else None


def _jsx_string_path(path: Path) -> str:
    """Path literal for ExtendScript File() — forward slashes."""
    return str(path.resolve()).replace("\\", "/")


def export_psd_to_png(psd_path: Path, png_path: Path | None = None) -> tuple[bool, str]:
    """Flatten-export a PSD to PNG via Photoshop JSX (keeps layers editable in .psd)."""
    psd_path = psd_path.resolve()
    if not psd_path.is_file():
        return False, f"ไม่พบ {psd_path}"
    png_path = (png_path or psd_path.with_suffix(".png")).resolve()
    ps = find_photoshop()
    if ps is None:
        return False, "ไม่พบ Photoshop.exe — ตั้ง PHOTOSHOP_EXE หรือ Save เป็น PNG เอง"

    psd_js = _jsx_string_path(psd_path)
    png_js = _jsx_string_path(png_path)
    jsx = f"""
#target photoshop
app.displayDialogs = DialogModes.NO;
var psd = new File("{psd_js}");
var png = new File("{png_js}");
var doc = app.open(psd);
var opts = new PNGSaveOptions();
opts.compression = 6;
opts.interlaced = false;
doc.saveAs(png, opts, true, Extension.LOWERCASE);
doc.close(SaveOptions.DONOTSAVECHANGES);
"""
    with tempfile.NamedTemporaryFile("w", suffix=".jsx", delete=False, encoding="utf-8") as fh:
        fh.write(jsx)
        jsx_path = Path(fh.name)
    try:
        # /r runs the script; wait so PNG exists before Studio reloads
        proc = subprocess.run(
            [str(ps), "/r", str(jsx_path)],
            timeout=120,
            check=False,
        )
        if not png_path.is_file():
            return False, (
                f"Photoshop ไม่ได้สร้าง PNG (exit {proc.returncode})\n"
                f"ลอง File > Export > Export As > PNG ชื่อ {png_path.name}"
            )
        return True, f"export {psd_path.name} → {png_path.name}"
    except subprocess.TimeoutExpired:
        return False, "Photoshop export หมดเวลา"
    except OSError as exc:
        return False, str(exc)
    finally:
        try:
            jsx_path.unlink(missing_ok=True)
        except OSError:
            pass


def open_in_photoshop(paths: list[Path]) -> tuple[bool, str]:
    """Open PNG/PSD files in Photoshop."""
    files = [p for p in paths if p.is_file()]
    if not files:
        return False, "ไม่มีไฟล์ให้เปิด"

    ps = find_photoshop()
    if ps is None:
        os.startfile(files[0])  # type: ignore[attr-defined]
        subprocess.Popen(["explorer", "/select,", str(files[0])])
        return True, (
            f"ไม่พบ Photoshop.exe — เปิดด้วยโปรแกรมเริ่มต้นแล้ว\n"
            f"ตั้ง PHOTOSHOP_EXE\nโฟลเดอร์: {files[0].parent}"
        )

    subprocess.Popen([str(ps), *[str(p) for p in files]], cwd=str(files[0].parent))
    return True, f"เปิดใน Photoshop แล้ว ({len(files)} ไฟล์)\n{ps}"


def open_custom_folder(folder: Path) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    subprocess.Popen(["explorer", str(folder)])
