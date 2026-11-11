from dataclasses import asdict, replace
import hashlib
import json
import os
from pathlib import Path
import shutil
import wave

from hinglish_clean.detection import CleanSettings, detect_blocks, write_json
from hinglish_cut.backends import LocalSpeech, bounded_windows
from hinglish_cut.media import prepare_media, conform_video, fingerprint, extract_audio, read_audio
from hinglish_cut.model import Transcript, Word
from hinglish_cut.cutting import merge_ranges
from .speech import speech_engine


def transcribe_media(media, digest, root, settings, progress=print, engines=None, *,
                     skip_invalid_recognition=False, predecoded_audio=None):
    """Words + timing for one prepared media file, cached per file content. `engines` keeps one speech engine
    loaded across several files ({'engine': None}); the caller closes it."""
    root = Path(root)
    config = settings.speech_settings()
    engines = {} if engines is None else engines
    facts = asdict(media)
    if digest.startswith('shorts-'):        # content fingerprint: the same video copied elsewhere reuses its words
        facts = {k: v for k, v in facts.items() if k not in ('id', 'path')}
    from hinglish_cut.backends import SPEECH_ANALYSIS_VERSION
    cache_spec = {'v': 2, 'source': digest, 'media': facts, 'settings': asdict(config),
                  'speech_analysis': SPEECH_ANALYSIS_VERSION}
    from hinglish_cut.model_storage import signature
    cache_spec['local_model_selection']=signature(root)
    if settings.speech_backend == 'turbo':
        from .setup_meaning import load_manifest
        manifest = load_manifest(root)
        cache_spec.update(v=3, backend='turbo', revision=manifest['speech_revision'], beam=5, language='hi')
    key = hashlib.sha256(json.dumps(cache_spec, sort_keys=True).encode()).hexdigest()
    cache = root / 'cache' / 'semantic' / 'analysis' / key
    cache.mkdir(parents=True, exist_ok=True)
    wav = cache / 'source.wav'
    if not wav.exists():
        if predecoded_audio is not None:
            supplied = Path(predecoded_audio).resolve()
            with wave.open(str(supplied), 'rb') as audio:
                if (audio.getframerate(),audio.getnchannels(),audio.getsampwidth(),audio.getcomptype()) != (16000,1,2,'NONE'):
                    raise ValueError('The saved Reel Recreate analysis audio is not 16 kHz mono PCM.')
                if abs(audio.getnframes()/16000-media.duration) > .05:
                    raise ValueError('The saved Reel Recreate analysis audio does not match the video duration.')
            try:os.link(supplied,wav)
            except OSError:shutil.copyfile(supplied,wav)
        else:
            extract_audio(media, cache / 'source.partial.wav')
            (cache / 'source.partial.wav').replace(wav)
    completed = cache / 'transcript.json'
    if completed.exists():
        data = json.loads(completed.read_text(encoding='utf-8'))
        if not skip_invalid_recognition and any(i.startswith('invalid_recognition_skipped:') for i in data['issues']):
            from hinglish_cut.recognition_quality import InvalidRecognitionError
            raise InvalidRecognitionError('This cached transcript contains unreadable speech gaps; strict editing requires those sections to be transcribed.')
        from hinglish_cut.recognition_quality import checked_transcript
        checked_transcript(' '.join(word['text'] for word in data['words']))
        if not any(i.startswith('uncertain_alignment') for i in data['issues']):
            progress('  Reusing completed transcript')
            return Transcript(media, [Word(**w) for w in data['words']], data['speech'], data['issues']), wav
        # made before numbers could be aligned: time those windows again (the recognised text is kept)
        progress('  Improving the word timing of a saved transcript')
    speech = detect_blocks(wav, media.duration, cache / 'vad',
                           CleanSettings(device=settings.device,cpu_threads=settings.cpu_threads), progress=progress)
    # Keep neighboring clauses together for ASR context. The raw
    # VAD intervals are still used for actual silence decisions.
    windows = bounded_windows(merge_ranges(speech, gap=1.0), media.duration, config.chunk_seconds)
    words, issues = [], []

    def engine():
        if engines.get('engine') is None:
            engines['engine'] = speech_engine(settings, root)
        return engines['engine']

    def timed(n, start, end, split, text):
        audio = read_audio(wav, start, end)
        window_issues = []
        aligned = []
        if text.strip():
            try:
                aligned = engine().align(audio, text)
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
            w.text = engine().romanize(w.text)
            w.aligned = w.aligned and w.score >= config.alignment_threshold
        if split or (n and windows[n - 1][2]):
            if aligned: aligned[0].aligned = aligned[-1].aligned = False
        return {'words': [asdict(w) for w in aligned], 'issues': window_issues}

    for n, (start, end, split) in enumerate(windows):
        saved = cache / f'window-{n:06d}.json'
        progress(f'  Words and timing {n + 1}/{len(windows)} ({start:.1f}s)')
        if saved.exists():
            data = json.loads(saved.read_text(encoding='utf-8'))
            if not skip_invalid_recognition and any(i.startswith('invalid_recognition_skipped:') for i in data['issues']):
                from hinglish_cut.recognition_quality import InvalidRecognitionError
                raise InvalidRecognitionError('This speech window was unreadable; strict editing cannot reuse a skipped transcript.')
            from hinglish_cut.recognition_quality import checked_transcript
            checked_transcript(' '.join(word['text'] for word in data['words']))
            if any(i.startswith('uncertain_alignment') for i in data['issues']) and data['words']:
                again = timed(n, start, end, split, ' '.join(w['text'] for w in data['words']))
                if not again['issues']:
                    data = again
                    write_json(saved, data)
        else:
            from hinglish_cut.recognition_quality import InvalidRecognitionError
            try:
                data = timed(n, start, end, split, engine().recognize(read_audio(wav, start, end)))
            except InvalidRecognitionError:
                if not skip_invalid_recognition:raise
                progress(f'  Unreadable recognition at {start:.1f}-{end:.1f}s; excluding this text from gaming moment selection')
                data={'words':[],'issues':[f'invalid_recognition_skipped:{start:.2f}-{end:.2f}']}
            write_json(saved, data)
        words.extend(Word(**w) for w in data['words'])
        issues.extend(data['issues'])
    if not words:
        issues.append('no_transcript')
    transcript = Transcript(media, words, speech, issues)
    write_json(completed, asdict(transcript))
    return transcript, wav


def analyze_sources(paths, root, settings, progress=print, predecoded_audio=None):
    from hinglish_cut.compute_policy import heavy_device
    settings.device=heavy_device(root,settings.device)
    root = Path(root)
    engines = {}
    transcripts, wavs, errors = [], {}, []
    seen = {}
    active_settings = settings
    try:
        for i, source in enumerate(paths, 1):
            progress(f'Analyzing source {i}/{len(paths)}: {source.name}')
            try:
                digest = fingerprint(source)
                if digest in seen:
                    errors.append({'source': str(source), 'error': f'Duplicate copy skipped; same video as {seen[digest]}'})
                    continue
                seen[digest] = str(source)
                media, note = prepare_media(source, root / 'cache' / 'conformed', progress,encoder=settings.device)
                if media.rate != 30:
                    dest = root / 'cache' / 'conformed' / f'{source.stem}-{digest[:20]}-semantic-30fps.mp4'
                    from hinglish_cut.media import probe
                    if dest.exists():
                        media = probe(dest)
                    else:
                        progress('  Preparing a common 30 fps timeline')
                        if settings.device=='cuda':
                            from hinglish_cut.media import conform_video_cuda
                            media=conform_video_cuda(source,dest)
                        else:media = conform_video(source, dest)
                if media.channels > 2:
                    raise ValueError('Only mono/stereo talking-head audio is supported')
                from hinglish_cut.recognition_quality import InvalidRecognitionError
                try:
                    transcript, wav = transcribe_media(media, digest, root, active_settings, progress, engines,
                                                       predecoded_audio=predecoded_audio)
                except InvalidRecognitionError:
                    if active_settings.speech_backend == 'turbo':
                        raise
                    # Retry actual audio with the installed independent model;
                    # never substitute script text or omit an unreadable source.
                    # Free the first recognizer before loading another on GPU.
                    if engines.get('engine') is not None:
                        engines['engine'].close()
                        engines['engine'] = None
                    progress('  Retrying unreadable speech with the installed local multilingual recognizer')
                    active_settings = replace(settings, speech_backend='turbo')
                    transcript, wav = transcribe_media(media, digest, root,
                        active_settings, progress, engines, predecoded_audio=predecoded_audio)
                transcripts.append(transcript)
                wavs[media.id] = wav
            except Exception as error:
                from hinglish_cut.recognition_quality import InvalidRecognitionError
                detail = {'source': str(source), 'error': str(error)}
                if isinstance(error, InvalidRecognitionError):
                    detail['reason'] = 'invalid_recognition'
                errors.append(detail)
                progress(f'  Source needs attention: {error}')
    finally:
        if engines.get('engine') is not None: engines['engine'].close()
    return transcripts, wavs, errors
