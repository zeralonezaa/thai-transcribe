#!/bin/bash
# สร้างไฟล์เสียงทดสอบ: บทสนทนาภาษาไทย 2 ผู้พูด (ใช้เสียง Kanya ของ macOS)
# ผู้พูดคนที่ 2 ปรับ pitch ให้ต่ำลงเพื่อจำลองเสียงคนละคน
# ผลลัพธ์: samples/test_thai_2speakers.wav
set -euo pipefail
cd "$(dirname "$0")"

RATE=22050
VOICE="Kanya"

s1=(
  "สวัสดีครับ ยินดีต้อนรับเข้าสู่การประชุมในวันนี้"
  "เรื่องแรกคืองบประมาณของโครงการในไตรมาสถัดไป"
  "และเรื่องสุดท้ายคือการจัดอบรมทีมงานในเดือนหน้า"
)
s2=(
  "สวัสดีค่ะ วันนี้เรามีวาระสำคัญที่ต้องหารือกันสามเรื่อง"
  "เรื่องที่สองคือแผนการตลาดสำหรับผลิตภัณฑ์ตัวใหม่"
  "ถ้าอย่างนั้นเริ่มจากเรื่องแรกเลยนะคะ"
)

rm -f list.txt part*.wav silence.wav test_thai_2speakers.wav
ffmpeg -y -v error -f lavfi -i "anullsrc=r=${RATE}:cl=mono" -t 0.8 -c:a pcm_s16le silence.wav

i=0
for turn in 1 2 1 2 1 2; do
  i=$((i+1))
  if [ "$turn" = "1" ]; then
    text="${s1[$((i/2))]}"
    say -v "$VOICE" -o "part${i}.wav" --data-format="LEI16@${RATE}" "$text"
  else
    text="${s2[$((i/2 - 1))]}"
    say -v "$VOICE" -o "part_raw${i}.wav" --data-format="LEI16@${RATE}" "$text"
    # ลด pitch ~20% แล้วเร่งความเร็วกลับ ~1.25 เท่า -> เสียง "คนละคน"
    ffmpeg -v error -i "part_raw${i}.wav" -af "asetrate=${RATE}*0.8,aresample=${RATE},atempo=1.25" \
      -ac 1 -c:a pcm_s16le "part${i}.wav"
    rm -f "part_raw${i}.wav"
  fi
  echo "file 'part${i}.wav'" >> list.txt
  echo "file 'silence.wav'" >> list.txt
done

ffmpeg -y -v error -f concat -safe 0 -i list.txt -c:a pcm_s16le test_thai_2speakers.wav
rm -f part*.wav silence.wav list.txt
echo "สร้างไฟล์แล้ว: $(pwd)/test_thai_2speakers.wav"
