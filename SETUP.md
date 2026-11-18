# คู่มือติดตั้งบนเครื่อง PC (Windows / Linux)

สำหรับการย้าย thai-transcribe ไปรันบนเครื่องอื่น เช่น i7-14700K + 32GB RAM
(ถอดเสียงจะเร็วกว่า MacBook Air M5 ราว 3-5 เท่ากับโมเดล large-v3)

## สิ่งที่ต้องมีก่อน

| โปรแกรม | วิธีติดตั้ง |
|---|---|
| **Python 3.10–3.13** | [python.org/downloads](https://www.python.org/downloads/) — Windows ต้องติ๊ก **"Add python.exe to PATH"** |
| **ffmpeg** | Windows: `winget install Gyan.FFmpeg` แล้วปิด-เปิด Terminal / Linux: `sudo apt install ffmpeg` |

## ติดตั้ง (แกะ zip แล้วเข้าโฟลเดอร์)

**Windows** — ดับเบิลคลิก `setup_windows.bat` (หรือรันใน cmd)

**Linux** — `./setup.sh`

จบแล้วรอได้เลย ไม่ต้องตั้งค่าอะไรเพิ่ม

## การใช้งาน

```bat
:: Windows
.venv\Scripts\python transcribe.py "ไฟล์บันทึกการประชุม.m4a"
.venv\Scripts\python transcribe.py meeting.mp3 --speakers 4 --speaker-names "สมชาย,สุชาดา,วิภา,พิธีกร"
.venv\Scripts\python app.py        :: เปิดเว็บ UI ที่ http://localhost:7860
```

```bash
# Linux
.venv/bin/python transcribe.py "ไฟล์บันทึกการประชุม.m4a"
.venv/bin/python app.py            # เว็บ UI
```

ครั้งแรกที่รันจะดาวน์โหลดโมเดล Whisper large-v3 (~3GB) + ECAPA (~80MB) —
ครั้งต่อไปไม่โหลดซ้ำ

## เคล็ดลับสำหรับเครื่อง i7-14700K

- ค่าเริ่มต้น (`--model large-v3`, CPU int8) คือค่าที่ดีที่สุดของเครื่องนี้อยู่แล้ว
  ไฟล์ 1 ชม. ใช้เวลาราว 15-30 นาที (ประมาณการ)
- อยากเร็วขึ้นอีกแลกกับความแม่น: `--model medium` (เร็วราว 3 เท่า)
- ถ้ารู้สึกว่าช้าผิดปกติ ลอง `--cpu-threads 8` (บางครั้ง E-core ถ่วงให้ช้าลง)
- **ถ้าเครื่องมีการ์ดจอ NVIDIA**: สั่ง `.venv\Scripts\pip install nvidia-cublas-cu12 nvidia-cudnn-cu12`
  แล้วเพิ่ม `--device auto` จะเร็วขึ้นอีกหลายเท่า

## ปัญหาที่พบบ่อย

- **`ไม่พบโปรแกรม ffmpeg`** — ติดตั้ง ffmpeg แล้วปิด-เปิดหน้าต่าง Terminal ใหม่
- **เสียงออกมาเป็นภาษาอื่น** — เพิ่ม `--language th`
- **ไฟล์ยาวมาก (2-3 ชม.)** — แนะนำ `--model medium` และปล่อยรันไว้
