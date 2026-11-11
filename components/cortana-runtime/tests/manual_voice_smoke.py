"""Offline synthetic speech smoke test; does not use a microphone or speakers.

Run from the repository root: agent\\.venv\\Scripts\\python tests\\manual_voice_smoke.py
This verifies integration, not the accuracy of the user's real voice or accent.
"""

import io
import json
import sys
import time
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "agent"))

from core import stt, tts
from core.wakeword_match import match_wake_word


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    output = ROOT / "tmp" / "voice-validation"
    output.mkdir(parents=True, exist_ok=True)
    reports = []
    for label, text in [
        ("english", "Cortana, open Chrome."),
        ("hindi", "कॉर्टाना, यूट्यूब खोलो।"),
        ("hinglish", "Cortana, YouTube kholo."),
    ]:
        start = time.monotonic()
        data = tts.synthesize(text)
        tts_seconds = round(time.monotonic() - start, 2)
        path = output / (label + ".wav")
        path.write_bytes(data)
        with wave.open(io.BytesIO(data)) as wav:
            duration = round(wav.getnframes() / wav.getframerate(), 2)
        start = time.monotonic()
        recognized = stt.transcribe(str(path))
        stt_seconds = round(time.monotonic() - start, 2)
        start = time.monotonic()
        wake_transcript = stt.transcribe(str(path), wake_tier=True)
        wake_seconds = round(time.monotonic() - start, 2)
        result = {
            "sample": label, "input": text, "transcript": recognized,
            "wake_transcript": wake_transcript, "wake": match_wake_word(wake_transcript),
            "tts_seconds": tts_seconds, "stt_seconds": stt_seconds,
            "wake_seconds": wake_seconds, "duration_seconds": duration, "wav_bytes": len(data),
        }
        reports.append(result)
        (output / "results.json").write_text(json.dumps(reports, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(result, ensure_ascii=False), flush=True)
    silence = output / "silence.wav"
    with wave.open(str(silence), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(16000)
        wav.writeframes(bytes(16000 * 2 * 2))
    reports.append({"sample": "silence", "transcript": stt.transcribe(str(silence))})
    (output / "results.json").write_text(json.dumps(reports, ensure_ascii=False, indent=2), encoding="utf-8")
    print("DONE", json.dumps(reports[-1]), flush=True)


if __name__ == "__main__":
    main()
