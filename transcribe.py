#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
thai-transcribe — ถอดเสียงเป็นข้อความ แยกผู้พูด และสร้างคำบรรยายภาษาไทย

ความสามารถ:
  1. ถอดเสียงจากไฟล์เสียง/วิดีโอ (mp3, wav, m4a, mp4, mkv, aac, ogg ฯลฯ)
     ด้วย Whisper (faster-whisper) รองรับภาษาไทยพร้อม timestamp ระดับคำ
  2. แยกบุคคลที่พูด (speaker diarization) ด้วย embedding เสียง ECAPA-TDNN
     + clustering — ทำงานในเครื่องทั้งหมด ไม่ต้องใช้ token ใด ๆ
  3. สร้างคำบรรยาย SRT พร้อมชื่อผู้พูด, ไฟล์ transcript TXT และ JSON

การใช้งาน:
    .venv/bin/python transcribe.py <ไฟล์เสียงหรือวิดีโอ> [ตัวเลือก]

ตัวอย่าง:
    .venv/bin/python transcribe.py meeting.m4a
    .venv/bin/python transcribe.py meeting.m4a --model large-v3 --speakers 3
    .venv/bin/python transcribe.py clip.mp4 --language th
    .venv/bin/python transcribe.py podcast.mp3 --no-speaker-label   # SRT ไม่มีชื่อผู้พูด
"""

import argparse
import io
import json
import shutil
import subprocess
import sys
import wave
from pathlib import Path

import numpy as np

SAMPLE_RATE = 16000
MODEL_CACHE = Path(__file__).resolve().parent / "models"

# initial_prompt ภาษาไทย ช่วยลดปัญหา Whisper "เพี้ยน" ไปเป็นอักษรจีน/เขมร
THAI_PROMPT = "ถอดความบทสนทนาภาษาไทยเป็นตัวอักษรภาษาไทยที่ถูกต้อง"


# ---------------------------------------------------------------------------
# ยูทิลิตี้ทั่วไป
# ---------------------------------------------------------------------------

def log(msg: str) -> None:
    print(msg, file=sys.stderr, flush=True)


def clock(t: float) -> str:
    """วินาที -> hh:mm:ss (สำหรับแสดงผลในคอนโซล/TXT)"""
    ms = int(round(t * 1000))
    h, r = divmod(ms, 3_600_000)
    m, r = divmod(r, 60_000)
    s = r // 1000
    return f"{h:02d}:{m:02d}:{s:02d}"


def srt_ts(t: float) -> str:
    """วินาที -> hh:mm:ss,mmm (รูปแบบ SRT)"""
    ms = max(0, int(round(t * 1000)))
    h, r = divmod(ms, 3_600_000)
    m, r = divmod(r, 60_000)
    s, ms = divmod(r, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def decode_audio(path: str, sr: int = SAMPLE_RATE) -> np.ndarray:
    """แปลงไฟล์เสียง/วิดีโอใด ๆ ให้เป็น mono float32 numpy ที่ sr ที่กำหนด (ผ่าน ffmpeg)"""
    if shutil.which("ffmpeg") is None:
        sys.exit("ไม่พบโปรแกรม ffmpeg — ติดตั้งก่อนด้วย:  brew install ffmpeg")
    proc = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", path, "-map", "0:a:0",
         "-ac", "1", "-ar", str(sr), "-f", "wav", "-"],
        capture_output=True,
    )
    if proc.returncode != 0:
        sys.exit(f"อ่านไฟล์เสียงไม่สำเร็จ: {proc.stderr.decode('utf-8', 'ignore').strip()}")
    with wave.open(io.BytesIO(proc.stdout)) as wf:
        raw = wf.readframes(wf.getnframes())
    return np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0


# ---------------------------------------------------------------------------
# ขั้นที่ 1: ถอดเสียงด้วย faster-whisper
# ---------------------------------------------------------------------------

def run_whisper(audio: np.ndarray, args) -> tuple[list[dict], dict]:
    """คืน (words, info) — words เป็น list ของ {start, end, word, probability}"""
    from faster_whisper import WhisperModel

    device = args.device
    if device == "auto":
        try:
            import ctranslate2
            supported = ctranslate2.get_supported_devices()
        except Exception:
            supported = ["cpu"]
        device = next((d for d in ("cuda", "mps", "cpu") if d in supported), "cpu")
        log(f"      เลือกอุปกรณ์อัตโนมัติ: {device}")
    compute_type = args.compute_type or {"cpu": "int8", "mps": "float32"}.get(device, "default")
    log(f"[2/4] โหลดโมเดล Whisper '{args.model}' (device={device}, compute={compute_type}) ...")
    model = WhisperModel(
        args.model,
        device=device,
        compute_type=compute_type,
        cpu_threads=args.cpu_threads or 0,
    )

    language = None if args.language == "auto" else args.language
    initial_prompt = args.initial_prompt
    if initial_prompt is None and language == "th":
        initial_prompt = THAI_PROMPT

    log("[2/4] กำลังถอดเสียง (แสดงผลสด ๆ ระหว่างประมวลผล) ...")
    seg_iter, info = model.transcribe(
        audio,
        language=language,
        task=args.task,
        beam_size=5,
        word_timestamps=True,
        vad_filter=True,
        vad_parameters=dict(min_silence_duration_ms=500),
        initial_prompt=initial_prompt,
        temperature=0.0,                    # ปิด fallback แบบสุ่ม -> ผลคงที่ทุกครั้ง
        condition_on_previous_text=False,  # ลดการลากความผิดพลาดข้ามประโยค
    )

    words: list[dict] = []
    for seg in seg_iter:
        text = seg.text.strip()
        if text:
            log(f"  [{clock(seg.start)}] {text}")
        for w in seg.words or []:
            token = w.word.strip()
            if token:
                # เก็บ raw token (มีช่องว่างนำหน้า) ไว้ใช้ตอนประกอบข้อความใหม่
                # เพื่อคงการเว้นวรรคตามผลถอดเสียงจริงของ Whisper
                words.append({
                    "start": float(w.start),
                    "end": float(w.end),
                    "word": token,
                    "raw": w.word,
                    "probability": float(w.probability),
                })
    return words, {
        "language": info.language,
        "language_probability": round(float(info.language_probability), 4),
        "duration": float(info.duration),
    }


# ---------------------------------------------------------------------------
# ขั้นที่ 2: แยกผู้พูดด้วย ECAPA embeddings + agglomerative clustering
# ---------------------------------------------------------------------------

def build_windows(words: list[dict], max_len=4.0, max_gap=0.5, min_len=0.6) -> list[tuple[float, float]]:
    """รวมคำที่อยู่ติดกันเป็นหน้าต่างเสียงยาว ~max_len วินาที เพื่อสกัด embedding ต่อหน้าต่าง"""
    windows: list[tuple[float, float]] = []
    cs, ce = words[0]["start"], words[0]["end"]
    for w in words[1:]:
        s, e = w["start"], w["end"]
        if s - ce > max_gap or e - cs > max_len:
            if ce - cs >= min_len:
                windows.append((cs, ce))
            cs, ce = s, e
        else:
            ce = max(ce, e)
    if ce - cs >= min_len:
        windows.append((cs, ce))
    return windows


def trim_to_energy(seg: np.ndarray, sr: int, frac=0.08, frame=0.02) -> np.ndarray:
    """ตัดส่วนเงียบ/เสียงรบกวนขอบนำ-ท้ายออก เหลือเฉพาะช่วงที่มีเสียงพูดจริง
    (ป้องกัน embedding ของหน้าต่างที่มี noise ปะปนจากถูกจัดเป็นคนละผู้พูด)"""
    if len(seg) < int(frame * sr) * 3:
        return seg
    n = int(frame * sr)
    n_frames = len(seg) // n
    rms = np.sqrt(np.mean(seg[: n_frames * n].reshape(n_frames, n) ** 2, axis=1))
    thr = frac * rms.max()
    active = np.nonzero(rms > thr)[0]
    if len(active) == 0:
        return seg
    return seg[active[0] * n : (active[-1] + 1) * n]


def embed_windows(audio: np.ndarray, windows, batch_size=8) -> np.ndarray:
    """สกัด speaker embedding (192 มิติ) ของแต่ละหน้าต่างเสียง แล้ว normalize"""
    import torch
    from speechbrain.inference.speaker import EncoderClassifier

    classifier = EncoderClassifier.from_hparams(
        source="speechbrain/spkrec-ecapa-voxceleb",
        savedir=str(MODEL_CACHE / "ecapa"),
        run_opts={"device": "cpu"},
    )
    sr = SAMPLE_RATE
    embs = []
    for i in range(0, len(windows), batch_size):
        chunk = []
        for s, e in windows[i : i + batch_size]:
            seg = trim_to_energy(audio[int(s * sr) : int(e * sr)], sr)
            if len(seg) < int(0.3 * sr):  # สั้นเกินไป -> pad ให้ยาวพอ
                seg = np.pad(seg, (0, int(0.3 * sr) - len(seg)))
            seg = seg / (np.max(np.abs(seg)) + 1e-9)
            chunk.append(torch.from_numpy(seg.copy()))
        wav = torch.nn.utils.rnn.pad_sequence(chunk, batch_first=True)
        out = classifier.encode_batch(wav)          # [B, 1, 192]
        embs.append(out.squeeze(1).detach().cpu().numpy())
    X = np.concatenate(embs, axis=0)
    return X / (np.linalg.norm(X, axis=1, keepdims=True) + 1e-9)


def cluster_windows(X: np.ndarray, n_speakers=None, threshold=0.6) -> np.ndarray:
    """จัดกลุ่ม embedding -> ป้ายผู้พูด (0,1,2,...) ด้วย cosine distance

    ถ้าไม่ได้ระบุจำนวนผู้พูด จะลองหลาย ๆ threshold แล้วเลือกผลลัพธ์ที่ได้คะแนน
    silhouette สูงสุด (กลุ่มแน่น/แยกกันชัดที่สุด) แทนการใช้ threshold ตายตัว
    """
    from sklearn.cluster import AgglomerativeClustering
    from sklearn.metrics import silhouette_score

    def run(th):
        return AgglomerativeClustering(
            n_clusters=None, distance_threshold=float(th),
            metric="cosine", linkage="average",
        ).fit_predict(X)

    if len(X) <= 1:
        return np.zeros(len(X), dtype=int)
    if n_speakers:
        n = max(1, min(int(n_speakers), len(X)))
        return AgglomerativeClustering(
            n_clusters=n, metric="cosine", linkage="average"
        ).fit_predict(X)

    best = None  # (score, labels, threshold)
    for th in (0.5, 0.55, 0.6, 0.65, 0.7, 0.75):
        try:
            labels = run(th)
        except Exception:
            continue
        k = len(set(labels))
        if k < 2 or k >= len(X):
            continue
        score = silhouette_score(X, labels, metric="cosine")
        if best is None or score > best[0]:
            best = (score, labels, th)
    if best is None:  # กรณีข้อมูลน้อยมาก — ถือว่าเป็นผู้พูดเดียวกันทั้งหมด
        return np.zeros(len(X), dtype=int)
    log(f"      เลือก threshold={best[2]:.2f} (silhouette={best[0]:.3f})")
    return best[1]


def label_words(words: list[dict], windows, win_labels: np.ndarray) -> list[int]:
    """กำหนดผู้พูดให้แต่ละคำ = ผู้พูดของหน้าต่างที่คำนั้นซ้อนทับมากที่สุด"""
    labels = []
    for w in words:
        s, e = w["start"], w["end"]
        best_i, best_overlap = 0, -1.0
        for i, (ws, we) in enumerate(windows):
            overlap = min(e, we) - max(s, ws)
            if overlap > best_overlap:
                best_overlap, best_i = overlap, i
        if best_overlap <= 0:  # คำที่ไม่ตรงกับหน้าต่างใด -> ใช้หน้าต่างที่ใกล้ที่สุดตามเวลา
            c = (s + e) / 2
            best_i = min(range(len(windows)), key=lambda i: abs((windows[i][0] + windows[i][1]) / 2 - c))
        labels.append(int(win_labels[best_i]))
    return labels


# ---------------------------------------------------------------------------
# ขั้นที่ 3: รวมคำเป็นประโยคของแต่ละผู้พูด (utterance)
# ---------------------------------------------------------------------------

def group_utterances(words: list[dict], labels: list[int], max_gap=1.5) -> list[dict]:
    utterances = []
    cur = None
    for w, spk in zip(words, labels):
        if cur and cur["speaker"] == spk and w["start"] - cur["end"] <= max_gap:
            cur["end"] = max(cur["end"], w["end"])
            cur["words"].append(w)
        else:
            if cur:
                utterances.append(cur)
            cur = {"speaker": spk, "start": w["start"], "end": w["end"], "words": [w]}
    if cur:
        utterances.append(cur)
    for u in utterances:
        u["text"] = "".join(x["raw"] for x in u["words"]).strip()
    return [u for u in utterances if u["text"]]


# สระ/วรรณยุกต์ที่ไม่มีทางขึ้นต้นคำภาษาไทยได้ (ั า ำ ิ ี ึ ื ุ ู ฯลฯ)
# (เ แ โ ใ ไ ไม่รวม เพราะนำหน้าคำได้ปกติ)
THAI_TRAILING_MARKS = set(
    "\u0e30\u0e31\u0e32\u0e33\u0e34\u0e35\u0e36\u0e37\u0e38\u0e39\u0e3a"
    "\u0e47\u0e48\u0e49\u0e4a\u0e4b\u0e4c\u0e4d\u0e4e"
)


def fix_leading_fragments(utterances: list[dict], max_gap=0.5) -> list[dict]:
    """ถ้าประโยคหนึ่งขึ้นต้นด้วยสระ/วรรณยุกต์ลอย ๆ แปลว่า Whisper กำหนด token
    ผิดกลุ่ม (ตัวอย่าง: 'หน้' อยู่ประโยคก่อน แต่ 'า' หลุดไปประโยคถัดไป)
    ให้ย้ายคำนั้นกลับไปต่อท้ายประโยคก่อนหน้า"""
    i = 1
    while i < len(utterances):
        u, p = utterances[i], utterances[i - 1]
        w = u["words"][0]
        if w["word"] and w["word"][0] in THAI_TRAILING_MARKS and w["start"] - p["end"] <= max_gap:
            p["words"].append(w)
            p["end"] = max(p["end"], w["end"])
            p["text"] = "".join(x["raw"] for x in p["words"]).strip()
            u["words"] = u["words"][1:]
            if not u["words"]:
                utterances.pop(i)
                continue
            u["start"] = u["words"][0]["start"]
            u["text"] = "".join(x["raw"] for x in u["words"]).strip()
        i += 1
    return utterances


# ---------------------------------------------------------------------------
# ขั้นที่ 4: เขียนไฟล์ผลลัพธ์ SRT / TXT / JSON
# ---------------------------------------------------------------------------

def split_blocks(words: list[dict], max_chars=80, max_dur=6.0) -> list[list[dict]]:
    """หั่นประโยคยาวเป็นหลาย ๆ บล็อกคำบรรยาย (คุมจำนวนอักขระ/ความยาวเวลา)

    ภาษาไทยไม่มีช่องว่างคั่นคำ การหั่นตรงตำแหน่ง token ใด ๆ อาจตัดกลางคำ
    จึงย้อนกลับไปตัดที่ "ขอบเขตวลี" ล่าสุดก่อน (จุดที่ token ถัดไปมีช่องว่างนำหน้า
    ตามการถอดเสียงของ Whisper) ถ้าไม่พบจึงยอมตัดที่ตำแหน่งปัจจุบัน
    """
    blocks, cur = [], []

    def text_of(ws):
        return "".join(x["raw"] for x in ws).strip()

    for w in words:
        cur.append(w)
        if len(text_of(cur)) >= max_chars or cur[-1]["end"] - cur[0]["start"] >= max_dur:
            cut = None
            for j in range(len(cur) - 1, 0, -1):        # หาขอบเขตวลีล่าสุด
                if cur[j]["raw"].startswith(" "):
                    cut = j
                    break
            if cut:
                blocks.append(cur[:cut])
                cur = cur[cut:]
            else:
                blocks.append(cur)
                cur = []
    if cur:
        blocks.append(cur)
    return blocks


def render_srt(utterances, n_speakers: int, speaker_template="ผู้พูด {n}",
               max_chars=80, max_duration=6.0, speaker_label=True) -> str:
    """เรนเดอร์คำบรรยายเป็นข้อความ SRT"""
    out = []
    idx = 1
    prev_end = 0.0
    for u in utterances:
        for blk in split_blocks(u["words"], max_chars, max_duration):
            start = max(blk[0]["start"], prev_end + 0.001)   # กัน timestamp ทับกัน
            end = max(blk[-1]["end"], start + 0.2)
            prev_end = end
            text = "".join(x["raw"] for x in blk).strip()
            if not text:
                continue
            if speaker_label and n_speakers > 1:
                text = f"{speaker_template.format(n=u['speaker'] + 1)}\n{text}"
            out.append(f"{idx}\n{srt_ts(start)} --> {srt_ts(end)}\n{text}\n\n")
            idx += 1
    return "".join(out)


def render_txt(utterances, n_speakers: int, speaker_template="ผู้พูด {n}") -> str:
    """เรนเดอร์บทถอดความเป็นข้อความ TXT"""
    lines = []
    for u in utterances:
        name = speaker_template.format(n=u["speaker"] + 1) if n_speakers > 1 else "ผู้พูด"
        lines.append(f"[{clock(u['start'])}] {name}: {u['text']}")
    return "\n".join(lines) + ("\n" if lines else "")


def render_json(utterances, meta: dict) -> str:
    data = dict(meta)
    data["utterances"] = [
        {
            "start": round(u["start"], 3),
            "end": round(u["end"], 3),
            "speaker": u["speaker"] + 1,
            "text": u["text"],
            "words": [
                {"start": round(w["start"], 3), "end": round(w["end"], 3),
                 "word": w["word"], "speaker": u["speaker"] + 1,
                 "probability": round(w["probability"], 3)}
                for w in u["words"]
            ],
        }
        for u in utterances
    ]
    return json.dumps(data, ensure_ascii=False, indent=2)


def write_srt(path: Path, utterances, n_speakers: int, args) -> None:
    path.write_text(render_srt(utterances, n_speakers, args.speaker_template,
                               args.max_chars, args.max_duration,
                               not args.no_speaker_label), encoding="utf-8")


def write_txt(path: Path, utterances, n_speakers: int, args) -> None:
    path.write_text(render_txt(utterances, n_speakers, args.speaker_template),
                    encoding="utf-8")


def write_json(path: Path, utterances, meta: dict) -> None:
    path.write_text(render_json(utterances, meta), encoding="utf-8")


# ---------------------------------------------------------------------------
# pipeline รวม (ใช้ร่วมกันทั้ง CLI และเว็บแอป)
# ---------------------------------------------------------------------------

def diarize(audio: np.ndarray, words: list[dict], speakers=None, threshold=0.6):
    """แยกผู้พูด -> (labels ระดับคำ, จำนวนผู้พูด)"""
    windows = build_windows(words)
    # หน้าต่างสั้น ๆ ให้ embedding ไม่น่าเชื่อถือ จึงทำ clustering เฉพาะ
    # "anchor" (ยาว >= 1.2 วิ) แล้วผูกหน้าต่างสั้นเข้ากับ anchor ที่ใกล้ที่สุด
    anchors = [w for w in windows if w[1] - w[0] >= 1.2]
    shorts = [w for w in windows if w[1] - w[0] < 1.2]
    if len(anchors) < 2:
        log("      เสียงสั้นเกินไปสำหรับการแยกผู้พูด — ถือว่ามีผู้พูดเดียว")
        return [0] * len(words), 1
    X = embed_windows(audio, anchors)
    anchor_labels = cluster_windows(X, speakers, threshold)
    all_windows = list(anchors)
    all_labels = list(anchor_labels)
    for s in shorts:  # หน้าต่างสั้น -> label ของ anchor ที่ใกล้กันที่สุดตามเวลา
        c = (s[0] + s[1]) / 2
        j = min(range(len(anchors)),
                key=lambda k: abs((anchors[k][0] + anchors[k][1]) / 2 - c))
        all_windows.append(s)
        all_labels.append(anchor_labels[j])
    # จัดเลขผู้พูดตามลำดับการปรากฏครั้งแรก
    order, remap = [], {}
    for lab in all_labels:
        if lab not in remap:
            remap[lab] = len(order)
            order.append(lab)
    win_labels = np.array([remap[l] for l in all_labels])
    labels = label_words(words, all_windows, win_labels)
    return labels, len(order)


def pipeline(audio: np.ndarray, *, language="th", model_size="large-v3",
             device="cpu", compute_type=None, speakers=None,
             cluster_threshold=0.6, no_diarize=False, initial_prompt=None,
             task="transcribe", cpu_threads=0) -> dict:
    """ถอดเสียง + แยกผู้พูด ครบสายการผลิต

    คืน dict: {words, utterances, n_speakers, language, language_probability, duration}
    """
    class _Opts:  # แปลงพารามิเตอร์ให้เข้ารูปที่ run_whisper ใช้
        pass
    opts = _Opts()
    opts.model = model_size
    opts.device = device
    opts.compute_type = compute_type
    opts.cpu_threads = cpu_threads
    opts.language = language
    opts.task = task
    opts.initial_prompt = initial_prompt

    words, info = run_whisper(audio, opts)
    if not words:
        raise RuntimeError("ไม่พบเสียงพูดในไฟล์นี้")

    n_speakers = 1
    labels = [0] * len(words)
    if not no_diarize:
        log("[diarize] แยกผู้พูด (ECAPA embeddings + clustering) ...")
        labels, n_speakers = diarize(audio, words, speakers, cluster_threshold)
        log(f"[diarize] จำนวนผู้พูด: {n_speakers}"
            + (f" (ระบุเอง: {speakers})" if speakers else " (ประมาณอัตโนมัติ)"))

    utterances = fix_leading_fragments(group_utterances(words, labels))
    return {
        "words": words,
        "utterances": utterances,
        "n_speakers": n_speakers,
        **info,
    }


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def parse_args(argv=None):
    p = argparse.ArgumentParser(
        prog="thai-transcribe",
        description="ถอดเสียงเป็นข้อความ แยกผู้พูด และสร้างคำบรรยายภาษาไทย (SRT/TXT/JSON)",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("input", help="ไฟล์เสียง/วิดีโอ (mp3 wav m4a mp4 mkv aac ogg flac ...)")
    p.add_argument("-o", "--output-dir", default=None,
                   help="โฟลเดอร์ผลลัพธ์ (ค่าเริ่มต้น: โฟลเดอร์เดียวกับไฟล์ต้นฉบับ)")
    p.add_argument("--model", default="large-v3",
                   help="ขนาดโมเดล Whisper: tiny base small medium large-v3 (แม่นสุดแต่ช้ากว่า)")
    p.add_argument("--language", default="th",
                   help="รหัสภาษา เช่น th, en หรือ 'auto' เพื่อตรวจอัตโนมัติ")
    p.add_argument("--task", default="transcribe", choices=["transcribe", "translate"],
                   help="transcribe = ถอดความ, translate = แปลเป็นภาษาอังกฤษ")
    p.add_argument("--speakers", type=int, default=None,
                   help="ระบุจำนวนผู้พูด (ไม่ระบุ = ประมาณอัตโนมัติ)")
    p.add_argument("--cluster-threshold", type=float, default=0.6,
                   help="เกณฑ์ระยะ cosine ตอนประมาณจำนวนผู้พูดอัตโนมัติ (ยิ่งสูงยิ่งรวมกลุ่ม)")
    p.add_argument("--no-diarize", action="store_true", help="ไม่ต้องแยกผู้พูด")
    p.add_argument("--no-speaker-label", action="store_true",
                   help="ไม่ใส่ชื่อผู้พูดในไฟล์ SRT (เหมาะกับการเบิร์นลงวิดีโอ)")
    p.add_argument("--speaker-template", default="ผู้พูด {n}",
                   help="รูปแบบชื่อผู้พูด เช่น 'Speaker {n}' หรือ 'พิธีกร {n}'")
    p.add_argument("--max-chars", type=int, default=80, help="อักขระสูงสุดต่อบล็อกคำบรรยาย")
    p.add_argument("--max-duration", type=float, default=6.0, help="วินาทีสูงสุดต่อบล็อกคำบรรยาย")
    p.add_argument("--initial-prompt", default=None,
                   help="prompt เริ่มต้นควบคุมสไตล์/อักขระของผลถอดความ")
    p.add_argument("--device", default="cpu", choices=["cpu", "mps", "auto"],
                   help="อุปกรณ์ประมวลผล (Apple Silicon ลอง 'mps' ได้เร็วขึ้น, auto = ตรวจอัตโนมัติ)")
    p.add_argument("--compute-type", default=None, help="default / int8 / int8_float32 / float32")
    p.add_argument("--cpu-threads", type=int, default=None, help="จำนวน thread (ค่าเริ่มต้น: ทุก core)")
    return p.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    src = Path(args.input)
    if not src.exists():
        sys.exit(f"ไม่พบไฟล์: {src}")

    out_dir = Path(args.output_dir) if args.output_dir else src.parent
    out_dir.mkdir(parents=True, exist_ok=True)
    base = out_dir / src.stem

    log(f"[1/4] อ่านไฟล์: {src.name}")
    audio = decode_audio(str(src))
    log(f"      ความยาว ~{clock(len(audio) / SAMPLE_RATE)} นาที:วินาที")

    log("[2/4] ถอดเสียง + [3/4] แยกผู้พูด")
    result = pipeline(
        audio,
        language=args.language,
        model_size=args.model,
        device=args.device,
        compute_type=args.compute_type,
        speakers=args.speakers,
        cluster_threshold=args.cluster_threshold,
        no_diarize=args.no_diarize,
        initial_prompt=args.initial_prompt,
        task=args.task,
        cpu_threads=args.cpu_threads,
    )
    words = result["words"]
    utterances = result["utterances"]
    n_speakers = result["n_speakers"]
    info = {"language": result["language"],
            "language_probability": result["language_probability"],
            "duration": result["duration"]}
    log(f"      ภาษาที่ตรวจพบ: {info['language']} ({info['language_probability']:.0%})")

    # --- เขียนผลลัพธ์ ---
    log(f"[4/4] เขียนไฟล์ผลลัพธ์ -> {out_dir}/")
    write_srt(base.with_suffix(".srt"), utterances, n_speakers, args)
    write_txt(base.with_suffix(".txt"), utterances, n_speakers, args)
    meta = {
        "source": str(src),
        "model": args.model,
        "task": args.task,
        **info,
        "num_speakers": n_speakers,
    }
    write_json(base.with_suffix(".json"), utterances, meta)

    log("-" * 56)
    log("เสร็จเรียบร้อย! ไฟล์ผลลัพธ์:")
    for ext in (".srt", ".txt", ".json"):
        log(f"  - {base.with_suffix(ext).name}")
    log(f"  จำนวนผู้พูด: {n_speakers} | ประโยค: {len(utterances)} | คำ: {len(words)}")


if __name__ == "__main__":
    main()
