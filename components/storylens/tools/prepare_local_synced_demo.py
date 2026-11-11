"""Prepare acoustic word anchors and offline reference retrieval, sequentially.

This worker does not choose the creative edit. The director receives its measured
words and makes the choices separately. Originals and prior trials are untouched.
"""
import gc, json, os, subprocess, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
OUT = ROOT / 'output/reference-analysis/local-documentary-synced'
OUT.mkdir(parents=True, exist_ok=True)
os.environ['HF_HUB_OFFLINE'] = '1'
os.environ['TRANSFORMERS_OFFLINE'] = '1'


def save(name, data):
    (OUT / name).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf8')


def main():
    import numpy as np
    from imageio_ffmpeg import get_ffmpeg_exe
    source = next(x['path'] for x in json.loads((ROOT / 'output/reference-analysis/crick-edit-editing-style/inventory.json').read_text(encoding='utf8')) if x['slug'] == 'reference-08')
    save('source.json', {'path': source, 'start': 0, 'seconds': 60})
    ffmpeg = get_ffmpeg_exe()
    args = [ffmpeg, '-v', 'error', '-nostdin', '-threads', '2', '-i', source, '-t', '60', '-vn', '-ac', '1', '-ar', '16000', '-f', 'f32le', '-']
    audio = np.frombuffer(subprocess.check_output(args), dtype='<f4').copy()
    if not (OUT / 'recognized-words.json').exists():
        from faster_whisper import WhisperModel
        manifest = json.loads((ROOT / 'models/meaning-upgrade.json').read_text())
        model = WhisperModel(manifest['speech_path'], device='cpu', compute_type='int8', cpu_threads=2, num_workers=1, local_files_only=True)
        segments, info = model.transcribe(audio, language='hi', beam_size=3, temperature=0, word_timestamps=True,
            condition_on_previous_text=False, vad_filter=False,
            initial_prompt='क्रिकेट डॉक्यूमेंटरी। डेल स्टेन। सचिन तेंदुलकर। रोहित शर्मा। टेस्ट मैच। विकेट। 150 किलोमीटर प्रति घंटा।',
            hallucination_silence_threshold=1)
        lines, words = [], []
        for segment in segments:
            lines.append({'start': segment.start, 'end': segment.end, 'text': segment.text.strip()})
            words.extend({'text': w.word.strip(), 'start': w.start, 'end': w.end, 'probability': w.probability} for w in segment.words or [])
            print(f'Local acoustic transcript through {segment.end:.2f}s', flush=True)
            save('recognized-words.partial.json', words)
        save('recognized-words.json', words)
        save('recognized-segments.json', lines)
        del model
        gc.collect()
    words = json.loads((OUT / 'recognized-words.json').read_text(encoding='utf8'))
    if not (OUT / 'aligned-words.json').exists():
        from hinglish_cut.backends import LocalSpeech
        from hinglish_cut.model import Settings
        backend = LocalSpeech(Settings(device='cpu', cpu_threads=2, offline=True), ROOT / 'models')
        # Bounded ASR segments supply the text; the separate CTC model estimates
        # phonetic onsets. Numeric tokens keep their acoustic ASR timing rather
        # than falsely presenting interpolated digit timings as forced alignment.
        result, issues = [], []
        lines = json.loads((OUT / 'recognized-segments.json').read_text(encoding='utf8'))
        for line in lines:
            selected = [w for w in words if line['start']-.01 <= w['start'] < line['end']-.001]
            if not selected:
                continue
            begin = max(0, line['start']-.12)
            end = min(60, line['end']+.12)
            try:
                aligned = backend.align(audio[round(begin*16000):round(end*16000)], ' '.join(w['text'] for w in selected))
                if len(aligned) != len(selected):
                    raise ValueError('Word mapping changed')
                for original, word in zip(selected, aligned):
                    acoustic = word.score >= .08 and not any(c.isdigit() for c in original['text'])
                    result.append({**original, 'asr_start': original['start'], 'asr_end': original['end'],
                        'start': begin+word.start if acoustic else original['start'],
                        'end': begin+word.end if acoustic else original['end'],
                        'score': word.score, 'timing_source': 'local MMS forced alignment' if acoustic else 'local Whisper acoustic timestamp',
                        'alignment_disagreement_seconds': round(begin+word.start-original['start'], 3)})
            except ValueError as error:
                issues.append({'start': begin, 'error': str(error)})
                result.extend({**w, 'timing_source': 'local Whisper acoustic timestamp', 'score': 0} for w in selected)
            print(f'Acoustic alignment through {end:.2f}s', flush=True)
        for i, w in enumerate(result):
            w['id'] = f'w{i:03}'
        save('aligned-words.json', result)
        save('alignment-receipt.json', {'local_only': True, 'asr': 'faster-whisper large-v3-turbo CPU int8 beam3',
            'aligner': 'MMS 300m 1130 forced aligner CPU', 'words': len(result), 'seconds': len(audio)/16000,
            'issues': issues, 'limit': 'ASR text and phonetic onsets are estimates, not human-certified word boundaries. Numeric tokens retain ASR timing.'})
        backend.close()
        del backend
        gc.collect()
    if not (OUT / 'retrieved-memory.json').exists():
        from hinglish_niche.style_memory import StyleEmbedder, search
        embedder = StyleEmbedder(ROOT)
        rows = []
        for style in ['beneath-documentary-edit', 'crick-edit-editing-style']:
            for purpose, query, kinds in [
                ('motion', 'Cricket documentary narration player name photo reveal typography statistics emphasis camera motion narrative pacing', ['approved-animation','reviewed-chapter','scene-evidence','reviewed-pattern']),
                ('sound', 'Cricket documentary voice narration sound effects whoosh impact transitions audio synchronisation rhythm', ['sound-event-candidate','audio-window','rhythm-region'])]:
                matches = search(ROOT, style, query, 3, embedder=embedder, kinds=kinds)
                rows.extend({'style': style, 'purpose': purpose, 'source': r['source'], 'start': r['start'], 'end': r['end'], 'reference': r['text']} for r in matches)
        save('retrieved-memory.json', {'embedding_model': embedder.model_name, 'local_only': True, 'examples': rows})
    print('PREPARATION COMPLETE', flush=True)


if __name__ == '__main__':
    main()
