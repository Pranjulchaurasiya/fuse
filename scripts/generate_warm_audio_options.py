"""
Generate three distinct professional audio options for testing:
Option A: Premium Cinematic Cyber Ambient (warm sub-bass, filtered low-pass chord pad, smooth vinyl texture, gentle pulse)
Option B: Pure Tactile Studio Foley (muted beat, deep acoustic 40Hz sub-drops, clean mechanical keyboard clicks, organic low-frequency whooshes)
Option C: Sleek Tech Groove (smooth filtered 808 sub, warm muted kick, zero shrill high beeps, professional compressor curve)
"""

import os
import wave
import numpy as np
import scipy.signal as signal

OUTPUT_DIR = r"c:\Users\pranj\Documents\Fuse\audio_test_options"
os.makedirs(OUTPUT_DIR, exist_ok=True)

SR = 44100
DURATION = 20.0
TOTAL_SAMPLES = int(SR * DURATION)

def save_wav(filename, samples):
    samples = np.clip(samples, -0.95, 0.95)
    int16_samples = (samples * 32767).astype(np.int16)
    path = os.path.join(OUTPUT_DIR, filename)
    with wave.open(path, 'wb') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(SR)
        wf.writeframes(int16_samples.tobytes())
    print(f"[+] Created: {path}")
    return path

def lowpass_filter(data, cutoff, order=4):
    sos = signal.butter(order, cutoff, 'lp', fs=SR, output='sos')
    return signal.sosfilt(sos, data)

def make_warm_sub_drop(duration=1.4, f_start=95, f_end=32):
    t = np.linspace(0, duration, int(SR * duration))
    freq = np.geomspace(f_start, f_end, len(t))
    env = np.exp(-3.2 * t)
    wave_data = np.sin(2 * np.pi * np.cumsum(freq) / SR) * env
    return wave_data * 0.85

def make_soft_foley_click(duration=0.03):
    t = np.linspace(0, duration, int(SR * duration))
    env = np.exp(-120 * t)
    noise = np.random.normal(0, 0.3, len(t)) * env
    filtered = lowpass_filter(noise, cutoff=2200, order=2)
    tone = np.sin(2 * np.pi * 420 * t) * env * 0.4
    return (filtered + tone) * 0.7

def make_smooth_whoosh(duration=0.6):
    t = np.linspace(0, duration, int(SR * duration))
    env = np.sin(np.pi * t / duration) ** 2.2
    noise = np.random.normal(0, 0.5, len(t)) * env
    filtered = lowpass_filter(noise, cutoff=900, order=3)
    return filtered * 0.85

# ==============================================================================
# OPTION A: Premium Cinematic Ambient Tech (Apple/Stripe Product Film)
# Warm analog chords, 45Hz sub bass, gentle rhythmic pulse, zero harshness
# ==============================================================================
def generate_option_a():
    t_full = np.linspace(0, DURATION, TOTAL_SAMPLES)
    track = np.zeros(TOTAL_SAMPLES)
    
    # 1. Warm Analog Synth Pad (Minor 9th chord progression: Dm9 -> BbMaj7 -> Gm9 -> A7sus4)
    # 5-second harmonic changes
    chord_freqs = [
        [73.42, 110.0, 146.83, 174.61, 220.0],   # Dm9 (warm, mysterious)
        [58.27, 87.31, 116.54, 146.83, 174.61],  # BbMaj7 (expanding)
        [49.00, 73.42, 98.00,  116.54, 146.83],  # Gm9 (deep resolution)
        [55.00, 82.41, 110.0,  146.83, 164.81],  # A7sus4 (forward drive)
    ]
    
    pad = np.zeros(TOTAL_SAMPLES)
    sec_per_chord = 5.0
    for idx, freqs in enumerate(chord_freqs):
        c_start = int(idx * sec_per_chord * SR)
        c_end = int((idx + 1) * sec_per_chord * SR)
        c_len = c_end - c_start
        t_c = np.linspace(0, sec_per_chord, c_len)
        fade_env = np.sin(np.pi * t_c / sec_per_chord) ** 0.8
        
        chord_signal = np.zeros(c_len)
        for f in freqs:
            # Add subtle detune for analog warmth
            tone = np.sin(2 * np.pi * f * t_c) + 0.3 * np.sin(2 * np.pi * (f * 1.002) * t_c)
            chord_signal += tone
        pad[c_start:c_end] += chord_signal * fade_env * 0.18
        
    pad = lowpass_filter(pad, cutoff=600, order=3)
    track += pad

    # 2. Deep Sub-Bass Riser and Transitions
    for trans_time in [0.0, 4.8, 9.8, 14.8]:
        sub = make_warm_sub_drop(1.6, f_start=80, f_end=35)
        st = int(trans_time * SR)
        track[st:st + len(sub)] += sub * 0.65
        
        if trans_time > 0:
            wh = make_smooth_whoosh(0.5)
            w_st = int((trans_time - 0.35) * SR)
            track[w_st:w_st + len(wh)] += wh * 0.45

    # 3. Soft Velvet Shimmer (low-amplitude subtle pink noise floor)
    pink = np.random.normal(0, 0.04, TOTAL_SAMPLES)
    pink_warm = lowpass_filter(pink, cutoff=450, order=2)
    track += pink_warm * 0.3

    return save_wav("Option_A_Cinematic_Ambient.wav", track)

# ==============================================================================
# OPTION B: Pure Tactile Foley & Sub (No Metronome, Minimal UI Sound Design)
# Clean, modern, cinematic sub-impacts + soft mechanical interface haptics
# ==============================================================================
def generate_option_b():
    track = np.zeros(TOTAL_SAMPLES)

    # Transition Sub-Impacts (Deep 35Hz cinema rumble)
    impact_moments = [0.0, 4.8, 9.8, 14.8]
    for m in impact_moments:
        sub = make_warm_sub_drop(1.8, f_start=90, f_end=30)
        st = int(m * SR)
        track[st:st + len(sub)] += sub * 0.8
        
        if m > 0:
            whoosh = make_smooth_whoosh(0.65)
            w_st = int((m - 0.45) * SR)
            track[w_st:w_st + len(whoosh)] += whoosh * 0.5

    # Scene 1: Soft typing & subtle alarm thrum
    # Very low filtered hum (60Hz) during Scene 1 emergency
    t_s1 = np.linspace(0, 4.8, int(4.8 * SR))
    s1_hum = np.sin(2 * np.pi * 55 * t_s1) * 0.25 * (np.linspace(0.2, 0.8, len(t_s1)) ** 2)
    track[:len(s1_hum)] += s1_hum

    # Subtle mechanical click pattern for code/metrics
    click_times = [0.8, 1.1, 1.4, 1.7, 2.1, 2.5, 3.0, 5.4, 5.8, 6.2, 10.4, 10.8, 11.2, 15.2, 15.6]
    for ct in click_times:
        click = make_soft_foley_click()
        st = int(ct * SR)
        track[st:st + len(click)] += click * 0.55

    # Scene 4: Uplifting clean harmonic chime (soft acoustic bell tone)
    t_bell = np.linspace(0, 3.5, int(3.5 * SR))
    bell = (np.sin(2 * np.pi * 523.25 * t_bell) * 0.6 + np.sin(2 * np.pi * 659.25 * t_bell) * 0.4) * np.exp(-1.8 * t_bell)
    bell_filtered = lowpass_filter(bell, cutoff=1400, order=2)
    st_bell = int(14.8 * SR)
    track[st_bell:st_bell + len(bell_filtered)] += bell_filtered * 0.45

    return save_wav("Option_B_Pure_Tactile_Foley.wav", track)

# ==============================================================================
# OPTION C: Warm Tech Groove (Deep 808 Sub + Muted Lo-Fi Kick, Zero Harsh Highs)
# Modern tech founder promo beat, strictly below 1500Hz
# ==============================================================================
def generate_option_c():
    track = np.zeros(TOTAL_SAMPLES)
    bpm = 118.0
    beat_len = 60.0 / bpm
    total_beats = int(DURATION / beat_len)

    # Warm Muted Kick (808 style: 85Hz down to 40Hz with smooth envelope)
    def make_warm_808_kick():
        dur = 0.35
        t = np.linspace(0, dur, int(SR * dur))
        f = np.geomspace(85, 38, len(t))
        env = np.exp(-9.0 * t)
        k = np.sin(2 * np.pi * np.cumsum(f) / SR) * env
        return k * 0.75

    # Soft Shaker / Hat (Heavily lowpassed at 1800Hz - soft paper texture, not shrill)
    def make_velvet_shaker():
        dur = 0.04
        t = np.linspace(0, dur, int(SR * dur))
        n = np.random.normal(0, 0.2, len(t)) * np.exp(-70 * t)
        return lowpass_filter(n, cutoff=1600, order=2) * 0.4

    for b in range(total_beats):
        bt = b * beat_len
        # Kick on 1 and 3
        if b % 2 == 0:
            k = make_warm_808_kick()
            st = int(bt * SR)
            track[st:st + len(k)] += k * 0.8
        # Velvet hat on eighth notes
        sh = make_velvet_shaker()
        st_sh = int((bt + beat_len * 0.5) * SR)
        if st_sh + len(sh) < TOTAL_SAMPLES:
            track[st_sh:st_sh + len(sh)] += sh * 0.35

    # Atmospheric Warm Bassline
    bass_t = np.linspace(0, DURATION, TOTAL_SAMPLES)
    sub_drone = (np.sin(2 * np.pi * 48 * bass_t) + 0.3 * np.sin(2 * np.pi * 72 * bass_t)) * 0.22
    track += lowpass_filter(sub_drone, cutoff=250, order=3)

    # Cinematic Transitions
    for trans_time in [0.0, 4.8, 9.8, 14.8]:
        sub = make_warm_sub_drop(1.5, f_start=100, f_end=35)
        st = int(trans_time * SR)
        track[st:st + len(sub)] += sub * 0.7
        if trans_time > 0:
            wh = make_smooth_whoosh(0.55)
            w_st = int((trans_time - 0.38) * SR)
            track[w_st:w_st + len(wh)] += wh * 0.45

    return save_wav("Option_C_Warm_Tech_Groove.wav", track)

if __name__ == "__main__":
    generate_option_a()
    generate_option_b()
    generate_option_c()
    print("Done creating test audio options!")
