"""Voice endpoints — Phase 3 (STT/TTS) and Phase 4 (wake word).

Mic ownership lives in the Electron renderer (MediaRecorder / getUserMedia
— the well-trodden, driver-safe way to capture audio on Windows), not in
this Python process. The renderer records short audio clips and posts
them here; the agent does all the actual local model inference, which
keeps the "local-only" boundary from spec section 2/3 intact (bytes
leave the browser layer only to hit localhost:8000, nothing external).

    POST /api/stt         multipart audio file -> {text}
    POST /api/tts         {text} -> audio/wav bytes
    POST /api/wake-check   multipart short audio clip -> {detected, transcript}
    GET  /api/voice/config -> wake word + model info, for the UI to display

Wake word note (Phase 4): this is phrase-spotting — run the cheap "tiny"
STT model over short (~2s) clips and check whether the wake word appears
in the transcript — not a trained acoustic wake-word model like Porcupine
or openWakeWord. It's the pragmatic local-only MVP the spec calls for
("local wake-word detector", section 6.1) without a custom model-training
step. Swapping in a proper trained detector later is a drop-in
replacement for this router's /api/wake-check handler.
"""

import logging
import tempfile
from pathlib import Path

from fastapi import APIRouter, HTTPException, UploadFile, Form
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict, Field

from core import stt, tts
from core.config import settings
from core.wakeword_match import match_wake_word

router = APIRouter(tags=["voice"])
MAX_AUDIO_BYTES = 6 * 1024 * 1024
_log = logging.getLogger(__name__)


class SpeechRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str = Field(min_length=1, max_length=4000)


async def _save_upload_to_tmp(file: UploadFile) -> str:
    suffix = Path(file.filename or "audio.wav").suffix.lower()
    if suffix not in {".wav", ".webm", ".ogg", ".mp3", ".mp4", ".m4a"}:
        suffix = ".webm"
    data = await file.read(MAX_AUDIO_BYTES + 1)
    if len(data) > MAX_AUDIO_BYTES:
        await file.close()
        raise HTTPException(status_code=413, detail="Recording is too large. Keep a voice command under 30 seconds.")
    if not data:
        await file.close()
        raise HTTPException(status_code=400, detail="Empty audio upload.")
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix, prefix="cortana-voice-") as tmp:
        tmp.write(data)
    await file.close()
    return tmp.name


async def _transcribe_off_loop(path: str, *, wake_tier: bool, language=None) -> str:
    """Runs Whisper on a worker thread instead of the event loop.

    This is not a micro-optimization — it is a correctness fix. Whisper
    inference is blocking, CPU-bound work that takes seconds. Calling it
    directly inside an `async def` endpoint runs it *on the event loop*,
    which stops FastAPI serving anything else for the whole duration.

    With the wake word on, the desktop app posts to /api/wake-check every
    ~4 seconds, so the loop was blocked essentially continuously and
    /api/chat never got scheduled — the UI sat on "THINKING" forever.
    run_in_threadpool hands the work to a worker thread and yields the
    loop, so chat and speech no longer compete for the same thread.
    """
    if language not in {None, "en", "hi", "auto"}:
        raise HTTPException(400, "Choose English, Hindi or automatic language detection.")
    try:
        return await run_in_threadpool(stt.transcribe, path, wake_tier=wake_tier, language=language)
    except stt.RecordingError as exc:
        raise HTTPException(400, str(exc)) from exc
    except stt.SpeechUnavailable as exc:
        raise HTTPException(503, str(exc)) from exc
    except Exception as exc:
        _log.error('Local speech recognition failed (%s).', type(exc).__name__)
        raise HTTPException(503, 'The local speech engine failed. The microphone recording reached Cortana.') from exc


@router.post("/api/stt")
async def speech_to_text(audio: UploadFile, language: str = Form(default="en")):
    path = await _save_upload_to_tmp(audio)
    try:
        text = await _transcribe_off_loop(path, wake_tier=False, language=language)
    finally:
        Path(path).unlink(missing_ok=True)
    return {"text": text}


@router.post("/api/wake-check")
async def wake_check(audio: UploadFile, language: str = Form(default="en")):
    path = await _save_upload_to_tmp(audio)
    try:
        transcript = await _transcribe_off_loop(path, wake_tier=True, language=language)
    finally:
        Path(path).unlink(missing_ok=True)

    match = match_wake_word(transcript, settings.wake_word)
    return {"detected": match["detected"], "transcript": transcript, "remainder": match["remainder"]}


@router.post('/api/stt-preview')
async def speech_preview(audio: UploadFile, language: str = Form(default='en')):
    if language not in {'en', 'hi', 'auto'}:
        raise HTTPException(400, 'Choose English, Hindi or automatic language detection.')
    path = await _save_upload_to_tmp(audio)
    try:
        text = await run_in_threadpool(stt.preview, path, language)
        match = match_wake_word(text or '', settings.wake_word)
        return {'text': text or '', 'detected': match['detected'], 'remainder': match['remainder'], 'provisional': True}
    finally:
        Path(path).unlink(missing_ok=True)


@router.post("/api/tts")
async def text_to_speech(body: SpeechRequest):
    import time
    started = time.monotonic()
    text = body.text.strip()
    if not text:
        raise HTTPException(status_code=400, detail="No text provided.")
    try:
        # SAPI5 synthesis is blocking too — same threadpool reasoning as STT.
        audio_bytes = await run_in_threadpool(tts.synthesize, text)
    except tts.VoiceUnavailable as e:
        raise HTTPException(status_code=409, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"TTS failed: {e}")
    if not audio_bytes:
        raise HTTPException(status_code=500, detail="TTS produced no audio.")
    from core.performance import record
    record('voice_synthesis', seconds=time.monotonic()-started, characters=len(text))
    return Response(content=audio_bytes, media_type="audio/wav")


@router.get("/api/voice/config")
def voice_config():
    return {
        "wake_word": settings.wake_word,
        "stt_model_size": settings.stt_model_size,
        "stt_wake_model_size": settings.stt_wake_model_size,
        "language": stt._language(settings.stt_language) or "auto",
        "local_only": True,
        "wake_method": "local_phrase_spotting",
        "speaker_authentication": False,
        "hindi_voice_available": tts.hindi_model_path().is_file(),
        "hindi_voice_engine": "piper",
    }


@router.get("/api/voice/voices")
def voices():
    try:
        return {"voices": tts.list_voices()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Could not list voices: {e}")
