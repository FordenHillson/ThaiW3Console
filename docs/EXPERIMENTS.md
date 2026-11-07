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

## Fallback ที่ยังไม่ใช้

**Fallback A:** patch texture atlas ของเมนูแบบ `ThaiW3Setup/core/logo.py` — สำรองถ้าคุณภาพ glyph / align ยังไม่พอสำหรับ UI จริง
