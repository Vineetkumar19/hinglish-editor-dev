"""Offline speech for the local Storylens help call."""
from base64 import b64decode, b64encode
from collections import OrderedDict
from io import BytesIO
import json
import os
from pathlib import Path
from queue import Empty, SimpleQueue
import re
import subprocess
import sys
from threading import Lock, Thread
import wave

_CORTANA = Path('D:/Cortana')
_WHISPER = _CORTANA / (
    'models/speech/models--mobiuslabsgmbh--faster-whisper-large-v3-turbo/'
    'snapshots/0a363e9161cbc7ed1431c9597a8ceaf0c4f78fcf'
)
_VOICE_PYTHON = _CORTANA / 'agent/.venv/Scripts/python.exe'
_VOICES = {
    'en': 'en_US-lessac-high/en/en_US/lessac/high/en_US-lessac-high.onnx',
    'hi': 'hi_IN-priyamvada-medium/hi_IN-priyamvada-medium.onnx',
}
_FEATURE_TERMS = (
    'Storylens, Smart Clean, Smart Edit, Auto Captions, Smart Visuals, Long to Shorts, '
    'Premiere Pro, After Effects, DaVinci Resolve, CapCut, File Explorer, Chrome, '
    'WhatsApp, Gmail, YouTube'
)
_HINDI_TERMS = 'खोलो, दबाओ, क्लिक करो, बटन, वीडियो चुनो, फ़ोल्डर चुनो, बताओ, समझाओ, कैसे, इस्तेमाल'
_HINGLISH_TERMS = 'kholo, dabao, click karo, batao, samjhao, kaise, folder, chuno, istemaal'
_HINDI_TEXT = re.compile(r'[\u0900-\u097f]')
_HINGLISH_CUE = re.compile(r'\b(?:kholo|batao|samjhao|kaise|chuno|istemaal)\b', re.IGNORECASE)
_HINDI_PRONUNCIATIONS = {
    'cortana ai': 'कॉर्टाना ए आई',
    'cortana': 'कॉर्टाना',
    'storylens ai': 'स्टोरीलेंस ए आई',
    'storylens': 'स्टोरीलेंस',
    'smart clean': 'स्मार्ट क्लीन',
    'smart edit': 'स्मार्ट एडिट',
    'smart zoom': 'स्मार्ट ज़ूम',
    'smart visuals': 'स्मार्ट विज़ुअल्स',
    'auto captions': 'ऑटो कैप्शंस',
    'match cut finder': 'मैच कट फ़ाइंडर',
    'intro create': 'इंट्रो क्रिएट',
    'reel recreate': 'रील रीक्रिएट',
    'reference reel': 'रेफ़रेंस रील',
    'add b-roll': 'ऐड बी रोल',
    'b-roll': 'बी रोल',
    'eye contact': 'आई कॉन्टैक्ट',
    'motion graphics': 'मोशन ग्राफ़िक्स',
    'gaming highlights': 'गेमिंग हाइलाइट्स',
    'thumbnail': 'थंबनेल',
    'cinematic footage': 'सिनेमैटिक फ़ुटेज',
    'selective slow motion': 'सेलेक्टिव स्लो मोशन',
    'beat studio': 'बीट स्टूडियो',
    'image downloader': 'इमेज डाउनलोडर',
    'downloader': 'डाउनलोडर',
    'photo collector': 'फ़ोटो कलेक्टर',
    'cricket desk': 'क्रिकेट डेस्क',
    'gaming desk': 'गेमिंग डेस्क',
    'call qa': 'कॉल क्यू ए',
    'long to shorts': 'लॉन्ग टू शॉर्ट्स',
    'color grade': 'कलर ग्रेड',
    'voice clone': 'वॉइस क्लोन',
    'import template': 'इंपोर्ट टेम्पलेट',
    'template aligner': 'टेम्पलेट अलाइनर',
    'template text': 'टेम्पलेट टेक्स्ट',
    'copy paste': 'कॉपी पेस्ट',
    'template library': 'टेम्पलेट लाइब्रेरी',
    'animation presets': 'ऐनिमेशन प्रीसेट्स',
    'cinematic text': 'सिनेमैटिक टेक्स्ट',
    'editor handoff': 'एडिटर हैंडऑफ़',
    'sound design': 'साउंड डिज़ाइन',
    'publishing studio': 'पब्लिशिंग स्टूडियो',
    'schedule post': 'शेड्यूल पोस्ट',
    'scheduled posts': 'शेड्यूल्ड पोस्ट्स',
    'prepare and post': 'प्रिपेयर ऐंड पोस्ट',
    'premiere pro': 'प्रीमियर प्रो',
    'premiere': 'प्रीमियर',
    'after effects': 'आफ़्टर इफ़ेक्ट्स',
    'davinci resolve': 'दा विंची रिज़ॉल्व',
    'davinci': 'दा विंची',
    'capcut': 'कैप कट',
    'file explorer': 'फ़ाइल एक्सप्लोरर',
    'chrome': 'क्रोम',
    'youtube': 'यूट्यूब',
    'instagram': 'इंस्टाग्राम',
    'whatsapp': 'व्हाट्सऐप',
    'gmail': 'जीमेल',
    'shorts': 'शॉर्ट्स',
    'video': 'वीडियो',
    'audio': 'ऑडियो',
    'folder': 'फ़ोल्डर',
    'file': 'फ़ाइल',
    'upload': 'अपलोड',
    'render': 'रेंडर',
    'generate': 'जनरेट',
    'export': 'एक्सपोर्ट',
    'preview': 'प्रीव्यू',
    'api': 'ए पी आई',
    'xml': 'एक्स एम एल',
    'srt': 'एस आर टी',
    'mp4': 'एम पी फ़ोर',
}
_HINDI_NAME = re.compile(
    r'(?<![A-Za-z0-9])(?:' +
    '|'.join(re.escape(name) for name in sorted(_HINDI_PRONUNCIATIONS, key=len, reverse=True))
    + r')(?![A-Za-z0-9])',
    re.IGNORECASE,
)
_MODEL_LOCK = Lock()
_VOICE_LOCK = Lock()
_SAMPLE_RATE = 16000
_MAX_SECONDS = 25
_model = None
_cuda_prepared = False
_worker = None
_responses = None
# Repeat acknowledgements do not need another neural synthesis. Keep only exact
# voice/text matches in bounded RAM; never persist private call text or audio.
_voice_cache = OrderedDict()
_voice_cache_bytes = 0
_VOICE_CACHE_LIMIT = 16 * 1024 * 1024
_VOICE_CACHE_ENTRIES = 96


def _cache_voice(key, audio):
    global _voice_cache_bytes
    if len(audio) > _VOICE_CACHE_LIMIT:
        return
    previous = _voice_cache.pop(key, None)
    if previous is not None:
        _voice_cache_bytes -= len(previous)
    _voice_cache[key] = audio
    _voice_cache_bytes += len(audio)
    while len(_voice_cache) > _VOICE_CACHE_ENTRIES or _voice_cache_bytes > _VOICE_CACHE_LIMIT:
        _, removed = _voice_cache.popitem(last=False)
        _voice_cache_bytes -= len(removed)


def _voice_path(language):
    return _CORTANA / 'models/tts' / _VOICES[language]


def available(root):
    """Check installed files without allocating either model."""
    cuda = Path(root) / 'tools/cuda-reference-runtime/bin'
    return (
        (_WHISPER / 'model.bin').is_file()
        and (cuda / 'cublas64_12.dll').is_file()
        and (cuda / 'cudnn64_9.dll').is_file()
        and _VOICE_PYTHON.is_file()
        and all(_voice_path(language).is_file() and Path(str(_voice_path(language)) + '.json').is_file()
                for language in _VOICES)
    )


def _load(root):
    global _model, _cuda_prepared
    if _model is None:
        if not _cuda_prepared:
            from .caption_compute import prepare_runtime
            prepare_runtime(root, {'device': 'cuda'})
            _cuda_prepared = True
        from faster_whisper import WhisperModel
        _model = WhisperModel(
            str(_WHISPER), device='cuda', compute_type='int8_float16',
            local_files_only=True, num_workers=1,
        )
    return _model


def _audio(data):
    import av
    import numpy as np

    if not 0 < len(data) <= 1280 * 1024:
        raise ValueError('The call audio was empty or too large.')
    samples = 0
    chunks = []
    resampler = av.AudioResampler(format='flt', layout='mono', rate=_SAMPLE_RATE)

    def append(frame):
        nonlocal samples
        samples += frame.samples
        if samples > _MAX_SECONDS * _SAMPLE_RATE:
            raise ValueError('Please keep each question under 25 seconds.')
        chunks.append(frame.to_ndarray().reshape(-1))

    try:
        with av.open(BytesIO(data)) as source:
            if not source.streams.audio:
                raise ValueError('The call recording contains no audio.')
            for frame in source.decode(audio=0):
                frame.pts = None
                for converted in resampler.resample(frame):
                    append(converted)
            for converted in resampler.resample(None):
                append(converted)
    except av.FFmpegError as error:
        raise ValueError('The call recording could not be decoded.') from error
    return np.concatenate(chunks) if chunks else np.empty(0, dtype=np.float32)


def recognition_terms(control_names=()):
    # Every product name remains available even while another tool is open.
    # UI-local button hints must not replace Photo Collector, Voice Clone, etc.
    from .support_call_knowledge import FEATURES, TOPICS
    names = ['Storylens', 'Cortana', 'Topaz Video AI', 'Microsoft Excel', 'Lionel Messi']
    names += [row[0] for row in FEATURES.values()]
    names += [row['name'] for row in TOPICS if 'voice' in row]
    names += ['Financial Tracker', 'AI Agents section']
    names += [str(name)[:60] for name in control_names[:10]]
    return ' '.join(dict.fromkeys(names))


def _decode(model, samples, language_hint, control_names=()):
    explicit = language_hint if language_hint in ('hi', 'en') else None
    terms = recognition_terms(control_names)
    # Keep product names first. Whisper limits hotwords to half its text window;
    # verbose Hindi command hints previously displaced real feature names.
    options = {
        'beam_size': 3,
        'best_of': 1,
        'temperature': 0,
        'max_new_tokens': 128,
        'condition_on_previous_text': False,
        'hotwords': terms,
        'vad_filter': True,
        'vad_parameters': {'min_silence_duration_ms': 450, 'speech_pad_ms': 200},
    }

    if explicit == 'hi':
        options['initial_prompt'] = 'हिंदी और English में Storylens के features की बातचीत।'

    def decode(language):
        segments, info = model.transcribe(samples, language=language, **options)
        text = ' '.join(
            segment.text.strip() for segment in segments
            if segment.avg_logprob >= -1 and segment.compression_ratio <= 2.4
            and (segment.no_speech_prob <= 0.6 or segment.avg_logprob >= -0.5)
        ).strip()
        return text, info

    text, info = decode(explicit)
    language = info.language
    if language not in ('en', 'hi'):
        probabilities = dict(info.all_language_probs or ())
        if probabilities.get('en', 0) + probabilities.get('hi', 0) < 0.15:
            return '', ''
        language = max(('en', 'hi'), key=lambda key: probabilities.get(key, 0))
        text, _ = decode(language)
    if not explicit and (_HINDI_TEXT.search(text) or _HINGLISH_CUE.search(text)):
        language = 'hi'
    # In a short who-is question the recognizer can spell the surname as
    # the adjective. Leave ordinary uses and longer names such as Messy Mya alone.
    if re.fullmatch(r"who(?:\s+is|['\u2019]s)\s+(?:lionel\s+)?messy[.?!]?", text, re.I):
        text = re.sub(r'messy', 'Messi', text, flags=re.I)
    return text, language


def _speech_text(text, language):
    if language != 'hi':
        return text
    return _HINDI_NAME.sub(lambda match: _HINDI_PRONUNCIATIONS[match[0].lower()], text)


def warm(root):
    """Load the CUDA decoder and initialize its first inference kernels."""
    import numpy as np

    with _MODEL_LOCK:
        cold = _model is None
        model = _load(root)
        if cold:
            segments, _ = model.transcribe(
                np.zeros(_SAMPLE_RATE, dtype=np.float32), language='en',
                beam_size=1, max_new_tokens=8, temperature=0,
            )
            list(segments)


def transcribe(root, data, language_hint='auto', control_names=()):
    """Return the transcript and an English/Hindi language code for this turn."""
    import numpy as np

    samples = _audio(data)
    if samples.size < _SAMPLE_RATE // 5 or np.max(np.abs(samples)) < 0.001:
        return '', ''
    with _MODEL_LOCK:
        return _decode(_load(root), samples, language_hint, control_names)


def _read_responses(worker, responses):
    try:
        for line in worker.stdout:
            responses.put(line)
    finally:
        responses.put(None)


def _stop_worker():
    global _worker, _responses
    worker, _worker, _responses = _worker, None, None
    if worker is None:
        return
    try:
        worker.stdin.close()
    except OSError:
        pass
    try:
        worker.wait(timeout=0.5)
    except subprocess.TimeoutExpired:
        worker.kill()
        worker.wait(timeout=2)
    worker.stdout.close()


def _start_worker():
    global _worker, _responses
    _worker = subprocess.Popen(
        [str(_VOICE_PYTHON), '-B', '-u', str(Path(__file__).resolve()), '--voice-worker'],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
        creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0),
    )
    _responses = SimpleQueue()
    Thread(target=_read_responses, args=(_worker, _responses), daemon=True).start()


def synthesize(root, text, language):
    """Return a local WAV from the cached, personal-use Piper voices."""
    text = text.strip()[:900]
    if not text:
        raise ValueError('The assistant reply was empty.')
    hindi_characters = sum('\u0900' <= char <= '\u097f' for char in text)
    language = 'hi' if hindi_characters and (language == 'hi' or hindi_characters * 4 >= len(text)) else 'en'
    key = (language, _speech_text(text, language))
    with _VOICE_LOCK:
        cached = _voice_cache.get(key)
        if cached is not None:
            _voice_cache.move_to_end(key)
            return cached
        if _worker is None or _worker.poll() is not None:
            _stop_worker()
            _start_worker()
        request = json.dumps({'text': key[1], 'language': language}).encode('utf-8') + b'\n'
        try:
            _worker.stdin.write(request)
            _worker.stdin.flush()
            line = _responses.get(timeout=15)
            if not line:
                raise RuntimeError('The local voice process exited.')
            answer = json.loads(line)
            if not answer.get('audio'):
                raise RuntimeError('The local voice model could not synthesize the reply.')
            audio = b64decode(answer['audio'], validate=True)
            _cache_voice(key, audio)
            return audio
        except (BrokenPipeError, OSError, ValueError, Empty, RuntimeError) as error:
            _stop_worker()
            raise RuntimeError('Storylens could not start or read its local speaking voice.') from error


def release():
    """Free call-owned speech resources without touching other Ollama models."""
    global _model, _voice_cache_bytes
    with _MODEL_LOCK:
        model, _model = _model, None
        if model is not None:
            model.model.unload_model()
    with _VOICE_LOCK:
        _stop_worker()
        _voice_cache.clear()
        _voice_cache_bytes = 0


def _voice_worker():
    # The user's installed Cortana environment already includes the offline
    # Piper runtime. Read only its existing voice weights and send WAV on stdout.
    from piper import PiperVoice, SynthesisConfig

    voices = {}
    rates = {'en': 1.16, 'hi': 1.07}
    for line in sys.stdin.buffer:
        try:
            request = json.loads(line)
            language = request['language']
            if language not in voices:
                voices[language] = PiperVoice.load(_voice_path(language), use_cuda=False)
            target = BytesIO()
            voice = voices[language]
            config = SynthesisConfig(length_scale=voice.config.length_scale * rates[language])
            with wave.open(target, 'wb') as output:
                output.setparams((1, 2, voice.config.sample_rate, 0, 'NONE', 'not compressed'))
                pause = bytes(2 * round(voice.config.sample_rate * 0.14))
                for index, sentence in enumerate(voice.synthesize(request['text'], syn_config=config)):
                    if index:
                        output.writeframes(pause)
                    output.writeframes(sentence.audio_int16_bytes)
            answer = {'audio': b64encode(target.getvalue()).decode('ascii')}
        except (KeyError, OSError, ValueError, RuntimeError):
            answer = {'error': 'The installed local voice could not speak.'}
        print(json.dumps(answer), flush=True)


if __name__ == '__main__' and sys.argv[1:] == ['--voice-worker']:
    _voice_worker()
