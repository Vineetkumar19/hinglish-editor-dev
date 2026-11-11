# Storylens Voiceover

The owner requested VoiceStudio voice cloning in Storylens: save a personal voice,
paste a script on later visits, and download the generated narration as MP3.
The owner supplied `A:\Full Drive\thisis.vineet\e7\e7 night life11.mp4` and
explicitly permitted a separate visible browser tab for application validation.

## Sources and scope

- VoiceStudio: https://github.com/debpalash/VoiceStudio
- OmniVoice: https://github.com/k2-fsa/omnivoice
- ElevenLabs public workflow reference:
  https://elevenlabs.io/docs/eleven-creative/voices/voice-cloning/instant-voice-cloning
- The saved VoiceStudio source was reviewed, including its profiles, generation,
  model loading, reference-audio validation, language and speed interfaces.
- `tools/voicestudio-runtime/source/omnivoice` is a preserved inference-source
  copy. License/notice files and file hashes are retained beside it. This does
  not copy ElevenLabs's private code or use their paid API.
- Setup uses a private interpreter and private Transformers/Hub packages;
  the existing torch CUDA wheel is reused. Storylens's Transformers 4.57.6 and
  caption/video runtime are not upgraded. OmniVoice weights are local under
  `models/voicestudio/OmniVoice` (about 3.26 GB for speech model and tokenizer).

## Product workflow

Voiceover appears in the main tools list and the editor-panel tools list. A
profile stores a validated mono recording and exact reference transcript locally.
VoiceStudio's supplied-transcript limit is 20 seconds, so new samples must be
3–20 seconds. English, Hindi and automatic multilingual/Hinglish selection are
offered. Script words, numbers, punctuation and line breaks are not rewritten.
Speed ranges from 0.7 to 1.3. MP3 is encoded at 192 kbps; WAV is also retained.
Generation history and browser drafts survive ordinary navigation/reopening.

Work runs through the existing GPU file lock, one generation at a time; model
inference lives in a subprocess and releases its memory on exit. There is no
diagnostic timeout killing a healthy generation. Existing Ollama-release
preferences are respected. Each result records engine, script, selected voice,
settings, time and technical logs. A stable request identifier prevents a lost
HTTP response from creating a duplicate generation. Incomplete work owned by a
dead process is marked interrupted, never advertised as a finished MP3.

The API uses existing local-host/origin/token protection. Audio links contain a
local token and expose only a complete job's MP3/WAV, with no-store and no-referrer
headers. User-controlled paths are not accepted. Shared plain-language errors
are used, with original diagnostics under Technical details.

## Voice source

An existing Demucs-separated recording was matched to the exact supplied E7 MP4
by audio correlation (0.9998128). The first 8.55 seconds and matching spoken text
were saved as a reference; original media is unchanged. Source separation can
leave music/effect leakage, and perceptual voice similarity must be judged by
listening. See `output/voiceover-evidence/reference-source.json`.

## Validation

Tests were written and run before implementation (initially missing-module
failures), then passed after implementation. Coverage includes saved profiles,
invalid/silent/long audio, script preservation, settings validation, duplicate
requests, process restart, simultaneous service instances, real WAV/MP3 encoding,
and useful failures. A real local HTTP integration check covers authenticated
upload/profile/start/history, blocked downloads before completion, traversal
rejection, missing credentials, and token-injected feature HTML.

Live validation and actual inference results are tracked in
`output/voiceover-evidence/status.json`. Do not call unit-test synthetic audio an
actual cloned narration. Primary Storylens services and Adobe apps are not
restarted by setup; a new service must load the new routes when safe.

Earlier shared-error regression checks expose existing HTML fixtures lacking
feedback.js in auto-caption-2.html, auto-captions.html and preview-reader-proof.html.
Those files were not changed for Voiceover; record these separately from the new
feature's results. Existing saved task queue/deferrals remain intact.


## Final live result and pronunciation repair

The initial Roman Hindi sample played and downloaded but independent local
recognition found misread words. That was not accepted as a completed script
reading. Hindi spelling preparation now uses the configured local Qwen with
full selected creator context. The original pasted script is saved unchanged;
only the voice engine receives phonetic Hindi spellings. Fixed token count,
number preservation and phonetic comparisons reject rewriting or dropped words.
Only validated preparation is cached; confirmed failed jobs can start a new
attempt without losing the script. All preparation/model receipts are retained.

The final 57-character mixed Hindi/English script generated 3.76 seconds of real
cloned narration in 44.94 seconds after the queue was free. Independent local
Whisper recognized the complete wording, including Namaste and Let's begin.
Browser playback reached the end with no media error. The downloaded MP3's hash
matches the generated file, and the saved result reopened after service restart.
This is one short script, not a full-length or every-language acceptance claim.
Voice similarity and desired delivery remain for owner listening approval.

Eighteen feature unit/integration tests pass. Final safe probes: nine pass, one
hardening observation. With the valid local connection token, a foreign Origin
receives HTTP 200 rather than an explicit origin rejection. Browser CORS still
blocks foreign response access; no unauthenticated bypass was demonstrated. The
observation was recorded and left unchanged under the owner's final-review rule.

The owner authorized restarting main Storylens only after checking it was idle.
The recorded prior B-roll job had failed with saved progress, but a new live
B-roll worker was detected before any termination. The restart was therefore
deferred; main Storylens and Adobe were left running. The verified separate
Voiceover page remains available on port 8897. No permission to stop the active
B-roll job was inferred. Keep all earlier tasks and deferrals.
