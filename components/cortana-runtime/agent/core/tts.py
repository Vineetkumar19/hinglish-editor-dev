"""Local Windows speech, serialized on one COM thread with language-aware voices."""

import io
import os
import re
import tempfile
import threading
import wave
from functools import lru_cache
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from pathlib import Path
from types import SimpleNamespace

_engine = None
_hindi_voice = None
_english_voice = None
_submit_lock = threading.Lock()
_FEMALE_NAME_HINTS = ("zira", "hazel", "eva", "aria", "jenny", "susan", "heera")


class VoiceUnavailable(RuntimeError):
    pass


def _initialize_com():
    if os.name == "nt":
        import ctypes
        ctypes.windll.ole32.CoInitialize(None)


# SAPI objects are apartment-bound. A lock around arbitrary FastAPI workers is
# insufficient: the engine must always be created and used on the same thread.
_worker = ThreadPoolExecutor(max_workers=1, thread_name_prefix="cortana-speech", initializer=_initialize_com)


def _get_engine():
    global _engine
    if _engine is None:
        import pyttsx3
        _engine = pyttsx3.init("sapi5" if os.name == "nt" else None)
    return _engine


def _voice_languages(voice) -> list[str]:
    result = []
    for language in getattr(voice, "languages", []) or []:
        if isinstance(language, bytes):
            language = language.decode("utf-8", errors="ignore")
        value = str(language).lower().lstrip("\x00\x01\x02\x03\x04\x05\x06\x07\x08").replace("_", "-")
        if value in {"439", "0439"}:
            value = "hi-in"
        elif value in {"409", "0409", "809", "0809"}:
            value = "en"
        result.append(value)
    # Older SAPI wrappers do not populate the languages field.
    identity = (str(getattr(voice, "id", "")) + " " + str(getattr(voice, "name", ""))).lower()
    if "hi-in" in identity or "hiin" in identity or "heera" in identity or "hindi" in identity:
        result.append("hi-in")
    if "en-us" in identity or "enus" in identity or "en-gb" in identity or "engb" in identity:
        result.append("en")
    return list(dict.fromkeys(result))


def _pick_voice_id(voices, language: str = "en") -> str | None:
    candidates = [v for v in voices if any(item.split("-")[0] == language for item in _voice_languages(v))]
    # Hindi text must not silently be read through an English voice that drops it.
    if not candidates:
        return None
    for voice in candidates:
        if (getattr(voice, "gender", "") or "").lower() == "female":
            return voice.id
    for voice in candidates:
        if any(hint in (getattr(voice, "name", "") or "").lower() for hint in _FEMALE_NAME_HINTS):
            return voice.id
    return candidates[0].id


def hindi_model_path() -> Path:
    from core.config import ROOT_DIR, settings
    return Path(getattr(
        settings, "tts_hindi_model_path",
        ROOT_DIR / "models" / "tts" / "hi_IN-priyamvada-medium" / "hi_IN-priyamvada-medium.onnx",
    ))


def _synthesize_hindi(text: str) -> bytes:
    """Ungated local Piper voice; attribution/license are stored beside the weights."""
    global _hindi_voice
    model = hindi_model_path()
    if not model.is_file() or not Path(str(model) + ".json").is_file():
        raise VoiceUnavailable(
            "The local Hindi voice is not installed. Run Cortana setup. The reply is available as text."
        )
    if _hindi_voice is None:
        from piper import PiperVoice
        _hindi_voice = PiperVoice.load(model, use_cuda=False)
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as output:
        _hindi_voice.synthesize_wav(text, output)
    return buffer.getvalue()


def _sapi_voices(speaker):
    result = []
    for token in speaker.GetVoices():
        result.append(SimpleNamespace(
            id=token.Id,
            name=token.GetDescription(),
            gender=token.GetAttribute("Gender"),
            languages=token.GetAttribute("Language").split(";"),
            token=token,
        ))
    return result


def _synthesize_windows(text: str, language: str) -> bytes:
    """Render directly to a WAV; no pyttsx3 message pump or speaker playback.

    SAPI's file stream generates no speech-completion events. Relying on
    pyttsx3.runAndWait() therefore hung on the second request on this machine.
    """
    from comtypes.client import CreateObject
    from core.config import settings

    speaker = CreateObject("SAPI.SpVoice")
    voices = _sapi_voices(speaker)
    selected_id = settings.tts_voice_id or _pick_voice_id(voices, language)
    selected = next((item for item in voices if item.id == selected_id), None)
    if selected is None:
        raise VoiceUnavailable(f"No suitable {language} Windows speech voice is installed. The reply is available as text.")
    if not any(item.startswith(language) for item in _voice_languages(selected)):
        raise VoiceUnavailable("The selected voice does not support this reply's language. The reply is available as text.")
    speaker.Voice = selected.token
    speaker.Rate = max(-10, min(10, round((settings.tts_rate - 180) / 20)))
    speaker.SynchronousSpeakTimeout = 10000
    with tempfile.TemporaryDirectory(prefix="cortana-tts-") as temporary:
        path = Path(temporary) / "speech.wav"
        stream = CreateObject("SAPI.SpFileStream")
        stream.Open(str(path), 3, False)  # SSFMCreateForWrite; no event embedding
        try:
            speaker.AudioOutputStream = stream
            speaker.Speak(text, 16)  # synchronous SVSFIsNotXML: never interpret model text as XML
        finally:
            stream.Close()
        data = path.read_bytes()
        if len(data) < 44 or not data.startswith(b"RIFF"):
            raise RuntimeError("Windows speech returned no playable WAV audio.")
        return data


def _synthesize_on_worker(text: str) -> bytes:
    from core.config import ROOT_DIR, settings

    language = "hi" if re.search(r"[\u0900-\u097F]", text) else "en"
    english_model = ROOT_DIR / "models" / "tts" / "en_US-lessac-high" / "en" / "en_US" / "lessac" / "high" / "en_US-lessac-high.onnx"
    if language == "en" and not settings.tts_voice_id and english_model.is_file():
        global _english_voice
        if _english_voice is None:
            from piper import PiperVoice
            _english_voice = PiperVoice.load(english_model, use_cuda=False)
        buffer = io.BytesIO()
        with wave.open(buffer, "wb") as output:
            _english_voice.synthesize_wav(text, output)
        return buffer.getvalue()
    # Piper avoids requiring an administrator to install an extra Windows voice.
    # It shares the dedicated worker so two speech requests cannot overlap.
    if language == "hi" and settings.tts_voice_id in {"", "piper:hi_IN-priyamvada-medium"} and hindi_model_path().is_file():
        return _synthesize_hindi(text)
    if os.name == "nt":
        return _synthesize_windows(text, language)
    engine = _get_engine()
    installed = engine.getProperty("voices") or []
    voice_id = settings.tts_voice_id or _pick_voice_id(installed, language)
    if settings.tts_voice_id and not any(v.id == voice_id for v in installed):
        raise VoiceUnavailable("The configured Windows speech voice is not installed.")
    if language == "hi":
        chosen = next((v for v in installed if v.id == voice_id), None)
        if chosen is None or not any(lang.startswith("hi") for lang in _voice_languages(chosen)):
            raise VoiceUnavailable(
                "A Hindi Windows speech voice is not installed or selected. "
                "The reply is available as text; install a Hindi voice in Windows language settings to hear it."
            )
    if not voice_id:
        raise VoiceUnavailable("No suitable English Windows speech voice is installed. The reply is available as text.")
    engine.setProperty("voice", voice_id)
    engine.setProperty("rate", settings.tts_rate)
    with tempfile.TemporaryDirectory(prefix="cortana-tts-") as tmp:
        destination = Path(tmp) / "speech.wav"
        try:
            engine.save_to_file(text, str(destination))
            engine.runAndWait()
            data = destination.read_bytes() if destination.exists() else b""
            if len(data) < 44 or not data.startswith(b"RIFF"):
                raise RuntimeError("Windows speech returned no playable WAV audio.")
            return data
        except Exception:
            engine.stop()
            raise


def _run(operation, *args, timeout=45):
    with _submit_lock:
        job = _worker.submit(operation, *args)
        try:
            return job.result(timeout=timeout)
        except TimeoutError as exc:
            job.cancel()
            raise RuntimeError("Windows speech timed out. The reply is available as text.") from exc


@lru_cache(maxsize=8)
def _routine_audio(text, voice_id, rate):
    return _run(_synthesize_on_worker, text)


def synthesize(text: str) -> bytes:
    from core.config import settings
    if text in {
        'Hello Master Chief.',
        'Hello Master Chief. Say Hey Cortana when you need me.',
        "Hello Master Chief. I'm listening.",
        'Yes, Master Chief. I can hear you.',
        "I'm doing well, Master Chief. Ready to help.",
    }:
        return _routine_audio(text, settings.tts_voice_id, settings.tts_rate)
    return _run(_synthesize_on_worker, text)


def _list_voices_on_worker() -> list[dict]:
    if os.name == "nt":
        from comtypes.client import CreateObject
        installed = _sapi_voices(CreateObject("SAPI.SpVoice"))
    else:
        installed = _get_engine().getProperty("voices") or []
    english = _pick_voice_id(installed, "en")
    hindi = _pick_voice_id(installed, "hi")
    result = [
        {
            "id": voice.id,
            "name": voice.name,
            "gender": getattr(voice, "gender", None),
            "languages": _voice_languages(voice),
            "auto_selected": voice.id == english,
            "hindi_selected": voice.id == hindi,
        }
        for voice in installed
    ]
    if hindi_model_path().is_file():
        result.append({
            "id": "piper:hi_IN-priyamvada-medium",
            "name": "Priyamvada — local Hindi (Piper)",
            "gender": "Female",
            "languages": ["hi-in"],
            "auto_selected": False,
            "hindi_selected": True,
            "dataset_license": "CC-BY-NC-SA-4.0",
        })
    return result


def list_voices() -> list[dict]:
    return _run(_list_voices_on_worker, timeout=15)
