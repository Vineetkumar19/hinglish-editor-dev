"""Local multilingual transcription. Runtime never uploads audio or downloads weights."""

import logging
import os
import sys
import threading
import time
from pathlib import Path

_models: dict[str, object] = {}
_model_lock = threading.Lock()
_inference_lock = threading.Lock()
_preview_lock = threading.Lock()
_dll_handles = []
_gpu_unavailable = False
_warmup_state = 'on_demand'
_log = logging.getLogger(__name__)
NO_SPEECH_THRESHOLD = 0.6
MIN_AVG_LOGPROB = -1.0
MAX_AUDIO_SECONDS = 60
MIB = 1024 ** 2


class RecordingError(ValueError):
    """The uploaded recording has no usable audio."""


class SpeechUnavailable(RuntimeError):
    """No installed speech decoder can run within the current resources."""


def _prepare_cuda_libraries():
    """Locate private/existing runtime DLLs without changing Windows PATH."""
    if os.name != 'nt' or _dll_handles:
        return
    roots = [Path(sys.prefix) / 'Lib' / 'site-packages' / 'nvidia' / part / 'bin'
             for part in ('cublas', 'cudnn')]
    roots.append(Path(os.environ.get('LOCALAPPDATA', '')) / 'Programs' / 'Ollama' / 'lib' / 'ollama' / 'cuda_v12')
    found = [str(root) for root in roots if root.is_dir()]
    for root in found:
        _dll_handles.append(os.add_dll_directory(root))
    if found:
        os.environ['PATH'] = os.pathsep.join([*found, os.environ.get('PATH', '')])


def _load_audio_bounded(audio_path: str):
    """Decode locally with a duration cap before Whisper allocates model features.

    Passing an array also avoids faster-whisper 1.2.1's obsolete
    av.open(metadata_errors=...) call with modern PyAV versions.
    """
    import av
    import numpy as np

    sampling_rate = 16000
    maximum_samples = sampling_rate * MAX_AUDIO_SECONDS
    resampler = av.AudioResampler(format="s16", layout="mono", rate=sampling_rate)
    frames = []
    total = 0

    def append(frame):
        nonlocal total
        samples = frame.to_ndarray().reshape(-1)
        total += samples.size
        if total > maximum_samples:
            raise ValueError(f"Recording exceeds {MAX_AUDIO_SECONDS} seconds. Use a shorter command.")
        frames.append(samples)

    with av.open(audio_path, mode="r") as container:
        if not container.streams.audio:
            raise ValueError("The recording contains no audio.")
        if container.duration and container.duration / av.time_base > MAX_AUDIO_SECONDS + 1:
            raise ValueError(f"Recording exceeds {MAX_AUDIO_SECONDS} seconds. Use a shorter command.")
        for frame in container.decode(audio=0):
            frame.pts = None
            for converted in resampler.resample(frame):
                append(converted)
        for converted in resampler.resample(None):
            append(converted)
    if not frames or not total:
        raise ValueError("The recording contains no audio samples.")
    return np.concatenate(frames).astype(np.float32) / 32768.0


def _language(value: str | None) -> str | None:
    """Whisper expects None for detection, rather than the literal string 'auto'."""
    normalized = (value or "").strip().lower()
    return None if normalized in {"", "auto", "detect"} else normalized


def _get_model(size: str, device: str, compute_type: str):
    from core.config import ROOT_DIR, settings

    download_root = str(getattr(settings, "stt_download_root", ROOT_DIR / "models" / "whisper"))
    key = f"{size}:{device}:{compute_type}:{download_root}"
    with _model_lock:
        if key not in _models:
            if device == 'cuda':
                _prepare_cuda_libraries()
            try:
                from faster_whisper import WhisperModel
            except ImportError as exc:
                raise RuntimeError("Local speech recognition is not installed. Run Cortana setup.") from exc
            try:
                _models[key] = WhisperModel(
                    size,
                    device=device,
                    compute_type=compute_type,
                    download_root=download_root,
                    local_files_only=getattr(settings, "stt_local_files_only", True),
                    cpu_threads=getattr(settings, "stt_cpu_threads", 4),
                    num_workers=1,
                )
            except (FileNotFoundError, ValueError) as exc:
                raise RuntimeError(
                    f"Local speech model '{size}' is unavailable in {download_root}. "
                    "Run Cortana setup to download it, then retry."
                ) from exc
        return _models[key]


def _decode(audio, size: str, device: str, compute_type: str, wake_tier: bool, language=None, *, provisional=False) -> str:
    from core.config import settings

    model = _get_model(size, device, compute_type)
    if device == 'cuda':
        model.model.load_model()
    options = {
        "beam_size": 1 if provisional else 3,
        "best_of": 1,
        "temperature": 0.0,  # one bounded decode; no six-temperature retry cascade
        "max_new_tokens": 128,
        "language": _language(language or settings.stt_language),
        "task": "transcribe",  # preserve Hindi; never translate the user's request to English
        "condition_on_previous_text": False,
        "hotwords": "Cortana, WhatsApp, Instagram, Gmail, Google Calendar, Chrome kholo, YouTube kholo",
        "vad_filter": settings.stt_vad_filter,
    }
    if settings.stt_vad_filter:
        options["vad_parameters"] = {
            "min_silence_duration_ms": settings.stt_vad_min_silence_ms,
        }
    segments, info = model.transcribe(audio, **options)
    if options['language'] is None and getattr(info, 'language', None) not in {None, 'en', 'hi'}:
        # Background audio sometimes looks like an unrelated language to
        # Whisper. This mode is specifically for Hindi and English.
        probabilities = dict(info.all_language_probs or [])
        if sum(probabilities.get(code, 0) for code in ('en', 'hi')) < 0.15:
            return ''
        options['language'] = max(('en', 'hi'), key=lambda code: probabilities.get(code, 0))
        segments, _ = model.transcribe(audio, **options)
    kept = []
    # Segments is a generator: inference errors can occur here, not only in transcribe().
    for segment in segments:
        no_speech = getattr(segment, "no_speech_prob", 0.0) or 0.0
        confidence = getattr(segment, "avg_logprob", 0.0) or 0.0
        compression = getattr(segment, 'compression_ratio', 0.0) or 0.0
        if compression > 2.4 or confidence < MIN_AVG_LOGPROB or (no_speech > NO_SPEECH_THRESHOLD and confidence < -0.5):
            continue
        text = segment.text.strip()
        if text:
            kept.append(text)
    return " ".join(kept).strip()


def transcribe(audio_path: str, *, wake_tier: bool = False, language=None) -> str:
    global _gpu_unavailable
    import av
    import httpx
    import psutil
    from core.config import settings
    from core.model_profiles import ModelAdmissionError, prepare_inference
    from core.resource_broker import GPUUnavailable, gpu_slot, retain_for_next_turn
    from core.performance import record

    if not Path(audio_path).is_file():
        raise RecordingError("Audio recording is missing.")
    size = settings.stt_wake_model_size if wake_tier else settings.stt_model_size
    started = time.monotonic()
    device, precision = settings.stt_device, settings.stt_compute_type
    with _inference_lock:
        try:
            audio = _load_audio_bounded(audio_path)
        except (av.FFmpegError, ValueError) as exc:
            raise RecordingError("The recording contains invalid or unsupported audio.") from exc
        # Short commands can finish on the lightweight decoder before a cold
        # CUDA model initializes. A warm GPU still handles full recognition.
        fast_speech = (device == 'cuda' and len(audio) <= 8 * 16000 and not gpu_model_loaded()
                       and psutil.virtual_memory().available >= 512 * MIB)
        if device == 'cuda' and not _gpu_unavailable and not fast_speech:
            try:
                with gpu_slot():
                    prepare_inference('cortana-speech')
                    try:
                        text = _decode(audio, size, device, precision, wake_tier, language)
                    except Exception:
                        _release_gpu_models()
                        raise
                    retain_for_next_turn()
            except (GPUUnavailable, ModelAdmissionError, httpx.HTTPError):
                device = 'cpu'
            except RuntimeError as exc:
                detail = str(exc).lower()
                if not any(word in detail for word in ('cuda', 'cudnn', 'cublas', 'gpu', 'out of memory')):
                    raise
                # Retry GPU on a later turn after transient allocation failures.
                _gpu_unavailable = 'out of memory' not in detail
                device = 'cpu'
                _log.warning('GPU speech decoder failed; retrying locally on CPU.')
        elif device == 'cuda':
            device = 'cpu'
        if device != 'cuda':
            if settings.stt_device == 'cuda':
                available = psutil.virtual_memory().available
                size = (settings.stt_preview_model_size if fast_speech or available < 1024 * MIB
                        else settings.stt_cpu_fallback_model_size)
                precision = 'int8'
                if available < 384 * MIB or (available < 512 * MIB and not _model_cached(size, device, precision)):
                    raise SpeechUnavailable('Speech recognition needs more available RAM. Free some memory, then speak again.')
            text = _decode(audio, size, device, precision, wake_tier, language)
        record('transcription', seconds=time.monotonic()-started,
               model=size, device=device, audio_seconds=len(audio)/16000)
        return text


def _model_cached(size, device, precision):
    with _model_lock:
        prefix = f'{size}:{device}:{precision}:'
        return any(key.startswith(prefix) for key in _models)


def _release_gpu_models():
    # Only this process's Whisper instances; never touch another project.
    with _model_lock:
        for key, model in _models.items():
            if ':cuda:' in key:
                model.model.unload_model()


def gpu_model_loaded():
    with _model_lock:
        return any(':cuda:' in key and model.model.model_is_loaded for key, model in _models.items())


def preview(audio_path: str, language=None):
    """Provisional text only; drop overlapping work rather than queueing it."""
    import psutil
    from core.config import settings
    if not _preview_lock.acquire(blocking=False):
        return None
    if not _inference_lock.acquire(blocking=False):
        _preview_lock.release()
        return None
    try:
        size = settings.stt_preview_model_size
        if psutil.virtual_memory().available < (512 if _model_cached(size, 'cpu', 'int8') else 768) * MIB:
            return None
        audio = _load_audio_bounded(audio_path)
        return _decode(audio, size, 'cpu', 'int8', False, language, provisional=True)
    finally:
        _inference_lock.release()
        _preview_lock.release()


def warmup():
    global _warmup_state
    """Load installed weights off the event loop before the first command."""
    from core.config import settings
    _warmup_state = 'warming'
    try:
        model = _get_model(settings.stt_wake_model_size, settings.stt_device, settings.stt_compute_type)
        if settings.stt_device == 'cuda':
            import numpy as np
            # Weight loading alone does not initialize cuDNN's first encoder
            # kernels. Decode local silence without VAD; discard all output.
            with _inference_lock:
                segments, _ = model.transcribe(np.zeros(16000, dtype=np.float32),
                    language='en', vad_filter=False, beam_size=1, best_of=1,
                    max_new_tokens=1, condition_on_previous_text=False)
                for _ in segments:
                    pass
        if settings.stt_device != 'cuda':
            _get_model(settings.stt_preview_model_size, 'cpu', 'int8')
        _warmup_state = 'ready'
    except Exception:
        _warmup_state = 'unavailable'
        _log.warning('Speech warmup unavailable; the first recording will retry.')


def runtime_status():
    from core.config import settings
    return {'recognition': settings.stt_model_size,
            'device': 'cpu fallback' if _gpu_unavailable else settings.stt_device,
            'warmup': _warmup_state, 'precision': settings.stt_compute_type}
