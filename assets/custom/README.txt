ThaiW3Console — sync กับ Photoshop
================================
ไฟล์ที่ Studio อ่านเข้าเกม:  <id>.png   (เช่น 401380.png)
ไฟล์ทำงานใน Photoshop:       <id>.psd  (ชั้นเลเยอร์)

วิธีแนะนำ
1) ใน Studio กด Export → Photoshop (ได้ไฟล์ .png)
2) ใน PS: File > Save As > Photoshop (*.PSD) ชื่อเดียวกัน เช่น 401380.psd
   เก็บในโฟลเดอร์นี้ assets/custom/
3) แต่งเลเยอร์ใน .psd แล้ว Ctrl+S บันทึก .psd
4) Studio จะ export .psd → .png ให้อัตโนมัติ แล้วพรีวิวเอง

หรือถ้าแก้บน .png โดยตรง: Ctrl+S ทับ .png ก็ sync ได้เช่นกัน
อย่า Save As คนละชื่อ/คนละโฟลเดอร์

หมายเหตุ: glyph ในเกมเป็น 1-bit ตาม alpha
