#!/usr/bin/env python3
"""build_product_ad.py — High-octane, animated 35-second product commercial for Fuse.

Generates:
1. Studio-grade neural voiceover for 4 punchy scenes (edge-tts).
2. Dynamic 1080p 30fps motion graphics rendered frame-by-frame with Pillow:
   - Scene 1: The 3:14 AM Nightmare (flipping clock, AWS notification, accelerating dollar meter)
   - Scene 2: The Dilemma (Split-screen: Static rate limit killing customers vs runaway loop)
   - Scene 3: Enter Fuse (Surgical laser isolating the bad caller while real buyers flow smoothly)
   - Scene 4: Peace of Mind & CTA (Live KPI bento cards, glowing Fuse logo, GitHub repo)
3. Synchronized kinetic captions.
4. Synth audio bed mixed under voiceover for broadcast commercial quality.
5. Final output: Fuse_Product_Commercial_1080p.mp4
"""

import os
import sys
import math
import json
import time
import shutil
import subprocess
from PIL import Image, ImageDraw, ImageFont

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BUILD_DIR = os.path.join(REPO_ROOT, "scratch_ad_build")
OUTPUT_VIDEO = os.path.join(REPO_ROOT, "Fuse_Product_Commercial_1080p.mp4")

WIDTH = 1920
HEIGHT = 1080
FPS = 30

# Color Palette (Dark Cyberpunk / Premium SaaS)
COLOR_BG_DARK = (7, 9, 15)
COLOR_BG_CARD = (15, 20, 32)
COLOR_BORDER = (35, 45, 65)
COLOR_CYAN = (0, 240, 255)
COLOR_CYAN_GLOW = (0, 150, 200)
COLOR_AMBER = (255, 184, 0)
COLOR_RED = (255, 42, 85)
COLOR_GREEN = (0, 229, 153)
COLOR_WHITE = (255, 255, 255)
COLOR_MUTED = (142, 154, 168)
COLOR_GOLD = (255, 215, 0)

# Fonts
def get_font(name="segoeuib.ttf", size=32):
    font_path = os.path.join("C:\\Windows\\Fonts", name)
    if os.path.exists(font_path):
        try:
            return ImageFont.truetype(font_path, size)
        except Exception:
            pass
    return ImageFont.load_default()

FONT_TITLE_XL = get_font("segoeuib.ttf", 68)
FONT_TITLE_L = get_font("segoeuib.ttf", 48)
FONT_TITLE_M = get_font("segoeuib.ttf", 36)
FONT_BODY = get_font("segoeui.ttf", 26)
FONT_BODY_B = get_font("segoeuib.ttf", 26)
FONT_MONO = get_font("consola.ttf", 24)
FONT_MONO_S = get_font("consola.ttf", 18)
FONT_MONO_L = get_font("consolab.ttf", 52)
FONT_SUBTITLE = get_font("segoeuib.ttf", 26)
FONT_COUNTER = get_font("consolab.ttf", 96)

def draw_lightning_bolt(draw, cx, cy, size=28, color=COLOR_CYAN):
    """Draws a crisp geometric lightning bolt."""
    pts = [
        (cx - size * 0.25, cy - size),
        (cx + size * 0.6, cy - size * 0.08),
        (cx + size * 0.05, cy - size * 0.08),
        (cx + size * 0.25, cy + size),
        (cx - size * 0.6, cy + size * 0.08),
        (cx - size * 0.05, cy + size * 0.08),
    ]
    draw.polygon(pts, fill=color)

# Scenes definition (Timed to natural 1.0x neural speech pace, total = 45.5s)
SCENES = [
    {
        "id": "scene1",
        "title": "SCENE 1: THE NIGHTMARE",
        "text": "It is three A M. A three-line retry loop in your AI agent just ran up an eight-thousand-dollar AWS bill while you slept.",
        "duration": 9.5,
    },
    {
        "id": "scene2",
        "title": "SCENE 2: THE DILEMMA",
        "text": "Standard rate limits? They are dumb. Set them too strict, and you kill paying customers. Set them too high... and you go cloud bankrupt.",
        "duration": 11.5,
    },
    {
        "id": "scene3",
        "title": "SCENE 3: ENTER FUSE",
        "text": "Meet Fuse: the cognitive circuit breaker for AWS. Fuse does not pull the plug on your whole store. It uses real-time telemetry to surgically isolate the runaway loop at the edge.",
        "duration": 13.0,
    },
    {
        "id": "scene4",
        "title": "SCENE 4: PEACE OF MIND",
        "text": "Zero customer downtime. Zero three A M heart attacks. Build without the cloud bill anxiety. Protect your cloud with Fuse today.",
        "duration": 11.5,
    },
]

TOTAL_DURATION = sum(s["duration"] for s in SCENES)  # 45.5s
TOTAL_FRAMES = int(TOTAL_DURATION * FPS)


def ensure_audio():
    """Generates studio neural audio for each scene using edge-tts."""
    os.makedirs(BUILD_DIR, exist_ok=True)
    audio_files = []

    print("[*] Generating natural studio voiceover...")
    for s in SCENES:
        out_mp3 = os.path.join(BUILD_DIR, f"{s['id']}.mp3")
        if not os.path.exists(out_mp3) or os.path.getsize(out_mp3) < 1000:
            synthesized = False
            # 1. Try edge-tts first
            try:
                cmd = [
                    sys.executable, "-m", "edge_tts",
                    "--text", s["text"],
                    "--write-media", out_mp3,
                    "--voice", "en-US-ChristopherNeural",
                    "--rate=+3%",
                ]
                subprocess.run(cmd, check=True, capture_output=True)
                synthesized = True
                print(f"    + Synthesized {s['id']}.mp3 (edge-tts)")
            except Exception as e:
                pass

            # 2. Fallback to gTTS if edge-tts connection reset
            if not synthesized:
                try:
                    from gtts import gTTS
                    tts = gTTS(text=s["text"], lang="en", tld="com")
                    tts.save(out_mp3)
                    synthesized = True
                    print(f"    + Synthesized {s['id']}.mp3 (gTTS natural)")
                except Exception as g_err:
                    print(f"    [!] gTTS failed: {g_err}")

            if not synthesized:
                raise RuntimeError(f"Could not synthesize audio for {s['id']}")
        audio_files.append(out_mp3)

    # Concatenate all scene audios into master voiceover with crossfade/gaps
    concat_list_path = os.path.join(BUILD_DIR, "audio_concat.txt")
    with open(concat_list_path, "w", encoding="utf-8") as f:
        for a in audio_files:
            # Escape path for ffmpeg concat
            clean_path = a.replace("\\", "/")
            f.write(f"file '{clean_path}'\n")

    master_audio_path = os.path.join(BUILD_DIR, "master_voice.mp3")
    cmd = [
        "ffmpeg", "-y", "-f", "concat", "-safe", "0",
        "-i", concat_list_path,
        "-c", "copy",
        master_audio_path
    ]
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
    print(f"[+] Master voiceover assembled: {master_audio_path}")
    return master_audio_path


def draw_rounded_rect(draw, bbox, radius, fill=None, outline=None, width=1):
    """Draws a smooth rounded rectangle."""
    x1, y1, x2, y2 = bbox
    draw.rounded_rectangle([x1, y1, x2, y2], radius=radius, fill=fill, outline=outline, width=width)


def draw_gradient_background(draw, t):
    """Draws a subtle pulsing dark cyber background."""
    # Radial dark blue pulse in center
    pulse = math.sin(t * 1.5) * 15
    for y in range(0, HEIGHT, 16):
        ratio = y / HEIGHT
        r = int(COLOR_BG_DARK[0] + ratio * 8)
        g = int(COLOR_BG_DARK[1] + ratio * 10 + pulse * 0.1)
        b = int(COLOR_BG_DARK[2] + ratio * 18 + pulse * 0.2)
        draw.rectangle([0, y, WIDTH, y + 16], fill=(max(0, min(255, r)), max(0, min(255, g)), max(0, min(255, b))))

    # Draw subtle high-tech grid dots
    grid_spacing = 80
    for gx in range(40, WIDTH, grid_spacing):
        for gy in range(40, HEIGHT, grid_spacing):
            draw.point((gx, gy), fill=(25, 35, 55))


def render_scene_1(draw, t, scene_t):
    """Scene 1: The 3:14 AM Nightmare."""
    # 1. Background radial warning glow
    pulse = (math.sin(scene_t * 6.0) + 1.0) / 2.0  # 0 to 1
    glow_alpha = int(pulse * 40)
    
    # Header tag
    draw.text((WIDTH // 2, 70), "ALERT: RUNAWAY AGENT BILLING SPIKE", fill=COLOR_RED, font=FONT_TITLE_M, anchor="mt")

    # Digital Clock: 03:14 AM
    clock_y = 140
    clock_text = "03:14:28 AM"
    draw.text((WIDTH // 2, clock_y), clock_text, fill=(180, 190, 210), font=FONT_TITLE_L, anchor="mt")

    # AWS Push Notification Card (Slides in smoothly)
    card_w, card_h = 820, 150
    card_x = (WIDTH - card_w) // 2
    slide_progress = min(1.0, scene_t * 2.5)  # 0 to 1
    card_y = int(-150 + slide_progress * 380)

    # Card background (glassmorphic dark slate with red edge)
    draw_rounded_rect(draw, (card_x, card_y, card_x + card_w, card_y + card_h), radius=16, fill=(20, 24, 38), outline=COLOR_RED, width=2)
    # App icon badge
    draw_rounded_rect(draw, (card_x + 25, card_y + 30, card_x + 80, card_y + 85), radius=12, fill=(255, 153, 0))
    draw.text((card_x + 52, card_y + 57), "AWS", fill=(0, 0, 0), font=FONT_BODY_B, anchor="mm")

    # Notification text
    draw.text((card_x + 100, card_y + 28), "Amazon CloudWatch Billing Alert • now", fill=(220, 225, 235), font=FONT_BODY_B)
    draw.text((card_x + 100, card_y + 68), "CRITICAL: Monthly spend threshold ($500.00) exceeded.", fill=(255, 100, 120), font=FONT_BODY)
    draw.text((card_x + 100, card_y + 104), "Account: 515903395012 • Estimated Total: $8,452.18", fill=COLOR_MUTED, font=FONT_MONO_S)

    # Giant Accelerating Dollar Counter
    counter_y = 480
    draw_rounded_rect(draw, (WIDTH // 2 - 420, counter_y, WIDTH // 2 + 420, counter_y + 200), radius=24, fill=(16, 20, 32), outline=(50, 60, 85), width=2)

    draw.text((WIDTH // 2, counter_y + 35), "UNCHECKED CLOUD SPEND", fill=COLOR_MUTED, font=FONT_MONO_S, anchor="mt")

    # Compute accelerating dollar amount
    # From $120 to $8,452 exponentially
    exp_factor = min(1.0, (scene_t / 7.0) ** 1.8)
    current_amount = 120.0 + exp_factor * 8332.0
    amount_str = f"${current_amount:,.2f}"

    # Glow effect
    color_counter = COLOR_RED if current_amount > 2000 else COLOR_AMBER
    draw.text((WIDTH // 2, counter_y + 115), amount_str, fill=color_counter, font=FONT_COUNTER, anchor="mm")

    # Radar wave rings
    if pulse > 0.1:
        ring_radius = int(220 + pulse * 70)
        draw.ellipse([WIDTH // 2 - ring_radius, counter_y + 100 - ring_radius // 2, WIDTH // 2 + ring_radius, counter_y + 100 + ring_radius // 2], outline=(255, 50, 80), width=int(pulse * 3))

    # Code snippet cue
    snippet_box_y = 730
    draw_rounded_rect(draw, (WIDTH // 2 - 380, snippet_box_y, WIDTH // 2 + 380, snippet_box_y + 110), radius=12, fill=(12, 15, 24), outline=(40, 50, 70), width=1)
    draw.text((WIDTH // 2 - 350, snippet_box_y + 20), "# The 3-line bug: missing retry backoff", fill=(100, 115, 135), font=FONT_MONO_S)
    draw.text((WIDTH // 2 - 350, snippet_box_y + 45), "while not response.ok:", fill=(255, 120, 140), font=FONT_MONO)
    draw.text((WIDTH // 2 - 350, snippet_box_y + 75), "    response = client.invoke(payload)  # Spinning 5,000x/sec", fill=(255, 200, 100), font=FONT_MONO)


def render_scene_2(draw, t, scene_t):
    """Scene 2: The Impossible Dilemma (Split-screen)."""
    # Header
    draw.text((WIDTH // 2, 70), "THE DILEMMA: TRADITIONAL RATE LIMITS ARE DUMB", fill=COLOR_WHITE, font=FONT_TITLE_M, anchor="mt")

    card_w, card_h = 820, 680
    y_card = 160

    # LEFT CARD: Static Rate Limit (Kills Customers)
    x_left = 100
    draw_rounded_rect(draw, (x_left, y_card, x_left + card_w, y_card + card_h), radius=20, fill=COLOR_BG_CARD, outline=(60, 30, 40), width=2)
    
    # Left Header
    draw_rounded_rect(draw, (x_left + 30, y_card + 30, x_left + card_w - 30, y_card + 90), radius=10, fill=(35, 15, 22))
    draw.text((x_left + card_w // 2, y_card + 60), "STATIC WAF RATE LIMIT (e.g. 100 rps)", fill=(255, 90, 120), font=FONT_TITLE_M, anchor="mm")

    draw.text((x_left + 50, y_card + 120), "Scenario: Marketing Flash Sale (1,000 Real Buyers)", fill=COLOR_MUTED, font=FONT_BODY)

    # 4 Cart Rows
    carts = [
        ("Customer #104", "$140 Checkout", "DROPPED (429)"),
        ("Customer #892", "$320 Enterprise", "DROPPED (429)"),
        ("Stripe Webhook", "Payment Verify", "DROPPED (429)"),
        ("Customer #311", "$85 Order", "DROPPED (429)"),
    ]
    for i, (buyer, item, status) in enumerate(carts):
        row_y = y_card + 180 + i * 85
        draw_rounded_rect(draw, (x_left + 50, row_y, x_left + card_w - 50, row_y + 70), radius=12, fill=(24, 18, 28), outline=(60, 30, 45), width=1)
        draw.text((x_left + 75, row_y + 35), buyer, fill=COLOR_WHITE, font=FONT_BODY_B, anchor="lm")
        draw.text((x_left + 300, row_y + 35), item, fill=COLOR_MUTED, font=FONT_BODY, anchor="lm")
        draw.text((x_left + card_w - 75, row_y + 35), status, fill=COLOR_RED, font=FONT_BODY_B, anchor="rm")

    # Big Red Stamped Watermark
    stamp_prog = min(1.0, max(0.0, (scene_t - 2.0) * 4.0))
    if stamp_prog > 0:
        draw_rounded_rect(draw, (x_left + 140, y_card + 540, x_left + card_w - 140, y_card + 630), radius=16, fill=(80, 10, 25), outline=COLOR_RED, width=3)
        draw.text((x_left + card_w // 2, y_card + 585), "FALSE POSITIVE OUTAGE", fill=COLOR_RED, font=FONT_TITLE_M, anchor="mm")

    # RIGHT CARD: Unchecked Runaway Loop
    x_right = WIDTH - card_w - 100
    draw_rounded_rect(draw, (x_right, y_card, x_right + card_w, y_card + card_h), radius=20, fill=COLOR_BG_CARD, outline=(60, 50, 20), width=2)

    # Right Header
    draw_rounded_rect(draw, (x_right + 30, y_card + 30, x_right + card_w - 30, y_card + 90), radius=10, fill=(35, 30, 15))
    draw.text((x_right + card_w // 2, y_card + 60), "HIGH THRESHOLD (No Protection)", fill=COLOR_AMBER, font=FONT_TITLE_M, anchor="mm")

    draw.text((x_right + 50, y_card + 120), "Scenario: Stuck Client Loop (1 Single IP Caller)", fill=COLOR_MUTED, font=FONT_BODY)

    # Code Box inside Right Card
    code_box_y = y_card + 175
    draw_rounded_rect(draw, (x_right + 50, code_box_y, x_right + card_w - 50, code_box_y + 260), radius=12, fill=(10, 14, 22), outline=(40, 50, 70), width=1)
    draw.text((x_right + 75, code_box_y + 30), "# Recursive Agent Without Backoff", fill=(90, 110, 130), font=FONT_MONO_S)
    draw.text((x_right + 75, code_box_y + 65), "for retry in range(999999):", fill=(255, 120, 120), font=FONT_MONO)
    draw.text((x_right + 75, code_box_y + 105), "    try_execute_tool(context)", fill=(255, 200, 100), font=FONT_MONO)
    draw.text((x_right + 75, code_box_y + 145), "    # 40 requests/sec for 14 hours", fill=(120, 140, 160), font=FONT_MONO_S)
    draw.text((x_right + 75, code_box_y + 185), "    # Costs $250/hour unchecked", fill=(255, 80, 80), font=FONT_MONO_S)

    rot_cx = x_right + card_w // 2
    rot_cy = y_card + 540
    draw.text((rot_cx, rot_cy), "SPENDING DISASTER OVER THE WEEKEND", fill=COLOR_AMBER, font=FONT_BODY_B, anchor="mm")
    draw_rounded_rect(draw, (x_right + 140, y_card + 575, x_right + card_w - 140, y_card + 645), radius=14, fill=(45, 30, 10), outline=COLOR_AMBER, width=2)
    draw.text((rot_cx, y_card + 610), "SURPRISE $5,000+ BILL", fill=COLOR_AMBER, font=FONT_TITLE_M, anchor="mm")


def render_scene_3(draw, t, scene_t):
    """Scene 3: Enter Fuse — Surgical Isolation."""
    # Electric Cyan Header
    draw.text((WIDTH // 2, 60), "FUSE: THE COGNITIVE CIRCUIT BREAKER", fill=COLOR_CYAN, font=FONT_TITLE_L, anchor="mt")
    draw.text((WIDTH // 2, 125), "Surgical Edge Quarantine • Zero Customer Disruption", fill=COLOR_MUTED, font=FONT_BODY, anchor="mt")

    # Main Interactive Architecture Canvas
    canvas_w, canvas_h = 1760, 680
    cx1 = (WIDTH - canvas_w) // 2
    cy1 = 180
    draw_rounded_rect(draw, (cx1, cy1, cx1 + canvas_w, cy1 + canvas_h), radius=24, fill=COLOR_BG_CARD, outline=(30, 50, 80), width=2)

    # 1. Left Column: Incoming Traffic Stream (Real Buyers vs Rogue Loop)
    left_x = cx1 + 50
    draw.text((left_x + 175, cy1 + 45), "INCOMING TRAFFIC", fill=COLOR_WHITE, font=FONT_TITLE_M, anchor="mm")

    # 3 Real Users
    users = [
        ("Buyer #891 (Organic)", "IP: 49.36.12.8", COLOR_GREEN),
        ("Buyer #230 (Flash Sale)", "IP: 157.48.91.4", COLOR_GREEN),
        ("Stripe Webhook (Order)", "IP: 54.187.20.1", COLOR_GREEN),
    ]
    for i, (uname, uip, ucol) in enumerate(users):
        uy = cy1 + 100 + i * 95
        draw_rounded_rect(draw, (left_x, uy, left_x + 350, uy + 80), radius=12, fill=(16, 24, 34), outline=(40, 70, 70), width=1)
        draw.ellipse([left_x + 20, uy + 28, left_x + 45, uy + 53], fill=ucol)
        draw.text((left_x + 58, uy + 18), uname, fill=COLOR_WHITE, font=FONT_BODY_B)
        draw.text((left_x + 58, uy + 48), uip, fill=COLOR_MUTED, font=FONT_MONO_S)

        # Animated green data packet flowing toward Gateway
        pkt_progress = (t * 1.5 + i * 0.3) % 1.0
        pkt_x = int(left_x + 360 + pkt_progress * 280)
        draw.ellipse([pkt_x - 8, uy + 40 - 8, pkt_x + 8, uy + 40 + 8], fill=COLOR_GREEN)

    # 1 Rogue Agent Loop (Red)
    rogue_y = cy1 + 400
    draw_rounded_rect(draw, (left_x, rogue_y, left_x + 350, rogue_y + 115), radius=14, fill=(35, 15, 25), outline=COLOR_RED, width=2)
    draw.ellipse([left_x + 20, rogue_y + 25, left_x + 50, rogue_y + 55], fill=COLOR_RED)
    draw.text((left_x + 62, rogue_y + 20), "ROGUE RETRY LOOP", fill=COLOR_RED, font=FONT_BODY_B)
    draw.text((left_x + 62, rogue_y + 50), "IP: 192.168.1.10 (Single)", fill=COLOR_WHITE, font=FONT_MONO_S)
    draw.text((left_x + 62, rogue_y + 78), "Volume: 850 req/min", fill=COLOR_AMBER, font=FONT_MONO_S)

    # 2. Center Column: Fuse Cognitive Brain & WAF Shield
    center_x = cx1 + 680
    brain_y = cy1 + 130
    brain_w, brain_h = 390, 440
    draw_rounded_rect(draw, (center_x, brain_y, center_x + brain_w, brain_y + brain_h), radius=20, fill=(12, 22, 38), outline=COLOR_CYAN, width=2)
    
    # Brain Header Badge
    draw_rounded_rect(draw, (center_x + 20, brain_y + 20, center_x + brain_w - 20, brain_y + 75), radius=10, fill=(0, 60, 90))
    draw.text((center_x + brain_w // 2, brain_y + 48), "FUSE ENGINE", fill=COLOR_CYAN, font=FONT_TITLE_M, anchor="mm")

    # Real-time metrics inside Fuse
    draw.text((center_x + brain_w // 2, brain_y + 115), "Z-Score: 4.85 (Critical)", fill=COLOR_RED, font=FONT_MONO, anchor="mm")
    draw.text((center_x + brain_w // 2, brain_y + 155), "Diversity: 0.001 (Dominant)", fill=COLOR_AMBER, font=FONT_MONO, anchor="mm")
    draw.text((center_x + brain_w // 2, brain_y + 195), "Heartbeat: Post-Deploy Release", fill=COLOR_MUTED, font=FONT_MONO_S, anchor="mm")

    # Surgical Targeting Animation
    draw_rounded_rect(draw, (center_x + 20, brain_y + 245, center_x + brain_w - 20, brain_y + 410), radius=14, fill=(18, 32, 54), outline=COLOR_CYAN, width=1)
    draw.text((center_x + brain_w // 2, brain_y + 275), "SURGICAL TARGETING", fill=COLOR_CYAN, font=FONT_BODY_B, anchor="mm")
    
    laser_active = scene_t > 3.0
    if laser_active:
        # Draw targeting crosshair with centered anchor
        draw.text((center_x + brain_w // 2, brain_y + 320), "TARGET: 192.168.1.10/32", fill=COLOR_RED, font=FONT_MONO_S, anchor="mm")
        draw.text((center_x + brain_w // 2, brain_y + 365), "ACTION: WAF IP_BLOCKED", fill=COLOR_GREEN, font=FONT_BODY_B, anchor="mm")
        
        # Draw glowing laser line from Fuse to Rogue Loop
        laser_pulse = (math.sin(t * 10) + 1.0) / 2.0
        draw.line([(center_x, brain_y + 325), (left_x + 440, rogue_y + 55)], fill=(0, 240, 255), width=int(2 + laser_pulse * 3))
        # Shield barrier over rogue loop
        draw_rounded_rect(draw, (left_x + 370, rogue_y + 25, left_x + 480, rogue_y + 90), radius=10, fill=(80, 15, 25), outline=COLOR_RED, width=2)
        draw.text((left_x + 425, rogue_y + 58), "429", fill=COLOR_WHITE, font=FONT_TITLE_M, anchor="mm")

    # 3. Right Column: Protected API Gateway & Backend
    right_x = cx1 + 1180
    draw.text((right_x + 245, cy1 + 45), "CUSTOMER API GATEWAY", fill=COLOR_GREEN, font=FONT_TITLE_M, anchor="mm")

    # Gateway Box
    gw_w, gw_h = 490, 500
    draw_rounded_rect(draw, (right_x, cy1 + 100, right_x + gw_w, cy1 + 100 + gw_h), radius=20, fill=(14, 25, 24), outline=COLOR_GREEN, width=2)
    draw.text((right_x + gw_w // 2, cy1 + 145), "STATUS: 100% OPERATIONAL", fill=COLOR_GREEN, font=FONT_TITLE_M, anchor="mm")

    # Live flow lines passing safely into gateway
    for i in range(3):
        gy = cy1 + 220 + i * 85
        draw_rounded_rect(draw, (right_x + 30, gy, right_x + gw_w - 30, gy + 65), radius=10, fill=(20, 36, 32), outline=(50, 100, 80), width=1)
        draw.text((right_x + 50, gy + 32), f"Order #{10280 + i}", fill=COLOR_WHITE, font=FONT_BODY_B, anchor="lm")
        draw.text((right_x + gw_w - 50, gy + 32), "200 OK", fill=COLOR_GREEN, font=FONT_BODY_B, anchor="rm")

    draw_rounded_rect(draw, (right_x + 30, cy1 + 510, right_x + gw_w - 30, cy1 + 575), radius=10, fill=(15, 45, 30))
    draw.text((right_x + gw_w // 2, cy1 + 542), "Zero Lost Revenue • Legitimate Buyers Protected", fill=COLOR_GREEN, font=FONT_BODY_B, anchor="mm")


def render_scene_4(draw, t, scene_t):
    """Scene 4: Peace of Mind & CTA."""
    # Header
    draw.text((WIDTH // 2, 70), "PEACE OF MIND FOR MODERN CLOUD TEAMS", fill=COLOR_WHITE, font=FONT_TITLE_L, anchor="mt")
    draw.text((WIDTH // 2, 140), "Sleep peacefully. Your AWS workload has an autonomous circuit breaker.", fill=COLOR_MUTED, font=FONT_BODY, anchor="mt")

    # Three Bento Metric Cards
    cards = [
        ("100% UPTIME", "Zero customer disruption\nStore stays open during spikes", COLOR_GREEN),
        ("SURGICAL WAF BLOCK", "Rogue retry loop quarantined\nIsolated at regional edge", COLOR_CYAN),
        ("$7,900 SAVED", "Runaway severed in minutes\nZero 3 AM billing surprises", COLOR_GOLD),
    ]
    card_w, card_h = 520, 220
    total_w = 3 * card_w + 2 * 60
    start_x = (WIDTH - total_w) // 2
    cards_y = 210

    for i, (val, desc, col) in enumerate(cards):
        cx = start_x + i * (card_w + 60)
        pop_prog = min(1.0, max(0.0, (scene_t - i * 0.4) * 3.0))
        if pop_prog > 0:
            draw_rounded_rect(draw, (cx, cards_y, cx + card_w, cards_y + card_h), radius=20, fill=COLOR_BG_CARD, outline=col, width=2)
            title_font = FONT_TITLE_M if len(val) > 12 else FONT_TITLE_L
            draw.text((cx + card_w // 2, cards_y + 65), val, fill=col, font=title_font, anchor="mm")
            
            lines = desc.split("\n")
            draw.text((cx + card_w // 2, cards_y + 130), lines[0], fill=COLOR_WHITE, font=FONT_BODY_B, anchor="mm")
            draw.text((cx + card_w // 2, cards_y + 165), lines[1], fill=COLOR_MUTED, font=FONT_BODY, anchor="mm")

    # Central Hero Banner & Call To Action
    hero_y = 480
    hero_w, hero_h = 1680, 480
    hx = (WIDTH - hero_w) // 2
    draw_rounded_rect(draw, (hx, hero_y, hx + hero_w, hero_y + hero_h), radius=28, fill=(12, 17, 28), outline=COLOR_CYAN, width=3)

    # Fuse Logo Mark (Vector Lightning Bolt)
    logo_cx = WIDTH // 2
    logo_cy = hero_y + 105
    draw.ellipse([logo_cx - 55, logo_cy - 55, logo_cx + 55, logo_cy + 55], fill=(0, 60, 90), outline=COLOR_CYAN, width=3)
    draw_lightning_bolt(draw, logo_cx, logo_cy, size=28, color=COLOR_CYAN)

    # Main CTA Headings
    draw.text((WIDTH // 2, hero_y + 195), "FUSE: COGNITIVE CIRCUIT BREAKER", fill=COLOR_WHITE, font=FONT_TITLE_L, anchor="mm")
    draw.text((WIDTH // 2, hero_y + 250), "Built for Bharat Builds Tour 2026 • First Commit (Ship It Track)", fill=COLOR_MUTED, font=FONT_BODY, anchor="mm")

    # CTA Button
    btn_w, btn_h = 880, 75
    btn_x = (WIDTH - btn_w) // 2
    btn_y = hero_y + 305
    draw_rounded_rect(draw, (btn_x, btn_y, btn_x + btn_w, btn_y + btn_h), radius=18, fill=COLOR_CYAN, outline=COLOR_WHITE, width=2)
    draw.text((WIDTH // 2, btn_y + 38), "GET STARTED ON GITHUB — OPEN SOURCE", fill=(5, 10, 20), font=FONT_TITLE_M, anchor="mm")

    # GitHub Repo Link
    draw.text((WIDTH // 2, hero_y + 425), "github.com/Pranjulchaurasiya/fuse", fill=COLOR_CYAN, font=FONT_MONO, anchor="mm")


def draw_subtitles(draw, text):
    """Draws centered kinetic subtitles with high contrast backdrop pill and multiline wrap."""
    import textwrap
    if not text:
        return

    # Check if text exceeds comfortable line width
    bbox = draw.textbbox((0, 0), text, font=FONT_SUBTITLE)
    text_w = bbox[2] - bbox[0]
    
    if text_w > WIDTH - 200:
        lines = textwrap.wrap(text, width=82)
    else:
        lines = [text]

    line_h = 36
    sub_box_h = 24 + len(lines) * line_h
    sub_box_y = HEIGHT - 25 - sub_box_h

    # Compute max width among wrapped lines
    max_line_w = 0
    for l in lines:
        lb = draw.textbbox((0, 0), l, font=FONT_SUBTITLE)
        max_line_w = max(max_line_w, lb[2] - lb[0])

    box_w = max(450, min(WIDTH - 80, max_line_w + 70))
    box_x = (WIDTH - box_w) // 2

    # Backdrop pill
    draw_rounded_rect(draw, (box_x, sub_box_y, box_x + box_w, sub_box_y + sub_box_h), radius=16, fill=(10, 12, 18), outline=(60, 75, 100), width=1)
    
    # Centered subtitle lines
    start_y = sub_box_y + 14 + line_h // 2
    for idx, line_text in enumerate(lines):
        draw.text((WIDTH // 2, start_y + idx * line_h), line_text, fill=COLOR_WHITE, font=FONT_SUBTITLE, anchor="mm")


def render_all_frames():
    """Renders all frames to disk."""
    frames_dir = os.path.join(BUILD_DIR, "frames")
    if os.path.exists(frames_dir):
        shutil.rmtree(frames_dir)
    os.makedirs(frames_dir, exist_ok=True)

    print(f"[*] Rendering {TOTAL_FRAMES} frames ({TOTAL_DURATION:.1f}s @ {FPS} FPS)...")
    
    # Precompute scene start times
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
        for i, start_t in enumerate(scene_starts):
            if t >= start_t:
                scene_idx = i

        current_scene = SCENES[scene_idx]
        scene_t = t - scene_starts[scene_idx]

        # Create frame image
        img = Image.new("RGB", (WIDTH, HEIGHT), COLOR_BG_DARK)
        draw = ImageDraw.Draw(img)

        # 1. Base gradient background
        draw_gradient_background(draw, t)

        # 2. Scene-specific motion graphics
        if scene_idx == 0:
            render_scene_1(draw, t, scene_t)
        elif scene_idx == 1:
            render_scene_2(draw, t, scene_t)
        elif scene_idx == 2:
            render_scene_3(draw, t, scene_t)
        elif scene_idx == 3:
            render_scene_4(draw, t, scene_t)

        # 3. Kinetic Subtitle Bar
        draw_subtitles(draw, current_scene["text"])

        # Save frame
        frame_filename = os.path.join(frames_dir, f"frame_{frame_idx:05d}.jpg")
        img.save(frame_filename, "JPEG", quality=92)

        if (frame_idx + 1) % 150 == 0 or frame_idx == TOTAL_FRAMES - 1:
            elapsed = time.time() - t0
            fps_render = (frame_idx + 1) / max(0.01, elapsed)
            print(f"    + Rendered {frame_idx + 1}/{TOTAL_FRAMES} frames ({fps_render:.1f} fps)")

    print(f"[+] All {TOTAL_FRAMES} frames rendered in {time.time() - t0:.1f}s.")
    return frames_dir


def compile_final_video(frames_dir, master_audio_path):
    """Compiles frames and audio into broadcast MP4 using FFmpeg."""
    print("[*] Compiling master video with FFmpeg...")
    
    # Check audio duration
    ffprobe_cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "json", master_audio_path]
    res = subprocess.run(ffprobe_cmd, capture_output=True, text=True)
    audio_dur = float(json.loads(res.stdout)["format"]["duration"])
    print(f"    + Master audio duration: {audio_dur:.2f}s (Video target: {TOTAL_DURATION:.2f}s)")

    # Adjust audio speed slightly if needed to match video duration exactly
    tempo_ratio = audio_dur / TOTAL_DURATION
    tempo_filter = f"atempo={tempo_ratio:.4f}"

    # Build subtle futuristic synth drone bed using FFmpeg audio filter
    # Synth drone at 55Hz and 110Hz with slow lowpass filter
    cmd = [
        "ffmpeg", "-y",
        "-framerate", str(FPS),
        "-i", os.path.join(frames_dir, "frame_%05d.jpg"),
        "-i", master_audio_path,
        "-filter_complex", (
            f"[1:a]{tempo_filter},volume=1.0[voice]; "
            f"aevalsrc=sin(2*PI*55*t)*0.02+sin(2*PI*110*t)*0.01:d={TOTAL_DURATION}[synth]; "
            "[voice][synth]amix=inputs=2:duration=first:dropout_transition=2[aout]"
        ),
        "-map", "0:v",
        "-map", "[aout]",
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-preset", "fast",
        "-crf", "18",
        "-c:a", "aac",
        "-b:a", "192k",
        "-shortest",
        OUTPUT_VIDEO
    ]

    subprocess.run(cmd, check=True)
    video_size_mb = os.path.getsize(OUTPUT_VIDEO) / (1024 * 1024)
    print("\n" + "=" * 65)
    print(f"[SUCCESS] Product Commercial Created: {OUTPUT_VIDEO}")
    print(f"Resolution: {WIDTH}x{HEIGHT} @ {FPS}fps | Size: {video_size_mb:.2f} MB")
    print("=" * 65)


def main():
    print("=" * 65)
    print("BUILDING FUSE ANIMATED PRODUCT COMMERCIAL (1080P)")
    print("=" * 65)
    master_audio = ensure_audio()
    frames_dir = render_all_frames()
    compile_final_video(frames_dir, master_audio)


if __name__ == "__main__":
    main()
