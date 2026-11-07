# ThaiW3Console

R&D: แปล The Witcher 3 ด้วยเทคนิค **bitmap sentence glyph** — เรนเดอร์ประโยคไทยด้วย Google Sarabun เป็นรูป แล้วฝังเป็น glyph ทั้งประโยคใน `DefineFont3` (รหัส PUA) แทนข้อความใน `.w3strings`

แยกจาก [ThaiW3Setup](https://github.com/FordenHillson/ThaiW3Setup) ซึ่งใช้ฟอนต์ตัวอักษรทีละตัว

## สถานะ

ทดลอง / POC — เป้าหมายรอบแรกคือให้เห็นข้อความไทยทับป้าย **main menu** (New game / Continue / Quit)

## ติดตั้งเครื่องมือ

```bat
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

ตั้ง `WITCHER3_PATH` ถ้าเกมไม่อยู่ที่ Steam library เริ่มต้น

## Spike

```bat
:: สร้าง mod ทดสอบใน export\spike1 (ไม่แตะเกม)
python spikes\01_bitmap_glyph_swf.py

:: ติดตั้งเข้า mods\modThaiConsole
python spikes\01_bitmap_glyph_swf.py --install

:: POC จาก Google Sheets
python spikes\02_main_menu_poc.py --install
```

หลังติดตั้ง: ตั้ง **Options → Language → Text Language = English** แล้วดู main menu

## Studio (preview + Photoshop sync)

```bat
launch_studio.bat
```

หรือ `python -m studio`

1. **Export → Photoshop** — สร้าง `assets/custom/<id>.png` แล้วเปิดใน PS  
2. แต่งใน PS แล้ว **Save ทับไฟล์เดิม** → Studio พรีวิวเอง (watch โฟลเดอร์)  
3. **Export + Install เข้าเกม** — ใช้ PNG จาก PS ถ้ารมี ไม่งั้นใช้ Sarabun  

ตั้ง `PHOTOSHOP_EXE` ถ้าระบบหา Photoshop ไม่เจอ

หมายเหตุ: glyph ในเกมเป็น 1-bit ตาม alpha — เงาสีเทาหลายระดับจะกลายเป็นขาวทึบ

## ทดสอบ mod.io (Private)

```bat
python devtools\pack_modio.py --from-game
```

ได้ `export\modio\modThaiConsole.zip` — อัปเป็น **Private** บน [mod.io](https://mod.io/g/the-witcher-3) แล้ว Subscribe จากเมนู Mods ในเกม  
รายละเอียด: `docs/MODIO_PRIVATE.md`

## โครงสร้าง

- `core/render.py` — ประโยค → PNG (Sarabun)
- `core/custom_art.py` / `core/photoshop_link.py` — PNG sync กับ Photoshop
- `core/preview_board.py` — ประกอบพรีวิวเมนู / mask
- `core/swf_bitmap_glyph.py` — PNG mask → shape glyph ใน `fonts_en.redswf`
- `core/pack_mod.py` — แพ็ก `modThaiConsole`
- `assets/custom/` — โฟลเดอร์ sync PNG ต่อ string id
- `studio/` — เครื่องมือ edit/preview
- `docs/EXPERIMENTS.md` — บันทึกผลทดลอง

## เครดิต

คำแปลชุมชน w3tu / Google Sheets · The Witcher 3 © CD PROJEKT S.A.
