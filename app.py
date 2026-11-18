#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
thai-transcribe เว็บแอป (Gradio)

เปิดเว็บ UI ให้อัปโหลดไฟล์เสียง/วิดีโอ แล้วได้คำบรรยาย SRT + บทถอดความ
พร้อมแยกผู้พูด — ใช้ pipeline เดียวกับ CLI (transcribe.py)

รันในเครื่อง:
    .venv/bin/python app.py        # เปิด http://localhost:7860
"""

import os
import tempfile
from pathlib import Path

import gradio as gr

import transcribe as T

# จำกัดความยาวไฟล์ (วินาที) — ปรับได้ตามกำลังเซิร์ฟเวอร์ เช่นบน Hugging Face
#  Space ที่เป็น CPU ฟรี ควรคุมไว้ราว 10 นาที
MAX_SECONDS = int(os.environ.get("MAX_SECONDS", 10 * 60))

AUDIO_EXTS = [".mp3", ".wav", ".m4a", ".aac", ".ogg", ".oga", ".flac",
              ".mp4", ".mov", ".mkv", ".webm", ".aiff", ".aif", ".wma"]


def transcribe_file(file_path, speakers: int, model: str, show_label: bool,
                    progress=gr.Progress()):
    """handler หลัก: ไฟล์เสียง -> (ไฟล์ SRT, บทถอดควาย, สรุป)"""
    if not file_path:
        raise gr.Error("กรุณาเลือกไฟล์เสียง/วิดีโอก่อนกดปุ่ม 'ถอดเสียง'")

    progress(0.05, desc="กำลังอ่านไฟล์เสียง...")
    audio = T.decode_audio(file_path)
    duration = len(audio) / T.SAMPLE_RATE
    if duration > MAX_SECONDS:
        raise gr.Error(f"ไฟล์ยาว {T.clock(duration)} เกินกำหนด "
                       f"(สูงสุด {MAX_SECONDS // 60} นาทีสำหรับเว็บรุ่นนี้)")

    progress(0.15, desc=f"กำลังถอดเสียงด้วยโมเดล {model} "
                        f"(ไฟล์ {T.clock(duration)} — รอสักครู่...)")
    result = T.pipeline(
        audio,
        language="th",
        model_size=model,
        device=os.environ.get("WHISPER_DEVICE", "cpu"),
        speakers=speakers if speakers and speakers > 0 else None,
    )

    progress(0.9, desc="กำลังจัดรูปคำบรรยาย...")
    utts, n_spk = result["utterances"], result["n_speakers"]
    srt_text = T.render_srt(utts, n_spk, speaker_label=show_label)
    txt_text = T.render_txt(utts, n_spk)

    stem = Path(file_path).stem or "transcript"
    srt_file = tempfile.NamedTemporaryFile(
        prefix=f"{stem}_", suffix=".srt", delete=False, mode="w", encoding="utf-8")
    srt_file.write(srt_text)
    srt_file.close()

    summary = (f"✅ เสร็จเรียบร้อย — ผู้พูด {n_spk} คน | ประโยค {len(utts)} | "
               f"ความยาว {T.clock(duration)} | ภาษา {result['language']} "
               f"({result['language_probability']:.0%})")
    return srt_file.name, txt_text, summary


def build_ui() -> gr.Blocks:
    with gr.Blocks(title="thai-transcribe — ถอดเสียงไทย แยกผู้พูด") as demo:
        gr.Markdown(
            """
            # 🎙️ thai-transcribe
            ถอดเสียง **ภาษาไทย** เป็นข้อความ แยกบุคคลที่พูด และได้ **คำบรรยาย SRT**
            พร้อมดาวน์โหลด — ประมวลผลด้วย AI ตัวเดียวกับ
            [โปรเจกต์ GitHub](https://github.com/zeralonezaa/thai-transcribe)

            📌 รองรับไฟล์เสียง/วิดีโอ: mp3, wav, m4a, mp4, mkv, aac, ogg, flac ฯลฯ
            (ยาวไม่เกิน **10 นาที**) · ใช้งานฟรี · ไฟล์ยิ่งยาวยิ่งรอนาน
            """
        )
        with gr.Row():
            with gr.Column():
                file_in = gr.File(
                    label="ไฟล์เสียง / วิดีโอ",
                    file_types=AUDIO_EXTS,
                )
                speakers_in = gr.Slider(
                    0, 10, value=0, step=1,
                    label="จำนวนผู้พูด",
                    info="0 = ให้ระบบตรวจอัตโนมัติ (ถ้ารู้จำนวนจริง ใส่เลยจะแม่นขึ้น)",
                )
                model_in = gr.Dropdown(
                    choices=["small", "medium", "large-v3"],
                    value=os.environ.get("WEB_MODEL_DEFAULT", "small"),
                    label="ขนาดโมเดล Whisper",
                    info="small = เร็ว | medium = สมดุล | large-v3 = แม่นสุดแต่ช้ามาก",
                )
                label_in = gr.Checkbox(value=True, label="ใส่ชื่อผู้พูดในคำบรรยาย")
                btn = gr.Button("🚀 ถอดเสียง", variant="primary")
            with gr.Column():
                summary_out = gr.Markdown("⏳ ยังไม่มีผลลัพธ์")
                srt_out = gr.File(label="ดาวน์โหลดคำบรรยาย (SRT)")
                txt_out = gr.Textbox(
                    label="บทถอดความ (พร้อมชื่อผู้พูดและเวลา)",
                    lines=14, max_lines=25, buttons=["copy"],
                )
        btn.click(
            transcribe_file,
            inputs=[file_in, speakers_in, model_in, label_in],
            outputs=[srt_out, txt_out, summary_out],
            api_name="transcribe",
        )
        gr.Markdown(
            """
            ---
            ⚠️ ระบบประมวลผลทีละไฟล์ตามคิว — ไฟล์ 1 นาที ใช้เวลาราว 1-3 นาทีขึ้นกับโมเดล
            · การแยกผู้พูดเป็นการประมาณจากลายเสียง อาจคลาดเคลื่อนได้ในบางกรณี
            """
        )
    return demo


if __name__ == "__main__":
    demo = build_ui()
    demo.queue(max_size=20, default_concurrency_limit=1)
    demo.launch(server_name="0.0.0.0", server_port=int(os.environ.get("PORT", 7860)))
