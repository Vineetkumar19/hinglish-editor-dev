"""Voice contract tests use fixtures/mocks, never the microphone or cloud services."""

import io
import sys
import tempfile
import threading
import time
import unittest
import wave
from contextlib import nullcontext
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "agent"))

from fastapi import FastAPI
from fastapi.testclient import TestClient
from core import stt, tts
from core.config import settings
from core.wakeword_match import match_wake_word
from routers import voice


def wav_bytes(seconds=1, sample_rate=16000):
    stream = io.BytesIO()
    with wave.open(stream, "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(sample_rate)
        output.writeframes(bytes(int(sample_rate * seconds) * 2))
    return stream.getvalue()


class WakeWordTests(unittest.TestCase):
    def test_preserves_multilingual_command_exactly(self):
        for wake in ("Cortana", "कॉर्टाना", "कोर्टाना", "Core tana"):
            result = match_wake_word(f"Hey {wake}, 25 दिसंबर को 6:30 PM पर ₹500 याद दिलाओ।")
            self.assertTrue(result["detected"], wake)
            self.assertEqual(result["remainder"], "25 दिसंबर को 6:30 PM पर ₹500 याद दिलाओ।")

    def test_ordinary_words_or_mention_in_sentence_do_not_activate(self):
        for text in ("banana", "corona", "open Chrome", "tell me about Cortana", "वो कोर्टाना की बात है"):
            self.assertFalse(match_wake_word(text)["detected"], text)

    def test_short_hindi_command_is_not_stripped(self):
        self.assertEqual(match_wake_word("कोर्टाना, रुको")["remainder"], "रुको")


class SpeechRecognitionTests(unittest.TestCase):
    def setUp(self):
        # Unit tests must not acquire another project's real GPU lease or query
        # its Ollama residency, even when the decode itself is mocked.
        self.enterContext(patch('core.resource_broker.gpu_slot', side_effect=nullcontext))
        self.enterContext(patch('core.model_profiles.prepare_inference'))
        self.enterContext(patch.object(stt, '_gpu_unavailable', False))
        self.enterContext(patch.object(stt, 'gpu_model_loaded', return_value=True))

    def test_language_auto_and_hindi_are_forwarded_correctly(self):
        recorded = []
        model = SimpleNamespace(transcribe=lambda audio, **kwargs: (
            recorded.append(kwargs) or iter([
                SimpleNamespace(text=" हाँ ", no_speech_prob=0.1, avg_logprob=-0.2),
                SimpleNamespace(text="YouTube खोलो", no_speech_prob=0.1, avg_logprob=-0.2),
            ]), None,
        ))
        with patch.object(stt, "_get_model", return_value=model), patch.object(settings, "stt_language", "auto"):
            self.assertEqual(stt._decode("fixture", "small", "cpu", "int8", False), "हाँ YouTube खोलो")
        self.assertIsNone(recorded[0]["language"])
        self.assertEqual(recorded[0]["task"], "transcribe")
        self.assertFalse(recorded[0]["condition_on_previous_text"])
        self.assertEqual(recorded[0]["temperature"], 0.0)
        self.assertEqual(recorded[0]["beam_size"], 3)
        self.assertEqual(recorded[0]["max_new_tokens"], 128)
        self.assertEqual(stt._language("hi"), "hi")
        self.assertIsNone(stt._language(""))

    def test_low_confidence_noise_is_discarded(self):
        model = SimpleNamespace(transcribe=lambda *args, **kwargs: (
            iter([SimpleNamespace(text="invented words", no_speech_prob=0.9, avg_logprob=-1.5)]), None,
        ))
        with patch.object(stt, "_get_model", return_value=model):
            self.assertEqual(stt._decode("fixture", "small", "cpu", "int8", False), "")

    def test_model_loader_uses_local_files_only(self):
        calls = []
        fake = SimpleNamespace(WhisperModel=lambda *args, **kwargs: calls.append((args, kwargs)) or object())
        stt._models.clear()
        with patch.dict(sys.modules, {"faster_whisper": fake}):
            stt._get_model("test-model", "cpu", "int8")
        self.assertTrue(calls[0][1]["local_files_only"])
        self.assertEqual(calls[0][1]["download_root"], str(settings.stt_download_root))
        stt._models.clear()

    def test_current_pyav_decodes_pcm_and_rejects_long_audio(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "sample.wav"
            path.write_bytes(wav_bytes(1))
            decoded = stt._load_audio_bounded(str(path))
            self.assertEqual(decoded.shape, (16000,))
            self.assertEqual(str(decoded.dtype), "float32")
            path.write_bytes(wav_bytes(62))
            with self.assertRaisesRegex(ValueError, "exceeds 60 seconds"):
                stt._load_audio_bounded(str(path))

    def test_cuda_failure_retries_on_cpu_but_bad_audio_does_not(self):
        with tempfile.NamedTemporaryFile(suffix=".wav") as audio:
            with patch.object(stt, "_load_audio_bounded", return_value="audio"), \
                 patch.object(settings, "stt_device", "cuda"), \
                 patch.object(stt, "_decode", side_effect=[RuntimeError("CUDA driver unavailable"), "ठीक है"]) as decode:
                self.assertEqual(stt.transcribe(audio.name), "ठीक है")
                self.assertEqual(decode.call_args.args[2:4], ("cpu", "int8"))
            with patch.object(stt, "_load_audio_bounded", return_value="audio"), \
                 patch.object(settings, "stt_device", "cuda"), \
                 patch.object(stt, "_decode", side_effect=RuntimeError("Invalid audio")) as decode:
                with self.assertRaisesRegex(RuntimeError, "Invalid audio"):
                    stt.transcribe(audio.name)
                self.assertEqual(decode.call_count, 1)

    def test_wake_and_command_decode_are_serialized(self):
        active = 0
        maximum = 0
        counter_lock = threading.Lock()
        def decode(*args):
            nonlocal active, maximum
            with counter_lock:
                active += 1
                maximum = max(maximum, active)
            time.sleep(0.03)
            with counter_lock:
                active -= 1
            return "yes"
        with tempfile.NamedTemporaryFile(suffix=".wav") as audio, \
             patch.object(stt, "_load_audio_bounded", return_value="audio"), \
             patch.object(stt, "_decode", side_effect=decode):
            with ThreadPoolExecutor(max_workers=2) as executor:
                results = list(executor.map(lambda wake: stt.transcribe(audio.name, wake_tier=wake), [False, True]))
        self.assertEqual(results, ["yes", "yes"])
        self.assertEqual(maximum, 1)

    def test_low_ram_uses_lightweight_local_speech_without_disabling_gpu_retry(self):
        from core.model_profiles import ModelAdmissionError
        with tempfile.NamedTemporaryFile(suffix=".wav") as audio, \
             patch.object(settings, 'stt_device', 'cuda'), \
             patch('psutil.virtual_memory', return_value=SimpleNamespace(available=740 * stt.MIB)), \
             patch('core.model_profiles.prepare_inference', side_effect=ModelAdmissionError('Low RAM')), \
             patch.object(stt, '_load_audio_bounded', return_value='audio'), \
             patch.object(stt, '_decode', return_value='YouTube खोलो') as decode:
            self.assertEqual(stt.transcribe(audio.name, wake_tier=True), 'YouTube खोलो')
            self.assertEqual(decode.call_args.args[1:4], (settings.stt_preview_model_size, 'cpu', 'int8'))
            self.assertFalse(stt._gpu_unavailable)

    def test_short_audio_uses_lightweight_decoder_without_cold_gpu_start(self):
        with tempfile.NamedTemporaryFile(suffix='.wav') as audio, \
             patch.object(settings, 'stt_device', 'cuda'), \
             patch('psutil.virtual_memory', return_value=SimpleNamespace(available=2048 * stt.MIB)), \
             patch.object(stt, 'gpu_model_loaded', return_value=False), \
             patch.object(stt, '_load_audio_bounded', return_value=[0] * 16000), \
             patch.object(stt, '_decode', return_value='Open Chrome') as decode:
            self.assertEqual(stt.transcribe(audio.name), 'Open Chrome')
            decode.assert_called_once_with([0] * 16000, settings.stt_preview_model_size, 'cpu', 'int8', False, None)


class SpeechSynthesisTests(unittest.TestCase):
    def test_voice_selection_matches_language_before_gender(self):
        voices = [
            SimpleNamespace(id="english", name="Zira", gender="Female", languages=[b"\x05en-US"]),
            SimpleNamespace(id="hindi", name="Heera", gender="Female", languages=["hi-IN"]),
        ]
        self.assertEqual(tts._pick_voice_id(voices, "en"), "english")
        self.assertEqual(tts._pick_voice_id(voices, "hi"), "hindi")
        self.assertIsNone(tts._pick_voice_id(voices[:1], "hi"))

    def test_hindi_uses_local_piper_without_opening_sapi(self):
        with tempfile.NamedTemporaryFile(suffix=".onnx") as model, \
             patch.object(settings, "tts_voice_id", ""), \
             patch.object(tts, "hindi_model_path", return_value=Path(model.name)), \
             patch.object(tts, "_synthesize_hindi", return_value=b"RIFFfixture") as hindi, \
             patch.object(tts, "_get_engine") as sapi:
            self.assertEqual(tts._synthesize_on_worker("YouTube खुल गया।"), b"RIFFfixture")
            hindi.assert_called_once_with("YouTube खुल गया।")
            sapi.assert_not_called()


class VoiceEndpointTests(unittest.TestCase):
    def setUp(self):
        app = FastAPI()
        app.include_router(voice.router)
        self.client = TestClient(app)

    def test_empty_and_large_audio_rejected_before_transcription(self):
        with patch.object(stt, "transcribe") as transcribe:
            response = self.client.post("/api/stt", files={"audio": ("sample.webm", b"", "audio/webm")})
            self.assertEqual(response.status_code, 400)
            with patch.object(voice, "MAX_AUDIO_BYTES", 10):
                response = self.client.post("/api/stt", files={"audio": ("sample.webm", b"x" * 11, "audio/webm")})
                self.assertEqual(response.status_code, 413)
            transcribe.assert_not_called()

    def test_temp_recording_removed_on_decode_failure(self):
        paths = []
        def fail(path, **kwargs):
            paths.append(path)
            self.assertTrue(Path(path).is_file())
            raise stt.RecordingError("Invalid test recording.")
        with patch.object(stt, "transcribe", side_effect=fail):
            response = self.client.post("/api/stt", files={"audio": ("sample.wav", wav_bytes(), "audio/wav")})
            self.assertEqual(response.status_code, 400)
        self.assertEqual(len(paths), 1)
        self.assertFalse(Path(paths[0]).exists())

    def test_both_capture_modes_report_resource_errors_as_retryable(self):
        with patch.object(stt, 'transcribe', side_effect=stt.SpeechUnavailable('Free some RAM.')):
            for endpoint in ('/api/stt', '/api/wake-check'):
                response = self.client.post(endpoint, files={'audio': ('sample.wav', wav_bytes(), 'audio/wav')})
                self.assertEqual(response.status_code, 503)
                self.assertEqual(response.json()['detail'], 'Free some RAM.')

    def test_preview_is_provisional_and_temp_audio_is_removed(self):
        paths = []
        def recognize(path, language):
            paths.append(path)
            return 'Hey Cortana open Chrome'
        with patch.object(stt, 'preview', side_effect=recognize):
            response = self.client.post('/api/stt-preview', files={'audio': ('preview.wav', wav_bytes(), 'audio/wav')})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['provisional'])
        self.assertEqual(response.json()['remainder'], 'open Chrome')
        self.assertFalse(Path(paths[0]).exists())

    def test_tts_limits_and_missing_voice_are_explicit(self):
        with patch.object(tts, "synthesize") as synthesize:
            response = self.client.post("/api/tts", json={"text": "x" * 4001})
            self.assertEqual(response.status_code, 422)
            synthesize.assert_not_called()
        with patch.object(tts, "synthesize", side_effect=tts.VoiceUnavailable("Hindi voice missing")):
            response = self.client.post("/api/tts", json={"text": "नमस्ते"})
            self.assertEqual(response.status_code, 409)
            self.assertEqual(response.json()["detail"], "Hindi voice missing")

    def test_wake_endpoint_preserves_hindi_remainder(self):
        with patch.object(stt, "transcribe", return_value="कॉर्टाना, YouTube खोलो"):
            response = self.client.post("/api/wake-check", files={"audio": ("sample.wav", wav_bytes(), "audio/wav")})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["detected"])
        self.assertEqual(response.json()["remainder"], "YouTube खोलो")


if __name__ == "__main__":
    unittest.main()
