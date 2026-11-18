#!/bin/bash
# ติดตั้ง thai-transcribe บน Linux/macOS — ต้องมี Python 3.10+ กับ ffmpeg ก่อน
set -euo pipefail
cd "$(dirname "$0")"

if ! command -v ffmpeg >/dev/null; then
  echo "[!] ยังไม่พบ ffmpeg — ติดตั้งด้วย:  sudo apt install ffmpeg   (Ubuntu/Debian)"
  exit 1
fi

PY=$(command -v python3)
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/pip install -r requirements.txt

echo
echo "============================================================"
echo " ติดตั้งเสร็จ! ทดสอบด้วยคำสั่ง:"
echo "   .venv/bin/python transcribe.py samples/test_thai_2speakers.wav --model small"
echo
echo " ใช้งานจริง:  .venv/bin/python transcribe.py 'ไฟล์บันทึก.m4a'"
echo " เปิดเว็บ UI: .venv/bin/python app.py   (แล้วเปิด http://localhost:7860)"
echo "============================================================"
