# Experiments — Bitmap Sentence Glyphs

โปรเจกต์: ThaiW3Console · เกม: The Witcher 3 Remastered (Steam, v5.01c) · วันที่: 2026-11-07

## สรุปสถานะ

| เกณฑ์ | ผล |
| --- | --- |
| แทนข้อความ main menu ด้วย PUA + glyph ทั้งประโยค | **สำเร็จ** |
| ฟอนต์เรนเดอร์ | Google Sarabun Bold → mask → DefineFont3 shape |
| แหล่งคำแปล | Google Sheets w3tu (`sheet.py`) |
| อ่านได้ในเกม / ขนาดสูงพอ | ผ่าน (หลังล็อกความสูง `0.85·EM`) |
| จัดแนวแนวนอนในคอลัมน์เมนู | **ดีขึ้นชัด** หลัง shared advance + center (ยืนยันจากภาพ) |
| จัดกลางแนวตั้งในช่องไฮไลต์ | เคยชิดล่างเพราะ glyph ยื่นใต้ baseline 25% → จัดกลางในแถบ [−EM_h, 0] + ตัวปรับ `เยื้องแนวตั้ง` ใน studio |
| ขอบตัวอักษร | ยังหยัก/ไม่ antialias — polish |

## เทคนิคที่ใช้ (ยืนยันแล้ว)

1. เรนเดอร์ประโยคไทยเป็น PNG (Sarabun)
2. แปลง alpha เป็น mask 1-bit แล้วเป็น shape แบบ scanline rectangles ใน `DefineFont3`
3. map รหัส PUA (`U+E000+n`) → glyph ทั้งประโยค
4. ใน `en.w3strings` ใส่ PUA ตัวเดียวแทนข้อความอังกฤษ
5. แพ็ก `mods/modThaiConsole` (`fonts_en.redswf` + `en.w3strings`) + `mods.settings` Priority=0

ข้อจำกัดถาวร: advance ของ DefineFont3 เป็น **SI16 ≤ 32767** (~1.6·EM) — ประโยคกว้างกว่านี้ใช้ overhang (shape ยื่นเกิน advance)

## Timeline การทดลอง

### 1) Pack แรก — ไม่เห็นผลบนเมนู

- แทน id ผิด (`Quit` แทน `Exit`) และ `Continue` คนละชุด
- `modThaiConsole` ไม่อยู่ใน `mods.settings` → string ไม่ชนะ

### 2) ASCII marker — แบบ A

เมนูโชว์ `THAI-CONT2` / `THAI-NEW3` / … → ยืนยันว่า override `en.w3strings` ใช้ได้

**id จริงของ main menu**

| id | EN | TH (จาก sheet) |
| --- | --- | --- |
| 1083486 | Continue | เล่นเกมต่อ |
| 1083488 | New game | เริ่มเกมใหม่ |
| 1066020 | Load game | โหลดเกม |
| 1066021 | Settings | ตัวเลือก |
| 1236547 | Mods | ม็อด |
| 1469941 | Patch Highlights | ไฮไลต์แพตช์ |
| 1066066 | Credits | เครดิต |
| 401380 | Exit | ออก |

### 3) PUA glyph รอบแรก — เห็นไทย แต่ขนาดไม่คงที่

ประโยคยาวถูกสเกลลงคนละค่าเพื่อไม่ให้ advance > 32767 → «ออก» ใหญ่ / «ไฮไลต์แพตช์» เล็ก

### 4) `uniform_scale` แบบบีบด้วยความกว้าง — เล็กทั้งชุด

สเกลเดียวที่ถูกจำกัดด้วยประโยคยาวที่สุด → อ่านยาก

### 5) สเกลตามความสูง `0.85·EM` + overhang — อ่านได้

ขนาดสูงสม่ำเสมอ อ่านรู้เรื่องเต็มช่องเมนู → **MVP ผ่าน**

ยังเหลือ: ขอบหยัก (scanline 1-bit, ไม่มี antialias) และ **ข้อความในคอลัมน์ไม่ align**

## Alignment (สังเกตจากภาพในเกม)

อาการ: ป้ายไทยในแนวตั้ง **ไม่ตรงแนวกัน** (ซ้าย/กลางของคำไม่เรียงเป็นคอลัมน์เดียว) ทั้งที่ความสูงตัวอักษรใกล้เคียงกัน

สาเหตุที่เป็นไปได้สูง:

- แต่ละ glyph มี **advance ไม่เท่ากัน** (สั้น ≈ ความกว้างจริง, ยาวถูกตัดที่ 32767)
- TextField เมนูจัดกลางตาม advance → จุดศูนย์กลางของกล่อง metrics ไม่ตรงกับจุดกลางของหมึกตัวอักษรเมื่อมี overhang หรือ advance สั้นกว่าเพื่อน
- ยังไม่ได้บังคับ **slot กว้างคงที่** แล้วจัดกลางหมึกภายใน slot

แนวแก้ที่ติดตั้งแล้ว + ยืนยันจากภาพ:

- ทุกป้ายใช้ `advance` เดียวกัน (= 32767) + จัดกลางหมึกใน slot → **คอลัมน์เรียงตรงขึ้น**
- ยังเหลือ: baseline ในกรอบไฮไลต์ลอยขึ้นนิด, ขอบหยักจาก scanline 1-bit

## ไฟล์ที่เกี่ยวข้อง

- `core/render.py` — Sarabun → PNG
- `core/swf_bitmap_glyph.py` — mask → glyph / inject ลง `fonts_en.redswf`
- `core/pack_mod.py` — `MENU_POC` + ติดตั้ง mod
- `spikes/02_main_menu_poc.py` — แพ็ก POC จาก sheet
- `studio/app.py` — edit/preview

## Spike 4 — ขยายด้วยคำแปล ThaiW3Setup + วัดขนาด pack

แหล่ง: `ThaiW3Setup/assets/translations.json.gz` · สคริปต์: `spikes/03_pack_size.py` · รายงาน: `export/spike4/SIZE_REPORT.md`

| ชุดที่ pack จริง | glyphs | fonts_en (1 ฟอนต์) | mod รวม |
| --- | --- | --- | --- |
| สั้น–กลาง ≤100 ตัว เต็ม PUA | 6,400 | 11.7 MB | **26 MB** |
| ซับ/บทพูด 80–250 ตัว (ตัวอย่าง) | 400 | 6.3 MB | 21 MB |
| รอบแก้ (force MENU_POC + scale แยก + size 52 ×3 ฟอนต์) | 6,400 | **58 MB** | **~73 MB** |

ข้อค้นพบ:

- ชีตมี ~**86k** ข้อความไม่ซ้ำ แต่ BMP PUA มีแค่ **6,400** โค้ด → ใส่ครบทั้งเกมในฟอนต์เดียวไม่ได้
- ถ้า inject ครบ 3 ฟอนต์ใน `fonts_en.redswf` ส่วน glyph ≈ ×3 (~50 MB สำหรับชุด 6,400)
- ประมาณ shape ดิบทั้งชีต ~**2.5–3 GB / ฟอนต์** (ก่อน zlib) — ไม่สมเหตุผลเทียบ `modThaiLanguage` ของ Setup (~16.5 MB แปลครบแบบตัวอักษร)
- **Mods / Patch Highlights** ไม่อยู่ในชีต id → หลุดจากชุด 6,400 จนบังคับ `MENU_POC` + `by_text`
- **ไทยในแถบ Options เล็ก:** `normalize_masks` + scale รวมทำให้ป้ายสั้นหดตามประโยคสูงสุด → ปิด `shared_scale` ใน bulk pack
- **`3ลาก่อน` / ข้อความทับกัน:** glyph กว้างกว่า SI16 แล้ว `align=center` → x ติดลบยื่นซ้ายทับ `3.` และยื่นขวาทับป้ายข้าง ๆ → bulk pack ใช้ `fit_width` + `align=left`
- **จอดำ / ค้างเข้าเกม:** ชุด 6,400 × 3 ฟอนต์ (`fonts_en` ~73 MB, mod ~87 MB) ทำให้โหลดค้าง — ถอนออกแล้วกลับเมนู POC 8 ป้าย; ชุดใหญ่เก็บที่ `mods_disabled\modThaiConsole_6400_hang`

## Fallback ที่ยังไม่ใช้

**Fallback A:** patch texture atlas ของเมนูแบบ `ThaiW3Setup/core/logo.py` — สำรองถ้าคุณภาพ glyph / align ยังไม่พอสำหรับ UI จริง
