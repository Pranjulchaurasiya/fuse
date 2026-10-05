"""build_viral_motion_video.py — Viral 4:5 Motion Graphics Commercial for Fuse.

Replicates the signature aesthetic of Charlie Hills' viral videos:
- 4:5 Vertical Aspect Ratio (1080x1350)
- Top Identity Capsule with glowing beacon
- Dynamic Step Badge [• STEP X · ACTION]
- Giant high-impact headline
- Glassmorphic AI Prompt Pill with character typewriter & animated cursor
- Interactive Component Card with spring slide-up and staggered checkmark pops
- Segmented Story Progress Bar at bottom
- Studio Neural Voiceover (en-US-ChristopherNeural) + synth audio bed
"""

import asyncio
import json
import math
import os
import shutil
import subprocess
import sys
import time
from PIL import Image, ImageDraw, ImageFont

# Canvas dimensions (4:5 vertical portrait)
WIDTH = 1080
HEIGHT = 1350
FPS = 30

# Colors (Modern Deep Midnight & Neon Accents)
COLOR_BG = (8, 12, 22)
COLOR_CARD = (16, 23, 38)
COLOR_CARD_BORDER = (45, 60, 90)
COLOR_WHITE = (248, 250, 252)
COLOR_MUTED = (148, 163, 184)
COLOR_CYAN = (0, 229, 255)
COLOR_BLUE = (37, 99, 235)
COLOR_GREEN = (34, 197, 94)
COLOR_RED = (239, 68, 68)
COLOR_AMBER = (245, 158, 11)

BUILD_DIR = r"c:\Users\pranj\Documents\Fuse\scratch_viral_build"
OUTPUT_VIDEO = r"c:\Users\pranj\Documents\Fuse\Fuse_Viral_Commercial_4x5.mp4"

# Load TrueType Fonts
def load_font(name, size):
    fonts_dir = r"C:\Windows\Fonts"
    candidates = {
        "regular": ["segoeui.ttf", "arial.ttf"],
        "bold": ["segoeuib.ttf", "arialbd.ttf"],
        "semibold": ["seguisb.ttf", "segoeuib.ttf"],
        "light": ["segoeuisl.ttf", "segoeui.ttf"],
        "mono": ["consola.ttf", "cour.ttf"],
        "mono_bold": ["consolab.ttf", "courbd.ttf"],
    }
    for fname in candidates.get(name, ["segoeui.ttf"]):
        path = os.path.join(fonts_dir, fname)
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                pass
    return ImageFont.load_default()

FONTS = {
    "header_pill": load_font("bold", 22),
    "step_pill": load_font("bold", 22),
    "headline": load_font("bold", 46),
    "prompt": load_font("regular", 25),
    "prompt_cursor": load_font("bold", 28),
    "card_title": load_font("bold", 30),
    "body": load_font("regular", 24),
    "body_bold": load_font("bold", 24),
    "mono": load_font("mono", 22),
    "mono_bold": load_font("mono_bold", 22),
    "mono_sm": load_font("mono", 18),
    "check_label": load_font("bold", 23),
}

# The 4 Viral Scenes
SCENES = [
    {
        "id": 1,
        "step_name": "STEP 1 · THE 3 AM LEAK",
        "headline": "A 3-line retry loop will bankrupt you",
        "prompt": "Deploy AI agent with automated tool retry on AWS Lambda.",
        "voice_script": "It's three A M. A three-line retry loop in your AI agent just ran up an eight-thousand dollar AWS bill while you slept.",
        "duration": 9.5,
        "checks": [
            ("5,000 req/sec recursive retry loop", False),
            ("Single IP caller (192.168.1.10)", False),
            ("CloudWatch billing alert triggered", False),
            ("Unchecked spend exceeds $8,400", False),
        ],
    },
    {
        "id": 2,
        "step_name": "STEP 2 · THE DILEMMA",
        "headline": "Traditional rate limits are dumb",
        "prompt": "Why can't we just set a strict 100 RPS rate limit on API Gateway?",
        "voice_script": "Standard rate limits? They're dumb. Set them too strict, and you drop paying customers. Set them too high, and you go cloud bankrupt.",
        "duration": 10.5,
        "checks": [
            ("Drops 1,000 real flash-sale buyers", False),
            ("Kills $42,000 in checkout revenue", False),
            ("Causes false positive store outages", False),
            ("Still leaks low-rate recursive loops", False),
        ],
    },
    {
        "id": 3,
        "step_name": "STEP 3 · THE BREAKTHROUGH",
        "headline": "Surgically isolate the rogue caller",
        "prompt": "Fuse: analyze caller diversity and isolate runaway IP at WAF edge.",
        "voice_script": "Meet Fuse. It doesn't pull the plug on your whole store. It uses real-time telemetry to isolate the runaway loop at the edge.",
        "duration": 11.5,
        "checks": [
            ("Statistical anomaly Z-score: 4.85", True),
            ("Caller diversity: 0.001 (Dominant loop)", True),
            ("WAF IP block deployed in < 1ms", True),
            ("100% of legitimate buyers breeze through", True),
        ],
    },
    {
        "id": 4,
        "step_name": "STEP 4 · PEACE OF MIND",
        "headline": "Build without the cloud bill anxiety",
        "prompt": "git clone https://github.com/Pranjulchaurasiya/fuse.git",
        "voice_script": "Zero customer downtime. Zero three A M heart attacks. Protect your AWS cloud with Fuse today.",
        "duration": 9.5,
        "checks": [
            ("100% store uptime during severe spikes", True),
            ("$7,900+ saved on a single runaway loop", True),
            ("Built for Bharat Builds Tour 2026", True),
            ("100% Serverless and Open Source", True),
        ],
    },
]

TOTAL_DURATION = sum(s["duration"] for s in SCENES)
TOTAL_FRAMES = int(TOTAL_DURATION * FPS)


# Apple Spring / Damped Harmonic Oscillator Physics
def spring(t, zeta=0.75, omega=16.0):
    """Returns spring progress from 0.0 to 1.0 with subtle overshoot."""
    if t <= 0:
        return 0.0
    if t > 1.2:
        return 1.0
    omega_d = omega * math.sqrt(1.0 - zeta * zeta)
    decay = math.exp(-zeta * omega * t)
    return 1.0 - decay * (math.cos(omega_d * t) + (zeta / math.sqrt(1.0 - zeta * zeta)) * math.sin(omega_d * t))


def ease_out_expo(t):
    if t <= 0:
        return 0.0
    if t >= 1.0:
        return 1.0
    return 1.0 - math.pow(2, -10 * t)


# Vector Shape Drawing Helpers
def draw_rounded_rect(draw, bbox, radius, fill=None, outline=None, width=1):
    draw.rounded_rectangle(bbox, radius=radius, fill=fill, outline=outline, width=width)


def draw_lightning_bolt(draw, cx, cy, size=24, color=COLOR_CYAN):
    half = size // 2
    pts = [
        (cx + int(half * 0.1), cy - half),
        (cx - int(half * 0.7), cy + int(half * 0.1)),
        (cx - int(half * 0.05), cy + int(half * 0.1)),
        (cx - int(half * 0.25), cy + half),
        (cx + int(half * 0.7), cy - int(half * 0.1)),
        (cx + int(half * 0.05), cy - int(half * 0.1)),
    ]
    draw.polygon(pts, fill=color)


def draw_checkmark(draw, cx, cy, radius, is_valid=True, scale=1.0):
    """Draws an Apple-style circular verified checkmark or error badge with spring scale."""
    if scale <= 0.01:
        return
    r = int(radius * scale)
    color_circle = (20, 60, 40) if is_valid else (60, 20, 30)
    color_border = COLOR_GREEN if is_valid else COLOR_RED
    color_icon = COLOR_GREEN if is_valid else COLOR_RED

    draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=color_circle, outline=color_border, width=max(1, int(2 * scale)))

    if is_valid:
        # Checkmark tick lines
        p1 = (cx - int(r * 0.45), cy - int(r * 0.05))
        p2 = (cx - int(r * 0.12), cy + int(r * 0.35))
        p3 = (cx + int(r * 0.45), cy - int(r * 0.35))
        draw.line([p1, p2, p3], fill=color_icon, width=max(2, int(3 * scale)), joint="curve")
    else:
        # X cross lines
        d = int(r * 0.35)
        draw.line([(cx - d, cy - d), (cx + d, cy + d)], fill=color_icon, width=max(2, int(3 * scale)))
        draw.line([(cx + d, cy - d), (cx - d, cy + d)], fill=color_icon, width=max(2, int(3 * scale)))


async def generate_speech_audio():
    """Synthesizes high-fidelity audio tracks using edge-tts."""
    os.makedirs(BUILD_DIR, exist_ok=True)
    voice = "en-US-ChristopherNeural"
    audio_files = []

    print("[*] Generating natural studio voiceover for viral format...")
    for s in SCENES:
        scene_mp3 = os.path.join(BUILD_DIR, f"scene_{s['id']}.mp3")
        text = s["voice_script"]

        if not os.path.exists(scene_mp3) or os.path.getsize(scene_mp3) < 1000:
            import edge_tts
            success = False
            for attempt in range(5):
                try:
                    communicate = edge_tts.Communicate(text, voice)
                    await communicate.save(scene_mp3)
                    if os.path.exists(scene_mp3) and os.path.getsize(scene_mp3) > 1000:
                        success = True
                        print(f"    + Generated audio for Step {s['id']}: {text[:35]}...")
                        break
                except Exception as e:
                    print(f"    ! Retry {attempt + 1}/5 for Step {s['id']}: {e}")
                    await asyncio.sleep(2.0 * (attempt + 1))
            if not success:
                print(f"    ! Fallback to gTTS for Step {s['id']}")
                from gtts import gTTS
                tts = gTTS(text, lang="en", tld="com")
                tts.save(scene_mp3)
        else:
            print(f"    + Reusing existing audio for Step {s['id']}")
        audio_files.append(scene_mp3)

    # Concat all into master voice
    concat_txt = os.path.join(BUILD_DIR, "concat.txt")
    with open(concat_txt, "w", encoding="utf-8") as f:
        for a in audio_files:
            clean = a.replace("\\", "/")
            f.write(f"file '{clean}'\n")

    master_voice = os.path.join(BUILD_DIR, "master_voice.mp3")
    cmd = ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", concat_txt, "-c", "copy", master_voice]
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
    return master_voice


# Background Cyber Mesh
def draw_background(draw, t):
    # Deep midnight gradient
    for y in range(0, HEIGHT, 24):
        ratio = y / HEIGHT
        r = int(COLOR_BG[0] + ratio * 8)
        g = int(COLOR_BG[1] + ratio * 10)
        b = int(COLOR_BG[2] + ratio * 20)
        draw.rectangle([0, y, WIDTH, y + 24], fill=(r, g, b))

    # Ambient radial cyan glow in center
    cx, cy = WIDTH // 2, HEIGHT // 2 - 100
    glow_r = int(450 + math.sin(t * 1.5) * 30)
    for rad in range(glow_r, glow_r - 120, -20):
        alpha_factor = (glow_r - rad) / 120.0
        r_col = int(8 + alpha_factor * 8)
        g_col = int(14 + alpha_factor * 20)
        b_col = int(28 + alpha_factor * 40)
        draw.ellipse([cx - rad, cy - rad, cx + rad, cy + rad], outline=(r_col, g_col, b_col), width=2)

    # Subtle tech dot grid
    for gx in range(60, WIDTH, 60):
        for gy in range(60, HEIGHT, 60):
            draw.point((gx, gy), fill=(24, 34, 54))


# Persistent Header Capsule
def draw_header_capsule(draw, t):
    pill_w, pill_h = 440, 48
    px1 = (WIDTH - pill_w) // 2
    py1 = 45
    draw_rounded_rect(draw, (px1, py1, px1 + pill_w, py1 + pill_h), radius=24, fill=(16, 26, 44), outline=(40, 70, 110), width=1)

    # Glowing Cyan Beacon Dot
    beacon_pulse = (math.sin(t * 8.0) + 1.0) / 2.0
    dot_r = int(5 + beacon_pulse * 2)
    draw.ellipse([px1 + 25 - dot_r, py1 + 24 - dot_r, px1 + 25 + dot_r, py1 + 24 + dot_r], fill=COLOR_CYAN)

    draw.text((px1 + 45, py1 + 24), "PRANJUL CHAURASIYA · FUSE", fill=COLOR_WHITE, font=FONTS["header_pill"], anchor="lm")


# Step Badge
def draw_step_badge(draw, step_name, scene_t):
    badge_w, badge_h = 320, 44
    bx1 = (WIDTH - badge_w) // 2
    by1 = 125

    prog = spring(scene_t - 0.05, zeta=0.7, omega=18.0)
    scale = min(1.0, prog)
    if scale > 0.01:
        draw_rounded_rect(draw, (bx1, by1, bx1 + badge_w, by1 + badge_h), radius=22, fill=(20, 35, 60), outline=COLOR_CYAN, width=1)
        draw.ellipse([bx1 + 22, by1 + 17, bx1 + 32, by1 + 27], fill=COLOR_CYAN)
        draw.text((bx1 + badge_w // 2 + 10, by1 + 22), step_name, fill=COLOR_WHITE, font=FONTS["step_pill"], anchor="mm")


# Giant Headline
def draw_headline(draw, headline, scene_t):
    prog = spring(scene_t - 0.15, zeta=0.8, omega=16.0)
    offset_y = int((1.0 - prog) * 35)
    draw.text((WIDTH // 2, 215 + offset_y), headline, fill=COLOR_WHITE, font=FONTS["headline"], anchor="mt")


# Interactive AI Prompt Input Pill
def draw_prompt_pill(draw, prompt_text, scene_t, t):
    pill_w, pill_h = 960, 110
    px1 = (WIDTH - pill_w) // 2
    py1 = 300

    prog = spring(scene_t - 0.28, zeta=0.75, omega=15.0)
    offset_y = int((1.0 - prog) * 40)
    cur_y = py1 + offset_y

    draw_rounded_rect(draw, (px1, cur_y, px1 + pill_w, cur_y + pill_h), radius=32, fill=(16, 24, 40), outline=(50, 75, 115), width=2)

    # Avatar Circle on Left
    av_cx, av_cy = px1 + 55, cur_y + 55
    draw.ellipse([av_cx - 30, av_cy - 30, av_cx + 30, av_cy + 30], fill=(24, 40, 70), outline=COLOR_CYAN, width=2)
    draw_lightning_bolt(draw, av_cx, av_cy, size=24, color=COLOR_CYAN)

    # Typewriter Animation
    type_start_t = 0.5
    typing_speed = 36.0  # chars per second
    elapsed_typing = max(0.0, scene_t - type_start_t)
    char_count = min(len(prompt_text), int(elapsed_typing * typing_speed))
    visible_text = prompt_text[:char_count]

    # Blinking Cursor |
    cursor_blink = (int(scene_t * 5.0) % 2) == 0
    cursor_str = "|" if cursor_blink else ""

    draw.text((px1 + 105, cur_y + 55), visible_text + cursor_str, fill=COLOR_WHITE, font=FONTS["prompt"], anchor="lm")

    # Send Button (↑) on Right with Spring Pop when typing finishes
    btn_cx, btn_cy = px1 + pill_w - 55, cur_y + 55
    btn_r = 28
    typing_done = char_count >= len(prompt_text)
    btn_scale = spring(scene_t - (type_start_t + len(prompt_text) / typing_speed), zeta=0.6, omega=20.0) if typing_done else 1.0

    btn_color = COLOR_CYAN if typing_done else COLOR_BLUE
    cur_r = int(btn_r * min(1.15, max(0.9, btn_scale)))
    draw.ellipse([btn_cx - cur_r, btn_cy - cur_r, btn_cx + cur_r, btn_cy + cur_r], fill=btn_color)
    # Up arrow icon
    draw.line([(btn_cx, btn_cy - 12), (btn_cx, btn_cy + 12)], fill=(10, 15, 25), width=3)
    draw.line([(btn_cx - 8, btn_cy - 4), (btn_cx, btn_cy - 12), (btn_cx + 8, btn_cy - 4)], fill=(10, 15, 25), width=3)


# Segmented Story Progress Bar at Bottom
def draw_segmented_progress_bar(draw, active_scene_idx, scene_t, scene_duration):
    num_scenes = len(SCENES)
    total_w = 960
    gap = 20
    seg_w = (total_w - (num_scenes - 1) * gap) // num_scenes
    start_x = (WIDTH - total_w) // 2
    bar_y = 1275
    bar_h = 8

    scene_progress = min(1.0, max(0.0, scene_t / scene_duration))

    for i in range(num_scenes):
        sx = start_x + i * (seg_w + gap)
        # Background bar
        draw_rounded_rect(draw, (sx, bar_y, sx + seg_w, bar_y + bar_h), radius=4, fill=(35, 45, 65))

        if i < active_scene_idx:
            # Fully completed
            draw_rounded_rect(draw, (sx, bar_y, sx + seg_w, bar_y + bar_h), radius=4, fill=COLOR_CYAN)
        elif i == active_scene_idx:
            # Active filling bar
            fill_w = int(seg_w * scene_progress)
            if fill_w > 0:
                draw_rounded_rect(draw, (sx, bar_y, sx + fill_w, bar_y + bar_h), radius=4, fill=COLOR_CYAN)


# Component Card Inside Details
def render_card_scene_1(draw, card_x, card_y, card_w, card_h, scene_t, t):
    """Scene 1: 3:14 AM Nightmare & Spending Ticker."""
    # Top visual zone (0 to 320)
    draw_rounded_rect(draw, (card_x + 40, card_y + 35, card_x + card_w - 40, card_y + 130), radius=16, fill=(24, 20, 32), outline=COLOR_RED, width=2)
    # AWS Badge
    draw_rounded_rect(draw, (card_x + 60, card_y + 50, card_x + 115, card_y + 105), radius=12, fill=(255, 153, 0))
    draw.text((card_x + 87, card_y + 77), "AWS", fill=(0, 0, 0), font=FONTS["body_bold"], anchor="mm")
    draw.text((card_x + 135, card_y + 65), "CloudWatch Billing Alert • 03:14 AM", fill=COLOR_WHITE, font=FONTS["body_bold"])
    draw.text((card_x + 135, card_y + 95), "CRITICAL: Account budget ($500.00) breached", fill=COLOR_RED, font=FONTS["mono_sm"])

    # Exponential Ticker
    exp_factor = min(1.0, (scene_t / 7.0) ** 2.0)
    current_val = 120.0 + exp_factor * 8332.18
    draw.text((card_x + card_w // 2, card_y + 175), f"${current_val:,.2f}", fill=COLOR_RED, font=load_font("bold", 54), anchor="mm")
    draw.text((card_x + card_w // 2, card_y + 220), "UNCHECKED RECURSIVE INVOCATIONS", fill=COLOR_MUTED, font=FONTS["mono_sm"], anchor="mm")

    # The 3-line bug
    draw_rounded_rect(draw, (card_x + 40, card_y + 245, card_x + card_w - 40, card_y + 335), radius=12, fill=(12, 16, 26), outline=(45, 55, 75), width=1)
    draw.text((card_x + 65, card_y + 265), "while not response.ok:  # Missing backoff!", fill=(255, 120, 120), font=FONTS["mono"])
    draw.text((card_x + 65, card_y + 295), "    client.invoke(payload)  # Spinning 5,000x/s", fill=(255, 200, 100), font=FONTS["mono"])


def render_card_scene_2(draw, card_x, card_y, card_w, card_h, scene_t, t):
    """Scene 2: Split-screen dilemma (False Positive Outage)."""
    # Split boxes
    box_w = (card_w - 110) // 2
    bx_left = card_x + 40
    bx_right = bx_left + box_w + 30
    by = card_y + 35
    bh = 300

    # Left: Strict Rate Limit
    draw_rounded_rect(draw, (bx_left, by, bx_left + box_w, by + bh), radius=16, fill=(28, 18, 26), outline=COLOR_RED, width=2)
    draw.text((bx_left + box_w // 2, by + 30), "STRICT 100 RPS LIMIT", fill=COLOR_RED, font=FONTS["card_title"], anchor="mm")
    draw.text((bx_left + box_w // 2, by + 65), "Scenario: Marketing Flash Sale", fill=COLOR_MUTED, font=FONTS["mono_sm"], anchor="mm")

    carts = [
        ("Buyer #104", "$140 Checkout", "DROPPED (429)"),
        ("Buyer #892", "$320 Enterprise", "DROPPED (429)"),
        ("Stripe Webhook", "Payment Verify", "DROPPED (429)"),
    ]
    for idx, (bname, bval, bstat) in enumerate(carts):
        cy_item = by + 95 + idx * 55
        draw_rounded_rect(draw, (bx_left + 15, cy_item, bx_left + box_w - 15, cy_item + 45), radius=8, fill=(20, 14, 22))
        draw.text((bx_left + 25, cy_item + 22), bname, fill=COLOR_WHITE, font=FONTS["mono_sm"], anchor="lm")
        draw.text((bx_left + box_w - 25, cy_item + 22), bstat, fill=COLOR_RED, font=FONTS["mono_sm"], anchor="rm")

    draw.text((bx_left + box_w // 2, by + bh - 25), "FALSE POSITIVE OUTAGE", fill=COLOR_RED, font=FONTS["body_bold"], anchor="mm")

    # Right: High Threshold (No protection)
    draw_rounded_rect(draw, (bx_right, by, bx_right + box_w, by + bh), radius=16, fill=(28, 24, 16), outline=COLOR_AMBER, width=2)
    draw.text((bx_right + box_w // 2, by + 30), "HIGH THRESHOLD", fill=COLOR_AMBER, font=FONTS["card_title"], anchor="mm")
    draw.text((bx_right + box_w // 2, by + 65), "Scenario: Stuck Client Loop", fill=COLOR_MUTED, font=FONTS["mono_sm"], anchor="mm")

    draw_rounded_rect(draw, (bx_right + 20, by + 95, bx_right + box_w - 20, by + 215), radius=10, fill=(16, 14, 12))
    draw.text((bx_right + 35, by + 120), "for retry in range(999999):", fill=(255, 120, 120), font=FONTS["mono_sm"])
    draw.text((bx_right + 35, by + 150), "    call_api() # 40 req/s", fill=(255, 200, 100), font=FONTS["mono_sm"])
    draw.text((bx_right + 35, by + 180), "    # 14 hours unchecked", fill=COLOR_MUTED, font=FONTS["mono_sm"])

    draw.text((bx_right + box_w // 2, by + bh - 25), "SURPRISE $5,000+ BILL", fill=COLOR_AMBER, font=FONTS["body_bold"], anchor="mm")


def render_card_scene_3(draw, card_x, card_y, card_w, card_h, scene_t, t):
    """Scene 3: Live Surgical WAF Isolation Canvas."""
    # Top visual: Gateway with routing
    cy_mid = card_y + 175
    # Left: Rogue vs Legit Callers
    draw_rounded_rect(draw, (card_x + 40, card_y + 35, card_x + 360, card_y + 140), radius=14, fill=(16, 24, 36), outline=(40, 60, 90), width=1)
    draw.ellipse([card_x + 60, card_y + 65, card_x + 75, card_y + 80], fill=COLOR_GREEN)
    draw.text((card_x + 90, card_y + 65), "Organic Buyers (49.36.12.8)", fill=COLOR_WHITE, font=FONTS["mono_sm"], anchor="lm")
    draw.ellipse([card_x + 60, card_y + 105, card_x + 75, card_y + 120], fill=COLOR_GREEN)
    draw.text((card_x + 90, card_y + 105), "Stripe Webhooks (54.187.20.1)", fill=COLOR_WHITE, font=FONTS["mono_sm"], anchor="lm")

    # Rogue Loop
    draw_rounded_rect(draw, (card_x + 40, card_y + 160, card_x + 360, card_y + 265), radius=14, fill=(35, 18, 25), outline=COLOR_RED, width=2)
    draw.ellipse([card_x + 60, card_y + 195, card_x + 75, card_y + 210], fill=COLOR_RED)
    draw.text((card_x + 90, card_y + 195), "ROGUE RETRY LOOP (Single IP)", fill=COLOR_RED, font=FONTS["mono_sm"], anchor="lm")
    draw.text((card_x + 90, card_y + 230), "IP: 192.168.1.10 (850 req/m)", fill=COLOR_AMBER, font=FONTS["mono_sm"], anchor="lm")

    # Center: Fuse Shield Target
    fuse_cx = card_x + card_w // 2 + 30
    draw_rounded_rect(draw, (fuse_cx - 90, card_y + 80, fuse_cx + 90, card_y + 225), radius=16, fill=(14, 28, 48), outline=COLOR_CYAN, width=2)
    draw.text((fuse_cx, card_y + 115), "FUSE WAF", fill=COLOR_CYAN, font=FONTS["body_bold"], anchor="mm")
    draw.text((fuse_cx, card_y + 145), "Z-Score: 4.85", fill=COLOR_RED, font=FONTS["mono_sm"], anchor="mm")
    draw.text((fuse_cx, card_y + 175), "Quarantine: ON", fill=COLOR_GREEN, font=FONTS["mono_sm"], anchor="mm")

    # Laser targeting rogue loop
    laser_pulse = (math.sin(t * 12.0) + 1.0) / 2.0
    draw.line([(fuse_cx - 90, card_y + 180), (card_x + 360, card_y + 210)], fill=COLOR_CYAN, width=int(2 + laser_pulse * 3))

    # Right: Protected API Gateway
    gw_x = card_x + card_w - 360
    draw_rounded_rect(draw, (gw_x, card_y + 35, card_x + card_w - 40, card_y + 265), radius=16, fill=(16, 32, 28), outline=COLOR_GREEN, width=2)
    draw.text((gw_x + 160, card_y + 70), "API GATEWAY", fill=COLOR_GREEN, font=FONTS["body_bold"], anchor="mm")
    draw.text((gw_x + 160, card_y + 105), "100% OPERATIONAL", fill=COLOR_GREEN, font=FONTS["mono_sm"], anchor="mm")

    for i in range(2):
        oy = card_y + 145 + i * 50
        draw_rounded_rect(draw, (gw_x + 20, oy, gw_x + 300, oy + 40), radius=8, fill=(22, 44, 38))
        draw.text((gw_x + 35, oy + 20), f"Order #{10280 + i}", fill=COLOR_WHITE, font=FONTS["mono_sm"], anchor="lm")
        draw.text((gw_x + 285, oy + 20), "200 OK", fill=COLOR_GREEN, font=FONTS["mono_sm"], anchor="rm")


def render_card_scene_4(draw, card_x, card_y, card_w, card_h, scene_t, t):
    """Scene 4: Peace of Mind Bento Stats & GitHub CTA."""
    # Bento stats
    bento_w = (card_w - 100) // 2
    b1_x = card_x + 40
    b2_x = b1_x + bento_w + 20
    by = card_y + 35
    bh = 135

    draw_rounded_rect(draw, (b1_x, by, b1_x + bento_w, by + bh), radius=14, fill=(16, 30, 24), outline=COLOR_GREEN, width=2)
    draw.text((b1_x + bento_w // 2, by + 45), "100% UPTIME", fill=COLOR_GREEN, font=FONTS["card_title"], anchor="mm")
    draw.text((b1_x + bento_w // 2, by + 85), "Zero Customer Disruption", fill=COLOR_WHITE, font=FONTS["mono_sm"], anchor="mm")

    draw_rounded_rect(draw, (b2_x, by, b2_x + bento_w, by + bh), radius=14, fill=(20, 28, 48), outline=COLOR_CYAN, width=2)
    draw.text((b2_x + bento_w // 2, by + 45), "$7,900+ SAVED", fill=COLOR_CYAN, font=FONTS["card_title"], anchor="mm")
    draw.text((b2_x + bento_w // 2, by + 85), "Zero 3 AM Outage Surprises", fill=COLOR_WHITE, font=FONTS["mono_sm"], anchor="mm")

    # CTA Button
    btn_y = card_y + 195
    draw_rounded_rect(draw, (card_x + 40, btn_y, card_x + card_w - 40, btn_y + 80), radius=20, fill=COLOR_CYAN, outline=COLOR_WHITE, width=2)
    draw.text((card_x + card_w // 2, btn_y + 40), "GET STARTED ON GITHUB — OPEN SOURCE", fill=(5, 10, 20), font=FONTS["card_title"], anchor="mm")


# Interactive Preview Card with Spring Physics and 4 Checkmark Pops
def draw_preview_card(draw, scene, scene_t, t):
    card_w, card_h = 960, 780
    card_x = (WIDTH - card_w) // 2
    card_y = 440

    # Spring slide-up entrance
    card_prog = spring(scene_t - 0.35, zeta=0.8, omega=14.0)
    offset_y = int((1.0 - card_prog) * 60)
    cur_y = card_y + offset_y

    # Outer Glassmorphic Card Container
    draw_rounded_rect(draw, (card_x, cur_y, card_x + card_w, cur_y + card_h), radius=32, fill=COLOR_CARD, outline=COLOR_CARD_BORDER, width=2)

    # 1. Render Top Visualization Content depending on Scene
    sid = scene["id"]
    if sid == 1:
        render_card_scene_1(draw, card_x, cur_y, card_w, card_h, scene_t, t)
    elif sid == 2:
        render_card_scene_2(draw, card_x, cur_y, card_w, card_h, scene_t, t)
    elif sid == 3:
        render_card_scene_3(draw, card_x, cur_y, card_w, card_h, scene_t, t)
    elif sid == 4:
        render_card_scene_4(draw, card_x, cur_y, card_w, card_h, scene_t, t)

    # 2. Render 4 Staggered Verified Checkmarks at the bottom of the card
    checks = scene["checks"]
    check_start_y = cur_y + 390
    check_spacing = 85

    for idx, (label, is_valid) in enumerate(checks):
        cy_row = check_start_y + idx * check_spacing
        draw_rounded_rect(draw, (card_x + 40, cy_row, card_x + card_w - 40, cy_row + 70), radius=14, fill=(20, 28, 46), outline=(40, 55, 80), width=1)

        # Staggered pop-in timing (+0.2s per checkmark after prompt finishes)
        check_t = scene_t - (1.6 + idx * 0.22)
        scale_check = spring(check_t, zeta=0.65, omega=22.0)

        chk_cx = card_x + 85
        chk_cy = cy_row + 35
        draw_checkmark(draw, chk_cx, chk_cy, radius=20, is_valid=is_valid, scale=min(1.0, max(0.0, scale_check)))

        # Label opacity / entrance
        if scale_check > 0.05:
            text_color = COLOR_WHITE if is_valid else (255, 180, 180)
            draw.text((card_x + 130, cy_row + 35), label, fill=text_color, font=FONTS["check_label"], anchor="lm")


def render_all_frames():
    frames_dir = os.path.join(BUILD_DIR, "frames")
    if os.path.exists(frames_dir):
        shutil.rmtree(frames_dir)
    os.makedirs(frames_dir, exist_ok=True)

    print(f"[*] Rendering {TOTAL_FRAMES} frames ({TOTAL_DURATION:.1f}s @ {FPS} FPS)...")

    # Precalculate scene start times
    scene_starts = []
    accum = 0.0
    for s in SCENES:
        scene_starts.append(accum)
        accum += s["duration"]

    t0 = time.time()
    for frame_idx in range(TOTAL_FRAMES):
        t = frame_idx / FPS

        # Determine active scene
        scene_idx = 0
        for i, st in enumerate(scene_starts):
            if t >= st:
                scene_idx = i

        cur_scene = SCENES[scene_idx]
        scene_t = t - scene_starts[scene_idx]

        # Canvas
        img = Image.new("RGB", (WIDTH, HEIGHT), COLOR_BG)
        draw = ImageDraw.Draw(img)

        # 1. Background Grid & Radial Glow
        draw_background(draw, t)

        # 2. Persistent Top Header Capsule
        draw_header_capsule(draw, t)

        # 3. Step Badge
        draw_step_badge(draw, cur_scene["step_name"], scene_t)

        # 4. Big Bold Headline
        draw_headline(draw, cur_scene["headline"], scene_t)

        # 5. Interactive AI Input Pill
        draw_prompt_pill(draw, cur_scene["prompt"], scene_t, t)

        # 6. Interactive Component Card with Checkmarks
        draw_preview_card(draw, cur_scene, scene_t, t)

        # 7. Segmented Story Progress Bar
        draw_segmented_progress_bar(draw, scene_idx, scene_t, cur_scene["duration"])

        # Save Frame
        frame_path = os.path.join(frames_dir, f"frame_{frame_idx:05d}.jpg")
        img.save(frame_path, "JPEG", quality=94)

        if (frame_idx + 1) % 150 == 0 or frame_idx == TOTAL_FRAMES - 1:
            elapsed = time.time() - t0
            fps_val = (frame_idx + 1) / max(0.01, elapsed)
            print(f"    + Rendered {frame_idx + 1}/{TOTAL_FRAMES} frames ({fps_val:.1f} fps)")

    print(f"[+] All {TOTAL_FRAMES} frames rendered in {time.time() - t0:.1f}s.")
    return frames_dir


def compile_final_video(frames_dir, master_audio_path):
    print("[*] Compiling final viral 4:5 MP4 video with FFmpeg...")

    # Generate lo-fi cyberpunk ambient synth audio bed
    ambient_wav = os.path.join(BUILD_DIR, "ambient.wav")
    cmd_synth = [
        "ffmpeg", "-y",
        "-f", "lavfi",
        "-i", f"anoisesrc=c=pink:r=44100:a=0.015,lowpass=f=280[pink]; sine=f=80:r=44100:d={TOTAL_DURATION}[sub]; [pink][sub]amix=inputs=2:duration=first",
        "-t", str(TOTAL_DURATION),
        ambient_wav
    ]
    subprocess.run(cmd_synth, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    # Mixed Audio: voice (volume 1.25) + ambient synth (volume 0.15)
    mixed_audio = os.path.join(BUILD_DIR, "master_mix.mp3")
    cmd_mix = [
        "ffmpeg", "-y",
        "-i", master_audio_path,
        "-i", ambient_wav,
        "-filter_complex", "[0:a]volume=1.25[v]; [1:a]volume=0.18[a]; [v][a]amix=inputs=2:duration=first:dropout_transition=2",
        mixed_audio
    ]
    subprocess.run(cmd_mix, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    # Master Video Assembly
    cmd_render = [
        "ffmpeg", "-y",
        "-framerate", str(FPS),
        "-i", os.path.join(frames_dir, "frame_%05d.jpg"),
        "-i", mixed_audio,
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "18",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        "-b:a", "192k",
        "-shortest",
        OUTPUT_VIDEO
    ]
    subprocess.run(cmd_render, check=True)
    print(f"\n[SUCCESS] Viral 4:5 Commercial Created: {OUTPUT_VIDEO}")


async def main():
    print("=" * 65)
    print("BUILDING VIRAL 4:5 MOTION GRAPHICS VIDEO (CHARLIE HILLS STYLE)")
    print("=" * 65)
    master_audio = await generate_speech_audio()
    frames_dir = render_all_frames()
    compile_final_video(frames_dir, master_audio)


if __name__ == "__main__":
    asyncio.run(main())
