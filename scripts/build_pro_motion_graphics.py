"""build_pro_motion_graphics.py — Cinematic High-Production Motion Graphics Ad for Fuse.

Full overhaul:
- Bespoke, non-generic compositions for all 4 scenes (no repeated left-text/right-card formula):
  * Scene 1: Full-Screen Emergency Terminal & Runaway Cloud Spend Meter
  * Scene 2: The Monolithic WAF Toll Wall Collision & Revenue Fallout
  * Scene 3: Cybernetic Dual-Highway Intelligent Router (Fuse Circuit Breaker)
  * Scene 4: Luxury Linear/Apple Style Asymmetric Bento Grid & Glowing GitHub Star Button
- Volumetric colored ambient light blooms & specular top-edge glass reflections
- Analog film grain texture overlay
- Cybernetic telemetry HUD & timecode
- Dynamic whip pan & zoom punch transitions (1.14x scale, directional blur, seam flash)
- Tactile camera impact shakes on 124 BPM bass drops
- Kinetic staggered typography with live rolling counters
- Bespoke upbeat electronic synth track with rich tactile sound design (booms, whooshes, laser zaps, pops)
"""

import math
import os
import shutil
import subprocess
import time
import numpy as np
import wave
from PIL import Image, ImageDraw, ImageFont, ImageFilter

WIDTH = 1920
HEIGHT = 1080
FPS = 30
DURATION = 20.0
TOTAL_FRAMES = int(DURATION * FPS)

BUILD_DIR = r"c:\Users\pranj\Documents\Fuse\scratch_pro_motion"
OUTPUT_VIDEO = r"c:\Users\pranj\Documents\Fuse\Fuse_Pro_Motion_Ad_1080p.mp4"

# Load Fonts
def load_font(name, size):
    fonts_dir = r"C:\Windows\Fonts"
    candidates = {
        "bold": ["segoeuib.ttf", "arialbd.ttf"],
        "heavy": ["ariblk.ttf", "segoeuib.ttf"],
        "regular": ["segoeui.ttf", "arial.ttf"],
        "semibold": ["seguisb.ttf", "segoeuib.ttf"],
        "mono": ["consola.ttf", "cour.ttf"],
        "mono_bold": ["consolab.ttf", "courbd.ttf"],
    }
    for fname in candidates.get(name, ["segoeui.ttf"]):
        p = os.path.join(fonts_dir, fname)
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                pass
    return ImageFont.load_default()

FONTS = {
    "mega_title": load_font("heavy", 84),
    "hero_title": load_font("heavy", 60),
    "hero_sub": load_font("bold", 30),
    "card_title": load_font("bold", 24),
    "card_body": load_font("regular", 20),
    "card_body_b": load_font("bold", 20),
    "mono": load_font("mono", 20),
    "mono_bold": load_font("mono_bold", 20),
    "mono_sm": load_font("mono", 16),
    "ticker_huge": load_font("heavy", 80),
    "ticker_med": load_font("heavy", 54),
    "badge": load_font("bold", 16),
    "hud": load_font("mono_bold", 15),
}

# Math & Easing Helpers
def ease_in_out_cubic(t):
    t = max(0.0, min(1.0, t))
    return 4 * t * t * t if t < 0.5 else 1.0 - math.pow(-2 * t + 2, 3) / 2

def spring(t, zeta=0.70, omega=18.0):
    if t <= 0: return 0.0
    if t > 1.2: return 1.0
    omega_d = omega * math.sqrt(1.0 - zeta * zeta)
    decay = math.exp(-zeta * omega * t)
    return 1.0 - decay * (math.cos(omega_d * t) + (zeta / math.sqrt(1.0 - zeta * zeta)) * math.sin(omega_d * t))

def smoothstep(edge0, edge1, x):
    t = max(0.0, min(1.0, (x - edge0) / (edge1 - edge0)))
    return t * t * (3.0 - 2.0 * t)

# Volumetric Lighting & Glassmorphism
def apply_ambient_bloom(img, cx, cy, radius, color, max_alpha=70):
    bloom = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    b_draw = ImageDraw.Draw(bloom)
    c_r, c_g, c_b = color
    steps = 22
    for i in range(steps):
        r = int(radius * (1.0 - i / steps))
        alpha = int(max_alpha * (1.0 - (r / radius) ** 1.8))
        b_draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(c_r, c_g, c_b, alpha))
    img.paste(bloom, (0, 0), bloom)

def draw_glass_card(img, bbox, radius, fill_color, border_color, glow_color=None, shadow_alpha=110):
    x1, y1, x2, y2 = bbox
    # Diffuse shadow
    shadow_img = Image.new("RGBA", img.size, (0, 0, 0, 0))
    s_draw = ImageDraw.Draw(shadow_img)
    s_col = (glow_color[0], glow_color[1], glow_color[2], int(shadow_alpha * 0.45)) if glow_color else (0, 0, 0, shadow_alpha)
    s_draw.rounded_rectangle([x1, y1 + 14, x2, y2 + 28], radius=radius, fill=s_col)
    shadow_blurred = shadow_img.filter(ImageFilter.GaussianBlur(26))
    img.paste(shadow_blurred, (0, 0), shadow_blurred)

    # Card body
    card_layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    c_draw = ImageDraw.Draw(card_layer)
    c_draw.rounded_rectangle(bbox, radius=radius, fill=fill_color, outline=border_color, width=1)
    # Specular light edge (Apple glass highlight)
    c_draw.line([(x1 + radius, y1), (x2 - radius, y1)], fill=(255, 255, 255, 120), width=2)
    img.paste(card_layer, (0, 0), card_layer)

def draw_shockwave(draw, cx, cy, radius, color, max_radius=130):
    if radius <= 0 or radius > max_radius:
        return
    alpha_ratio = 1.0 - (radius / max_radius)
    c_r, c_g, c_b = color[:3]
    stroke_w = max(1, int(4 * alpha_ratio))
    draw.ellipse([cx - radius, cy - radius, cx + radius, cy + radius], outline=(c_r, c_g, c_b), width=stroke_w)

def add_film_grain(img, intensity=0.03):
    arr = np.array(img, dtype=np.float32)
    noise = np.random.normal(0, intensity * 255, arr.shape)
    arr = np.clip(arr + noise, 0, 255).astype(np.uint8)
    return Image.fromarray(arr)

def draw_hud_telemetry(draw, current_scene_str, time_str="03:14:22 UTC"):
    draw.text((80, 50), "FUSE // AUTONOMOUS CIRCUIT BREAKER", fill=(140, 160, 190), font=FONTS["hud"])
    draw.text((80, 72), f"SYS_STATUS: ACTIVE  •  {current_scene_str}", fill=(0, 220, 240), font=FONTS["mono_sm"])
    draw.text((WIDTH - 80, 50), time_str, fill=(200, 220, 240), font=FONTS["hud"], anchor="ra")
    draw.text((WIDTH - 80, 72), "LATENCY: 0.12ms  •  REGION: ap-south-1", fill=(140, 160, 190), font=FONTS["mono_sm"], anchor="ra")

    draw.line([(80, HEIGHT - 55), (120, HEIGHT - 55)], fill=(100, 120, 150), width=2)
    draw.line([(80, HEIGHT - 55), (80, HEIGHT - 95)], fill=(100, 120, 150), width=2)
    draw.line([(WIDTH - 80, HEIGHT - 55), (WIDTH - 120, HEIGHT - 55)], fill=(100, 120, 150), width=2)
    draw.line([(WIDTH - 80, HEIGHT - 55), (WIDTH - 80, HEIGHT - 95)], fill=(100, 120, 150), width=2)


# Scene Definitions & Timing
SCENE_TIMINGS = [
    (0.00, 4.80),
    (4.80, 9.80),
    (9.80, 14.80),
    (14.80, 20.00),
]
TRANSITION_CENTERS = [4.80, 9.80, 14.80]
TRANS_DURATION = 0.38


# ==============================================================================
# SCENE 1: THE NIGHTMARE — Full-Screen Emergency Terminal & Runaway Spend Meter
# ==============================================================================
def render_scene_1(local_t, global_t):
    img = Image.new("RGBA", (WIDTH, HEIGHT), (10, 8, 16))
    
    # Volumetric Blooms
    apply_ambient_bloom(img, WIDTH // 2, HEIGHT // 2 - 40, radius=540, color=(220, 20, 60), max_alpha=75)
    apply_ambient_bloom(img, WIDTH // 4, HEIGHT // 3, radius=360, color=(140, 15, 60), max_alpha=45)
    draw = ImageDraw.Draw(img)

    # Grid
    for x in range(80, WIDTH, 120):
        for y in range(80, HEIGHT, 120):
            draw.point((x, y), fill=(80, 25, 45))

    # Top Alert Badge (0.05s)
    b_prog = spring(local_t - 0.05, zeta=0.65, omega=22.0)
    if b_prog > 0.02:
        draw_glass_card(img, (WIDTH // 2 - 290, 125, WIDTH // 2 + 290, 175), radius=14, 
                        fill_color=(45, 12, 22, 220), border_color=(255, 60, 90, 200), glow_color=(255, 30, 60))
        e_draw = ImageDraw.Draw(img)
        e_draw.text((WIDTH // 2, 150), "●  CRITICAL ALERT // UNCHECKED RECURSION DETECTED", fill=(255, 100, 120), font=FONTS["badge"], anchor="mm")

    # Staggered Kinetic Headline (0.18s, 0.45s)
    h1_prog = spring(local_t - 0.18, zeta=0.72, omega=20.0)
    if h1_prog > 0.02:
        draw.text((WIDTH // 2, 240), "AT 3:14 AM, A 3-LINE RETRY LOOP", fill=(255, 230, 240), font=FONTS["hero_title"], anchor="mm")

    h2_prog = spring(local_t - 0.45, zeta=0.65, omega=22.0)
    if h2_prog > 0.02:
        draw.text((WIDTH // 2, 315), "WILL BANKRUPT YOU.", fill=(255, 75, 95), font=FONTS["mega_title"], anchor="mm")

    # Left: VS Code Glass Terminal (0.35s)
    t_prog = spring(local_t - 0.35, zeta=0.7, omega=18.0)
    if t_prog > 0.02:
        t_x = int(200 + (1.0 - t_prog) * -120)
        term_bbox = (t_x, 410, t_x + 720, 850)
        draw_glass_card(img, term_bbox, radius=22, fill_color=(18, 12, 26, 230), border_color=(90, 35, 60, 180), glow_color=(255, 40, 80))
        t_draw = ImageDraw.Draw(img)
        t_draw.ellipse([t_x + 30, 438, t_x + 44, 452], fill=(255, 95, 87))
        t_draw.ellipse([t_x + 52, 438, t_x + 66, 452], fill=(254, 188, 46))
        t_draw.ellipse([t_x + 74, 438, t_x + 88, 452], fill=(40, 200, 64))
        t_draw.text((t_x + 115, 445), "lambda_handler.py — infinite_loop.py", fill=(180, 150, 170), font=FONTS["mono_sm"], anchor="lm")
        t_draw.line([(t_x, 475), (t_x + 720, 475)], fill=(60, 25, 45), width=1)

        t_draw.text((t_x + 30, 505), "1  import requests, os", fill=(120, 100, 125), font=FONTS["mono"])
        t_draw.text((t_x + 30, 540), "2  ", fill=(120, 100, 125), font=FONTS["mono"])
        t_draw.text((t_x + 30, 575), "3  def process_agent_task(prompt):", fill=(255, 215, 0), font=FONTS["mono"])
        cursor = " |" if int(global_t * 6) % 2 == 0 else ""
        t_draw.text((t_x + 30, 610), f"4      while not response.ok:{cursor}", fill=(255, 80, 100), font=FONTS["mono_bold"])
        t_draw.text((t_x + 30, 645), "5          # MISSING RETRY DELAY", fill=(180, 60, 80), font=FONTS["mono"])
        t_draw.text((t_x + 30, 680), "6          response = api.post(url, json=prompt)", fill=(240, 140, 70), font=FONTS["mono"])
        t_draw.text((t_x + 30, 715), "7          # SPINS AT 5,000 REQ/SEC", fill=(255, 75, 95), font=FONTS["mono_bold"])

        t_draw.rounded_rectangle([t_x + 30, 765, t_x + 690, 820], radius=12, fill=(60, 15, 30), outline=(255, 80, 100))
        t_draw.text((t_x + 360, 792), "CRITICAL: RECURSIVE THREAD SPAWNING 5,000 RPS", fill=(255, 120, 140), font=FONTS["mono_bold"], anchor="mm")

    # Right: AWS CloudWatch Meter with Live Ticker (0.50s)
    m_prog = spring(local_t - 0.50, zeta=0.7, omega=18.0)
    if m_prog > 0.02:
        m_x = int(1000 + (1.0 - m_prog) * 120)
        meter_bbox = (m_x, 410, m_x + 720, 850)
        draw_glass_card(img, meter_bbox, radius=22, fill_color=(24, 12, 28, 230), border_color=(140, 40, 70, 200), glow_color=(255, 50, 80))
        m_draw = ImageDraw.Draw(img)

        m_draw.rounded_rectangle([m_x + 35, 438, m_x + 100, 488], radius=10, fill=(255, 153, 0))
        m_draw.text((m_x + 67, 463), "AWS", fill=(0, 0, 0), font=FONTS["card_body_b"], anchor="mm")
        m_draw.text((m_x + 118, 453), "CloudWatch Cost Guardrail Alert", fill=(255, 240, 245), font=FONTS["card_body_b"])
        m_draw.text((m_x + 118, 478), "API Gateway Count Spiking 800% over baseline", fill=(255, 120, 140), font=FONTS["mono_sm"])
        m_draw.line([(m_x, 510), (m_x + 720, 510)], fill=(65, 25, 45), width=1)

        # Dynamic Ticker
        exp_factor = min(1.0, (local_t / 3.8) ** 2.2)
        val = 120.0 + exp_factor * 8332.18
        pulse = math.sin(global_t * 12.0) * 0.5 + 0.5
        m_draw.ellipse([m_x + 360 - 200, 555, m_x + 360 + 200, 645], outline=(255, 50, 70), width=int(1 + pulse * 3))
        m_draw.text((m_x + 360, 600), f"${val:,.2f}", fill=(255, 85, 105), font=FONTS["ticker_huge"], anchor="mm")
        m_draw.text((m_x + 360, 665), "OVERNIGHT RUNAWAY INVOCATION ACCRUAL", fill=(255, 180, 195), font=FONTS["mono_bold"], anchor="mm")

        m_draw.rounded_rectangle([m_x + 35, 720, m_x + 345, 815], radius=14, fill=(35, 15, 30), outline=(100, 30, 50))
        m_draw.text((m_x + 190, 752), "5,280 RPS", fill=(255, 200, 100), font=FONTS["card_title"], anchor="mm")
        m_draw.text((m_x + 190, 785), "RUNAWAY INVOCATIONS", fill=(200, 160, 180), font=FONTS["mono_sm"], anchor="mm")

        m_draw.rounded_rectangle([m_x + 375, 720, m_x + 685, 815], radius=14, fill=(35, 15, 30), outline=(100, 30, 50))
        m_draw.text((m_x + 530, 752), "ZERO BACKOFF", fill=(255, 80, 100), font=FONTS["card_title"], anchor="mm")
        m_draw.text((m_x + 530, 785), "EXPONENTIAL RETRY", fill=(200, 160, 180), font=FONTS["mono_sm"], anchor="mm")

        if local_t > 2.0:
            rip_t = local_t - 2.0
            if rip_t < 0.7:
                draw_shockwave(m_draw, m_x + 360, 600, radius=int(rip_t * 240), color=(255, 80, 100))

    draw_hud_telemetry(draw, "01_RUNAWAY_RECURSION_ALARM")
    return add_film_grain(img.convert("RGB"))


# ==============================================================================
# SCENE 2: THE DILEMMA — Monolithic WAF Toll Wall Collision
# ==============================================================================
def render_scene_2(local_t, global_t):
    img = Image.new("RGBA", (WIDTH, HEIGHT), (16, 12, 8))
    
    apply_ambient_bloom(img, WIDTH // 2 + 100, HEIGHT // 2, radius=560, color=(240, 140, 20), max_alpha=65)
    apply_ambient_bloom(img, WIDTH // 2 + 250, HEIGHT // 2, radius=400, color=(220, 40, 40), max_alpha=55)
    draw = ImageDraw.Draw(img)

    # Top Kinetic Headline (0.15s)
    h_prog = spring(local_t - 0.15, zeta=0.68, omega=22.0)
    if h_prog > 0.02:
        draw.text((WIDTH // 2, 135), "TRADITIONAL RATE LIMITS ARE DUMB.", fill=(255, 200, 50), font=FONTS["mega_title"], anchor="mm")
        draw.text((WIDTH // 2, 200), "They stop the flood by dropping your highest-value customers.", fill=(230, 210, 190), font=FONTS["hero_sub"], anchor="mm")

    # 1. Left: Mixed Inbound Stream (0.35s)
    l_prog = spring(local_t - 0.35, zeta=0.7, omega=18.0)
    if l_prog > 0.02:
        draw_glass_card(img, (160, 280, 740, 880), radius=22, fill_color=(25, 20, 22, 230), border_color=(120, 60, 40), glow_color=(240, 140, 20))
        l_draw = ImageDraw.Draw(img)
        l_draw.text((200, 320), "INCOMING MIXED TRAFFIC", fill=(255, 200, 100), font=FONTS["card_title"])
        l_draw.text((200, 350), "Flash Sale + Legitimate Orders + 1 Runaway Agent", fill=(180, 160, 150), font=FONTS["mono_sm"])

        requests = [
            ("Checkout: $450 Cart", "Organic Buyer (VIP)", "LEGIT"),
            ("Checkout: $120 Cart", "Organic Buyer", "LEGIT"),
            ("Webhook: Stripe Settlement", "Payment Gateway", "LEGIT"),
            ("POST /agent: 850 RPS", "Recursive Retry Loop", "ROGUE"),
            ("Checkout: $890 Enterprise", "Enterprise Client", "LEGIT"),
        ]
        for idx, (req_name, req_sub, req_type) in enumerate(requests):
            ry = 395 + idx * 92
            is_rogue = req_type == "ROGUE"
            bg_col = (50, 18, 25) if is_rogue else (30, 28, 38)
            border_col = (255, 80, 90) if is_rogue else (70, 65, 85)
            l_draw.rounded_rectangle([195, ry, 705, ry + 75], radius=14, fill=bg_col, outline=border_col)
            l_draw.ellipse([215, ry + 28, 235, ry + 48], fill=(255, 80, 90) if is_rogue else (40, 200, 100))
            l_draw.text((250, ry + 24), req_name, fill=(255, 255, 255), font=FONTS["card_body_b"])
            l_draw.text((250, ry + 48), req_sub, fill=(200, 170, 180) if is_rogue else (160, 180, 170), font=FONTS["mono_sm"])

    # 2. Center: The Bludgeon Wall (0.60s)
    wall_x = 810
    w_prog = spring(local_t - 0.60, zeta=0.6, omega=24.0)
    if w_prog > 0.02:
        draw_glass_card(img, (wall_x, 280, wall_x + 230, 880), radius=18, fill_color=(50, 12, 20, 240), border_color=(255, 50, 70), glow_color=(255, 30, 50))
        w_draw = ImageDraw.Draw(img)
        w_draw.text((wall_x + 115, 350), "STATIC WAF", fill=(255, 80, 100), font=FONTS["card_title"], anchor="mm")
        w_draw.text((wall_x + 115, 390), "100 RPS LIMIT", fill=(255, 200, 100), font=FONTS["card_body_b"], anchor="mm")
        w_draw.line([(wall_x + 25, 425), (wall_x + 205, 425)], fill=(120, 30, 45), width=2)
        w_draw.text((wall_x + 115, 550), "BLIND", fill=(255, 100, 120), font=FONTS["hero_sub"], anchor="mm")
        w_draw.text((wall_x + 115, 620), "THROTTLE", fill=(255, 100, 120), font=FONTS["card_title"], anchor="mm")
        w_draw.text((wall_x + 115, 730), "KILLS ALL", fill=(255, 220, 100), font=FONTS["card_body_b"], anchor="mm")
        w_draw.text((wall_x + 115, 770), "TRAFFIC", fill=(255, 220, 100), font=FONTS["card_body_b"], anchor="mm")

    # 3. Right: Collateral Damage (0.85s)
    r_prog = spring(local_t - 0.85, zeta=0.7, omega=18.0)
    if r_prog > 0.02:
        draw_glass_card(img, (1110, 280, 1760, 880), radius=22, fill_color=(28, 12, 18, 230), border_color=(180, 40, 60), glow_color=(255, 40, 60))
        r_draw = ImageDraw.Draw(img)
        r_draw.text((1150, 320), "COLLATERAL DAMAGE // FALSE POSITIVES", fill=(255, 80, 100), font=FONTS["card_title"])
        r_draw.text((1150, 350), "Real paying buyers throttled indiscriminately:", fill=(200, 160, 170), font=FONTS["mono_sm"])

        drops = [
            ("$450 VIP Cart", "DROPPED (429)", "-$450.00"),
            ("$120 Cart", "DROPPED (429)", "-$120.00"),
            ("Stripe Webhook", "FAILED (429)", "OUTAGE"),
            ("Agent Flood", "THROTTLED (429)", "PAUSED"),
            ("$890 Enterprise Cart", "DROPPED (429)", "-$890.00"),
        ]
        for idx, (d_name, d_status, d_loss) in enumerate(drops):
            dy = 395 + idx * 92
            r_draw.rounded_rectangle([1145, dy, 1725, dy + 75], radius=14, fill=(45, 14, 22), outline=(120, 30, 45))
            r_draw.text((1170, dy + 24), d_name, fill=(255, 255, 255), font=FONTS["card_body_b"])
            r_draw.text((1170, dy + 48), d_status, fill=(255, 90, 110), font=FONTS["mono_sm"])
            r_draw.text((1700, dy + 38), d_loss, fill=(255, 60, 80), font=FONTS["card_title"], anchor="rm")

    draw_hud_telemetry(draw, "02_STATIC_THROTTLE_FAIL")
    return add_film_grain(img.convert("RGB"))


# ==============================================================================
# SCENE 3: THE SOLUTION — Cybernetic Dual-Highway Intelligent Router
# ==============================================================================
def render_scene_3(local_t, global_t):
    img = Image.new("RGBA", (WIDTH, HEIGHT), (6, 12, 24))
    
    apply_ambient_bloom(img, WIDTH // 2, HEIGHT // 2 - 40, radius=560, color=(0, 200, 255), max_alpha=70)
    apply_ambient_bloom(img, 1450, 450, radius=420, color=(34, 197, 94), max_alpha=55)
    apply_ambient_bloom(img, 1450, 750, radius=420, color=(239, 68, 68), max_alpha=55)
    draw = ImageDraw.Draw(img)

    # Top Kinetic Headline (0.15s)
    h_prog = spring(local_t - 0.15, zeta=0.68, omega=22.0)
    if h_prog > 0.02:
        draw.text((WIDTH // 2, 130), "MEET FUSE // SURGICAL CIRCUIT BREAKER", fill=(0, 230, 255), font=FONTS["hero_title"], anchor="mm")
        draw.text((WIDTH // 2, 190), "Target the runaway loop at the edge. Never touch paying customers.", fill=(200, 235, 255), font=FONTS["hero_sub"], anchor="mm")

    # 1. Left Ingress Node (0.35s)
    i_prog = spring(local_t - 0.35, zeta=0.7, omega=18.0)
    if i_prog > 0.02:
        draw_glass_card(img, (140, 270, 560, 880), radius=22, fill_color=(12, 22, 38, 230), border_color=(0, 180, 240), glow_color=(0, 230, 255))
        i_draw = ImageDraw.Draw(img)
        i_draw.text((180, 310), "AWS API GATEWAY INGRESS", fill=(0, 230, 255), font=FONTS["card_title"])
        i_draw.text((180, 340), "Telemetry streamed to Fuse Engine", fill=(140, 180, 220), font=FONTS["mono_sm"])

        i_draw.rounded_rectangle([175, 395, 525, 580], radius=16, fill=(18, 32, 54), outline=(40, 90, 140))
        i_draw.text((350, 435), "CALLER TELEMETRY", fill=(255, 255, 255), font=FONTS["card_body_b"], anchor="mm")
        i_draw.text((350, 470), "• Rolling 1-min Count", fill=(180, 215, 245), font=FONTS["mono"], anchor="mm")
        i_draw.text((350, 505), "• Baseline Mean & StdDev", fill=(180, 215, 245), font=FONTS["mono"], anchor="mm")
        i_draw.text((350, 540), "• Caller Diversity Index", fill=(180, 215, 245), font=FONTS["mono"], anchor="mm")

        i_draw.rounded_rectangle([175, 620, 525, 830], radius=16, fill=(14, 40, 60), outline=(0, 200, 255))
        i_draw.text((350, 660), "DETERMINISTIC GATE", fill=(0, 230, 255), font=FONTS["card_body_b"], anchor="mm")
        i_draw.text((350, 715), "Z-SCORE >= 2.5", fill=(255, 215, 0), font=FONTS["hero_sub"], anchor="mm")
        i_draw.text((350, 775), "TRIGGER SURGICAL ISOLATION", fill=(200, 230, 255), font=FONTS["mono_sm"], anchor="mm")

    # 2. Center: Fuse Core Node (0.55s)
    fuse_cx = 760
    f_prog = spring(local_t - 0.55, zeta=0.65, omega=20.0)
    if f_prog > 0.02:
        draw_glass_card(img, (fuse_cx - 110, 440, fuse_cx + 110, 710), radius=24, fill_color=(10, 35, 60, 240), border_color=(0, 240, 255), glow_color=(0, 230, 255))
        f_draw = ImageDraw.Draw(img)
        f_draw.text((fuse_cx, 500), "FUSE", fill=(0, 230, 255), font=FONTS["hero_title"], anchor="mm")
        f_draw.text((fuse_cx, 550), "WAF ENGINE", fill=(255, 255, 255), font=FONTS["card_title"], anchor="mm")
        f_draw.text((fuse_cx, 615), "< 1ms", fill=(34, 197, 94), font=FONTS["ticker_med"], anchor="mm")
        f_draw.text((fuse_cx, 665), "EDGE ACTION", fill=(180, 240, 210), font=FONTS["mono_sm"], anchor="mm")

        # Pathways
        draw.line([(560, 575), (fuse_cx - 110, 575)], fill=(0, 230, 255), width=3)
        draw.line([(fuse_cx + 110, 535), (980, 430)], fill=(34, 197, 94), width=4)
        draw.line([(fuse_cx + 110, 615), (980, 715)], fill=(239, 68, 68), width=4)

    # 3. Upper Highway: Legitimate Buyers Safe (0.80s)
    u_prog = spring(local_t - 0.80, zeta=0.7, omega=18.0)
    if u_prog > 0.02:
        draw_glass_card(img, (980, 270, 1780, 540), radius=22, fill_color=(12, 38, 28, 230), border_color=(34, 197, 94), glow_color=(34, 197, 94))
        u_draw = ImageDraw.Draw(img)
        u_draw.ellipse([1020, 310, 1045, 335], fill=(34, 197, 94))
        u_draw.text((1065, 322), "HIGHWAY 1: LEGITIMATE BUYERS", fill=(34, 197, 94), font=FONTS["card_title"], anchor="lm")
        u_draw.rounded_rectangle([1530, 300, 1740, 345], radius=12, fill=(18, 65, 42), outline=(34, 197, 94))
        u_draw.text((1635, 322), "100% UNTOUCHED", fill=(255, 255, 255), font=FONTS["mono_bold"], anchor="mm")

        u_draw.text((1020, 385), "• Paying Customers pass through at full line speed", fill=(220, 255, 235), font=FONTS["card_body"])
        u_draw.text((1020, 425), "• Zero added latency (0ms) — No API proxy overhead", fill=(220, 255, 235), font=FONTS["card_body"])
        u_draw.text((1020, 465), "• Checkout revenue flow preserved during attacks", fill=(255, 215, 0), font=FONTS["card_body_b"])

    # 4. Lower Highway: Rogue Quarantine (1.05s)
    d_prog = spring(local_t - 1.05, zeta=0.7, omega=18.0)
    if d_prog > 0.02:
        draw_glass_card(img, (980, 600, 1780, 880), radius=22, fill_color=(38, 14, 24, 230), border_color=(239, 68, 68), glow_color=(239, 68, 68))
        d_draw = ImageDraw.Draw(img)
        d_draw.ellipse([1020, 640, 1045, 665], fill=(239, 68, 68))
        d_draw.text((1065, 652), "HIGHWAY 2: ROGUE QUARANTINE", fill=(255, 90, 110), font=FONTS["card_title"], anchor="lm")
        d_draw.rounded_rectangle([1530, 630, 1740, 675], radius=12, fill=(80, 15, 25), outline=(239, 68, 68))
        d_draw.text((1635, 652), "429 ISOLATED", fill=(255, 255, 255), font=FONTS["mono_bold"], anchor="mm")

        d_draw.text((1020, 715), "• Rogue IP address added to AWS WAF IP Set in < 1ms", fill=(255, 210, 220), font=FONTS["card_body"])
        d_draw.text((1020, 755), "• Packets dropped at regional edge before reaching Lambdas", fill=(255, 210, 220), font=FONTS["card_body"])
        d_draw.text((1020, 795), "• Automatic 15-minute cooldown recovery prevents permanent lockouts", fill=(255, 200, 100), font=FONTS["card_body_b"])

        if local_t > 1.3:
            rip_t = local_t - 1.3
            if rip_t < 0.6:
                draw_shockwave(d_draw, 1635, 652, radius=int(rip_t * 220), color=(239, 68, 68))

    draw_hud_telemetry(draw, "03_SURGICAL_QUARANTINE_ENGAGED")
    return add_film_grain(img.convert("RGB"))


# ==============================================================================
# SCENE 4: THE PAYOFF — Luxury Linear-Style Asymmetric Bento Grid
# ==============================================================================
def render_scene_4(local_t, global_t):
    img = Image.new("RGBA", (WIDTH, HEIGHT), (6, 16, 18))
    
    apply_ambient_bloom(img, 450, 520, radius=520, color=(34, 197, 94), max_alpha=65)
    apply_ambient_bloom(img, 1400, 420, radius=480, color=(0, 230, 255), max_alpha=60)
    draw = ImageDraw.Draw(img)

    # Top Kinetic Headline (0.15s)
    h_prog = spring(local_t - 0.15, zeta=0.68, omega=22.0)
    if h_prog > 0.02:
        draw.text((WIDTH // 2, 125), "ZERO DOWNTIME. ZERO 3 AM PANIC.", fill=(34, 197, 94), font=FONTS["mega_title"], anchor="mm")
        draw.text((WIDTH // 2, 190), "Your serverless workloads now have an autonomous self-healing circuit breaker.", fill=(210, 245, 230), font=FONTS["hero_sub"], anchor="mm")

    # Bento 1: Giant 100% Uptime (0.30s)
    b1_prog = spring(local_t - 0.30, zeta=0.65, omega=20.0)
    if b1_prog > 0.02:
        b1_bbox = (160, 270, 740, 880)
        draw_glass_card(img, b1_bbox, radius=24, fill_color=(12, 36, 26, 235), border_color=(34, 197, 94), glow_color=(34, 197, 94))
        b1 = ImageDraw.Draw(img)
        b1.text((450, 350), "STORE AVAILABILITY", fill=(180, 240, 210), font=FONTS["card_title"], anchor="mm")
        u_val = int(min(100, smoothstep(0.30, 1.05, local_t) * 100))
        b1.text((450, 460), f"{u_val}%", fill=(34, 197, 94), font=FONTS["ticker_huge"], anchor="mm")
        b1.text((450, 550), "ZERO FALSE POSITIVES", fill=(255, 255, 255), font=FONTS["card_body_b"], anchor="mm")
        b1.line([(240, 610), (660, 610)], fill=(25, 70, 50), width=2)
        b1.text((450, 670), "• Organic checkouts uninterrupted", fill=(200, 245, 225), font=FONTS["card_body"], anchor="mm")
        b1.text((450, 720), "• Stripe webhooks verified instantly", fill=(200, 245, 225), font=FONTS["card_body"], anchor="mm")
        b1.text((450, 770), "• 100% Serverless EventBridge Architecture", fill=(255, 215, 0), font=FONTS["card_body_b"], anchor="mm")

    # Bento 2: $7,900+ Saved Overnight (0.50s)
    b2_prog = spring(local_t - 0.50, zeta=0.65, omega=20.0)
    if b2_prog > 0.02:
        b2_bbox = (790, 270, 1760, 550)
        draw_glass_card(img, b2_bbox, radius=24, fill_color=(14, 30, 48, 235), border_color=(0, 220, 255), glow_color=(0, 220, 255))
        b2 = ImageDraw.Draw(img)
        b2.text((850, 325), "ESTIMATED ACCRUAL SAVED OVERNIGHT", fill=(180, 225, 250), font=FONTS["card_title"])
        s_val = int(smoothstep(0.50, 1.30, local_t) * 7900)
        b2.text((850, 410), f"${s_val:,}+", fill=(0, 230, 255), font=FONTS["ticker_huge"])
        b2.rounded_rectangle([1360, 360, 1700, 440], radius=14, fill=(16, 50, 80), outline=(0, 200, 240))
        b2.text((1530, 400), "< 60s TIME-TO-ISOLATION", fill=(255, 255, 255), font=FONTS["mono_bold"], anchor="mm")
        b2.text((850, 495), "Halted recursive agent loop before triggering DynamoDB & Lambda cost cascades.", fill=(160, 205, 230), font=FONTS["mono_sm"])

    # Bento 3: Tech Specs Pod (0.75s)
    b3_prog = spring(local_t - 0.75, zeta=0.7, omega=18.0)
    if b3_prog > 0.02:
        b3_bbox = (790, 600, 1280, 880)
        draw_glass_card(img, b3_bbox, radius=24, fill_color=(14, 25, 35, 235), border_color=(50, 100, 130))
        b3 = ImageDraw.Draw(img)
        b3.text((830, 650), "ARCHITECTURE SPECS", fill=(200, 230, 245), font=FONTS["card_title"])
        b3.text((830, 710), "● CloudWatch get_metric_data (1-min)", fill=(170, 200, 215), font=FONTS["card_body"])
        b3.text((830, 760), "● AWS WAF IP Set surgical blocking", fill=(170, 200, 215), font=FONTS["card_body"])
        b3.text((830, 810), "● Amazon Bedrock enrichment", fill=(170, 200, 215), font=FONTS["card_body"])

    # Bento 4: Glowing GitHub CTA Button Pod (1.00s)
    b4_prog = spring(local_t - 1.00, zeta=0.6, omega=22.0)
    if b4_prog > 0.02:
        b4_bbox = (1330, 600, 1760, 880)
        draw_glass_card(img, b4_bbox, radius=24, fill_color=(10, 40, 50, 240), border_color=(0, 240, 255), glow_color=(0, 240, 255))
        b4 = ImageDraw.Draw(img)
        b4.text((1545, 660), "DEPLOY FUSE TODAY", fill=(0, 230, 255), font=FONTS["card_title"], anchor="mm")

        pulse = math.sin(global_t * 8.0) * 0.5 + 0.5
        outline_w = int(2 + pulse * 3)
        b4.rounded_rectangle([1370, 715, 1720, 815], radius=18, fill=(0, 230, 255), outline=(255, 255, 255), width=outline_w)
        b4.text((1545, 750), "STAR ON GITHUB", fill=(8, 20, 30), font=FONTS["card_title"], anchor="mm")
        b4.text((1545, 785), "github.com/Pranjulchaurasiya/fuse", fill=(15, 60, 85), font=FONTS["mono_sm"], anchor="mm")

    draw_hud_telemetry(draw, "04_PRODUCTION_VERIFIED_METRICS")
    return add_film_grain(img.convert("RGB"))


def render_scene(scene_idx, local_t, global_t):
    if scene_idx == 0:
        return render_scene_1(local_t, global_t)
    elif scene_idx == 1:
        return render_scene_2(local_t, global_t)
    elif scene_idx == 2:
        return render_scene_3(local_t, global_t)
    elif scene_idx == 3:
        return render_scene_4(local_t, global_t)
    return Image.new("RGB", (WIDTH, HEIGHT), (10, 8, 16))


def get_camera_shake(t):
    shake_x, shake_y = 0, 0
    impact_times = [0.0, 4.80, 5.60, 6.80, 9.80, 10.85, 14.80]
    for hit in impact_times:
        dt = t - hit
        if 0 <= dt < 0.35:
            decay = ((0.35 - dt) / 0.35) ** 2.2
            freq = 52.0
            amp = 18.0 if hit in [0.0, 4.80, 9.80, 14.80] else 9.0
            shake_x += int(math.sin(dt * freq) * amp * decay)
            shake_y += int(math.cos(dt * freq * 0.8) * (amp * 0.7) * decay)
    return shake_x, shake_y


def render_all_frames():
    frames_dir = os.path.join(BUILD_DIR, "frames")
    if os.path.exists(frames_dir):
        shutil.rmtree(frames_dir)
    os.makedirs(frames_dir, exist_ok=True)

    print(f"[*] Rendering {TOTAL_FRAMES} cinematic frames ({DURATION:.1f}s @ {FPS} FPS)...")
    t0 = time.time()
    half_trans = TRANS_DURATION / 2.0

    for frame_idx in range(TOTAL_FRAMES):
        t = frame_idx / FPS

        in_transition = False
        trans_idx = -1
        prog = 0.0

        for idx, tc in enumerate(TRANSITION_CENTERS):
            if tc - half_trans <= t <= tc + half_trans:
                in_transition = True
                trans_idx = idx
                prog = (t - (tc - half_trans)) / TRANS_DURATION
                break

        if in_transition:
            # WHIP PAN & ZOOM PUNCH
            scene_out = trans_idx
            scene_in = trans_idx + 1

            local_out = t - SCENE_TIMINGS[scene_out][0]
            local_in = t - SCENE_TIMINGS[scene_in][0]

            img_out = render_scene(scene_out, local_out, t)
            img_in = render_scene(scene_in, local_in, t)

            p_whip = ease_in_out_cubic(prog)
            zoom_scale = 1.0 + 0.14 * math.sin(math.pi * prog)

            canvas = Image.new("RGB", (WIDTH * 2, HEIGHT), (10, 8, 16))
            x_out = int(-WIDTH * (p_whip ** 1.4))
            x_in = int(WIDTH * ((1.0 - p_whip) ** 1.4))

            canvas.paste(img_out, (x_out, 0))
            canvas.paste(img_in, (x_in, 0))

            frame_img = canvas.crop((0, 0, WIDTH, HEIGHT))

            if zoom_scale > 1.01:
                crop_w = int(WIDTH / zoom_scale)
                crop_h = int(HEIGHT / zoom_scale)
                crop_x = (WIDTH - crop_w) // 2
                crop_y = (HEIGHT - crop_h) // 2
                frame_img = frame_img.crop((crop_x, crop_y, crop_x + crop_w, crop_y + crop_h))
                frame_img = frame_img.resize((WIDTH, HEIGHT), Image.BICUBIC)

            if 0.20 <= prog <= 0.80:
                blur_r = int(22 * math.sin(math.pi * prog))
                frame_img = frame_img.filter(ImageFilter.BoxBlur((blur_r, 0)))

            seam_x = x_in
            if 0 <= seam_x < WIDTH:
                s_draw = ImageDraw.Draw(frame_img)
                streak_w = int(6 * math.sin(math.pi * prog))
                s_draw.line([(seam_x, 0), (seam_x, HEIGHT)], fill=(255, 255, 255), width=max(1, streak_w))

            img = frame_img
        else:
            scene_idx = 0
            for i, (st, et) in enumerate(SCENE_TIMINGS):
                if st <= t < et:
                    scene_idx = i
                    break
            else:
                scene_idx = len(SCENE_TIMINGS) - 1

            local_t = t - SCENE_TIMINGS[scene_idx][0]
            img = render_scene(scene_idx, local_t, t)

        # Camera Shake
        sx, sy = get_camera_shake(t)
        if sx != 0 or sy != 0:
            shaken_img = Image.new("RGB", (WIDTH, HEIGHT), (10, 8, 16))
            shaken_img.paste(img, (sx, sy))
            img = shaken_img

        # Persistent Frame Counter
        draw = ImageDraw.Draw(img)
        draw.text((120, HEIGHT - 55), f"TIME  {t:05.2f} s", fill=(255, 255, 255, 160), font=FONTS["mono_bold"])
        draw.text((WIDTH - 120, HEIGHT - 55), f"FRAME  {frame_idx + 1:04d} / {TOTAL_FRAMES}", fill=(255, 255, 255, 160), font=FONTS["mono_bold"], anchor="ra")

        frame_path = os.path.join(frames_dir, f"frame_{frame_idx:05d}.jpg")
        img.save(frame_path, "JPEG", quality=95)

        if (frame_idx + 1) % 100 == 0 or frame_idx == TOTAL_FRAMES - 1:
            elapsed = time.time() - t0
            fps_val = (frame_idx + 1) / max(0.01, elapsed)
            print(f"    + Rendered {frame_idx + 1}/{TOTAL_FRAMES} frames ({fps_val:.1f} fps)")

    print(f"[+] All {TOTAL_FRAMES} frames rendered in {time.time() - t0:.1f}s.")
    return frames_dir


def generate_audio_soundtrack():
    """Generates bespoke upbeat electronic synth track with synchronized SFX."""
    os.makedirs(BUILD_DIR, exist_ok=True)
    sr = 44100
    audio = np.zeros(int(sr * DURATION))

    def add_sfx(sound, start_time, vol=1.0):
        start_idx = int(start_time * sr)
        end_idx = min(len(audio), start_idx + len(sound))
        audio[start_idx:end_idx] += sound[:end_idx - start_idx] * vol

    def make_boom(d=1.2, f_start=130, f_end=35):
        t = np.linspace(0, d, int(sr * d))
        freq = np.geomspace(f_start, f_end, len(t))
        env = np.exp(-4.2 * t)
        s = np.sin(2 * np.pi * np.cumsum(freq) / sr) * env
        return np.tanh(s * 2.2) * 0.85

    def make_whoosh(d=0.5):
        t = np.linspace(0, d, int(sr * d))
        noise = np.random.uniform(-1, 1, len(t))
        env = np.sin(np.pi * t / d) ** 2
        mod = np.sin(2 * np.pi * np.geomspace(350, 2200, len(t)) * t)
        return noise * env * 0.6 + mod * env * 0.35

    def make_pop(d=0.08, freq=1100):
        t = np.linspace(0, d, int(sr * d))
        env = np.exp(-35 * t)
        return np.sin(2 * np.pi * freq * t) * env

    def make_laser(d=0.35):
        t = np.linspace(0, d, int(sr * d))
        carrier = np.geomspace(3200, 180, len(t))
        env = np.exp(-9.0 * t)
        return np.sin(2 * np.pi * np.cumsum(carrier) / sr) * env * 0.7

    # 124 BPM Groove
    beat_len = 60.0 / 124.0
    for b in range(int(DURATION / beat_len)):
        bt = b * beat_len
        add_sfx(make_boom(0.32, 135, 42), bt, vol=0.55)
        t_hat = np.linspace(0, 0.045, int(sr * 0.045))
        hat = np.random.uniform(-0.3, 0.3, len(t_hat)) * np.exp(-65 * t_hat)
        add_sfx(hat, bt + beat_len * 0.5, vol=0.4)
        if b % 2 == 1:
            t_snare = np.linspace(0, 0.16, int(sr * 0.16))
            snare = (np.random.uniform(-1, 1, len(t_snare)) * 0.6 + np.sin(2 * np.pi * 210 * t_snare) * 0.4) * np.exp(-22 * t_snare)
            add_sfx(snare, bt, vol=0.6)

    # Key Synced SFX Drops
    add_sfx(make_boom(1.6, 160, 30), 0.0, vol=1.0)
    add_sfx(make_whoosh(0.55), 4.5, vol=0.9)
    add_sfx(make_boom(1.2, 130, 40), 4.8, vol=0.95)
    add_sfx(make_pop(0.08, 800), 5.6, vol=0.7)
    add_sfx(make_pop(0.08, 950), 5.88, vol=0.7)
    add_sfx(make_pop(0.08, 1100), 6.20, vol=0.7)
    add_sfx(make_pop(0.08, 1250), 6.52, vol=0.7)
    add_sfx(make_boom(0.8, 180, 50), 6.8, vol=0.8)
    add_sfx(make_whoosh(0.55), 9.5, vol=0.9)
    add_sfx(make_laser(0.35), 9.85, vol=0.95)
    add_sfx(make_pop(0.08, 900), 10.65, vol=0.75)
    add_sfx(make_pop(0.08, 1100), 10.95, vol=0.75)
    add_sfx(make_pop(0.08, 1300), 11.25, vol=0.75)
    add_sfx(make_pop(0.08, 1500), 11.55, vol=0.75)
    add_sfx(make_whoosh(0.6), 14.5, vol=0.9)
    add_sfx(make_boom(1.8, 160, 30), 14.8, vol=1.0)

    audio = np.clip(audio, -0.98, 0.98)
    audio_int16 = (audio * 32767).astype(np.int16)
    audio_path = os.path.join(BUILD_DIR, "soundtrack.wav")
    with wave.open(audio_path, 'wb') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes(audio_int16.tobytes())
    print(f"[+] Master soundtrack & SFX created: {audio_path}")
    return audio_path


def compile_final_video(frames_dir, audio_path):
    print("[*] Compiling final 1080p landscape motion ad with FFmpeg...")
    cmd = [
        "ffmpeg", "-y",
        "-framerate", str(FPS),
        "-i", os.path.join(frames_dir, "frame_%05d.jpg"),
        "-i", audio_path,
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "18",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        "-b:a", "192k",
        "-shortest",
        OUTPUT_VIDEO
    ]
    subprocess.run(cmd, check=True)
    print(f"\n[SUCCESS] Cinematic Motion Graphics Video Created: {OUTPUT_VIDEO}")


def main():
    print("=" * 65)
    print("BUILDING CINEMATIC HIGH-PRODUCTION MOTION GRAPHICS AD")
    print("=" * 65)
    audio_path = generate_audio_soundtrack()
    frames_dir = render_all_frames()
    compile_final_video(frames_dir, audio_path)


if __name__ == "__main__":
    main()
