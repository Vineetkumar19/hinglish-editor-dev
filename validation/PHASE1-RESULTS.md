# Phase 1 silence-removal validation - 2026-09-09

Scope delivered: standalone `hinglish_clean`, CPU-only local speech detection,
frame-accurate silence decisions, MP4 rendering, editable Premiere XML, and
per-video review reports. Filler and retake classification are not implemented.

- Baseline backup: `baseline-phase1/before-phase1.zip`. All original
  `hinglish_cut/*.py` files match the baseline byte-for-byte.
- 42 unit/integration tests passed, including all 30 pre-existing tests.
- Tested empty/continuous speech, padding, short utterance retention at the
  planning layer, analysis overlap and cache reuse, isolated input selection,
  stereo/mono output, NTSC multi-cut sample rounding, output dimensions,
  linked XML duration, and retained output media after deleting input.
- Real supplied clip `VID20260802223806.mp4`: MP4 and XML exported.
- Real supplied clip `VID20260808004509.mp4`: 33.4667 seconds became 11.8333
  seconds; 21.6333 seconds marked as pauses. Six retained spans. The original
  and edited video are available in its output/phase1 folder for human review.
- Extracted portrait output frame inspected: upright, 1080 x 1920.
- A 75-second integration fixture uses real Hindi audio with five occurrences
  and known inserted silence, including one crossing the 60-second boundary.
  Output 11.32 seconds; all five occurrences retained. Rendered audio compared
  against the planned source concatenation: correlation 0.9999983. Frame
  brightness markers match source order (maximum RGB mean error 1.0).
  See `phase1-speech-check/validation.json` and the reproducible validation script.

Limits: detection checks cannot prove every quiet word was recognized as speech.
The fixture verifies occurrence retention and rendering, not transcription or
semantic accuracy. No new Premiere UI import was performed. Browser automation
blocked local file URLs, so review-page layout/playback was not visually tested
in a browser. No 1-2 hour recording or NVIDIA hardware benchmark was performed.
GPU acceleration is not enabled; the CPU build also runs on NVIDIA laptops.
