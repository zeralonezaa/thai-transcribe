#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
สรุปการประชุม (Minutes of Meeting) จากบทถอดความ

ใช้ LLM ผ่าน API แบบ OpenAI-compatible (ค่าเริ่มต้น api.openai.com แต่ชี้ไปที่
ผู้ให้บริการรายอื่นได้ เช่น DeepSeek, GLM, OpenRouter หรือ LLM ในเครื่อง
ผ่าน ollama/LM Studio) — ตั้งค่าผ่านตัวแปรสภาพแวดล้อม:

    SUMMARY_API_KEY   token ของบริการ (จำเป็น ไม่มี = ข้ามการสรุป)
    SUMMARY_BASE_URL  ค่าเริ่มต้น https://api.openai.com/v1
    SUMMARY_MODEL     ค่าเริ่มต้น gpt-4o-mini
"""

import json
import os
import urllib.error
import urllib.request

DEFAULT_BASE_URL = "https://api.openai.com/v1"
DEFAULT_MODEL = "gpt-4o-mini"

SYSTEM_PROMPT = """คุณคือผู้ช่วยจดบันทึกการประชุมมืออาชีพ
จงสรุป "บทถอดความการประชุม" ที่ได้รับเป็นภาษาไทย ตามโครงนี้เป๊ะ:

## ภาพรวมการประชุม
(สรุปสั้น 2-4 ประโยค ว่าประชุมเรื่องอะไร ใครเข้าร่วม ผลลัพธ์รวม)

## ประเด็นสำคัญที่หารือ
- (หัวข้อย่อย เรียงตามลำดับในที่ประชุม ระบุชื่อผู้พูดเมื่อเกี่ยวข้อง)

## มติที่ประชุม
- (ข้อสรุปที่ผู้เข้าร่วมตกลงร่วมกัน — ถ้าไม่มีให้เขียนว่า "ไม่พบมติที่ระบุชัดเจน")

## สิ่งที่ต้องทำต่อ
- [งาน] — ผู้รับผิดชอบ: (ถ้าระบุ) กำหนดเสร็จ: (ถ้าระบุ)

เขียนเป็น Markdown ภาษาไทยเท่านั้น ห้ามแต่งเนื้อหาที่ไม่มีในบทถอดความ"""


def has_api_key() -> bool:
    return bool(os.environ.get("SUMMARY_API_KEY"))


def summarize_meeting(transcript: str, max_chars: int = 60_000) -> str:
    """ส่งบทถอดความไปสรุป — คืนข้อความ Markdown ภาษาไทย

     raises RuntimeError ถ้าไม่ได้ตั้งค่า token หรือเรียก API ไม่สำเร็จ
    """
    api_key = os.environ.get("SUMMARY_API_KEY")
    if not api_key:
        raise RuntimeError("ยังไม่ได้ตั้งค่า SUMMARY_API_KEY — ข้ามการสรุปการประชุม")
    base_url = os.environ.get("SUMMARY_BASE_URL", DEFAULT_BASE_URL).rstrip("/")
    model = os.environ.get("SUMMARY_MODEL", DEFAULT_MODEL)

    if len(transcript) > max_chars:
        transcript = transcript[:max_chars] + "\n...(ตัดตอนท้ายเพราะยาวเกินไป)"

    payload = json.dumps({
        "model": model,
        "temperature": 0.3,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"บทถอดความการประชุม:\n\n{transcript}"},
        ],
    }).encode("utf-8")
    req = urllib.request.Request(
        f"{base_url}/chat/completions",
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "ignore")[:300]
        raise RuntimeError(f"เรียก API สรุปไม่สำเร็จ (HTTP {e.code}): {detail}") from e
    except urllib.error.URLError as e:
        raise RuntimeError(f"เชื่อมต่อ API สรุปไม่ได้: {e.reason}") from e

    try:
        return data["choices"][0]["message"]["content"].strip()
    except (KeyError, IndexError, TypeError) as e:
        raise RuntimeError(f"รูปแบบคำตอบจาก API ไม่ถูกต้อง: {str(data)[:300]}") from e
