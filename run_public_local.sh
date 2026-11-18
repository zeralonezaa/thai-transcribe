#!/bin/bash
# เปิดเว็บแอปบนเครื่อง + สร้างลิงก์สาธารณะทันทีผ่าน Cloudflare Tunnel
# (ใช้ได้ตราบใดที่เครื่องนี้เปิดอยู่และสคริปต์ยังรันอยู่)
#
# ครั้งแรกต้องมี cloudflared:  brew install cloudflared
set -euo pipefail
cd "$(dirname "$0")"

if ! command -v cloudflared >/dev/null; then
  echo "ยังไม่มี cloudflared — ติดตั้งด้วย: brew install cloudflared" >&2
  exit 1
fi

PORT="${PORT:-7860}"

echo "▶ เริ่มเว็บเซิร์ฟเวอร์ (port $PORT) ..."
.venv/bin/python app.py &
APP_PID=$!
trap 'kill $APP_PID 2>/dev/null || true' EXIT

sleep 8
echo
echo "▶ เปิด tunnel สาธารณะ — ลิงก์อยู่บรรทัดที่เขียนว่า trycloudflare.com"
echo "──────────────────────────────────────────────"
cloudflared tunnel --url "http://localhost:$PORT"
