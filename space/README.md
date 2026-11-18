---
title: thai-transcribe
emoji: 🎙️
colorFrom: blue
colorTo: indigo
sdk: gradio
sdk_version: 6.32.0
app_file: app.py
pinned: true
license: mit
short_description: ถอดเสียงไทย แยกผู้พูด ได้คำบรรยาย SRT
---

# 🎙️ thai-transcribe

อัปโหลดไฟล์เสียง/วิดีโอ แล้วได้:

- **คำบรรยาย SRT** พร้อมชื่อผู้พูด (ผู้พูด 1, ผู้พูด 2, ...)
- **บทถอดความ** ภาษาไทยพร้อม timestamp ระดับประโยค
- การแยกบุคคลที่พูดทำด้วยลายเสียง (ECAPA-TDNN) ทำงานใน Space นี้ทั้งหมด

โค้ดเปิดเผยที่
[github.com/zeralonezaa/thai-transcribe](https://github.com/zeralonezaa/thai-transcribe)
(MIT License)

## ข้อจำกัดของ Space ฟรี (CPU)

- รับไฟล์ยาวไม่เกิน **10 นาที**
- ประมวลผลทีละไฟล์ตามคิว — ไฟล์ 1 นาที ใช้เวลาราว 1-3 นาที (โมเดล small)
- ถ้าใช้งานหนัก/ไฟล์ยาว แนะนำรัน CLI บนเครื่องตัวเอง (ดู GitHub)
