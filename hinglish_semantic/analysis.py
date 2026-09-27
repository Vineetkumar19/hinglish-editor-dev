from dataclasses import asdict
import hashlib
import json
from pathlib import Path

from hinglish_clean.detection import CleanSettings, detect_blocks, write_json
from hinglish_cut.backends import LocalSpeech, bounded_windows
from hinglish_cut.media import prepare_media, conform_video, fingerprint, extract_audio, read_audio
from hinglish_cut.model import Transcript, Word
from hinglish_cut.cutting import merge_ranges
from .speech import speech_engine


def analyze_sources(paths, root, settings, progress=print):
    root = Path(root)
    config = settings.speech_settings()
    engine = None
    transcripts, wavs, errors = [], {}, []
    seen = {}
    try:
        for i, source in enumerate(paths, 1):
            progress(f'Analyzing source {i}/{len(paths)}: {source.name}')
            try:
                digest = fingerprint(source)
                if digest in seen:
                    errors.append({'source': str(source), 'error': f'Duplicate copy skipped; same video as {seen[digest]}'})
                    continue
                seen[digest] = str(source)
                media, note = prepare_media(source, root / 'cache' / 'conformed', progress)
                if media.rate != 30:
                    dest = root / 'cache' / 'conformed' / f'{source.stem}-{digest[:20]}-semantic-30fps.mp4'
                    from hinglish_cut.media import probe
                    if dest.exists():
                        media = probe(dest)
                    else:
                        progress('  Preparing a common 30 fps timeline')
                        media = conform_video(source, dest)
                if media.channels > 2:
                    raise ValueError('Only mono/stereo talking-head audio is supported')
                cache_spec = {'v': 2, 'source': digest, 'media': asdict(media), 'settings': asdict(config)}
                if settings.speech_backend == 'turbo':
                    from .setup_meaning import load_manifest
                    manifest = load_manifest(root)
                    cache_spec.update(v=3, backend='turbo', revision=manifest['speech_revision'], beam=5, language='hi')
                key = hashlib.sha256(json.dumps(cache_spec, sort_keys=True).encode()).hexdigest()
                cache = root / 'cache' / 'semantic' / 'analysis' / key
                cache.mkdir(parents=True, exist_ok=True)
                wav = cache / 'source.wav'
                if not wav.exists():
                    extract_audio(media, cache / 'source.partial.wav')
                    (cache / 'source.partial.wav').replace(wav)
                completed = cache / 'transcript.json'
                if completed.exists():
                    data = json.loads(completed.read_text(encoding='utf-8'))
                    transcript = Transcript(media, [Word(**w) for w in data['words']], data['speech'], data['issues'])
                    progress('  Reusing completed transcript')
                else:
                    speech = detect_blocks(wav, media.duration, cache / 'vad', CleanSettings(), progress=progress)
                    # Keep neighboring clauses together for ASR context. The raw
                    # VAD intervals are still used for actual silence decisions.
                    windows = bounded_windows(merge_ranges(speech, gap=1.0), media.duration, config.chunk_seconds)
                    words, issues = [], []
                    for n, (start, end, split) in enumerate(windows):
                        saved = cache / f'window-{n:06d}.json'
                        progress(f'  Words and timing {n + 1}/{len(windows)} ({start:.1f}s)')
                        if saved.exists():
                            data = json.loads(saved.read_text(encoding='utf-8'))
                        else:
                            if engine is None:
                                engine = speech_engine(settings, root)
                            audio = read_audio(wav, start, end)
                            text = engine.recognize(audio)
                            window_issues = []
                            aligned = []
                            if text.strip():
                                try:
                                    aligned = engine.align(audio, text)
                                    if not aligned or aligned[-1].end > end - start + .05:
                                        raise ValueError('Word alignment outside audio window')
                                except ValueError:
                                    aligned = [Word(w, 0, end - start, 0, False) for w in text.split()]
                                    window_issues.append(f'uncertain_alignment:{start:.2f}')
                            else:
                                window_issues.append(f'speech_without_transcript:{start:.2f}-{end:.2f}')
                            for w in aligned:
                                w.start += start
                                w.end += start
                                w.text = engine.romanize(w.text)
                                w.aligned = w.aligned and w.score >= config.alignment_threshold
                            if split or (n and windows[n - 1][2]):
                                if aligned: aligned[0].aligned = aligned[-1].aligned = False
                            data = {'words': [asdict(w) for w in aligned], 'issues': window_issues}
                            write_json(saved, data)
                        words.extend(Word(**w) for w in data['words'])
                        issues.extend(data['issues'])
                    if not words:
                        issues.append('no_transcript')
                    transcript = Transcript(media, words, speech, issues)
                    write_json(completed, asdict(transcript))
                transcripts.append(transcript)
                wavs[media.id] = wav
            except Exception as error:
                errors.append({'source': str(source), 'error': str(error)})
                progress(f'  Source needs attention: {error}')
    finally:
        if engine is not None: engine.close()
    return transcripts, wavs, errors
