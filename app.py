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

import summarize as S
import transcribe as T
from docx_export import export_docx

# จำกัดความยาวไฟล์ (วินาที) — ปรับได้ตามกำลังเซิร์ฟเวอร์ เช่นบน Hugging Face
#  Space ที่เป็น CPU ฟรี ควรคุมไว้ราว 10 นาที
MAX_SECONDS = int(os.environ.get("MAX_SECONDS", 10 * 60))

AUDIO_EXTS = [".mp3", ".wav", ".m4a", ".aac", ".ogg", ".oga", ".flac",
              ".mp4", ".mov", ".mkv", ".webm", ".aiff", ".aif", ".wma"]


def transcribe_file(file_path, speakers: int, model: str, show_label: bool,
                    names_text: str, do_summary: bool, progress=gr.Progress()):
    """handler หลัก: ไฟล์เสียง -> (SRT, DOCX, บทถอดความ, สรุป MoM, สถานะ)"""
    if not file_path:
        raise gr.Error("กรุณาเลือกไฟล์เสียง/วิดีโอก่อนกดปุ่ม 'ถอดเสียง'")

    names = [n.strip() for n in (names_text or "").split(",") if n.strip()] or None

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

    progress(0.85, desc="กำลังจัดรูปคำบรรยาย...")
    utts, n_spk = result["utterances"], result["n_speakers"]
    srt_text = T.render_srt(utts, n_spk, speaker_label=show_label, names=names)
    txt_text = T.render_txt(utts, n_spk, names=names)

    # สรุปการประชุมด้วย LLM (ถ้าติ๊กและมี API key)
    summary_md = ""
    if do_summary:
        progress(0.93, desc="กำลังสรุปการประชุมด้วย AI...")
        try:
            summary_md = S.summarize_meeting(txt_text)
        except RuntimeError as e:
            summary_md = f"(ไม่สามารถสรุปได้: {e})"

    stem = Path(file_path).stem or "transcript"
    srt_file = tempfile.NamedTemporaryFile(
        prefix=f"{stem}_", suffix=".srt", delete=False, mode="w", encoding="utf-8")
    srt_file.write(srt_text)
    srt_file.close()

    meta = {"source": Path(file_path).name, "duration": duration,
            "num_speakers": n_spk, "language": result["language"],
            "speaker_names": names or []}
    docx_file = tempfile.NamedTemporaryFile(
        prefix=f"{stem}_", suffix=".docx", delete=False)
    docx_file.close()
    export_docx(docx_file.name, utts, meta, summary_md or None)

    summary_status = (f"✅ เสร็จเรียบร้อย — ผู้พูด {n_spk} คน | ประโยค {len(utts)} | "
                      f"ความยาว {T.clock(duration)} | ภาษา {result['language']} "
                      f"({result['language_probability']:.0%})")
    return srt_file.name, docx_file.name, txt_text, summary_md, summary_status


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
                names_in = gr.Textbox(
                    label="ชื่อผู้พูด (ไม่ใส่ก็ได้)",
                    placeholder="เช่น สมชาย,สุชาดา — เรียงตามลำดับคนที่เริ่มพูดก่อน",
                )
                summary_in = gr.Checkbox(
                    value=False, label="สรุปการประชุมด้วย AI (MoM)",
                    info=("ต้องตั้งค่า SUMMARY_API_KEY บนเซิร์ฟเวอร์"
                          + (" — พร้อมใช้งาน ✓" if S.has_api_key() else " (ยังไม่ได้ตั้งค่า)")),
                )
                btn = gr.Button("🚀 ถอดเสียง", variant="primary")
            with gr.Column():
                summary_out = gr.Markdown("⏳ ยังไม่มีผลลัพธ์")
                srt_out = gr.File(label="ดาวน์โหลดคำบรรยาย (SRT)")
                docx_out = gr.File(label="ดาวน์โหลดบันทึกการประชุม (Word)")
                txt_out = gr.Textbox(
                    label="บทถอดความ (พร้อมชื่อผู้พูดและเวลา)",
                    lines=12, max_lines=20, buttons=["copy"],
                )
                mom_out = gr.Textbox(
                    label="สรุปการประชุม (MoM)",
                    lines=8, max_lines=20, buttons=["copy"],
                    placeholder="ติ๊ก 'สรุปการประชุมด้วย AI' ก่อนกดปุ่ม เพื่อรับสรุปหัวข้อ/มติ/สิ่งที่ต้องทำต่อ",
                )
        btn.click(
            transcribe_file,
            inputs=[file_in, speakers_in, model_in, label_in, names_in, summary_in],
            outputs=[srt_out, docx_out, txt_out, mom_out, summary_out],
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
