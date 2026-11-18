# thai-transcribe

เครื่องมือถอดเสียงเป็นข้อความ **ภาษาไทย** พร้อม **แยกบุคคลที่พูด** และสร้าง
**คำบรรยาย (SRT)** ทำงานในเครื่องทั้งหมด (offline) ไม่ต้องใช้ API key หรือ
token ใด ๆ — เหมาะกับไฟล์บันทึกการประชุม พอดแคสต์ สัมภาษณ์ หรือวิดีโอ

ใช้แบบไม่ต้องติดตั้งได้ที่เว็บ UI: **app.py** (Gradio) — รันในเครื่องหรือ deploy
ขึ้น [Hugging Face Space](https://huggingface.co/spaces) ได้ (ดูหัวข้อ "เว็บแอป")

## ความสามารถ

| ฟีเจอร์ | เทคโนโลยี |
|---|---|
| ถอดเสียงภาษาไทย (timestamp ระดับคำ) | Whisper ผ่าน faster-whisper (CTranslate2) |
| แยกบุคคลที่พูด (speaker diarization) | ECAPA-TDNN embeddings + clustering |
| ตั้งชื่อผู้พูดจริง | ระบุ "สมชาย,สุชาดา" แทน "ผู้พูด 1,2" |
| คำบรรยาย | SRT พร้อมชื่อผู้พูด + TXT + JSON |
| บันทึกการประชุม Word (.docx) | หัวกระดาษ + ตารางข้อมูล + บทถอดความ (สร้างเสมอ) |
| สรุปการประชุม (MoM) | LLM ผ่าน API แบบ OpenAI-compatible (ไม่บังคับ) |

รองรับไฟล์เสียง/วิดีโอแทบทุกนามสกุล (mp3, wav, m4a, mp4, mkv, aac, ogg, flac ฯลฯ)
ผ่าน ffmpeg

## ผลลัพธ์ที่ได้ (ต่อ 1 ไฟล์เสียง)

- `<ชื่อไฟล์>.srt` — คำบรรยายพร้อมชื่อผู้พูด (เปิดกับ VLC/IINA หรือเบิร์นลงวิดีโอได้)
- `<ชื่อไฟล์>.txt` — บทถอดความอ่านรวดเดียว พร้อมเวลาและชื่อผู้พูด
- `<ชื่อไฟล์>.docx` — บันทึกการประชุม Word: หัวกระดาษ + ตารางข้อมูล + บทถอดความ
- `<ชื่อไฟล์>.json` — ข้อมูลดิบครบทุกคำ (เวลา/ผู้พูด/ความมั่นใจ) สำหรับนำไปประมวลผลต่อ
- `<ชื่อไฟล์>.summary.md` — สรุปการประชุม (ภาพรวม/ประเด็น/มติ/สิ่งที่ต้องทำต่อ) เฉพาะเมื่อใช้ `--summarize`

## การสรุปการประชุม (MoM) ด้วย AI

รองรับ LLM ใดก็ได้ที่มี API แบบ OpenAI-compatible (OpenAI, DeepSeek, GLM,
OpenRouter, หรือ LLM ในเครื่องผ่าน ollama/LM Studio) — ตั้งค่าผ่านตัวแปรสภาพแวดล้อม:

```bash
export SUMMARY_API_KEY=sk-...                       # จำเป็น
export SUMMARY_BASE_URL=https://api.openai.com/v1   # เปลี่ยนเป็นผู้ให้บริการอื่นได้
export SUMMARY_MODEL=gpt-4o-mini                    # โมเดลที่ใช้สรุป
```

ถอดเสียงทำงาน offline ทั้งหมดเสมอ — ไม่มีข้อมูลถูกส่งออกนอกเครื่อง เว้นแต่จะเปิดใช้
`--summarize` (จะส่งเฉพาะ "บทถอดความ" ไปยัง API ที่คุณตั้งค่าเท่านั้น)

## การติดตั้ง

ต้องมีก่อน: Python 3.10+ และ ffmpeg

```bash
brew install ffmpeg

python3.13 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

> ย้ายไปรันบนเครื่อง Windows/Linux? ดู **SETUP.md** (มีสคริปต์ติดตั้ง
> `setup_windows.bat` / `setup.sh` ให้คลิกเดียวจบ)

> ครั้งแรกที่รัน โปรแกรมจะดาวน์โหลดโมเดล Whisper large-v3 (~3 GB) และ
> ECAPA (~80 MB) เก็บไว้ในเครื่องอัตโนมัติ ครั้งต่อไปจะไม่โหลดซ้ำ

## การใช้งาน

```bash
# ใช้งานทั่วไป — ถอดไทย + แยกผู้พูดอัตโนมัติ
.venv/bin/python transcribe.py ไฟล์บันทึก.m4a

# ระบุจำนวนผู้พูด (แม่นขึ้นถ้ารู้ล่วงหน้า)
.venv/bin/python transcribe.py meeting.mp3 --speakers 3

# ใช้ชื่อจริงของผู้พูด (เรียงตามลำดับคนที่เริ่มพูดก่อน)
.venv/bin/python transcribe.py meeting.mp3 --speaker-names "สมชาย,สุชาดา,วิภา"

# สรุปการประชุมเป็น MoM ด้วย AI (ตั้งค่า SUMMARY_API_KEY ก่อน)
export SUMMARY_API_KEY=sk-...   # และ/หรือ SUMMARY_BASE_URL, SUMMARY_MODEL
.venv/bin/python transcribe.py meeting.mp3 --summarize

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

## เว็บแอป (ไม่ต้องติดตั้ง)

`app.py` เป็นเว็บ UI ภาษาไทย (Gradio) ให้อัปโหลดไฟล์เสียง/วิดีโอ แล้วดาวน์โหลด
คำบรรยาย SRT + อ่านบทถอดความได้ทันที ใช้ pipeline เดียวกับ CLI

```bash
# ติดตั้ง dependencies เว็บเพิ่มจาก CLI
.venv/bin/pip install -r requirements-web.txt

# รันในเครื่อง -> เปิด http://localhost:7860
.venv/bin/python app.py

# เปิดลิงก์สาธารณะจากเครื่องผ่าน Cloudflare Tunnel (ต้องมี cloudflared)
./run_public_local.sh
```

**Deploy ขึ้น Hugging Face Space (ฟรี ถาวร)**

1. สมัครบัญชี [huggingface.co](https://huggingface.co) แล้วรัน
   `pip install huggingface_hub && huggingface-cli login`
2. `export HF_USER=<ชื่อบัญชี>` แล้ว `./deploy_space.sh`
3. ได้เว็บใช้งานสาธารณะที่ `https://huggingface.co/spaces/<ชื่อบัญชี>/thai-transcribe`

ข้อจำกัดของ Space ฟรี (CPU): ไฟล์ยาวไม่เกิน 10 นาที และประมวลผลช้ากว่าเครื่อง
ตัวเอง — ปรับได้ที่ตัวแปร `MAX_SECONDS` ใน `app.py`

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
