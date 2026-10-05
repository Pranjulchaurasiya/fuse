import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from scripts.build_enhanced_real_voice_video import ACT_CONFIGS, align_act_script_with_audio, create_running_subtitles

with open('transcription.json', encoding='utf-8') as f:
    d = json.load(f)
raw_words = [w for w in d['words'] if w['type'] == 'word']

for cfg in ACT_CONFIGS:
    w_start_idx, w_end_idx = cfg['audio_range']
    audio_slice = raw_words[w_start_idx : w_end_idx + 1]
    aligned = align_act_script_with_audio(cfg['script_words'], audio_slice)
    for w in aligned:
        w['v_start'] = w['start']
        w['v_end'] = w['end']
    cues = create_running_subtitles(aligned)
    print("=" * 60)
    print(f"{cfg['name']} ({len(cues)} cues):")
    for c in cues:
        dur = c['end'] - c['start']
        print(f"  [{dur:.2f}s | {len(c['text'].split())}w | {len(c['text'])}c] {c['text']}")
