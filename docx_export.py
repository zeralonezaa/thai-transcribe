#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ส่งออก "บันทึกการประชุม" เป็นไฟล์ Word (.docx) ภาษาไทย

ประกอบด้วย: หัวเรื่อง + ข้อมูลการประชุม + สรุปการประชุม (ถ้ามี) + บทถอดความ
แยกตามผู้พูด พร้อมเวลา
"""

import re
from datetime import datetime

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.shared import Pt, RGBColor

# ฟอนต์ไทยมาตรฐานสำหรับเอกสารราชการ/องค์กร (ถ้าเครื่องไม่มี Word จะ fallback เอง)
THAI_FONT = "TH Sarabun New"

THAI_MONTHS = ["มกราคม", "กุมภาพันธ์", "มีนาคม", "เมษายน", "พฤษภาคม", "มิถุนายน",
               "กรกฎาคม", "สิงหาคม", "กันยายน", "ตุลาคม", "พฤศจิกายน", "ธันวาคม"]


def _thai_now() -> str:
    now = datetime.now()
    return (f"{now.day} {THAI_MONTHS[now.month - 1]} "
            f"{now.year + 543} เวลา {now:%H:%M} น.")


def _set_thai_font(run):
    run.font.name = THAI_FONT
    rpr = run._element.get_or_add_rPr()
    rfonts = rpr.get_or_add_rFonts()
    for attr in ("w:cs", "w:eastAsia"):
        rfonts.set(qn(attr), THAI_FONT)


def _add_par(doc, text="", size=14, bold=False, color=None, align=None):
    p = doc.add_paragraph()
    if align is not None:
        p.alignment = align
    run = p.add_run(text)
    run.bold = bold
    run.font.size = Pt(size)
    if color:
        run.font.color.rgb = RGBColor(*color)
    _set_thai_font(run)
    return p


def _add_markdown(doc: Document, md: str):
    """วาด Markdown อย่างง่าย (หัวข้อ #/##/###, รายการ -, ตัวหนา **) ลง docx"""
    for line in md.splitlines():
        line = line.rstrip()
        if not line.strip():
            continue
        if line.startswith("### "):
            _add_par(doc, line[4:], size=14, bold=True)
        elif line.startswith("## "):
            _add_par(doc, line[3:], size=16, bold=True, color=(0x1F, 0x4E, 0x79))
        elif line.startswith("# "):
            _add_par(doc, line[2:], size=18, bold=True)
        elif line.lstrip().startswith(("- ", "* ")):
            p = doc.add_paragraph(style="List Bullet")
            _write_bold_segments(p, line.lstrip()[2:], size=14)
        else:
            p = doc.add_paragraph()
            _write_bold_segments(p, line, size=14)


def _write_bold_segments(par, text, size):
    """เขียนข้อความโดยแปลง **ตัวหนา** เป็น run ที่หนาจริง"""
    for i, seg in enumerate(re.split(r"\*\*(.+?)\*\*", text)):
        run = par.add_run(seg)
        run.bold = bool(i % 2)
        run.font.size = Pt(size)
        _set_thai_font(run)


def export_docx(path, utterances, meta: dict, summary_md: str | None = None):
    """เขียนไฟล์ .docx บันทึกการประชุม

    utterances: [{start,end,speaker(0-based),text}...]  (จาก transcribe.pipeline)
    meta: {source, duration, num_speakers, language, speaker_names?}
    """
    doc = Document()
    # ระยะขอบกระดาษแบบเอกสารไทย
    for section in doc.sections:
        section.top_margin = section.bottom_margin = Pt(56.7)   # ~2 ซม.
        section.left_margin = section.right_margin = Pt(62.4)   # ~2.2 ซม.

    names = meta.get("speaker_names") or []

    def label(u):
        if meta["num_speakers"] > 1:
            if u["speaker"] < len(names):
                return names[u["speaker"]]
            return f"ผู้พูด {u['speaker'] + 1}"
        return "ผู้พูด"

    def clock(t):
        h, r = divmod(int(t), 3600)
        m, s = divmod(r, 60)
        return f"{h:02d}:{m:02d}:{s:02d}"

    # หัวเรื่อง
    _add_par(doc, "บันทึกการประชุม", size=22, bold=True, align=WD_ALIGN_PARAGRAPH.CENTER)
    _add_par(doc, f"(ถอดความอัตโนมัติจากไฟล์เสียงโดย thai-transcribe)",
             size=11, color=(0x80, 0x80, 0x80), align=WD_ALIGN_PARAGRAPH.CENTER)
    _add_par(doc, "")  # เว้นบรรทัด

    # ข้อมูลการประชุม
    _add_par(doc, "ข้อมูลการประชุม", size=16, bold=True, color=(0x1F, 0x4E, 0x79))
    info = [
        ("ไฟล์เสียงต้นฉบับ", str(meta.get("source", "-"))),
        ("วันที่จัดทำ", _thai_now()),
        ("ความยาวเสียง", clock(meta.get("duration", 0))),
        ("ภาษาที่ตรวจพบ", str(meta.get("language", "-")).upper()),
        ("จำนวนผู้พูด", str(meta.get("num_speakers", 1))),
    ]
    if names:
        info.append(("รายชื่อผู้พูด", ", ".join(n for n in names if n)))
    table = doc.add_table(rows=len(info), cols=2)
    table.style = "Table Grid"
    for row, (k, v) in zip(table.rows, info):
        for cell, text, bold in ((row.cells[0], k, True), (row.cells[1], v, False)):
            cell.paragraphs[0].text = ""
            _write_bold_segments(cell.paragraphs[0], f"**{k}**" if bold else v, size=13)
    _add_par(doc, "")

    # สรุปการประชุม (ถ้ามี)
    if summary_md:
        _add_par(doc, "สรุปการประชุม", size=16, bold=True, color=(0x1F, 0x4E, 0x79))
        _add_markdown(doc, summary_md)
        _add_par(doc, "")

    # บทถอดความ
    _add_par(doc, "บทถอดความการประชุม", size=16, bold=True, color=(0x1F, 0x4E, 0x79))
    for u in utterances:
        p = doc.add_paragraph()
        run = p.add_run(f"[{clock(u['start'])}] {label(u)}: ")
        run.bold = True
        run.font.size = Pt(13)
        run.font.color.rgb = RGBColor(0x1F, 0x4E, 0x79)
        _set_thai_font(run)
        run2 = p.add_run(u["text"])
        run2.font.size = Pt(13)
        _set_thai_font(run2)

    doc.save(path)
