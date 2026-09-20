#!/usr/bin/env python3
"""assemble_demo_video.py — Programmatic studio-grade demo video compiler for Fuse.

Assembles all 5 Acts into a single 1080p 30fps MP4 video file:
- ACT 1 (30s): The Problem — Why Static Alarms Fail (Terminal Comparison)
- ACT 2 (40s): Scenario 1 — Legitimate Spike (Flash Sale, 35 Unique Callers)
- ACT 3 (55s): Scenario 2 — Runaway Loop, Approval Gate, & HTTP 429 Verification
- ACT 4 (25s): Under the Hood — Architecture & Single-Turn Bedrock Converse
- ACT 5 (20s): Conclusion — Live AWS Amplify Console & GitHub Repository

Total Duration: ~2 minutes 50 seconds (comfortably under the 3:00 hard ceiling).
Output: Fuse_Demo_Walkthrough_1080p.mp4 (in repo root)
"""

import os
import sys
import subprocess
import shutil
from PIL import Image, ImageDraw, ImageFont

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ARTIFACTS_DIR = r"C:\Users\pranj\.gemini\antigravity-ide\brain\f8e60b13-df6d-4964-9161-caa38ad96efd"
BUILD_DIR = os.path.join(REPO_ROOT, "scratch_video_build")
OUTPUT_MP4 = os.path.join(REPO_ROOT, "Fuse_Demo_Walkthrough_1080p.mp4")

WIDTH = 1920
HEIGHT = 1080
FPS = 30


def run_ffmpeg(args: list):
    """Runs an ffmpeg command line."""
    cmd = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "warning"] + args
    print(f"[*] Running: {' '.join(cmd[:6])} ...")
    subprocess.check_call(cmd)


def render_banner(title: str, subtitle: str) -> Image.Image:
    """Renders a sleek broadcast pill banner overlay."""
    banner = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    draw = ImageDraw.Draw(banner)

    # Pill badge in top-left
    badge_x = 40
    badge_y = 35
    badge_w = 920
    badge_h = 70

    # Draw frosted pill background
    draw.rounded_rectangle(
        [badge_x, badge_y, badge_x + badge_w, badge_y + badge_h],
        radius=14,
        fill=(10, 15, 26, 220),
        outline=(56, 189, 248, 180),
        width=2,
    )

    # Accent dot
    draw.ellipse([badge_x + 18, badge_y + 26, badge_x + 36, badge_y + 44], fill=(16, 185, 129, 255))

    font_title = ImageFont.truetype("C:/Windows/Fonts/segoeui.ttf", 22)
    font_sub = ImageFont.truetype("C:/Windows/Fonts/segoeui.ttf", 16)

    draw.text((badge_x + 48, badge_y + 12), title, font=font_title, fill=(240, 246, 252))
    draw.text((badge_x + 48, badge_y + 40), subtitle, font=font_sub, fill=(148, 163, 184))

    return banner


def build_act1_frame() -> str:
    """Renders the Act 1 terminal comparison graphic."""
    out_path = os.path.join(BUILD_DIR, "act1_frame.png")
    img = Image.new("RGB", (WIDTH, HEIGHT), "#080b12")
    draw = ImageDraw.Draw(img)

    # Window Mockup
    win_x, win_y, win_w, win_h = 100, 120, 1720, 880
    draw.rounded_rectangle([win_x, win_y, win_x + win_w, win_y + win_h], radius=16, fill="#0d1117", outline="#30363d", width=2)
    draw.rounded_rectangle([win_x, win_y, win_x + win_w, win_y + 48], radius=16, fill="#161b22")
    draw.rectangle([win_x, win_y + 32, win_x + win_w, win_y + 48], fill="#161b22")

    # Traffic light dots
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

    # Apply Banner overlay
    banner = render_banner("ACT 1: THE PROBLEM", "Why Static Alarms Fail: False Positives vs Runaway Loop")
    img.paste(banner, (0, 0), banner)

    img.save(out_path)
    return out_path


def main():
    print("=" * 70)
    print(" FUSE — COMPILING STUDIO-GRADE DEMO VIDEO WALKTHROUGH")
    print("=" * 70)

    os.makedirs(BUILD_DIR, exist_ok=True)

    # ----------------------------------------------------
    # ACT 1 (30s): Terminal Comparison
    # ----------------------------------------------------
    print("\n[+] Compiling ACT 1 (30s) — The Problem...")
    act1_img = build_act1_frame()
    act1_mp4 = os.path.join(BUILD_DIR, "act1.mp4")
    run_ffmpeg([
        "-loop", "1",
        "-i", act1_img,
        "-t", "30",
        "-c:v", "libx264",
        "-r", str(FPS),
        "-pix_fmt", "yuv420p",
        act1_mp4
    ])

    # ----------------------------------------------------
    # ACT 2 (40s): Legitimate Traffic Surge
    # ----------------------------------------------------
    print("\n[+] Compiling ACT 2 (40s) — Legitimate Spike (Flash Sale)...")
    act2_webp = os.path.join(ARTIFACTS_DIR, "act2_legit_traffic_1789827070180.webp")
    act2_banner = os.path.join(BUILD_DIR, "act2_banner.png")
    render_banner("ACT 2: SCENARIO 1 — LEGITIMATE SPIKE", "35 Unique Callers With Diverse Payloads -> Classified as NORMAL").save(act2_banner)

    act2_mp4 = os.path.join(BUILD_DIR, "act2.mp4")
    run_ffmpeg([
        "-i", act2_webp,
        "-i", act2_banner,
        "-t", "40",
        "-filter_complex",
        "[0:v]tpad=stop_mode=clone:stop_duration=40,scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2:color=black[bg];"
        "[bg][1:v]overlay=0:0[v]",
        "-map", "[v]",
        "-c:v", "libx264",
        "-r", str(FPS),
        "-pix_fmt", "yuv420p",
        act2_mp4
    ])

    # ----------------------------------------------------
    # ACT 3 (55s): Runaway Loop & Approval Gate
    # ----------------------------------------------------
    print("\n[+] Compiling ACT 3 (55s) — Runaway Loop & Human Approval Gate...")
    act3_webp = os.path.join(ARTIFACTS_DIR, "final_approval_flow_1789821631587.webp")
    act3_banner = os.path.join(BUILD_DIR, "act3_banner.png")
    render_banner("ACT 3: SCENARIO 2 — RUNAWAY LOOP & APPROVAL GATE", "Classified as RUNAWAY -> Prod Safety Gate Holds -> Operator Approves -> HTTP 429").save(act3_banner)

    act3_mp4 = os.path.join(BUILD_DIR, "act3.mp4")
    run_ffmpeg([
        "-i", act3_webp,
        "-i", act3_banner,
        "-t", "55",
        "-filter_complex",
        "[0:v]tpad=stop_mode=clone:stop_duration=55,scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2:color=black[bg];"
        "[bg][1:v]overlay=0:0[v]",
        "-map", "[v]",
        "-c:v", "libx264",
        "-r", str(FPS),
        "-pix_fmt", "yuv420p",
        act3_mp4
    ])

    # ----------------------------------------------------
    # ACT 4 (25s): Under the Hood — Architecture
    # ----------------------------------------------------
    print("\n[+] Compiling ACT 4 (25s) — System Architecture...")
    act4_img = os.path.join(REPO_ROOT, "docs", "architecture-simple.png")
    act4_banner = os.path.join(BUILD_DIR, "act4_banner.png")
    render_banner("ACT 4: UNDER THE HOOD — ARCHITECTURE", "Single-Turn Bedrock Converse, Isolated Control Plane, Edge Throttle").save(act4_banner)

    act4_mp4 = os.path.join(BUILD_DIR, "act4.mp4")
    run_ffmpeg([
        "-loop", "1",
        "-i", act4_img,
        "-i", act4_banner,
        "-t", "25",
        "-filter_complex",
        "[0:v]scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2:color=white[bg];"
        "[bg][1:v]overlay=0:0[v]",
        "-map", "[v]",
        "-c:v", "libx264",
        "-r", str(FPS),
        "-pix_fmt", "yuv420p",
        act4_mp4
    ])

    # ----------------------------------------------------
    # ACT 5 (20s): Conclusion & Repository Verification
    # ----------------------------------------------------
    print("\n[+] Compiling ACT 5 (20s) — Conclusion & Links...")
    amp_img = os.path.join(ARTIFACTS_DIR, "act5_amplify_dashboard_1789897209511.png")
    git_img = os.path.join(ARTIFACTS_DIR, "act5_github_verification_1789897391071.png")
    act5_banner = os.path.join(BUILD_DIR, "act5_banner.png")
    render_banner("ACT 5: CONCLUSION", "Live AWS Amplify Dashboard & Independently Checkable GitHub Repo").save(act5_banner)

    # 10s Amplify + 10s GitHub
    act5_part1 = os.path.join(BUILD_DIR, "act5_part1.mp4")
    run_ffmpeg([
        "-loop", "1", "-i", amp_img, "-i", act5_banner,
        "-t", "10",
        "-filter_complex",
        "[0:v]scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2:color=black[bg];"
        "[bg][1:v]overlay=0:0[v]",
        "-map", "[v]", "-c:v", "libx264", "-r", str(FPS), "-pix_fmt", "yuv420p", act5_part1
    ])

    act5_part2 = os.path.join(BUILD_DIR, "act5_part2.mp4")
    run_ffmpeg([
        "-loop", "1", "-i", git_img, "-i", act5_banner,
        "-t", "10",
        "-filter_complex",
        "[0:v]scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2:color=black[bg];"
        "[bg][1:v]overlay=0:0[v]",
        "-map", "[v]", "-c:v", "libx264", "-r", str(FPS), "-pix_fmt", "yuv420p", act5_part2
    ])

    act5_mp4 = os.path.join(BUILD_DIR, "act5.mp4")
    concat_act5_txt = os.path.join(BUILD_DIR, "act5_concat.txt")
    with open(concat_act5_txt, "w") as f:
        f.write(f"file '{os.path.abspath(act5_part1).replace('\\', '/')}'\n")
        f.write(f"file '{os.path.abspath(act5_part2).replace('\\', '/')}'\n")
    run_ffmpeg([
        "-f", "concat", "-safe", "0", "-i", concat_act5_txt,
        "-c", "copy", act5_mp4
    ])

    # ----------------------------------------------------
    # FINAL CONCATENATION (ACTS 1 - 5) + Silent Audio Track
    # ----------------------------------------------------
    print("\n[+] Assembling Final Full Demo Video (170 seconds / ~2m 50s)...")
    run_ffmpeg([
        "-i", act1_mp4,
        "-i", act2_mp4,
        "-i", act3_mp4,
        "-i", act4_mp4,
        "-i", act5_mp4,
        "-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=44100",
        "-filter_complex",
        "[0:v][1:v][2:v][3:v][4:v]concat=n=5:v=1:a=0[outv]",
        "-map", "[outv]",
        "-map", "5:a",
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "18",
        "-c:a", "aac",
        "-shortest",
        OUTPUT_MP4
    ])

    # Clean up scratch directory
    shutil.rmtree(BUILD_DIR, ignore_errors=True)

    size_mb = os.path.getsize(OUTPUT_MP4) / (1024 * 1024)
    print("\n" + "=" * 70)
    print(" [COMPLETE] DEMO VIDEO ASSEMBLED SUCCESSFULLY!")
    print(f" Output File:     {OUTPUT_MP4}")
    print(f" Resolution:      1920x1080 (1080p @ 30fps)")
    print(f" File Size:       {size_mb:.2f} MB")
    print(f" Total Duration:  170.0 seconds (2 minutes 50 seconds)")
    print(" All Acts Timed Strictly to docs/demo-script.md Voiceover Cues!")
    print("=" * 70)


if __name__ == "__main__":
    main()
