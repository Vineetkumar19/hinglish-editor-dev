"""Compare ASR context on the retained short edit fixture without changing its text."""
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    from hinglish_cut.backends import LocalSpeech, bounded_windows
    from hinglish_cut.media import read_audio
    from hinglish_cut.pipeline import load_settings
    fixture = ROOT / 'output/validation/new-laptop/edit-control-469f11cff8'
    cached = next((fixture/'cache').glob('*.json'))
    data = json.loads(cached.read_text(encoding='utf-8'))
    wav = cached.with_suffix('.wav')
    duration = data['media']['duration']
    speech = data['speech']
    settings = load_settings(ROOT/'config.rtx5070.json', 'cuda', True)
    engine = LocalSpeech(settings, ROOT/'models')
    windows = bounded_windows(speech, duration, settings.chunk_seconds)
    variants = {'existing_short_windows': [(a,b) for a,b,_ in windows],
        'joined_speech': [(windows[0][0], windows[-1][1])],
        'joined_with_context': [(max(0,speech[0][0]-.6), min(duration,speech[-1][1]+.6))],
        'whole_six_second_clip': [(0,duration)]}
    results = {}
    try:
        for label, spans in variants.items():
            t = time.monotonic()
            texts = [engine.recognize(read_audio(wav,a,b)) for a,b in spans]
            results[label] = {'text':' '.join(texts), 'spans':spans, 'seconds':round(time.monotonic()-t,2)}
            print(label+': '+results[label]['text'], flush=True)
    finally:
        engine.close()
    (ROOT/'output/validation/new-laptop/speech-context-comparison.json').write_text(json.dumps(results,indent=2,ensure_ascii=False),encoding='utf-8')


if __name__ == '__main__':
    main()
