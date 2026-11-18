# thai-transcribe

เครื่องมือถอดเสียงเป็นข้อความ **ภาษาไทย** พร้อม **แยกบุคคลที่พูด** และสร้าง
**คำบรรยาย (SRT)** ทำงานในเครื่องทั้งหมด (offline) ไม่ต้องใช้ API key หรือ
token ใด ๆ — เหมาะกับไฟล์บันทึกการประชุม พอดแคสต์ สัมภาษณ์ หรือวิดีโอ

## ความสามารถ

| ฟีเจอร์ | เทคโนโลยี |
|---|---|
| ถอดเสียงภาษาไทย (timestamp ระดับคำ) | Whisper ผ่าน faster-whisper (CTranslate2) |
| แยกบุคคลที่พูด (speaker diarization) | ECAPA-TDNN embeddings + clustering |
| คำบรรยาย | SRT พร้อมชื่อผู้พูด + TXT + JSON |

รองรับไฟล์เสียง/วิดีโอแทบทุกนามสกุล (mp3, wav, m4a, mp4, mkv, aac, ogg, flac ฯลฯ)
ผ่าน ffmpeg

## ผลลัพธ์ที่ได้ (ต่อ 1 ไฟล์เสียง)

- `<ชื่อไฟล์>.srt` — คำบรรยายพร้อมชื่อผู้พูด (เปิดกับ VLC/IINA หรือเบิร์นลงวิดีโอได้)
- `<ชื่อไฟล์>.txt` — บทถอดความอ่านรวดเดียว พร้อมเวลาและชื่อผู้พูด
- `<ชื่อไฟล์>.json` — ข้อมูลดิบครบทุกคำ (เวลา/ผู้พูด/ความมั่นใจ) สำหรับนำไปประมวลผลต่อ

## การติดตั้ง

ต้องมีก่อน: Python 3.10+ และ ffmpeg

```bash
brew install ffmpeg

python3.13 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

> ครั้งแรกที่รัน โปรแกรมจะดาวน์โหลดโมเดล Whisper large-v3 (~3 GB) และ
> ECAPA (~80 MB) เก็บไว้ในเครื่องอัตโนมัติ ครั้งต่อไปจะไม่โหลดซ้ำ

## การใช้งาน

```bash
# ใช้งานทั่วไป — ถอดไทย + แยกผู้พูดอัตโนมัติ
.venv/bin/python transcribe.py ไฟล์บันทึก.m4a

# ระบุจำนวนผู้พูด (แม่นขึ้นถ้ารู้ล่วงหน้า)
.venv/bin/python transcribe.py meeting.mp3 --speakers 3

# อยากได้คำบรรยายสะอาด ๆ ไม่มีชื่อผู้พูด (เช่นจะเบิร์นลงวิดีโอ)
.venv/bin/python transcribe.py clip.mp4 --no-speaker-label

# ไฟล์ยาว/อยากให้เร็วขึ้น — ลดขนาดโมเดล (แลกกับความแม่น)
.venv/bin/python transcribe.py meeting.mp3 --model medium

# Apple Silicon — ลอง MPS ได้เร็วขึ้น ~2 เท่า (ยังเป็น experimental)
.venv/bin/python transcribe.py meeting.mp3 --device mps
```

## ตัวเลือกที่สำคัญ

| ตัวเลือก | ค่าเริ่มต้น | คำอธิบาย |
|---|---|---|
| `--model` | `large-v3` | tiny / base / small / medium / large-v3 — สำหรับไทยแนะนำ `large-v3` (แม่นสุด) หรือ `medium` (เร็วกว่า ~3 เท่า) |
| `--language` | `th` | รหัสภาษา เช่น `en`, หรือ `auto` ให้ตรวจอัตโนมัติ |
| `--task` | `transcribe` | `translate` = แปลเป็นภาษาอังกฤษ |
| `--speakers` | ประมาณอัตโนมัติ | ระบุจำนวนผู้พูดถ้าทราบล่วงหน้า |
| `--cluster-threshold` | `0.6` | ปรับความ "ง่ายต่อการแยกคน" — สูงขึ้น = รวมกลุ่มง่ายขึ้น |
| `--no-diarize` | — | ข้ามการแยกผู้พูด (เร็วขึ้น) |
| `--no-speaker-label` | — | ไม่ใส่ชื่อผู้พูดใน SRT |
| `--speaker-template` | `ผู้พูด {n}` | เช่น `'Speaker {n}'` |
| `--max-chars` / `--max-duration` | 80 / 6.0 | ขนาดสูงสุดของแต่ละบล็อกคำบรรยาย |
| `--initial-prompt` | (ไทยอัตโนมัติ) | บังคับสไตล์/คำศัพท์เฉพาะ เช่น ชื่อองค์กร ชื่อผลิตภัณฑ์ |
| `--device` | `cpu` | `mps` (Apple Silicon) / `auto` |

## เทคนิคการใช้งาน

**เบิร์นคำบรรยายลงวิดีโอ**

```bash
ffmpeg -i video.mp4 -vf subtitles=meeting.srt out.mp4
```

**คำเฉพาะทาง/ชื่อเฉพาะถูกผิดบ่อย** — ใส่ผ่าน `--initial-prompt`
เช่น `--initial-prompt "บริษัท ไทยพาณิชย์ จำกัด (มหาชน) การประชุมคณะกรรมการ"`

**ไฟล์ยาวหลายชั่วโมง** — ใช้ `--model medium --device mps` และ `--cpu-threads`
ตามจำนวน core ของเครื่อง

## แนวทางทำงานภายใน

1. **ถอดเสียง** — faster-whisper ปิด temperature fallback (ผลคงที่ทุกครั้ง)
   พร้อม VAD ตัดช่วงเงียบ และ `condition_on_previous_text=False` กัน
   ข้อผิดพลาดลากยาวข้ามประโยค
2. **แยกผู้พูด** — แบ่งเสียงพูดเป็นหน้าต่าง ~4 วิ (ตัดขอบ noise ด้วยพลังงานเสียง)
   สกัดลายเสียง 192 มิติด้วย ECAPA-TDNN แล้วจัดกลุ่มด้วย agglomerative
   clustering — โหมดอัตโนมัติจะลองหลายค่า threshold แล้วเลือกค่าที่ได้
   silhouette score ดีที่สุด จากนั้นผูกป้ายผู้พูดระดับคำด้วยการซ้อนทับเวลา
3. **ประกอบผลลัพธ์** — รวมคำเป็นประโยคต่อผู้พูด, ซ่อมคำที่ Whisper ตัดข้าม
   ประโยค (กรณีขึ้นต้นด้วยสระลอย), หั่นบล็อกคำบรรยายที่ขอบเขตวลี

## ข้อจำกัด

- ประมวลผลด้วย CPU/MPS ในเครื่อง — ไฟล์ยาวหลายชั่วโมงใช้เวลาพอสมควร
- คนพูดซ้อนกัน (crosstalk) หรือเสียงคล้ายกันมาก อาจแยกผู้พูดคลาดเคลื่อน
- การแยกผู้พูดบอกเพียง "ผู้พูด 1, 2, 3" — ไม่ระบุตัวตนคน

## ทดสอบ

```bash
samples/make_test_audio.sh   # สังเคราะห์บทสนทนาไทย 2 คน ด้วยเสียง macOS TTS
.venv/bin/python transcribe.py samples/test_thai_2speakers.wav
```
