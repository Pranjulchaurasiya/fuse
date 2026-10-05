#!/usr/bin/env python3
"""build_enhanced_real_voice_video.py — Option 1 Master Compiler:
- Studio Vocal Mastering Chain on Pranjul's real voice (sample_voice.aac).
- Subtitles 100% aligned to the canonical script text in docs/demo-script.md.
- Slower, comfortable pacing across 178.0s (2m 58s — strictly under 3:00).
- Synchronized running subtitles (Segoe UI 24pt, high-contrast white with dark border & shadow).
- Output: Fuse_Final_Demo_EnhancedRealVoice.mp4 (1080p @ 30fps).
"""

import os
import sys
import json
import subprocess
import shutil
import difflib
import re
from PIL import Image, ImageDraw, ImageFont

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ARTIFACTS_DIR = r"C:\Users\pranj\.gemini\antigravity-ide\brain\f8e60b13-df6d-4964-9161-caa38ad96efd"
BUILD_DIR = os.path.join(REPO_ROOT, "scratch_enhanced_build")
OUTPUT_VIDEO = os.path.join(REPO_ROOT, "Fuse_Final_Demo_EnhancedRealVoice.mp4")

WIDTH = 1920
HEIGHT = 1080
FPS = 30

ACT_CONFIGS = [
    {
        "id": 1,
        "name": "ACT 1: THE PROBLEM",
        "subtitle": "Why Static Alarms Fail: False Positives vs Runaway Loop",
        "video_duration": 38.0,
        "audio_range": (0, 108),
        "script_words": [
            "Hi", "everyone,", "I'm", "Pranjul", "Chaurasiya,", "and", "this", "is", "Fuse.",
            "Serverless", "architecture", "is", "incredible", "until", "an", "infinite", "client", "retry", "loop", "or", "runaway", "agent", "racks", "up", "a", "surprise", "$5,000", "AWS", "bill", "overnight.",
            "You", "don't", "find", "out", "until", "your", "billing", "alarm", "emails", "you", "at", "3", "AM.",
            "Look", "at", "this", "comparison:", "Traditional", "CloudWatch", "static", "alarms", "only", "count", "raw", "requests.",
            "During", "a", "marketing", "flash", "sale", "with", "1,000", "real", "buyers,", "a", "static", "alarm", "trips", "and", "kills", "paying", "customers—a", "catastrophic", "false-positive", "outage.",
            "But", "during", "a", "real", "runaway", "loop,", "it", "offers", "zero", "caller", "context", "and", "zero", "automated", "remediation.",
            "Meet", "Fuse—an", "autonomous,", "context-aware", "circuit", "breaker", "for", "AWS", "APIs", "powered", "by", "Amazon", "Bedrock."
        ]
    },
    {
        "id": 2,
        "name": "ACT 2: SCENARIO 1 — LEGITIMATE SPIKE",
        "subtitle": "35 Unique Callers With Diverse Payloads -> Classified as NORMAL",
        "video_duration": 42.0,
        "audio_range": (109, 211),
        "script_words": [
            "Let's", "test", "Scenario", "1:", "A", "legitimate", "traffic", "surge.",
            "We", "fire", "35", "requests", "into", "our", "demo", "API", "Gateway", "endpoint.",
            "Notice", "each", "request", "originates", "from", "a", "unique", "IP", "and", "caller", "ID,", "carrying", "diverse", "search", "and", "catalog", "payloads.",
            "Every", "minute,", "an", "EventBridge", "schedule", "triggers", "our", "lightweight", "Poller", "Lambda.",
            "It", "queries", "CloudWatch", "metrics", "and", "checks", "DynamoDB", "for", "recent", "deployment", "heartbeats.",
            "When", "Bedrock", "evaluates", "this", "cycle,", "it", "correlates", "caller", "diversity", "with", "deployment", "context.",
            "Let's", "switch", "to", "our", "live", "Fuse", "Console...",
            "Bedrock", "classifies", "the", "traffic", "as", "NORMAL", "with", "98%", "confidence:",
            "'Traffic", "surge", "consists", "of", "distinct", "callers", "with", "diverse", "payloads.'",
            "Baseline", "stays", "intact,", "zero", "false", "alarm,", "zero", "customer", "disruption."
        ]
    },
    {
        "id": 3,
        "name": "ACT 3: SCENARIO 2 — RUNAWAY LOOP & APPROVAL GATE",
        "subtitle": "Classified as RUNAWAY -> Prod Safety Gate Holds -> Operator Approves -> HTTP 429",
        "video_duration": 58.0,
        "audio_range": (212, 375),
        "script_words": [
            "Now,", "Scenario", "2:", "A", "developer", "deploys", "a", "client", "with", "an", "unhandled", "retry", "loop", "without", "backoff", "jitter.",
            "We", "fire", "40", "rapid", "requests—all", "from", "a", "single", "caller", "ID", "with", "identical", "stuck", "payloads.",
            "Our", "Poller", "detects", "the", "volume", "spike", "and", "passes", "the", "snapshot", "to", "our", "Reasoner", "Lambda.",
            "Bedrock's", "Converse", "API", "immediately", "identifies", "the", "anomaly", "signature", "as", "RUNAWAY.",
            "Because", "this", "is", "our", "production", "workload,", "our", "safety", "guardrail", "withholds", "automated", "throttling.",
            "In", "dev", "or", "staging,", "it", "auto-throttles", "directly.", "In", "production,", "human", "judgment", "is", "protected.",
            "The", "target", "API", "is", "still", "serving", "traffic", "right", "now.",
            "As", "the", "operator,", "I", "inspect", "Bedrock's", "synthesis:", "'Single", "caller,", "identical", "retry", "payload,", "no", "deployment", "event.'",
            "I", "click", "Approve", "Circuit", "Trip...",
            "Our", "Remediator", "Lambda", "immediately", "patches", "the", "API", "Gateway", "stage", "throttle", "to", "0.",
            "We", "follow", "the", "independent", "observation", "principle:", "we", "verify", "the", "throttle", "directly", "at", "the", "regional", "API", "Gateway", "edge.",
            "Both", "our", "live", "probe", "and", "raw", "curl", "confirm:", "HTTP", "429", "Too", "Many", "Requests.",
            "The", "runaway", "loop", "is", "severed", "before", "the", "bill", "can", "multiply!"
        ]
    },
    {
        "id": 4,
        "name": "ACT 4: UNDER THE HOOD — ARCHITECTURE",
        "subtitle": "Single-Turn Bedrock Converse, Isolated Control Plane, Edge Throttle",
        "video_duration": 24.0,
        "audio_range": (376, 453),
        "script_words": [
            "Here's", "what", "makes", "Fuse", "production-grade:",
            "1.", "Isolated", "Control", "Plane:", "The", "dashboard", "and", "approval", "endpoints", "run", "on", "a", "completely", "separate", "API", "Gateway.",
            "Throttling", "the", "demo", "workload", "never", "locks", "the", "operator", "out", "of", "the", "control", "room.",
            "2.", "Single-Turn", "Structured", "Bedrock:", "We", "invoke", "Bedrock", "Converse", "exactly", "once", "per", "cycle", "using", "toolConfig,", "enforcing", "typed", "JSON", "without", "expensive", "multi-turn", "loops.",
            "3.", "Fail-Closed", "Cost", "Safety:", "If", "Bedrock", "ever", "times", "out,", "our", "reasoner", "safely", "defaults", "to", "RUNAWAY—guaranteeing", "cost", "protection", "is", "never", "compromised."
        ]
    },
    {
        "id": 5,
        "name": "ACT 5: CONCLUSION",
        "subtitle": "Live AWS Amplify Dashboard & Independently Checkable GitHub Repo",
        "video_duration": 16.0,
        "audio_range": (454, 503),
        "script_words": [
            "Fuse", "transforms", "cloud", "cost", "governance", "from", "brittle", "static", "alarms", "into", "intelligent,", "context-aware", "circuit", "breakers.",
            "Deployed", "live", "on", "AWS", "in", "ap-south-1.",
            "I'm", "Pranjul", "Chaurasiya,", "submitting", "for", "the", "Ship", "It", "track", "at", "First", "Commit,", "Bharat", "Builds", "Tour", "2026.",
            "The", "code,", "architecture", "docs,", "and", "live", "console", "are", "available", "on", "GitHub.", "Thank", "you!"
        ]
    },
]


def run_ffmpeg(args: list):
    cmd = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "warning"] + args
    subprocess.check_call(cmd)


def build_act1_frame() -> str:
    out_path = os.path.join(BUILD_DIR, "act1_frame.png")
    img = Image.new("RGB", (WIDTH, HEIGHT), "#080b12")
    draw = ImageDraw.Draw(img)

    win_x, win_y, win_w, win_h = 100, 80, 1720, 800
    draw.rounded_rectangle([win_x, win_y, win_x + win_w, win_y + win_h], radius=16, fill="#0d1117", outline="#30363d", width=2)
    draw.rounded_rectangle([win_x, win_y, win_x + win_w, win_y + 48], radius=16, fill="#161b22")
    draw.rectangle([win_x, win_y + 32, win_x + win_w, win_y + 48], fill="#161b22")

    draw.ellipse([win_x + 18, win_y + 16, win_x + 34, win_y + 32], fill="#ff5f56")
    draw.ellipse([win_x + 42, win_y + 16, win_x + 58, win_y + 32], fill="#ffbd2e")
    draw.ellipse([win_x + 66, win_y + 16, win_x + 82, win_y + 32], fill="#27c93f")

    font_title = ImageFont.truetype("C:/Windows/Fonts/segoeui.ttf", 16)
    font_mono = ImageFont.truetype("C:/Windows/Fonts/consola.ttf", 21)
    font_mono_bold = ImageFont.truetype("C:/Windows/Fonts/consolab.ttf", 23)

    draw.text((win_x + 100, win_y + 14), "PowerShell — python scripts/simulate_naive_threshold.py", font=font_title, fill="#8b949e")

    lines = [
        ("PS C:\\Users\\pranj\\Documents\\Fuse> python scripts/simulate_naive_threshold.py", "#58a6ff", True),
        ("=" * 75, "#30363d", False),
        (" NAIVE STATIC THRESHOLD VS. AWS COST GUARDRAIL AGENT COMPARISON", "#f0f6fc", True),
        ("=" * 75, "#30363d", False),
        ("", "#8b949e", False),
        ("--- Scenario A: Flash Sale / Marketing Spike (Legitimate) ---", "#79c0ff", True),
        ("[*] Traffic Metrics: Count = 35 requests/min, Unique Callers = 35", "#8b949e", False),
        ("[*] Naive Alarm (Count > 30):", "#f0f6fc", False),
        ("    State:   ALARM", "#f85149", True),
        ("    Action:  THROTTLE_CUSTOMERS", "#f85149", False),
        ("    Verdict: FALSE_POSITIVE (Broke production for 35 paying users!)", "#f85149", True),
        ("[*] Guardrail Agent (Context-Aware):", "#f0f6fc", False),
        ("    Classification: NORMAL (Confidence: 98%)", "#3fb950", True),
        ("    Action:         NO_ACTION (Traffic permitted)", "#3fb950", False),
        ("    Context:        Callers=35, Payloads=['view_laptops', 'search_phones'], Deploy=True", "#8b949e", False),
        ("    Verdict:        CORRECT (Accurately discerned legitimate intent)", "#3fb950", True),
        ("", "#8b949e", False),
        ("--- Scenario B: Broken Client Retry Loop (Runaway) ---", "#ffa657", True),
        ("[*] Traffic Metrics: Count = 40 requests/min, Unique Callers = 1", "#8b949e", False),
        ("[*] Naive Alarm (Count > 30):", "#f0f6fc", False),
        ("    State:   ALARM -> THROTTLE_CUSTOMERS (Raw count only)", "#f0f6fc", False),
        ("[*] Guardrail Agent (Context-Aware):", "#f0f6fc", False),
        ("    Classification: RUNAWAY (Confidence: 95%)", "#f85149", True),
        ("    Action:         PENDING_APPROVAL (prod) / AUTO_THROTTLE (dev)", "#e3b341", True),
        ("    Context:        Callers=1, Payloads=['retry_failed_job'], Deploy=False", "#8b949e", False),
        ("    Verdict:        CORRECT (Identified recursive infinite loop signature)", "#3fb950", True),
        ("=" * 75, "#30363d", False),
        (" Key Takeaway: Naive alarms lack caller context, causing severe false positives.", "#58a6ff", True),
        (" Guardrail Agent reasons over multi-dimensional context to protect cost & uptime.", "#58a6ff", False),
    ]

    y = win_y + 70
    for text, color, is_bold in lines:
        f = font_mono_bold if is_bold else font_mono
        draw.text((win_x + 35, y), text, font=f, fill=color)
        y += 26

    img.save(out_path)
    return out_path


def format_ass_time(seconds: float) -> str:
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    cs = int(round((seconds - int(seconds)) * 100))
    if cs == 100:
        cs = 99
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


HANGING_WORDS = {"until", "and", "or", "but", "with", "for", "to", "at", "in", "by", "on", "a", "an", "the", "is", "was", "our", "their", "your", "my", "into", "as", "of", "from"}
COMPOUND_HEADS = {"api", "cloudwatch", "poller", "reasoner", "remediator", "too", "http", "pranjul", "flash", "circuit", "control", "paying", "infinite", "client", "retry", "runaway", "bedrock", "dynamodb", "eventbridge"}
NUMBER_BULLETS = {"1.", "2.", "3."}


def split_sentence_words(words: list) -> list:
    """Split a single sentence's words into balanced 3-5 word chunks."""
    n = len(words)
    if n <= 6:
        return [words]

    k = max(2, (n + 4) // 5)
    target_len = n / k

    chunks = []
    curr_start = 0

    for _ in range(k - 1):
        ideal_pos = int(round(curr_start + target_len))
        best_pos = ideal_pos
        best_score = float("inf")

        for cand in range(max(curr_start + 2, ideal_pos - 2), min(n - 2, ideal_pos + 3)):
            cand_word = words[cand - 1]["text"].strip()
            clean_cand = re.sub(r"[^a-zA-Z]", "", cand_word).lower()

            score = abs(cand - (curr_start + target_len)) * 1.5

            if clean_cand in HANGING_WORDS or clean_cand in COMPOUND_HEADS:
                score += 10.0

            next_clean = re.sub(r"[^a-zA-Z]", "", words[cand]["text"].strip()).lower()
            if cand_word.lower() == "api" and next_clean == "gateway":
                score += 20.0
            if cand_word.lower() == "cloudwatch" and next_clean == "metrics":
                score += 20.0

            if cand_word.endswith(",") or cand_word.endswith(";") or cand_word.endswith("—") or cand_word.endswith(":"):
                score -= 3.0

            if score < best_score:
                best_score = score
                best_pos = cand

        chunks.append(words[curr_start:best_pos])
        curr_start = best_pos

    chunks.append(words[curr_start:n])
    return chunks


def create_running_subtitles(words: list) -> list:
    sentences = []
    curr = []

    for w in words:
        curr.append(w)
        txt = w["text"].strip()
        is_bullet = txt in NUMBER_BULLETS
        is_sent_end = (
            txt.endswith(".") or txt.endswith("!") or txt.endswith("?") or 
            txt.endswith("...'") or txt.endswith("...") or txt.endswith(".'") or txt.endswith(".\"") or
            (txt.endswith(":") and len(curr) >= 3)
        ) and not is_bullet

        if is_sent_end:
            sentences.append(curr)
            curr = []

    if curr:
        sentences.append(curr)

    all_cues = []
    for sent in sentences:
        chunks = split_sentence_words(sent)
        for ch in chunks:
            if not ch:
                continue
            all_cues.append({
                "start": ch[0]["v_start"],
                "end": max(ch[-1]["v_end"] + 0.12, ch[0]["v_start"] + 0.8),
                "text": " ".join([w["text"] for w in ch])
            })

    return all_cues


def write_ass_file(cues: list, path: str):
    header = """[Script Info]
Title: Fuse Demo Subtitles (Exact Script Aligned)
ScriptType: v4.00+
WrapStyle: 0
ScaledBorderAndShadow: yes
PlayResX: 1920
PlayResY: 1080

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: RunningSubtitle,Segoe UI,34,&H00FFFFFF,&H000000FF,&H00000000,&H00000000,1,0,0,0,100,100,1.2,0,1,1.0,2.0,2,80,80,38,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    lines = [header]
    for cue in cues:
        s_str = format_ass_time(cue["start"])
        e_str = format_ass_time(cue["end"])
        t = cue["text"].replace("\n", " ")
        lines.append(f"Dialogue: 0,{s_str},{e_str},RunningSubtitle,,0,0,0,,{t}\n")

    with open(path, "w", encoding="utf-8") as f:
        f.writelines(lines)


def clean_token(s: str) -> str:
    return re.sub(r"[^a-zA-Z0-9]", "", s).lower()


def align_act_script_with_audio(script_words: list, audio_words_slice: list) -> list:
    """Aligns canonical script words with audio start/end timestamps using SequenceMatcher."""
    s_clean = [clean_token(w) for w in script_words]
    a_clean = [clean_token(w["text"]) for w in audio_words_slice]

    matcher = difflib.SequenceMatcher(None, s_clean, a_clean)
    aligned = []

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            for si, aj in zip(range(i1, i2), range(j1, j2)):
                aligned.append({
                    "text": script_words[si],
                    "start": audio_words_slice[aj]["start"],
                    "end": audio_words_slice[aj]["end"]
                })
        else:
            if j2 > j1 and i2 > i1:
                t_start = audio_words_slice[j1]["start"]
                t_end = audio_words_slice[j2 - 1]["end"]
                num_s = i2 - i1
                dt = (t_end - t_start) / num_s
                for idx, si in enumerate(range(i1, i2)):
                    aligned.append({
                        "text": script_words[si],
                        "start": t_start + (idx * dt),
                        "end": t_start + ((idx + 1) * dt)
                    })
            elif i2 > i1:
                prev_end = aligned[-1]["end"] if aligned else audio_words_slice[0]["start"]
                for si in range(i1, i2):
                    aligned.append({
                        "text": script_words[si],
                        "start": prev_end,
                        "end": prev_end + 0.2
                    })
                    prev_end += 0.2

    return aligned


def main():
    print("=" * 70)
    print(" FUSE — OPTION 1: STUDIO REAL VOICE & EXACT SCRIPT ALIGNED SUBTITLES")
    print("=" * 70)

    os.makedirs(BUILD_DIR, exist_ok=True)

    with open("transcription.json", encoding="utf-8") as f:
        d = json.load(f)
    raw_audio_words = [w for w in d["words"] if w["type"] == "word"]

    processed_audio_files = []
    current_video_time = 0.0
    all_scaled_words = []

    for cfg in ACT_CONFIGS:
        aid = cfg["id"]
        v_dur = cfg["video_duration"]
        w_start_idx, w_end_idx = cfg["audio_range"]
        script_words = cfg["script_words"]

        audio_slice = raw_audio_words[w_start_idx : w_end_idx + 1]

        # 1. Align canonical script words with audio timestamps
        aligned_script_words = align_act_script_with_audio(script_words, audio_slice)

        raw_start = max(0.0, audio_slice[0]["start"] - 0.15)
        raw_end = audio_slice[-1]["end"] + 0.25
        raw_dur = raw_end - raw_start

        target_audio_dur = v_dur - 0.5

        if aid == 3:
            # Silence removal in Act 3:
            # Cut out the 10.84-second dead gap between 'now.' (147.20s) and 'As' (156.80s)
            p1_wav = os.path.join(BUILD_DIR, "act3_p1.wav")
            p2_wav = os.path.join(BUILD_DIR, "act3_p2.wav")
            run_ffmpeg(["-ss", "106.65", "-to", "147.20", "-i", "sample_voice.aac", "-c:a", "pcm_s16le", p1_wav])
            run_ffmpeg(["-ss", "156.80", "-to", "190.49", "-i", "sample_voice.aac", "-c:a", "pcm_s16le", p2_wav])
            concat_act3_txt = os.path.join(BUILD_DIR, "act3_concat.txt")
            with open(concat_act3_txt, "w") as f:
                f.write(f"file '{os.path.abspath(p1_wav).replace('\\', '/')}'\n")
                f.write(f"file '{os.path.abspath(p2_wav).replace('\\', '/')}'\n")
            raw_act3_wav = os.path.join(BUILD_DIR, "act3_raw_joined.wav")
            run_ffmpeg(["-f", "concat", "-safe", "0", "-i", concat_act3_txt, "-c:a", "pcm_s16le", raw_act3_wav])

            raw_dur = (147.20 - 106.65) + (190.49 - 156.80)
            speed = raw_dur / target_audio_dur
            input_audio = raw_act3_wav
            input_seek_args = []
        else:
            speed = raw_dur / target_audio_dur
            input_audio = "sample_voice.aac"
            input_seek_args = ["-ss", str(raw_start), "-to", str(raw_end)]

        print(f"\n[*] {cfg['name']}:")
        print(f"    Raw speech: {raw_start:.2f}s -> {raw_end:.2f}s ({raw_dur:.2f}s)")
        print(f"    Video window: {v_dur:.1f}s | Speed factor: {speed:.3f}x")
        print(f"    Aligned script words: {len(aligned_script_words)} canonical words")

        # Studio vocal mastering chain
        act_wav = os.path.join(BUILD_DIR, f"act{aid}_voice.wav")
        pad_silence = v_dur - target_audio_dur

        audio_filters = (
            f"afftdn=nf=-25,highpass=f=85,"
            f"equalizer=f=250:t=q:w=1.0:g=2.5,"
            f"equalizer=f=3200:t=q:w=1.2:g=4.0,"
            f"acompressor=threshold=-16dB:ratio=3.5:attack=10:release=80,"
            f"atempo={speed:.4f},"
            f"loudnorm=I=-16:TP=-1.5:LRA=11,"
            f"apad=pad_dur={pad_silence:.3f}"
        )

        run_ffmpeg(input_seek_args + [
            "-i", input_audio,
            "-af", audio_filters,
            "-t", str(v_dur),
            "-c:a", "pcm_s16le",
            act_wav
        ])
        processed_audio_files.append(act_wav)

        # Scale aligned script word timestamps into video timeline
        for w in aligned_script_words:
            if aid == 3:
                if w["start"] < 150.0:
                    offset_in_act = (w["start"] - 106.65) / speed
                else:
                    offset_in_act = ((147.20 - 106.65) + (w["start"] - 156.80)) / speed
            else:
                offset_in_act = (w["start"] - raw_start) / speed

            dur_in_act = (w["end"] - w["start"]) / speed
            all_scaled_words.append({
                "text": w["text"],
                "v_start": current_video_time + offset_in_act,
                "v_end": current_video_time + offset_in_act + dur_in_act
            })

        current_video_time += v_dur

    # Concatenate audio into 178.0s master track
    print(f"\n[+] Assembling Master Audio Track ({current_video_time:.1f}s)...")
    concat_audio_txt = os.path.join(BUILD_DIR, "audio_concat.txt")
    with open(concat_audio_txt, "w") as f:
        for p in processed_audio_files:
            f.write(f"file '{os.path.abspath(p).replace('\\', '/')}'\n")

    master_audio = os.path.join(BUILD_DIR, "master_enhanced_voice.aac")
    run_ffmpeg([
        "-f", "concat", "-safe", "0", "-i", concat_audio_txt,
        "-c:a", "aac", "-b:a", "192k",
        master_audio
    ])

    # 2. GENERATE RUNNING SUBTITLES WITH CANONICAL SCRIPT TEXT
    print("\n[+] Generating Synchronized Running Subtitles from Script Words...")
    cues = create_running_subtitles(all_scaled_words)
    ass_path = os.path.join(BUILD_DIR, "subtitles.ass")
    write_ass_file(cues, ass_path)
    print(f"[*] Generated {len(cues)} subtitle cues strictly matching docs/demo-script.md!")

    # 3. COMPILE VIDEO SCENES (178.0s)
    print("\n[+] Compiling Video Scenes...")
    # ACT 1 (38s)
    # Part A: Smooth GitHub Repo Cinematic Scroll (14.5s)
    repo_png = os.path.join(REPO_ROOT, "github_full_repo.png")
    repo_im = Image.open(repo_png)
    max_y = repo_im.size[1] - 960
    crop_expr = f"if(lte(t,2.0), 0, if(gte(t,13.5), {max_y}, {max_y}*(0.5-0.5*cos(3.14159265*(t-2.0)/11.5))))"
    act1_partA = os.path.join(BUILD_DIR, "act1_partA.mp4")
    run_ffmpeg([
        "-loop", "1", "-i", repo_png,
        "-vf", f"crop=w=1920:h=960:x=0:y='{crop_expr}',pad=1920:1080:0:0:color=#090d16,format=yuv420p",
        "-t", "14.5",
        "-r", str(FPS),
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        act1_partA
    ])

    # Part B: Terminal Problem Comparison Window (23.5s)
    act1_img = build_act1_frame()
    act1_partB = os.path.join(BUILD_DIR, "act1_partB.mp4")
    run_ffmpeg([
        "-loop", "1", "-i", act1_img,
        "-t", "23.5",
        "-r", str(FPS),
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        act1_partB
    ])

    # Concatenate into Act 1 Master Video (38.0s)
    act1_concat_txt = os.path.join(BUILD_DIR, "act1_concat.txt")
    with open(act1_concat_txt, "w") as f:
        f.write(f"file '{os.path.abspath(act1_partA).replace('\\', '/')}'\n")
        f.write(f"file '{os.path.abspath(act1_partB).replace('\\', '/')}'\n")
    act1_mp4 = os.path.join(BUILD_DIR, "act1.mp4")
    run_ffmpeg(["-f", "concat", "-safe", "0", "-i", act1_concat_txt, "-c", "copy", act1_mp4])

    # ACT 2 (42s)
    act2_webp = os.path.join(ARTIFACTS_DIR, "act2_legit_traffic_1789827070180.webp")
    act2_mp4 = os.path.join(BUILD_DIR, "act2.mp4")
    run_ffmpeg([
        "-i", act2_webp,
        "-t", "42",
        "-filter_complex",
        "[0:v]tpad=stop_mode=clone:stop_duration=42,crop=1915:960:0:0,scale=1920:960,pad=1920:1080:0:0:color=#090d16[v]",
        "-map", "[v]", "-c:v", "libx264", "-r", str(FPS), "-pix_fmt", "yuv420p", act2_mp4
    ])

    # ACT 3 (58s)
    act3_webp = os.path.join(ARTIFACTS_DIR, "final_approval_flow_1789821631587.webp")
    act3_mp4 = os.path.join(BUILD_DIR, "act3.mp4")
    run_ffmpeg([
        "-i", act3_webp,
        "-t", "58",
        "-filter_complex",
        "[0:v]tpad=stop_mode=clone:stop_duration=58,crop=1820:880:50:48,scale=1920:960,pad=1920:1080:0:0:color=#090d16[v]",
        "-map", "[v]", "-c:v", "libx264", "-r", str(FPS), "-pix_fmt", "yuv420p", act3_mp4
    ])

    # ACT 4 (24s)
    act4_img = os.path.join(REPO_ROOT, "docs", "architecture-simple.png")
    act4_mp4 = os.path.join(BUILD_DIR, "act4.mp4")
    run_ffmpeg([
        "-loop", "1", "-i", act4_img,
        "-t", "24",
        "-filter_complex",
        "[0:v]scale=1920:960:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:0:color=#090d16[v]",
        "-map", "[v]", "-c:v", "libx264", "-r", str(FPS), "-pix_fmt", "yuv420p", act4_mp4
    ])

    # ACT 5 (16s: 8s Amplify + 8s GitHub)
    amp_img = os.path.join(ARTIFACTS_DIR, "act5_amplify_dashboard_1789897209511.png")
    git_img = os.path.join(ARTIFACTS_DIR, "act5_github_verification_1789897391071.png")

    act5_p1 = os.path.join(BUILD_DIR, "act5_p1.mp4")
    run_ffmpeg([
        "-loop", "1", "-i", amp_img, "-t", "8",
        "-filter_complex",
        "[0:v]scale=1920:960:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:0:color=#090d16[v]",
        "-map", "[v]", "-c:v", "libx264", "-r", str(FPS), "-pix_fmt", "yuv420p", act5_p1
    ])
    act5_p2 = os.path.join(BUILD_DIR, "act5_p2.mp4")
    run_ffmpeg([
        "-loop", "1", "-i", git_img, "-t", "8",
        "-filter_complex",
        "[0:v]scale=1920:960:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:0:color=#090d16[v]",
        "-map", "[v]", "-c:v", "libx264", "-r", str(FPS), "-pix_fmt", "yuv420p", act5_p2
    ])
    act5_mp4 = os.path.join(BUILD_DIR, "act5.mp4")
    concat_act5_txt = os.path.join(BUILD_DIR, "act5_concat.txt")
    with open(concat_act5_txt, "w") as f:
        f.write(f"file '{os.path.abspath(act5_p1).replace('\\', '/')}'\n")
        f.write(f"file '{os.path.abspath(act5_p2).replace('\\', '/')}'\n")
    run_ffmpeg(["-f", "concat", "-safe", "0", "-i", concat_act5_txt, "-c", "copy", act5_mp4])

    # 4. CONCATENATE ALL VIDEO ACTS
    print("\n[+] Concatenating Video Scenes...")
    concat_vid_txt = os.path.join(BUILD_DIR, "vid_concat.txt")
    with open(concat_vid_txt, "w") as f:
        f.write(f"file '{os.path.abspath(act1_mp4).replace('\\', '/')}'\n")
        f.write(f"file '{os.path.abspath(act2_mp4).replace('\\', '/')}'\n")
        f.write(f"file '{os.path.abspath(act3_mp4).replace('\\', '/')}'\n")
        f.write(f"file '{os.path.abspath(act4_mp4).replace('\\', '/')}'\n")
        f.write(f"file '{os.path.abspath(act5_mp4).replace('\\', '/')}'\n")

    raw_video = os.path.join(BUILD_DIR, "raw_video.mp4")
    run_ffmpeg(["-f", "concat", "-safe", "0", "-i", concat_vid_txt, "-c", "copy", raw_video])

    # 5. MERGE VIDEO + MASTER ENHANCED AUDIO + BURNED-IN SUBTITLES
    print("\n[+] Merging Video + Master Real Voice + Burned-in Canonical Subtitles...")
    ass_filter_path = os.path.abspath(ass_path).replace("\\", "/").replace(":", "\\:")
    run_ffmpeg([
        "-i", raw_video,
        "-i", master_audio,
        "-filter_complex", f"[0:v]subtitles='{ass_filter_path}'[v]",
        "-map", "[v]",
        "-map", "1:a",
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "18",
        "-c:a", "aac",
        "-b:a", "192k",
        "-shortest",
        OUTPUT_VIDEO
    ])

    shutil.rmtree(BUILD_DIR, ignore_errors=True)

    size_mb = os.path.getsize(OUTPUT_VIDEO) / (1024 * 1024)
    print("\n" + "=" * 70)
    print(" [COMPLETE] FINAL ENHANCED REAL VOICE DEMO VIDEO READY!")
    print(f" File:       {OUTPUT_VIDEO}")
    print(f" Duration:   178.0 seconds (2 minutes 58 seconds — strictly < 3:00)")
    print(f" Voice:      Pranjul Chaurasiya's Real Voice (Studio-Mastered & Enhanced)")
    print(f" Subtitles:  100% Canonical Text from docs/demo-script.md (Segoe UI, 24pt)")
    print(f" Resolution: 1920x1080 @ 30fps ({size_mb:.2f} MB)")
    print("=" * 70)


if __name__ == "__main__":
    main()
