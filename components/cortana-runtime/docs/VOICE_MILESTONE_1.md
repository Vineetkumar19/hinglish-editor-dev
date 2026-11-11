# Voice pipeline — milestone 1

## GPU repair — 20 October 2026

The current configuration supersedes the older CPU baseline below. Both wake/final recognition now use the installed `large-v3-turbo` model on CUDA with `int8_float16`. NVIDIA cuDNN 9.10.2.21 is pinned in the private environment; the process discovers CUDA 12 cuBLAS from the existing Ollama installation without changing Windows settings. The service warms model weights and first CUDA kernels before reporting readiness. An actual CUDA failure is remembered for the process lifetime and falls back to the cached small CPU model; status reports `cpu fallback` rather than claiming GPU execution.

The same saved English test clip took 5.739 seconds with warm CPU large-v3-turbo and 0.157–0.173 seconds with warm GPU decoding. First GPU initialization took 9–13 seconds. With Cortana's 9B model concurrently loaded entirely in GPU memory (7,173,308,414 bytes reported by Ollama), speech decoded in 0.488 seconds initially and 0.173 seconds on repeat. These measurements exclude recording, endpoint detection, application loading and spoken playback; they do not prove sub-second complete user interactions or live microphone accuracy.

The renderer now requests provisional transcript snapshots during an utterance. They use the same GPU weights and appear as “Hearing you · provisional” on the right. Provisional text never dispatches actions. Preview work is bounded to one request and is skipped while final recognition owns the decoder; mute/cancel aborts UI requests and clears pending text. Final recognition still waits for an utterance boundary (currently 1.1 seconds of quiet); this alone prevents a blanket under-one-second promise. No shortening of the silence threshold has been made while cutoff complaints remain unresolved.

At the owner's explicit request, conversation is now continuous: it starts automatically, stays active across replies, and does not expire after one question. Mic off releases capture and remembers the preference; Mic on resumes conversation. Stop cancels a task while leaving conversation enabled. Cortana pauses incoming command capture during its own spoken reply, then resumes automatically. It cannot infer whether nearby speech is addressed to another assistant; the owner uses Mic off for that. The complete verbal workflow and new partial-text presentation remain pending live acceptance.

The reasoning model also preloads in the background. Routine greetings and voice checks bypass inference; ordinary conversation no longer receives unrelated app-launch schemas. Gmail follow-ups retain pending fields for ten minutes, preserve dictated dates without inventing a year, and ask only for missing details. Repeated identical draft preparation reuses the same draft rather than opening another compose window. These changes require actual-account acceptance; no email was sent.

## Earlier CPU baseline (superseded)

Verified on 20 October 2026 with the project's Python 3.12 environment. Cortana uses local audio capture in Electron, local faster-whisper recognition, the authenticated desktop-to-agent bridge, and local spoken replies. No microphone recording or speaker playback was performed during the automated checks below.

Push-to-talk and wake listening share one recorder. Typing or push-to-talk cancels a pending wake recording; Stop cancels the current capture/request/playback and sends the chat request ID to the backend cancellation endpoint. Late responses are ignored by the UI and cannot play old audio. An operating-system action already in progress may finish before backend cancellation takes effect. Greetings and reminders wait for the active turn. Errors and timeouts release the busy state; a failed spoken reply remains readable in chat.

Wake listening starts disabled on a fresh desktop profile. The user can enable the visible switch; that choice is remembered. Windows lock or loss of backend availability releases the microphone. Wake matching accepts a leading “Cortana” or Hindi spelling, retains Hindi text, numbers and punctuation, and does not activate merely because Cortana is mentioned in the middle of a sentence. It is local phrase spotting, **not speaker authentication**. Background speech can still activate it; sensitive actions rely on the separate approval system.

The decoder accepts English, Hindi and Hinglish using automatic language detection and the configured bilingual vocabulary prompt. A Hindi utterance can be returned in Romanized Hinglish, as observed below. It is not guaranteed to retain the original script. Recognition uses CPU int8, one beam and one temperature pass, a maximum of 128 new tokens, VAD and low-confidence filtering. Uploads are limited to 6 MiB and decoded audio to 60 seconds. Push-to-talk ends after 30 seconds; wake chunks are 4 seconds and open-conversation chunks 7 seconds. Chunked recognition has latency and gaps; an acoustic wake detector remains a later improvement.

| Synthetic input | Command transcript | TTS time | Command STT time | Wake STT time |
| --- | --- | ---: | ---: | ---: |
| Cortana, open Chrome. | Cortana, Open Chrome. | 0.36 s | 5.08 s, cold | 1.41 s |
| कॉर्टाना, यूट्यूब खोलो। | Cortana, YouTube kholo. | 2.62 s, first Hindi load | 2.95 s | 0.91 s |
| Cortana, YouTube kholo. | Cortana, YouTube kholo. | 0.09 s | 3.06 s | 1.05 s |

All three wake transcripts were detected and retained their command. Two seconds of silence returned an empty transcript. These timings exclude microphone recording, chat/model inference, tool execution and actual audio playback; they are not end-to-end response times or real-user accuracy measurements. Machine load can change them. Fixtures and full results are in `tmp/voice-validation/`.

The tests caught and fixed two actual integration failures: faster-whisper 1.2.1 passed an obsolete `metadata_errors` option to PyAV 19.0.1, and pyttsx3's callback loop hung on repeated Windows file synthesis. Cortana now decodes bounded audio through current PyAV APIs before supplying Whisper a PCM array, and renders Windows speech directly to a SAPI file stream on a dedicated COM thread. SAPI receives the literal-text flag so model output is not interpreted as XML.

English and Romanized Hinglish use the installed Microsoft Zira voice. Hindi text uses the local Piper Priyamvada voice on CPU. Naturalness, pronunciation of technical words, Romanized Hindi and longer mixed-language replies still require the user's listening assessment. Piper is not a clone of the Halo Cortana performer.

Required local files and packages:

- `agent/.venv` must contain the pinned project requirements, including faster-whisper 1.2.1, CTranslate2 4.8.3, PyAV 19.0.1 and piper-tts 1.8.0.
- Whisper `small` and `base` are cached under `models/speech`. Their downloaded revisions are `536b0662742c02347bc0e980a01041f333bce120` and `ebe41f70d5b6dfa9166e2c581c45c9c0cfc57b66`. Runtime loading uses `local_files_only=True`; a missing cache produces a setup error instead of silently downloading.
- `models/tts/hi_IN-priyamvada-medium/` contains the `.onnx`, matching `.onnx.json`, model card, license and `SOURCE.json`. The model SHA-256 is `aa63bcf2cd493b55a450f280e23cf77f03afc9af7015e6e5acd43b652f166c88`.
- The machine currently exposes Microsoft David and Zira through SAPI, without a Windows Hindi voice. Piper supplies Hindi without changing Windows language settings.

The Piper engine is GPL-3.0. The [Priyamvada model card](https://huggingface.co/rhasspy/piper-voices/blob/c10ece1aade47bb51c153c893d14e5bf8e5b7117/hi/hi_IN/priyamvada/medium/MODEL_CARD) attributes training to [PravalX](https://github.com/PravalX), uses the [AI4Bharat corpus](https://github.com/AI4Bharat/indicnlp_corpus), and declares its dataset license as [CC BY-NC-SA 4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/). This voice was installed for the personal noncommercial assistant baseline; do not assume it is a cleared commercial voiceover asset for the later content agent. Original files were preserved unchanged. [Piper's Python API](https://github.com/OHF-Voice/piper1-gpl/blob/main/docs/API_PYTHON.md), [Windows SAPI file-stream API](https://learn.microsoft.com/en-us/previous-versions/windows/desktop/ee125549(v=vs.85)) and [SAPI literal-text flags](https://learn.microsoft.com/en-us/previous-versions/windows/desktop/ms720892(v=vs.85)) document the implementation APIs.

Repeat the focused checks from the repository root:

```powershell
agent\.venv\Scripts\python.exe -m unittest discover -s tests -p test_voice_pipeline.py -v
node --test desktop/tests/voice.test.mjs
agent\.venv\Scripts\python.exe tests/manual_voice_smoke.py
```

The first two commands passed 15 Python and 5 JavaScript tests. The third generates synthetic WAV files and transcribes them locally; it does not access the microphone or play them. FastAPI's in-process test client and Windows SAPI need normal local process permissions; the restricted tooling sandbox blocks parts of those APIs.

Still required for real-user acceptance: hold the mic and try “Open Chrome”, “YouTube kholo” and “यूट्यूब खोलो”; verify the correct app/site opens; enable wake listening and repeat; attach the current screen and ask a spoken question; stop while recording, thinking and speaking; try a second request after each interruption; listen to an English and a Hindi reply. Repeat with the user's normal accent, distance and background noise. Confirm that locking Windows releases the microphone and that a saved wake preference behaves as expected after sign-in. Those checks must not be represented as already passed.
