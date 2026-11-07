# ทดสอบผ่าน mod.io (Private)

เป้าหมาย: ยืนยันว่าแพ็กม็อดโหลดผ่านระบบ Mods ในเกมได้ (เมนูเป็นไทยตาม POC)

## 1) สร้าง ZIP

```bat
.venv\Scripts\python devtools\pack_modio.py
```

หรือแพ็กจากม็อดที่ติดตั้งในเกมอยู่แล้ว:

```bat
.venv\Scripts\python devtools\pack_modio.py --from-game
```

ได้ไฟล์: `export\modio\modThaiConsole.zip`  
โครงใน ZIP: `modThaiConsole/content/{blob0.bundle,metadata.store,en.w3strings}`

## 2) อัปโหลด Private

1. เปิด [Witcher 3 Hub บน mod.io](https://mod.io/g/the-witcher-3) แล้ว login  
2. **Add → Mod**  
3. ใส่ชื่อ / คำอธิบายสั้น / รูปปก / แท็ก (เช่น Language)  
4. Visibility = **Private**  
5. Upload ไฟล์ `modThaiConsole.zip` (ใส่ version เช่น `0.1.0-poc`)  
6. Submit

## 3) ทดสอบในเกม (PC Remastered)

1. เมนูหลัก → **Mods** → login CDPR + เชื่อม mod.io  
2. หาม็อด Private ของคุณ → **Subscribe**  
3. รีสตาร์ทเกม  
4. Installed → ติ๊กเปิดม็อด  
5. Text Language = **English**  
6. ดู main menu — ถ้าป้ายเป็นไทยตาม Studio = **OK สำหรับท่อ mod.io**

หมายเหตุ: ขั้นนี้ยังไม่เท่ากับผ่านอนุมัติ console / แท็ก Available on consoles
