# Voiceover GPU-only — 29 October 2026

The owner requested moving voice cloning to GPU. The previous verified narration
already logged `device: cuda`; the worker nevertheless allowed silent CPU fallback.
`hinglish_voice/worker.py` now requires CUDA before loading the voice model, keeps
BF16 on supported GPUs (FP32 on CUDA otherwise), and logs the actual GPU name.
GPU-unavailable failures use the shared error catalog and preserve the saved script
and voice. WAV/MP3 encoding and copying completed audio to host memory remain normal
CPU operations; voice-model inference must run on CUDA.

The worker launches per generation, so this policy needs no application restart.
No services, Adobe applications, owner projects or unrelated jobs were interrupted.

## Validation

- TDD red failures were observed before the implementation; evidence is in
  `output/voiceover-gpu-20261029/tests-red.txt`.
- 22 focused unit/integration/HTTP checks pass, including CUDA selection, GPU
  precision support, model placement arguments, receipt, and shared errors.
- The real isolated worker was launched with CUDA hidden. It refused generation
  with a Voiceover GPU error and created no audio; saved outputs were untouched.
- Six safe final review probes pass, with no new findings in these checks.
  The earlier foreign-Origin hardening observation remains separately recorded;
  it was outside this change and was not repaired.
- One actual saved E7-voice generation was submitted through the running main
  Storylens API on port 8765. Its current status and final device receipt, when
  available, are in `output/voiceover-gpu-20261029/status.json` and `live-result.json`.
  A queued job is not a completed GPU-generation verification.

Voice similarity remains subject to owner listening approval. Existing cumulative
tasks, owner-testing boundaries and Publisher Studio deferral remain intact.


30 October owner listening sample: explicit CPU approval for this generation while Sound Design training occupied GPU. worker.gpu_config now supports task-level device=cpu using FP32; default CUDA still refuses automatic CPU fallback. Red-first explicit CPU/invalid-device tests and existing GPU checks pass. The long CPU generation was stopped only after owner requested a shorter sample. A private 8-step draft worker produced the 10.16-second opening Zomato excerpt, decoded successfully with nonzero audio. Main feature retains 32 steps and GPU default. The old queued GPU job belonged to an exited service and was marked cancelled; no live unrelated process was stopped. Audio: output/voiceover-listen-20261030/cpu-preview/Vineet-Zomato-Voiceover.mp3. Voice similarity is for owner listening approval; full-script generation remains uncompleted for this request.


## Owner rejection of CPU listening preview — 30 October 2026

Owner rates the delivered 10.16-second CPU OmniVoice preview 0/10 and reports poor Hindi speech quality. Treat it as rejected. Receipt inspection confirms eight generation steps in the separate preview worker versus the production default of 32; language was auto and speed 1.1. The upstream demo documents lower steps as faster and higher steps as better quality. This is a quality risk, not a proven sole cause. Earlier decode/RMS checks did not establish pronunciation or voice likeness. No new inference, model change or service restart was performed during this review. Follow-up must compare normal-step Hindi conditioning and an exact checked reference, preserve the existing profile, and obtain owner listening acceptance. Evidence: output/voiceover-listen-20261030/owner-quality-review.json.


### Owner language clarification — Hinglish

The owner explicitly clarifies the target is Hinglish (Hindi-English code-switching), not Hindi-only. This supersedes the preceding proposed explicit-Hindi fix. Preserve exact Hindi and English words, names, numbers and natural language switches in both reference and generated speech. Do not assume translating English or forcing Hindi-only improves the result. Evaluate the same mixed-language script at normal quality and obtain owner listening acceptance. No new generation was started for this correction.


## Hinglish delivery rejection and local comparison — 30 October 2026

Owner explicitly requested repair after rating the shortened 8-step output 0/10. Independent Whisper recognized reference content with a likely missing final hoon; a separate corrected profile was created via the live API, preserving the original. Actual app job 03d31b4e85df47d4afb9e56a9a7a7d58 generated 10.96s at normal32steps on CUDA, auto language and speed1.0. ASR recovered more English words, but OWNER REJECTED the audio. Latest clarification: primary problem is unnatural prosody, pauses, emphasis and sentence pacing, not principally mispronunciation. ASR is not an acceptance measure for those qualities.

Mixed-script pronunciation defects were reproduced before correction: existing Devanagari skipped Roman-Hindi preparation and the token regex split Hindi vowel marks. Corrected detection and token boundaries, forbidding changes to existing Devanagari. 27 voice unit/HTTP integration checks pass. This does not fix or prove natural delivery.

Owner requires FULLY LOCAL voice cloning. No cloud voice API or recording/script uploads. Chatterbox Multilingual V3 is being prepared in tools/chatterbox-runtime with pinned model revision5bb1f6ee58e50c3b8d408bc82a6d3740c2db6e18, existing CUDA reused read-only, separate Transformers/tokenizer dependencies. Its model download/import/tokenizer checks are setup evidence only; no Chatterbox generation or application integration accepted yet. Compare standard and lower-guidance expressive takes on the same words/reference before selecting an engine. An additional pause-bearing9.7s source excerpt is saved separately and not activated. Evidence/status: output/voiceover-quality-20261030. Competing publishing-training jobs were not stopped.


### Subsequent listening verdicts and reference correction

Chatterbox V3 standard and conversational takes were rejected. A 7.7-second phrase-rich reference improved delivery according to the owner but all three issues persisted: pauses/pacing, expression and voice resemblance. Original camera take VID20260808004135.mp4, crop1.4-6.0s with its actual internal pause preserved, still produced a substantially different voice/delivery and was rejected. None is accepted or integrated. The earlier short-reference ASR suggestion of a missing final hoon was NOT confirmed by whole-source ASR; the experimental transcript is not verified exact. Preserve the original voice profile.

An isolated public IndicF5-Hinglish candidate is being compared locally at32steps, retaining Hindi-English words. Pinned weights and Vocos decoder verified against upstream SHA256; separate runtime reuses CUDA without replacing production dependencies. This is inference comparison, not speaker training. No production restart or engine switch.

IndicF5 comparison completed: first11.648s output showed clipped peaks and ASR English-word failures. Separate12.939s take uses normal32steps, native speed0.9 and peak attenuation before PCM encoding; no post-stretching, no clipping in decoded output. ASR still misrecognizes Pin/Photo/Zomato, so this is not an accepted pronunciation or voice-quality fix. Owner listening of the different engine is pending. No production integration, no restart, no other GPU job interrupted. Artifacts: output/voiceover-quality-20261030/indicf5/validation.json and native-paced.mp3.


Owner rejected the15.061second IndicF5 E6 take as worst/pathetic and requested complete30-40second audio. Full earlier E6 narration is queued as three complete source passages joined consecutively without silence padding or tempo stretching, using the same original voice reference and32steps. This is a requested longer audition, not an accepted repair. Request/receipts: output/voiceover-quality-20261030/indicf5-e6-full. Publishing v6 training owns the shared GPU; no unrelated job interrupted.
