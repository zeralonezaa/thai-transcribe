@echo off
chcp 65001 >nul
REM ติดตั้ง thai-transcribe บน Windows — ต้องมี Python 3.10-3.13 กับ ffmpeg ก่อน
cd /d "%~dp0"

where ffmpeg >nul 2>nul
if errorlevel 1 (
    echo [!] ยังไม่พบ ffmpeg -- ติดตั้งด้วยคำสั่ง:  winget install Gyan.FFmpeg
    echo     แล้วปิด-เปิดหน้าต่างนี้ใหม่ ก่อนรันสคริปต์อีกครั้ง
    pause
    exit /b 1
)

py -3 -m venv .venv 2>nul || python -m venv .venv
if errorlevel 1 (
    echo [!] ยังไม่พบ Python -- ดาวน์โหลดจาก https://www.python.org/downloads/
    echo     สำคัญ: ติ๊ก "Add python.exe to PATH" ตอนติดตั้ง
    pause
    exit /b 1
)

.venv\Scripts\python -m pip install --upgrade pip
.venv\Scripts\pip install -r requirements.txt

echo.
echo ============================================================
echo  ติดตั้งเสร็จ! ทดสอบด้วยคำสั่ง:
echo    .venv\Scripts\python transcribe.py samples\test_thai_2speakers.wav --model small
echo.
echo  ใช้งานจริง:
echo    .venv\Scripts\python transcribe.py "ไฟล์บันทึก.m4a"
echo  เปิดเว็บ UI: .venv\Scripts\python app.py   (แล้วเปิด http://localhost:7860)
echo ============================================================
pause
