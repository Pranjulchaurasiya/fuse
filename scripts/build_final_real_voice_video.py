#!/usr/bin/env python3
"""build_final_real_voice_video.py — Master compiler using Pranjul's REAL recorded voice.

Features:
1. Slices Pranjul's real voice from sample_voice.aac using exact transcription boundaries.
2. Applies broadcast normalization (loudnorm EBU R128) and pitch-preserving atempo.
3. Renders video acts timed to Pranjul's natural presentation pace (Total 178.0s / 2m 58s).
4. Generates synchronized running subtitles (.ass) matching his exact spoken words.
5. Produces final master video: Fuse_Demo_Real_Voice.mp4 (1080p @ 30fps).
"""

import os
import sys
import json
import subprocess
import shutil
from PIL import Image, ImageDraw, ImageFont

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ARTIFACTS_DIR = r"C:\Users\pranj\.gemini\antigravity-ide\brain\f8e60b13-df6d-4964-9161-caa38ad96efd"
BUILD_DIR = os.path.join(REPO_ROOT, "scratch_real_voice_build")
OUTPUT_VIDEO = os.path.join(REPO_ROOT, "Fuse_Demo_Real_Voice.mp4")

WIDTH = 1920
HEIGHT = 1080
FPS = 30

# Act timeline definitions (Total = 178.0s = 2m 58s, strictly under 3:00 limit)
ACT_CONFIGS = [
    {
        "id": 1,
        "name": "ACT 1: THE PROBLEM",
        "subtitle": "Why Static Alarms Fail: False Positives vs Runaway Loop",
        "video_duration": 38.0,
        "word_range": (0, 108),
    },
    {
        "id": 2,
        "name": "ACT 2: SCENARIO 1 — LEGITIMATE SPIKE",
        "subtitle": "35 Unique Callers With Diverse Payloads -> Classified as NORMAL",
        "video_duration": 42.0,
        "word_range": (109, 211),
    },
    {
        "id": 3,
        "name": "ACT 3: SCENARIO 2 — RUNAWAY LOOP & APPROVAL GATE",
        "subtitle": "Classified as RUNAWAY -> Prod Safety Gate Holds -> Operator Approves -> HTTP 429",
        "video_duration": 58.0,
        "word_range": (212, 375),
    },
    {
        "id": 4,
        "name": "ACT 4: UNDER THE HOOD — ARCHITECTURE",
        "subtitle": "Single-Turn Bedrock Converse, Isolated Control Plane, Edge Throttle",
        "video_duration": 24.0,
        "word_range": (376, 453),
    },
    {
        "id": 5,
        "name": "ACT 5: CONCLUSION",
        "subtitle": "Live AWS Amplify Dashboard & Independently Checkable GitHub Repo",
        "video_duration": 16.0,
        "word_range": (454, 503),
    },
]


def run_ffmpeg(args: list):
    cmd = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "warning"] + args
    subprocess.check_call(cmd)


def render_banner(title: str, subtitle: str) -> Image.Image:
    banner = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    draw = ImageDraw.Draw(banner)
    bx, by, bw, bh = 40, 35, 920, 70
    draw.rounded_rectangle([bx, by, bx + bw, by + bh], radius=14, fill=(10, 15, 26, 220), outline=(56, 189, 248, 180), width=2)
    draw.ellipse([bx + 18, by + 26, bx + 36, by + 44], fill=(16, 185, 129, 255))
    font_title = ImageFont.truetype("C:/Windows/Fonts/segoeui.ttf", 22)
    font_sub = ImageFont.truetype("C:/Windows/Fonts/segoeui.ttf", 16)
    draw.text((bx + 48, by + 12), title, font=font_title, fill=(240, 246, 252))
    draw.text((bx + 48, by + 40), subtitle, font=font_sub, fill=(148, 163, 184))
    return banner


def build_act1_frame() -> str:
    out_path = os.path.join(BUILD_DIR, "act1_frame.png")
    img = Image.new("RGB", (WIDTH, HEIGHT), "#080b12")
    draw = ImageDraw.Draw(img)

    win_x, win_y, win_w, win_h = 100, 120, 1720, 880
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

    banner = render_banner("ACT 1: THE PROBLEM", "Why Static Alarms Fail: False Positives vs Runaway Loop")
    img.paste(banner, (0, 0), banner)
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


def create_running_subtitles(words: list) -> list:
    cues = []
    group = []
    g_start = None

    for w in words:
        if not group:
            g_start = w["v_start"]
        group.append(w["text"])
        dur = w["v_end"] - g_start
        ends_punct = any(w["text"].endswith(p) for p in [".", ",", "!", "?", ":", "..."])

        if len(group) >= 5 or (ends_punct and len(group) >= 3) or dur >= 2.0:
            cues.append({
                "start": g_start,
                "end": w["v_end"] + 0.1,
                "text": " ".join(group)
            })
            group = []
            g_start = None

    if group:
        cues.append({
            "start": g_start,
            "end": words[-1]["v_end"] + 0.2,
            "text": " ".join(group)
        })

    return cues


def write_ass_file(cues: list, path: str):
    header = """[Script Info]
Title: Fuse Demo Subtitles (Real Voice)
ScriptType: v4.00+
WrapStyle: 0
ScaledBorderAndShadow: yes
PlayResX: 1920
PlayResY: 1080

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: RunningSubtitle,Segoe UI,25,&H00FFFFFF,&H000000FF,&H0010141D,&HA0050810,1,0,0,0,100,100,0,0,1,2.8,1.2,2,80,80,60,1

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


def main():
    print("=" * 70)
    print(" FUSE — COMPILING MASTER VIDEO WITH PRANJUL'S REAL RECORDED VOICE")
    print("=" * 70)

    os.makedirs(BUILD_DIR, exist_ok=True)

    with open("transcription.json", encoding="utf-8") as f:
        d = json.load(f)
    words = [w for w in d["words"] if w["type"] == "word"]

    # ----------------------------------------------------
    # 1. PROCESS REAL AUDIO PER ACT
    # ----------------------------------------------------
    print("\n[+] Processing Pranjul's Voice Per Act...")
    processed_audio_files = []
    current_video_time = 0.0
    all_scaled_words = []

    for cfg in ACT_CONFIGS:
        aid = cfg["id"]
        v_dur = cfg["video_duration"]
        w_start_idx, w_end_idx = cfg["word_range"]
        act_words = words[w_start_idx : w_end_idx + 1]

        # Get timestamps in sample_voice.aac
        raw_start = max(0.0, act_words[0]["start"] - 0.15)
        raw_end = act_words[-1]["end"] + 0.25
        raw_dur = raw_end - raw_start

        # Target audio duration: leave 0.5s pause at end of act before scene cut
        target_audio_dur = v_dur - 0.5
        speed = raw_dur / target_audio_dur

        print(f"\n[*] {cfg['name']}:")
        print(f"    Raw speech: {raw_start:.2f}s -> {raw_end:.2f}s ({raw_dur:.2f}s)")
        print(f"    Video duration: {v_dur:.1f}s | Speed factor: {speed:.3f}x")

        # Slice raw audio and apply atempo + loudnorm
        act_wav = os.path.join(BUILD_DIR, f"act{aid}_voice.wav")
        pad_silence = v_dur - target_audio_dur

        run_ffmpeg([
            "-ss", str(raw_start),
            "-to", str(raw_end),
            "-i", "sample_voice.aac",
            "-af", f"highpass=f=80,atempo={speed:.4f},loudnorm=I=-16:TP=-1.5:LRA=11,apad=pad_dur={pad_silence:.3f}",
            "-t", str(v_dur),
            "-c:a", "pcm_s16le",
            act_wav
        ])
        processed_audio_files.append(act_wav)

        # Scale word timestamps for running subtitles
        for w in act_words:
            offset_in_act = (w["start"] - raw_start) / speed
            dur_in_act = (w["end"] - w["start"]) / speed
            w_copy = {
                "text": w["text"],
                "v_start": current_video_time + offset_in_act,
                "v_end": current_video_time + offset_in_act + dur_in_act
            }
            all_scaled_words.append(w_copy)

        current_video_time += v_dur

    # Concatenate audio into 178.0s master track
    print("\n[+] Assembling Master Voiceover Track (178.0s)...")
    concat_audio_txt = os.path.join(BUILD_DIR, "audio_concat.txt")
    with open(concat_audio_txt, "w") as f:
        for p in processed_audio_files:
            f.write(f"file '{os.path.abspath(p).replace('\\', '/')}'\n")

    master_audio = os.path.join(BUILD_DIR, "master_real_voice.aac")
    run_ffmpeg([
        "-f", "concat", "-safe", "0", "-i", concat_audio_txt,
        "-c:a", "aac", "-b:a", "192k",
        master_audio
    ])

    # ----------------------------------------------------
    # 2. GENERATE RUNNING SUBTITLES (.ass)
    # ----------------------------------------------------
    print("\n[+] Generating Synchronized Running Subtitles...")
    cues = create_running_subtitles(all_scaled_words)
    ass_path = os.path.join(BUILD_DIR, "subtitles.ass")
    write_ass_file(cues, ass_path)
    print(f"[*] Generated {len(cues)} subtitle cues matching Pranjul's voice!")

    # ----------------------------------------------------
    # 3. COMPILE VIDEO ACTS TO MATCH REAL TIMING (178.0s)
    # ----------------------------------------------------
    print("\n[+] Compiling Video Scenes...")
    # ACT 1 (38s)
    print("    - Compiling ACT 1 (38s)...")
    act1_img = build_act1_frame()
    act1_mp4 = os.path.join(BUILD_DIR, "act1.mp4")
    run_ffmpeg([
        "-loop", "1", "-i", act1_img,
        "-t", "38", "-c:v", "libx264", "-r", str(FPS), "-pix_fmt", "yuv420p", act1_mp4
    ])

    # ACT 2 (42s)
    print("    - Compiling ACT 2 (42s)...")
    act2_webp = os.path.join(ARTIFACTS_DIR, "act2_legit_traffic_1789827070180.webp")
    act2_banner = os.path.join(BUILD_DIR, "act2_banner.png")
    render_banner("ACT 2: SCENARIO 1 — LEGITIMATE SPIKE", "35 Unique Callers With Diverse Payloads -> Classified as NORMAL").save(act2_banner)
    act2_mp4 = os.path.join(BUILD_DIR, "act2.mp4")
    run_ffmpeg([
        "-i", act2_webp, "-i", act2_banner,
        "-t", "42",
        "-filter_complex",
        "[0:v]tpad=stop_mode=clone:stop_duration=42,scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2:color=black[bg];"
        "[bg][1:v]overlay=0:0[v]",
        "-map", "[v]", "-c:v", "libx264", "-r", str(FPS), "-pix_fmt", "yuv420p", act2_mp4
    ])

    # ACT 3 (58s)
    print("    - Compiling ACT 3 (58s)...")
    act3_webp = os.path.join(ARTIFACTS_DIR, "final_approval_flow_1789821631587.webp")
    act3_banner = os.path.join(BUILD_DIR, "act3_banner.png")
    render_banner("ACT 3: SCENARIO 2 — RUNAWAY LOOP & APPROVAL GATE", "Classified as RUNAWAY -> Prod Safety Gate Holds -> Operator Approves -> HTTP 429").save(act3_banner)
    act3_mp4 = os.path.join(BUILD_DIR, "act3.mp4")
    run_ffmpeg([
        "-i", act3_webp, "-i", act3_banner,
        "-t", "58",
        "-filter_complex",
        "[0:v]tpad=stop_mode=clone:stop_duration=58,scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2:color=black[bg];"
        "[bg][1:v]overlay=0:0[v]",
        "-map", "[v]", "-c:v", "libx264", "-r", str(FPS), "-pix_fmt", "yuv420p", act3_mp4
    ])

    # ACT 4 (24s)
    print("    - Compiling ACT 4 (24s)...")
    act4_img = os.path.join(REPO_ROOT, "docs", "architecture-simple.png")
    act4_banner = os.path.join(BUILD_DIR, "act4_banner.png")
    render_banner("ACT 4: UNDER THE HOOD — ARCHITECTURE", "Single-Turn Bedrock Converse, Isolated Control Plane, Edge Throttle").save(act4_banner)
    act4_mp4 = os.path.join(BUILD_DIR, "act4.mp4")
    run_ffmpeg([
        "-loop", "1", "-i", act4_img, "-i", act4_banner,
        "-t", "24",
        "-filter_complex",
        "[0:v]scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2:color=white[bg];"
        "[bg][1:v]overlay=0:0[v]",
        "-map", "[v]", "-c:v", "libx264", "-r", str(FPS), "-pix_fmt", "yuv420p", act4_mp4
    ])

    # ACT 5 (16s: 8s Amplify + 8s GitHub)
    print("    - Compiling ACT 5 (16s)...")
    amp_img = os.path.join(ARTIFACTS_DIR, "act5_amplify_dashboard_1789897209511.png")
    git_img = os.path.join(ARTIFACTS_DIR, "act5_github_verification_1789897391071.png")
    act5_banner = os.path.join(BUILD_DIR, "act5_banner.png")
    render_banner("ACT 5: CONCLUSION", "Live AWS Amplify Dashboard & Independently Checkable GitHub Repo").save(act5_banner)

    act5_p1 = os.path.join(BUILD_DIR, "act5_p1.mp4")
    run_ffmpeg([
        "-loop", "1", "-i", amp_img, "-i", act5_banner, "-t", "8",
        "-filter_complex",
        "[0:v]scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2:color=black[bg];"
        "[bg][1:v]overlay=0:0[v]",
        "-map", "[v]", "-c:v", "libx264", "-r", str(FPS), "-pix_fmt", "yuv420p", act5_p1
    ])
    act5_p2 = os.path.join(BUILD_DIR, "act5_p2.mp4")
    run_ffmpeg([
        "-loop", "1", "-i", git_img, "-i", act5_banner, "-t", "8",
        "-filter_complex",
        "[0:v]scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2:color=black[bg];"
        "[bg][1:v]overlay=0:0[v]",
        "-map", "[v]", "-c:v", "libx264", "-r", str(FPS), "-pix_fmt", "yuv420p", act5_p2
    ])
    act5_mp4 = os.path.join(BUILD_DIR, "act5.mp4")
    concat_act5_txt = os.path.join(BUILD_DIR, "act5_concat.txt")
    with open(concat_act5_txt, "w") as f:
        f.write(f"file '{os.path.abspath(act5_p1).replace('\\', '/')}'\n")
        f.write(f"file '{os.path.abspath(act5_p2).replace('\\', '/')}'\n")
    run_ffmpeg(["-f", "concat", "-safe", "0", "-i", concat_act5_txt, "-c", "copy", act5_mp4])

    # ----------------------------------------------------
    # 4. CONCATENATE ALL VIDEO ACTS (178.0s)
    # ----------------------------------------------------
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

    # ----------------------------------------------------
    # 5. MERGE VIDEO + MASTER REAL AUDIO + BURNED SUBTITLES
    # ----------------------------------------------------
    print("\n[+] Merging Video + Pranjul's Real Voice + Burned-in Subtitles...")
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

    # Clean up build directory
    shutil.rmtree(BUILD_DIR, ignore_errors=True)

    size_mb = os.path.getsize(OUTPUT_VIDEO) / (1024 * 1024)
    print("\n" + "=" * 70)
    print(" [COMPLETE] FINAL REAL VOICE DEMO VIDEO READY!")
    print(f" File:       {OUTPUT_VIDEO}")
    print(f" Duration:   178.0 seconds (2 minutes 58 seconds — strictly < 3:00)")
    print(f" Voice:      Pranjul Chaurasiya's 100% Real Authentic Voice")
    print(f" Subtitles:  Synchronized Running Subtitles (Segoe UI, 25pt)")
    print(f" Resolution: 1920x1080 @ 30fps ({size_mb:.2f} MB)")
    print("=" * 70)


if __name__ == "__main__":
    main()
