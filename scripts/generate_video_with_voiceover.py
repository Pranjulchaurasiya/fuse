#!/usr/bin/env python3
"""generate_voiceover_and_subtitles.py — ElevenLabs Voiceover & Synchronized Running Subtitles for Fuse.

Generates:
1. Act-by-act audio via ElevenLabs TTS with word-level timestamps.
2. Perfect time-alignment with video cut boundaries (0:00, 0:30, 1:10, 2:05, 2:30, 2:50).
3. Studio-grade styled running subtitles (.ass) — "not so small, not so large" (Font size 24 on 1080p).
4. Merged master video: Fuse_Final_Demo_With_Subtitles.mp4 (1080p @ 30fps).
"""

import os
import sys
import json
import base64
import subprocess
import requests

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_DIR = os.path.join(REPO_ROOT, "scratch_audio_build")
INPUT_VIDEO = os.path.join(REPO_ROOT, "Fuse_Demo_Walkthrough_1080p.mp4")
OUTPUT_VIDEO = os.path.join(REPO_ROOT, "Fuse_Final_Demo_With_Subtitles.mp4")

# Act timing definitions matching assemble_demo_video.py exactly (Total 170s)
ACTS = [
    {
        "id": 1,
        "name": "ACT 1: The Problem",
        "start_time": 0.0,
        "duration": 30.0,
        "text": (
            "Hi everyone, I'm Pranjul Chaurasiya, and this is Fuse. "
            "Serverless architecture is incredible, until an infinite client retry loop or runaway agent racks up a surprise $5,000 AWS bill overnight. "
            "You don't find out until your billing alarm emails you at 3 AM. "
            "Traditional CloudWatch alarms only count raw requests. During a flash sale with 1,000 real buyers, a static alarm trips and kills paying customers. "
            "Meet Fuse—an autonomous, context-aware circuit breaker for AWS APIs powered by Amazon Bedrock."
        )
    },
    {
        "id": 2,
        "name": "ACT 2: Legitimate Spike",
        "start_time": 30.0,
        "duration": 40.0,
        "text": (
            "Let's test Scenario 1: A legitimate traffic surge. "
            "We fire 35 requests into our demo API Gateway endpoint. Notice each request originates from a unique IP and caller ID, carrying diverse search and catalog payloads. "
            "Every minute, an EventBridge schedule triggers our lightweight Poller Lambda. It queries CloudWatch metrics and checks DynamoDB for recent deployment heartbeats. "
            "When Bedrock evaluates this cycle, it correlates caller diversity with deployment context. Let's switch to our live Fuse Console. "
            "Bedrock classifies the traffic as NORMAL with 98% confidence: 'Traffic surge consists of distinct callers with diverse payloads.' Baseline stays intact, zero false alarm, zero customer disruption."
        )
    },
    {
        "id": 3,
        "name": "ACT 3: Runaway Loop & Approval Gate",
        "start_time": 70.0,
        "duration": 55.0,
        "text": (
            "Now, Scenario 2: A developer deploys a client with an unhandled retry loop without backoff jitter. "
            "We fire 40 rapid requests—all from a single caller ID with identical stuck payloads. "
            "Our Poller detects the volume spike and passes the snapshot to our Reasoner Lambda. Bedrock's Converse API immediately identifies the anomaly signature as RUNAWAY. "
            "Because this is our production workload, our safety guardrail withholds automated throttling. In dev or staging, it auto-throttles directly. In production, human judgment is protected. "
            "The target API is still serving traffic right now. As the operator, I inspect Bedrock's synthesis: 'Single caller, identical retry payload, no deployment event.' "
            "I click Approve Circuit Trip... "
            "Our Remediator Lambda immediately patches the API Gateway stage throttle to 0. "
            "We verify the throttle directly at the regional API Gateway edge. Both our live probe and raw curl confirm: HTTP 429 Too Many Requests. The runaway loop is severed before the bill can multiply!"
        )
    },
    {
        "id": 4,
        "name": "ACT 4: Under the Hood",
        "start_time": 125.0,
        "duration": 25.0,
        "text": (
            "Here's what makes Fuse production-grade: "
            "First, Isolated Control Plane: The dashboard and approval endpoints run on a completely separate API Gateway. Throttling the demo workload never locks the operator out of the control room. "
            "Second, Single-Turn Structured Bedrock: We invoke Bedrock Converse exactly once per cycle using toolConfig, enforcing typed JSON without expensive multi-turn loops. "
            "Third, Fail-Closed Cost Safety: If Bedrock ever times out, our reasoner safely defaults to RUNAWAY—guaranteeing cost protection is never compromised."
        )
    },
    {
        "id": 5,
        "name": "ACT 5: Conclusion & Links",
        "start_time": 150.0,
        "duration": 20.0,
        "text": (
            "Fuse transforms cloud cost governance from brittle static alarms into intelligent, context-aware circuit breakers. "
            "Deployed live on AWS in ap-south-1. I'm Pranjul Chaurasiya, submitting for the Ship It track at First Commit, Bharat Builds Tour 2026. "
            "The code, architecture docs, and live console are open on GitHub. Thank you!"
        )
    }
]


def load_api_key() -> str:
    env_file = os.path.join(REPO_ROOT, ".env")
    if not os.path.exists(env_file):
        raise FileNotFoundError(".env file not found")
    with open(env_file, "r", encoding="utf-8") as f:
        for line in f:
            if line.startswith("ELEVENLABS_API_KEY="):
                return line.strip().split("=", 1)[1]
    raise ValueError("ELEVENLABS_API_KEY not found in .env")


def get_audio_duration(file_path: str) -> float:
    cmd = [
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        file_path
    ]
    res = subprocess.check_output(cmd).decode().strip()
    return float(res)


def generate_act_tts(act: dict, api_key: str, voice_id: str = "pNInz6obpgDQGcFmaJgB") -> tuple:
    """Calls ElevenLabs with-timestamps for an act."""
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}/with-timestamps"
    headers = {
        "xi-api-key": api_key,
        "Content-Type": "application/json"
    }
    payload = {
        "text": act["text"],
        "model_id": "eleven_turbo_v2_5",
        "voice_settings": {
            "stability": 0.65,
            "similarity_boost": 0.80,
            "style": 0.05,
            "use_speaker_boost": True
        }
    }
    print(f"[*] Calling ElevenLabs for {act['name']} ({len(act['text'])} chars)...")
    resp = requests.post(url, headers=headers, json=payload)
    if resp.status_code != 200:
        raise RuntimeError(f"ElevenLabs error ({resp.status_code}): {resp.text}")

    data = resp.json()
    audio_bytes = base64.b64decode(data["audio_base64"])
    raw_mp3 = os.path.join(OUTPUT_DIR, f"act{act['id']}_raw.mp3")
    with open(raw_mp3, "wb") as f:
        f.write(audio_bytes)

    alignment = data.get("alignment", {})
    return raw_mp3, alignment


def extract_words_from_alignment(alignment: dict) -> list:
    """Converts character-level alignment to word-level alignment."""
    chars = alignment.get("characters", [])
    starts = alignment.get("character_start_times_seconds", [])
    ends = alignment.get("character_end_times_seconds", [])

    words = []
    current_word = []
    word_start = None
    word_end = None

    for c, s, e in zip(chars, starts, ends):
        if c.isspace():
            if current_word:
                word_text = "".join(current_word)
                words.append({
                    "word": word_text,
                    "start": word_start,
                    "end": word_end
                })
                current_word = []
                word_start = None
                word_end = None
        else:
            if word_start is None:
                word_start = s
            word_end = e
            current_word.append(c)

    if current_word:
        words.append({
            "word": "".join(current_word),
            "start": word_start,
            "end": word_end
        })

    return words


def format_ass_time(seconds: float) -> str:
    """Formats seconds as H:MM:SS.cs for ASS subtitles."""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    cs = int(round((seconds - int(seconds)) * 100))
    if cs == 100:
        cs = 99
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def create_running_subtitle_cues(all_words: list) -> list:
    """Groups words into natural running phrases (3-6 words, 1.2-2.5s duration)."""
    cues = []
    current_group = []
    group_start = None

    for w in all_words:
        if not current_group:
            group_start = w["start"]
        current_group.append(w["word"])
        current_duration = w["end"] - group_start

        # Break on punctuation or word count threshold
        ends_with_punct = any(w["word"].endswith(p) for p in [".", ",", "!", "?", "—", ":", "..."])
        if len(current_group) >= 5 or (ends_with_punct and len(current_group) >= 3) or current_duration >= 2.2:
            cues.append({
                "start": group_start,
                "end": w["end"] + 0.1,  # slight linger for readability
                "text": " ".join(current_group)
            })
            current_group = []
            group_start = None

    if current_group:
        cues.append({
            "start": group_start,
            "end": all_words[-1]["end"] + 0.2,
            "text": " ".join(current_group)
        })

    return cues


def write_ass_file(cues: list, output_ass_path: str):
    """Writes styled ASS subtitle file with optimal font size and position."""
    header = """[Script Info]
Title: Fuse Demo Subtitles
ScriptType: v4.00+
WrapStyle: 0
ScaledBorderAndShadow: yes
PlayResX: 1920
PlayResY: 1080

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: RunningSubtitle,Segoe UI,25,&H00FFFFFF,&H000000FF,&H0010141D,&HA0050810,1,0,0,0,100,100,0,0,1,2.8,1.2,2,80,80,55,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    lines = [header]
    for cue in cues:
        start_str = format_ass_time(cue["start"])
        end_str = format_ass_time(cue["end"])
        text = cue["text"].replace("\n", " ")
        lines.append(f"Dialogue: 0,{start_str},{end_str},RunningSubtitle,,0,0,0,,{text}\n")

    with open(output_ass_path, "w", encoding="utf-8") as f:
        f.writelines(lines)
    print(f"[+] ASS Subtitles written: {output_ass_path} ({len(cues)} cues)")


def main():
    print("=" * 70)
    print(" FUSE — ELEVENLABS VOICEOVER & SYNCHRONIZED RUNNING SUBTITLES")
    print("=" * 70)

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    api_key = load_api_key()

    all_aligned_words = []
    processed_act_audio_files = []

    for act in ACTS:
        print(f"\n--- Processing {act['name']} (Allocated: {act['duration']}s) ---")
        raw_mp3, alignment = generate_act_tts(act, api_key)
        raw_dur = get_audio_duration(raw_mp3)
        print(f"[*] Raw duration: {raw_dur:.2f}s (Target max: {act['duration']}s)")

        words = extract_words_from_alignment(alignment)

        # Apply smooth speed adjustment if audio exceeds act duration
        target_dur = act["duration"]
        padded_mp3 = os.path.join(OUTPUT_DIR, f"act{act['id']}_timed.wav")

        if raw_dur > target_dur:
            speed = raw_dur / (target_dur - 0.5)
            print(f"[*] Audio slightly long ({raw_dur:.2f}s > {target_dur}s). Applying atempo={speed:.3f}")
            subprocess.check_call([
                "ffmpeg", "-y", "-hide_banner", "-loglevel", "warning",
                "-i", raw_mp3,
                "-filter:a", f"atempo={speed:.4f}",
                padded_mp3
            ])
            # Adjust word timestamps by speed factor
            for w in words:
                w["start"] = (w["start"] / speed) + act["start_time"]
                w["end"] = (w["end"] / speed) + act["start_time"]
        else:
            # Audio fits naturally! Pad remainder with silence so next Act hits its exact visual cue
            pad_seconds = target_dur - raw_dur
            print(f"[*] Audio fits perfectly ({raw_dur:.2f}s <= {target_dur}s). Adding {pad_seconds:.2f}s natural pause.")
            subprocess.check_call([
                "ffmpeg", "-y", "-hide_banner", "-loglevel", "warning",
                "-i", raw_mp3,
                "-af", f"apad=pad_dur={pad_seconds:.3f}",
                "-t", str(target_dur),
                padded_mp3
            ])
            # Word timestamps are directly placed with Act offset
            for w in words:
                w["start"] = w["start"] + act["start_time"]
                w["end"] = w["end"] + act["start_time"]

        all_aligned_words.extend(words)
        processed_act_audio_files.append(padded_mp3)

    # Concatenate all 5 acts into master 170.0s audio track
    print("\n[+] Assembling Master Audio Track (170.0s)...")
    concat_txt = os.path.join(OUTPUT_DIR, "audio_concat.txt")
    with open(concat_txt, "w") as f:
        for p in processed_act_audio_files:
            f.write(f"file '{os.path.abspath(p).replace('\\', '/')}'\n")

    master_audio = os.path.join(OUTPUT_DIR, "master_voiceover.aac")
    subprocess.check_call([
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "warning",
        "-f", "concat", "-safe", "0", "-i", concat_txt,
        "-c:a", "aac", "-b:a", "192k",
        master_audio
    ])
    master_dur = get_audio_duration(master_audio)
    print(f"[+] Master audio generated: {master_audio} (Duration: {master_dur:.2f}s)")

    # Generate ASS Subtitles
    print("\n[+] Generating Synchronized Running Subtitles...")
    cues = create_running_subtitle_cues(all_aligned_words)
    ass_path = os.path.join(REPO_ROOT, "fuse_demo_subtitles.ass")
    write_ass_file(cues, ass_path)

    # Burn subtitles and combine master audio with video
    print("\n[+] Merging Video + Master Voiceover + Burned-in Subtitles...")
    ass_filter_path = os.path.abspath(ass_path).replace("\\", "/").replace(":", "\\:")
    cmd = [
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "warning",
        "-i", INPUT_VIDEO,
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
    ]
    print(f"[*] Executing ffmpeg video encode...")
    subprocess.check_call(cmd)

    size_mb = os.path.getsize(OUTPUT_VIDEO) / (1024 * 1024)
    final_dur = get_audio_duration(OUTPUT_VIDEO)
    print("\n" + "=" * 70)
    print(" [SUCCESS] FINAL DEMO VIDEO READY!")
    print(f" File:       {OUTPUT_VIDEO}")
    print(f" Duration:   {final_dur:.2f} seconds (2m 50s)")
    print(f" File Size:  {size_mb:.2f} MB")
    print(f" Resolution: 1920x1080 @ 30fps")
    print(f" Subtitles:  Burned-in running subtitles (Segoe UI, 25pt, high-contrast)")
    print("=" * 70)


if __name__ == "__main__":
    main()
