"""render_cinematic_mockups.py — Generates non-generic, high-production motion design frames.

Features:
- Volumetric ambient lighting / colored radial blooms
- Frosted glassmorphism with 1px specular bevel highlights
- Distinct cinematic framing for each scene (no repeated left-text/right-card template)
- Rich technical micro-details (dot grids, terminal chrome, glowing status rings, syntax colors)
- Subtle film grain texture overlay
"""

import math
import os
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

WIDTH = 1920
HEIGHT = 1080
OUT_DIR = r"c:\Users\pranj\Documents\Fuse\scratch_pro_motion\cinematic_test"
os.makedirs(OUT_DIR, exist_ok=True)

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
    "mega_title": load_font("heavy", 88),
    "hero_title": load_font("heavy", 64),
    "hero_sub": load_font("bold", 32),
    "card_title": load_font("bold", 24),
    "card_body": load_font("regular", 20),
    "card_body_b": load_font("bold", 20),
    "mono": load_font("mono", 20),
    "mono_bold": load_font("mono_bold", 20),
    "mono_sm": load_font("mono", 16),
    "ticker_huge": load_font("heavy", 84),
    "ticker_med": load_font("heavy", 60),
    "badge": load_font("bold", 16),
    "hud": load_font("mono_bold", 15),
}

# Ambient Glow & Lighting Engine
def apply_ambient_bloom(img, cx, cy, radius, color, max_alpha=70):
    bloom = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    b_draw = ImageDraw.Draw(bloom)
    c_r, c_g, c_b = color
    steps = 25
    for i in range(steps):
        r = int(radius * (1.0 - i / steps))
        alpha = int(max_alpha * (1.0 - (r / radius) ** 1.8))
        b_draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(c_r, c_g, c_b, alpha))
    img.paste(bloom, (0, 0), bloom)

# Glassmorphism Card with Specular Top Highlight
def draw_glass_card(img, bbox, radius, fill_color, border_color, glow_color=None, shadow_alpha=110):
    x1, y1, x2, y2 = bbox
    
    # 1. Diffuse Glow / Drop Shadow
    shadow_img = Image.new("RGBA", img.size, (0, 0, 0, 0))
    s_draw = ImageDraw.Draw(shadow_img)
    s_col = (glow_color[0], glow_color[1], glow_color[2], int(shadow_alpha * 0.45)) if glow_color else (0, 0, 0, shadow_alpha)
    s_draw.rounded_rectangle([x1, y1 + 14, x2, y2 + 28], radius=radius, fill=s_col)
    shadow_blurred = shadow_img.filter(ImageFilter.GaussianBlur(28))
    img.paste(shadow_blurred, (0, 0), shadow_blurred)

    # 2. Card Body
    card_layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    c_draw = ImageDraw.Draw(card_layer)
    c_draw.rounded_rectangle(bbox, radius=radius, fill=fill_color, outline=border_color, width=1)

    # 3. Specular Highlight on top edge (Apple/Figma glass look)
    c_draw.line([(x1 + radius, y1), (x2 - radius, y1)], fill=(255, 255, 255, 120), width=2)
    img.paste(card_layer, (0, 0), card_layer)

def add_film_grain(img, intensity=0.035):
    """Adds a subtle cinematic analog texture across the frame."""
    arr = np.array(img, dtype=np.float32)
    noise = np.random.normal(0, intensity * 255, arr.shape)
    arr = np.clip(arr + noise, 0, 255).astype(np.uint8)
    return Image.fromarray(arr)

def draw_hud_telemetry(draw, current_scene_str, time_str="03:14:22 UTC"):
    """Draws sleek cyber technical telemetry around frame corners."""
    # Top Left Brand HUD
    draw.text((80, 55), "FUSE // AUTONOMOUS CIRCUIT BREAKER", fill=(140, 160, 190), font=FONTS["hud"])
    draw.text((80, 78), f"SYS_STATUS: ACTIVE  •  {current_scene_str}", fill=(0, 220, 240), font=FONTS["mono_sm"])

    # Top Right Telemetry
    draw.text((WIDTH - 80, 55), time_str, fill=(200, 220, 240), font=FONTS["hud"], anchor="ra")
    draw.text((WIDTH - 80, 78), "LATENCY: 0.12ms  •  REGION: ap-south-1", fill=(140, 160, 190), font=FONTS["mono_sm"], anchor="ra")

    # Bottom Corner Bracket Marks
    draw.line([(80, HEIGHT - 55), (120, HEIGHT - 55)], fill=(100, 120, 150), width=2)
    draw.line([(80, HEIGHT - 55), (80, HEIGHT - 95)], fill=(100, 120, 150), width=2)

    draw.line([(WIDTH - 80, HEIGHT - 55), (WIDTH - 120, HEIGHT - 55)], fill=(100, 120, 150), width=2)
    draw.line([(WIDTH - 80, HEIGHT - 55), (WIDTH - 80, HEIGHT - 95)], fill=(100, 120, 150), width=2)


# ==============================================================================
# SCENE 1: THE NIGHTMARE — Full-Screen Emergency Terminal & Runaway Spend
# ==============================================================================
def render_cinematic_s1():
    img = Image.new("RGBA", (WIDTH, HEIGHT), (10, 8, 16))
    
    # Dual Crimson & Violet Volumetric Blooms
    apply_ambient_bloom(img, WIDTH // 2, HEIGHT // 2 - 40, radius=520, color=(220, 20, 60), max_alpha=75)
    apply_ambient_bloom(img, WIDTH // 4, HEIGHT // 3, radius=360, color=(140, 15, 60), max_alpha=45)
    draw = ImageDraw.Draw(img)

    # Subtle Background Cyber Grid
    for x in range(80, WIDTH, 120):
        for y in range(80, HEIGHT, 120):
            draw.point((x, y), fill=(80, 25, 45))

    # Top Emergency Banner
    draw_glass_card(img, (WIDTH // 2 - 280, 130, WIDTH // 2 + 280, 180), radius=14, 
                    fill_color=(45, 12, 22, 220), border_color=(255, 60, 90, 200), glow_color=(255, 30, 60))
    e_draw = ImageDraw.Draw(img)
    e_draw.text((WIDTH // 2, 155), "●  CRITICAL ALERT // UNCHECKED RECURSION DETECTED", fill=(255, 100, 120), font=FONTS["badge"], anchor="mm")

    # Center Hero: GIANT RUNAWAY SPEND TICKER
    e_draw.text((WIDTH // 2, 260), "AT 3:14 AM, A 3-LINE RETRY LOOP", fill=(255, 230, 240), font=FONTS["hero_title"], anchor="mm")
    e_draw.text((WIDTH // 2, 330), "WILL BANKRUPT YOU.", fill=(255, 75, 95), font=FONTS["mega_title"], anchor="mm")

    # Dual Center Cards: Left Terminal Code vs Right AWS Spend HUD
    # 1. Left: VS Code Style Glass Terminal
    term_bbox = (200, 430, 920, 860)
    draw_glass_card(img, term_bbox, radius=22, fill_color=(18, 12, 26, 230), border_color=(90, 35, 60, 180), glow_color=(255, 40, 80))
    t_draw = ImageDraw.Draw(img)
    # Terminal Title Bar with Mac traffic lights
    t_draw.ellipse([230, 460, 244, 474], fill=(255, 95, 87))
    t_draw.ellipse([252, 460, 266, 474], fill=(254, 188, 46))
    t_draw.ellipse([274, 460, 288, 474], fill=(40, 200, 64))
    t_draw.text((315, 467), "lambda_handler.py — infinite_loop.py", fill=(180, 150, 170), font=FONTS["mono_sm"], anchor="lm")
    t_draw.line([(200, 495), (920, 495)], fill=(60, 25, 45), width=1)

    # Code lines with syntax highlighting
    t_draw.text((230, 525), "1  import requests, os", fill=(120, 100, 125), font=FONTS["mono"])
    t_draw.text((230, 560), "2  ", fill=(120, 100, 125), font=FONTS["mono"])
    t_draw.text((230, 595), "3  def process_agent_task(prompt):", fill=(255, 215, 0), font=FONTS["mono"])
    t_draw.text((230, 630), "4      while not response.ok:", fill=(255, 80, 100), font=FONTS["mono_bold"])
    t_draw.text((230, 665), "5          # MISSING RETRY DELAY", fill=(180, 60, 80), font=FONTS["mono"])
    t_draw.text((230, 700), "6          response = api.post(url, json=prompt)", fill=(240, 140, 70), font=FONTS["mono"])
    t_draw.text((230, 735), "7          # SPINS AT 5,000 REQ/SEC", fill=(255, 75, 95), font=FONTS["mono_bold"])

    # Glowing Red Terminal Footer Pill
    t_draw.rounded_rectangle([230, 780, 890, 830], radius=12, fill=(60, 15, 30), outline=(255, 80, 100))
    t_draw.text((560, 805), "CRITICAL: RECURSIVE THREAD SPAWNING 5,000 RPS", fill=(255, 120, 140), font=FONTS["mono_bold"], anchor="mm")

    # 2. Right: AWS CloudWatch Live Billing Meter
    meter_bbox = (1000, 430, 1720, 860)
    draw_glass_card(img, meter_bbox, radius=22, fill_color=(24, 12, 28, 230), border_color=(140, 40, 70, 200), glow_color=(255, 50, 80))
    m_draw = ImageDraw.Draw(img)

    # AWS Header Badge
    m_draw.rounded_rectangle([1035, 460, 1100, 510], radius=10, fill=(255, 153, 0))
    m_draw.text((1067, 485), "AWS", fill=(0, 0, 0), font=FONTS["card_body_b"], anchor="mm")
    m_draw.text((1118, 475), "CloudWatch Cost Guardrail Alert", fill=(255, 240, 245), font=FONTS["card_body_b"])
    m_draw.text((1118, 500), "API Gateway Count Spiking 800% over baseline", fill=(255, 120, 140), font=FONTS["mono_sm"])
    m_draw.line([(1000, 535), (1720, 535)], fill=(65, 25, 45), width=1)

    # Live Spend Figure
    m_draw.text((1360, 620), "$8,452.18", fill=(255, 85, 105), font=FONTS["ticker_huge"], anchor="mm")
    m_draw.text((1360, 685), "OVERNIGHT RUNAWAY INVOCATION ACCRUAL", fill=(255, 180, 195), font=FONTS["mono_bold"], anchor="mm")

    # Stat Row inside Meter
    m_draw.rounded_rectangle([1035, 735, 1345, 825], radius=14, fill=(35, 15, 30), outline=(100, 30, 50))
    m_draw.text((1190, 765), "5,280 RPS", fill=(255, 200, 100), font=FONTS["card_title"], anchor="mm")
    m_draw.text((1190, 795), "RUNAWAY INVOCATIONS", fill=(200, 160, 180), font=FONTS["mono_sm"], anchor="mm")

    m_draw.rounded_rectangle([1375, 735, 1685, 825], radius=14, fill=(35, 15, 30), outline=(100, 30, 50))
    m_draw.text((1530, 765), "ZERO BACKOFF", fill=(255, 80, 100), font=FONTS["card_title"], anchor="mm")
    m_draw.text((1530, 795), "EXPONENTIAL RETRY", fill=(200, 160, 180), font=FONTS["mono_sm"], anchor="mm")

    # Technical HUD Telemetry
    draw_hud_telemetry(draw, "01_RUNAWAY_RECURSION_ALARM")
    img = add_film_grain(img.convert("RGB"))
    img.save(os.path.join(OUT_DIR, "cinematic_s1.png"))
    print("[+] Generated cinematic_s1.png")


# ==============================================================================
# SCENE 2: THE DILEMMA — Neon Toll Wall Collision (Static Rate Limits Fail)
# ==============================================================================
def render_cinematic_s2():
    img = Image.new("RGBA", (WIDTH, HEIGHT), (16, 12, 8))
    
    # Warm Amber & Crimson Collision Blooms
    apply_ambient_bloom(img, WIDTH // 2 + 100, HEIGHT // 2, radius=560, color=(240, 140, 20), max_alpha=65)
    apply_ambient_bloom(img, WIDTH // 2 + 250, HEIGHT // 2, radius=400, color=(220, 40, 40), max_alpha=55)
    draw = ImageDraw.Draw(img)

    # Top Kinetic Headline
    draw.text((WIDTH // 2, 140), "TRADITIONAL RATE LIMITS ARE DUMB.", fill=(255, 200, 50), font=FONTS["mega_title"], anchor="mm")
    draw.text((WIDTH // 2, 205), "They stop the flood by dropping your highest-value customers.", fill=(230, 210, 190), font=FONTS["hero_sub"], anchor="mm")

    # Visual Pipeline: Incoming Traffic (Left) -> Harsh Barrier (Center) -> Revenue Drop (Right)
    # 1. Left: Incoming Mixed Stream
    draw_glass_card(img, (160, 290, 760, 880), radius=22, fill_color=(25, 20, 22, 230), border_color=(120, 60, 40), glow_color=(240, 140, 20))
    l_draw = ImageDraw.Draw(img)
    l_draw.text((200, 330), "INCOMING MIXED TRAFFIC", fill=(255, 200, 100), font=FONTS["card_title"])
    l_draw.text((200, 360), "Flash Sale + Legitimate Orders + 1 Runaway Agent", fill=(180, 160, 150), font=FONTS["mono_sm"])

    requests = [
        ("Checkout: $450 Cart", "Organic Buyer (VIP)", "LEGIT"),
        ("Checkout: $120 Cart", "Organic Buyer", "LEGIT"),
        ("Webhook: Stripe Settlement", "Payment Gateway", "LEGIT"),
        ("POST /agent: 850 RPS", "Recursive Retry Loop", "ROGUE"),
        ("Checkout: $890 Enterprise", "Enterprise Client", "LEGIT"),
    ]
    for idx, (req_name, req_sub, req_type) in enumerate(requests):
        ry = 405 + idx * 90
        is_rogue = req_type == "ROGUE"
        bg_col = (50, 18, 25) if is_rogue else (30, 28, 38)
        border_col = (255, 80, 90) if is_rogue else (70, 65, 85)
        l_draw.rounded_rectangle([195, ry, 725, ry + 75], radius=14, fill=bg_col, outline=border_col)
        l_draw.ellipse([215, ry + 28, 235, ry + 48], fill=(255, 80, 90) if is_rogue else (40, 200, 100))
        l_draw.text((250, ry + 24), req_name, fill=(255, 255, 255), font=FONTS["card_body_b"])
        l_draw.text((250, ry + 48), req_sub, fill=(200, 170, 180) if is_rogue else (160, 180, 170), font=FONTS["mono_sm"])

    # 2. Center: The Bludgeon Wall (WAF Static 100 RPS Limit)
    wall_x = 830
    draw_glass_card(img, (wall_x, 290, wall_x + 200, 880), radius=18, fill_color=(50, 12, 20, 240), border_color=(255, 50, 70), glow_color=(255, 30, 50))
    w_draw = ImageDraw.Draw(img)
    # Vertical Text for the Barrier
    w_draw.text((wall_x + 100, 360), "STATIC WAF", fill=(255, 80, 100), font=FONTS["card_title"], anchor="mm")
    w_draw.text((wall_x + 100, 400), "100 RPS LIMIT", fill=(255, 200, 100), font=FONTS["card_body_b"], anchor="mm")
    w_draw.line([(wall_x + 25, 435), (wall_x + 175, 435)], fill=(120, 30, 45), width=2)
    w_draw.text((wall_x + 100, 560), "BLIND", fill=(255, 100, 120), font=FONTS["hero_title"], anchor="mm")
    w_draw.text((wall_x + 100, 630), "THROTTLE", fill=(255, 100, 120), font=FONTS["card_title"], anchor="mm")
    w_draw.text((wall_x + 100, 740), "KILLS ALL", fill=(255, 220, 100), font=FONTS["card_body_b"], anchor="mm")
    w_draw.text((wall_x + 100, 780), "TRAFFIC", fill=(255, 220, 100), font=FONTS["card_body_b"], anchor="mm")

    # 3. Right: Collateral Damage / Lost Revenue
    draw_glass_card(img, (1090, 290, 1760, 880), radius=22, fill_color=(28, 12, 18, 230), border_color=(180, 40, 60), glow_color=(255, 40, 60))
    r_draw = ImageDraw.Draw(img)
    r_draw.text((1140, 330), "COLLATERAL DAMAGE // FALSE POSITIVES", fill=(255, 80, 100), font=FONTS["card_title"])
    r_draw.text((1140, 360), "Real paying buyers throttled indiscriminately:", fill=(200, 160, 170), font=FONTS["mono_sm"])

    drops = [
        ("$450 VIP Cart", "DROPPED (429)", "-$450.00"),
        ("$120 Cart", "DROPPED (429)", "-$120.00"),
        ("Stripe Webhook", "FAILED (429)", "OUTAGE"),
        ("Agent Flood", "THROTTLED (429)", "PAUSED"),
        ("$890 Enterprise Cart", "DROPPED (429)", "-$890.00"),
    ]
    for idx, (d_name, d_status, d_loss) in enumerate(drops):
        dy = 405 + idx * 90
        r_draw.rounded_rectangle([1135, dy, 1725, dy + 75], radius=14, fill=(45, 14, 22), outline=(120, 30, 45))
        r_draw.text((1160, dy + 24), d_name, fill=(255, 255, 255), font=FONTS["card_body_b"])
        r_draw.text((1160, dy + 48), d_status, fill=(255, 90, 110), font=FONTS["mono_sm"])
        r_draw.text((1700, dy + 38), d_loss, fill=(255, 60, 80), font=FONTS["card_title"], anchor="rm")

    draw_hud_telemetry(draw, "02_STATIC_THROTTLE_FAIL")
    img = add_film_grain(img.convert("RGB"))
    img.save(os.path.join(OUT_DIR, "cinematic_s2.png"))
    print("[+] Generated cinematic_s2.png")


# ==============================================================================
# SCENE 3: THE SOLUTION — Cybernetic Dual-Highway Intelligent Router
# ==============================================================================
def render_cinematic_s3():
    img = Image.new("RGBA", (WIDTH, HEIGHT), (6, 12, 24))
    
    # Electric Cyan & Deep Sapphire Volumetric Blooms
    apply_ambient_bloom(img, WIDTH // 2, HEIGHT // 2 - 40, radius=560, color=(0, 200, 255), max_alpha=70)
    apply_ambient_bloom(img, 1450, 480, radius=420, color=(34, 197, 94), max_alpha=55)
    apply_ambient_bloom(img, 1450, 780, radius=420, color=(239, 68, 68), max_alpha=55)
    draw = ImageDraw.Draw(img)

    # Top Kinetic Headline
    draw.text((WIDTH // 2, 135), "MEET FUSE // SURGICAL CIRCUIT BREAKER", fill=(0, 230, 255), font=FONTS["hero_title"], anchor="mm")
    draw.text((WIDTH // 2, 195), "Target the runaway loop at the edge. Never touch paying customers.", fill=(200, 235, 255), font=FONTS["hero_sub"], anchor="mm")

    # Center Visual: Intelligent Traffic Separation (Dual-Highway)
    # 1. Left Ingress Node: Incoming API Stream
    draw_glass_card(img, (140, 280, 560, 880), radius=22, fill_color=(12, 22, 38, 230), border_color=(0, 180, 240), glow_color=(0, 230, 255))
    i_draw = ImageDraw.Draw(img)
    i_draw.text((180, 320), "AWS API GATEWAY INGRESS", fill=(0, 230, 255), font=FONTS["card_title"])
    i_draw.text((180, 350), "Telemetry streamed to Fuse Engine", fill=(140, 180, 220), font=FONTS["mono_sm"])

    i_draw.rounded_rectangle([175, 410, 525, 590], radius=16, fill=(18, 32, 54), outline=(40, 90, 140))
    i_draw.text((350, 450), "CALLER TELEMETRY", fill=(255, 255, 255), font=FONTS["card_body_b"], anchor="mm")
    i_draw.text((350, 485), "• Rolling 1-min Count", fill=(180, 215, 245), font=FONTS["mono"], anchor="mm")
    i_draw.text((350, 520), "• Baseline Mean & StdDev", fill=(180, 215, 245), font=FONTS["mono"], anchor="mm")
    i_draw.text((350, 555), "• Caller Diversity Index", fill=(180, 215, 245), font=FONTS["mono"], anchor="mm")

    i_draw.rounded_rectangle([175, 630, 525, 830], radius=16, fill=(14, 40, 60), outline=(0, 200, 255))
    i_draw.text((350, 670), "DETERMINISTIC GATE", fill=(0, 230, 255), font=FONTS["card_body_b"], anchor="mm")
    i_draw.text((350, 720), "Z-SCORE >= 2.5", fill=(255, 215, 0), font=FONTS["hero_sub"], anchor="mm")
    i_draw.text((350, 780), "TRIGGER SURGICAL ISOLATION", fill=(200, 230, 255), font=FONTS["mono_sm"], anchor="mm")

    # 2. Center: The Fuse Intelligence Core (Pulsing Shield Node)
    fuse_cx = 760
    draw_glass_card(img, (fuse_cx - 110, 450, fuse_cx + 110, 710), radius=24, fill_color=(10, 35, 60, 240), border_color=(0, 240, 255), glow_color=(0, 230, 255))
    f_draw = ImageDraw.Draw(img)
    f_draw.text((fuse_cx, 510), "FUSE", fill=(0, 230, 255), font=FONTS["hero_title"], anchor="mm")
    f_draw.text((fuse_cx, 560), "WAF ENGINE", fill=(255, 255, 255), font=FONTS["card_title"], anchor="mm")
    f_draw.text((fuse_cx, 620), "< 1ms", fill=(34, 197, 94), font=FONTS["ticker_med"], anchor="mm")
    f_draw.text((fuse_cx, 665), "EDGE ACTION", fill=(180, 240, 210), font=FONTS["mono_sm"], anchor="mm")

    # Connecting Laser Pathways
    draw.line([(560, 580), (fuse_cx - 110, 580)], fill=(0, 230, 255), width=3)
    # Upper Highway to Green
    draw.line([(fuse_cx + 110, 540), (980, 440)], fill=(34, 197, 94), width=4)
    # Lower Highway to Red
    draw.line([(fuse_cx + 110, 620), (980, 720)], fill=(239, 68, 68), width=4)

    # 3. Right: Upper Highway (100% Legit Buyers Safe)
    draw_glass_card(img, (980, 280, 1780, 550), radius=22, fill_color=(12, 38, 28, 230), border_color=(34, 197, 94), glow_color=(34, 197, 94))
    u_draw = ImageDraw.Draw(img)
    u_draw.ellipse([1020, 320, 1045, 345], fill=(34, 197, 94))
    u_draw.text((1065, 332), "HIGHWAY 1: LEGITIMATE BUYERS", fill=(34, 197, 94), font=FONTS["card_title"], anchor="lm")
    u_draw.rounded_rectangle([1530, 310, 1740, 355], radius=12, fill=(18, 65, 42), outline=(34, 197, 94))
    u_draw.text((1635, 332), "100% UNTOUCHED", fill=(255, 255, 255), font=FONTS["mono_bold"], anchor="mm")

    u_draw.text((1020, 395), "• Paying Customers pass through at full line speed", fill=(220, 255, 235), font=FONTS["card_body"])
    u_draw.text((1020, 435), "• Zero added latency (0ms) — No API proxy overhead", fill=(220, 255, 235), font=FONTS["card_body"])
    u_draw.text((1020, 475), "• Checkout revenue flow preserved during attacks", fill=(255, 215, 0), font=FONTS["card_body_b"])

    # 4. Right: Lower Highway (Surgical Rogue Quarantine)
    draw_glass_card(img, (980, 610, 1780, 880), radius=22, fill_color=(38, 14, 24, 230), border_color=(239, 68, 68), glow_color=(239, 68, 68))
    d_draw = ImageDraw.Draw(img)
    d_draw.ellipse([1020, 650, 1045, 675], fill=(239, 68, 68))
    d_draw.text((1065, 662), "HIGHWAY 2: SURGICAL EDGE QUARANTINE", fill=(255, 90, 110), font=FONTS["card_title"], anchor="lm")
    d_draw.rounded_rectangle([1530, 640, 1740, 685], radius=12, fill=(80, 15, 25), outline=(239, 68, 68))
    d_draw.text((1635, 662), "429 ISOLATED", fill=(255, 255, 255), font=FONTS["mono_bold"], anchor="mm")

    d_draw.text((1020, 720), "• Rogue IP address added to AWS WAF IP Set in < 1ms", fill=(255, 210, 220), font=FONTS["card_body"])
    d_draw.text((1020, 760), "• Packets dropped at regional edge before reaching Lambdas", fill=(255, 210, 220), font=FONTS["card_body"])
    d_draw.text((1020, 800), "• Automatic 15-minute cooldown recovery prevents permanent lockouts", fill=(255, 200, 100), font=FONTS["card_body_b"])

    draw_hud_telemetry(draw, "03_SURGICAL_QUARANTINE_ENGAGED")
    img = add_film_grain(img.convert("RGB"))
    img.save(os.path.join(OUT_DIR, "cinematic_s3.png"))
    print("[+] Generated cinematic_s3.png")


# ==============================================================================
# SCENE 4: THE PAYOFF — Luxury Linear-Style Asymmetric Bento Grid
# ==============================================================================
def render_cinematic_s4():
    img = Image.new("RGBA", (WIDTH, HEIGHT), (6, 16, 18))
    
    # Emerald & Cyan Ambient Volumetric Blooms
    apply_ambient_bloom(img, 450, 520, radius=520, color=(34, 197, 94), max_alpha=65)
    apply_ambient_bloom(img, 1400, 420, radius=480, color=(0, 230, 255), max_alpha=60)
    draw = ImageDraw.Draw(img)

    # Top Kinetic Headline
    draw.text((WIDTH // 2, 125), "ZERO DOWNTIME. ZERO 3 AM PANIC.", fill=(34, 197, 94), font=FONTS["mega_title"], anchor="mm")
    draw.text((WIDTH // 2, 190), "Your serverless workloads now have an autonomous self-healing circuit breaker.", fill=(210, 245, 230), font=FONTS["hero_sub"], anchor="mm")

    # 4-Tile Luxury Bento Grid Layout:
    # Bento 1: Giant Emerald 100% Store Uptime (Left Tall Hero Pod)
    b1_bbox = (160, 270, 740, 880)
    draw_glass_card(img, b1_bbox, radius=24, fill_color=(12, 36, 26, 235), border_color=(34, 197, 94), glow_color=(34, 197, 94))
    b1 = ImageDraw.Draw(img)
    b1.text((450, 360), "STORE AVAILABILITY", fill=(180, 240, 210), font=FONTS["card_title"], anchor="mm")
    b1.text((450, 470), "100%", fill=(34, 197, 94), font=FONTS["ticker_huge"], anchor="mm")
    b1.text((450, 560), "ZERO FALSE POSITIVES", fill=(255, 255, 255), font=FONTS["card_body_b"], anchor="mm")
    b1.line([(240, 620), (660, 620)], fill=(25, 70, 50), width=2)
    b1.text((450, 680), "• Organic checkouts uninterrupted", fill=(200, 245, 225), font=FONTS["card_body"], anchor="mm")
    b1.text((450, 730), "• Stripe webhooks verified instantly", fill=(200, 245, 225), font=FONTS["card_body"], anchor="mm")
    b1.text((450, 780), "• 100% Serverless EventBridge Architecture", fill=(255, 215, 0), font=FONTS["card_body_b"], anchor="mm")

    # Bento 2: $7,900+ Saved Overnight (Right Top Wide Pod)
    b2_bbox = (790, 270, 1760, 550)
    draw_glass_card(img, b2_bbox, radius=24, fill_color=(14, 30, 48, 235), border_color=(0, 220, 255), glow_color=(0, 220, 255))
    b2 = ImageDraw.Draw(img)
    b2.text((850, 325), "ESTIMATED ACCRUAL SAVED OVERNIGHT", fill=(180, 225, 250), font=FONTS["card_title"])
    b2.text((850, 410), "$7,900+", fill=(0, 230, 255), font=FONTS["ticker_huge"])
    b2.rounded_rectangle([1360, 360, 1700, 440], radius=14, fill=(16, 50, 80), outline=(0, 200, 240))
    b2.text((1530, 400), "< 60s TIME-TO-ISOLATION", fill=(255, 255, 255), font=FONTS["mono_bold"], anchor="mm")
    b2.text((850, 495), "Halted recursive agent loop before triggering DynamoDB & Lambda cost cascades.", fill=(160, 205, 230), font=FONTS["mono_sm"])

    # Bento 3: Tech Specs Pod (Right Bottom Left)
    b3_bbox = (790, 600, 1280, 880)
    draw_glass_card(img, b3_bbox, radius=24, fill_color=(14, 25, 35, 235), border_color=(50, 100, 130))
    b3 = ImageDraw.Draw(img)
    b3.text((830, 650), "ARCHITECTURE SPECS", fill=(200, 230, 245), font=FONTS["card_title"])
    b3.text((830, 710), "● CloudWatch get_metric_data (1-min)", fill=(170, 200, 215), font=FONTS["card_body"])
    b3.text((830, 760), "● AWS WAF IP Set surgical blocking", fill=(170, 200, 215), font=FONTS["card_body"])
    b3.text((830, 810), "● Amazon Bedrock enrichment", fill=(170, 200, 215), font=FONTS["card_body"])

    # Bento 4: Glowing GitHub CTA Button Pod (Right Bottom Right)
    b4_bbox = (1330, 600, 1760, 880)
    draw_glass_card(img, b4_bbox, radius=24, fill_color=(10, 40, 50, 240), border_color=(0, 240, 255), glow_color=(0, 240, 255))
    b4 = ImageDraw.Draw(img)
    b4.text((1545, 660), "DEPLOY FUSE TODAY", fill=(0, 230, 255), font=FONTS["card_title"], anchor="mm")
    
    # Giant Centered Glowing Button
    b4.rounded_rectangle([1370, 715, 1720, 815], radius=18, fill=(0, 230, 255), outline=(255, 255, 255), width=2)
    b4.text((1545, 750), "STAR ON GITHUB", fill=(8, 20, 30), font=FONTS["card_title"], anchor="mm")
    b4.text((1545, 785), "github.com/Pranjulchaurasiya/fuse", fill=(15, 60, 85), font=FONTS["mono_sm"], anchor="mm")

    draw_hud_telemetry(draw, "04_PRODUCTION_VERIFIED_METRICS")
    img = add_film_grain(img.convert("RGB"))
    img.save(os.path.join(OUT_DIR, "cinematic_s4.png"))
    print("[+] Generated cinematic_s4.png")


if __name__ == "__main__":
    render_cinematic_s1()
    render_cinematic_s2()
    render_cinematic_s3()
    render_cinematic_s4()
    print("[SUCCESS] All 4 cinematic mockups generated!")
