# Validation record — updated 2026-09-20

## Auto Captions validation — 2026-09-20

- The complete automated suite passes: **110 tests**.
- Caption coverage includes coarse-to-word timing, readable cue grouping, UTF-8 Roman Hinglish SRT, transparent alpha video, and a two-layer Premiere/Resolve XML.
- JavaScript syntax checks pass for the standalone UI, Premiere 2024 CEP panel, and Premiere 25.6+ UXP panel.
- Python compilation and dependency checks pass; Pillow is installed and declared as a project dependency.
- A real local end-to-end caption job completed through both the command-line pipeline and the dashboard API. It reused a cached Swift transcript, rendered a QuickTime alpha overlay, and generated `CAPTIONED_SEQUENCE.xml`, SRT, ASS, transcript, and review pages.
- The caption UI was visually checked in the in-app browser. All six templates appear and switching to Auto Captions updates the run action.
- A 1920x1080 Creator Punch frame was rendered and inspected for safe placement, contrast, active-word emphasis, and clipping.
- Premiere/Resolve XML structure was parsed and verified to contain the source on V1/A1 and caption overlay on V2. Final playback still needs a short import check in each editor because those host applications are outside the automated test runner.

## Completed

- All 24 automated tests pass using the project's Python 3.12 environment.
- Compilation check passes for the application package.
- Dependency doctor imports NumPy, PyAV, torch, torchaudio, Transformers, Silero VAD and uroman successfully. PyTorch and torchaudio are both pinned to 2.9.1 CPU; pip reports no broken requirements.
- A synthetic media integration test actually encodes video with stereo audio, probes its frame rate, decodes audio, builds two cuts and verifies the reconstructed sample count.
- The demo produces four timeline clips in the correct script order, linked stereo XML and per-line audio previews. Its report was visually inspected in a browser. It is explicitly labeled as synthetic data.
- Tested matching behavior: out-of-order source files, retakes, ambiguous matches, missing lines, and prohibition on reusing source words.
- Tested cuts: full-word preservation, VAD-only speech protection, conservative handling of unaligned words, and nonoverlapping padding between adjacent script lines.
- Tested evaluation: changed numeric tokens, missing negations, allowed spelling aliases, malformed semantic-model responses, missing model checks, and reporting an all-missing script without creating an empty XML.
- Tested export: XML parsing, linked stereo tracks, escaped file URLs, rational NTSC rates, timeline continuity and rejection of mixed frame rates.
- A four-second public Hindi sample from the Oriserve model card was decoded locally. Silero found speech at approximately 0.93–2.97 seconds. The downloaded Swift model produced `Vah bas din mein kitni baar chalti hai?`, matching the model card's sentence apart from capitalization. This is one provider sample, not an independent benchmark or test of the user's recordings.
- Silero classified a one-second all-zero waveform as containing no speech. Directly bypassing VAD and giving that silence to Whisper produced a hallucinated word, demonstrating why the pipeline requires VAD before ASR. The application does not use raw silence as speech.
- Offline model loading was corrected to resolve local snapshot directories first, avoiding unwanted metadata requests by AutoProcessor.

## Remaining setup and real-world verification

- **Model downloads:** Whisper-Hindi2Hinglish-Swift is downloaded. The MMS alignment weights and Qwen semantic-evaluator weights are not fully downloaded. Large transfers stalled in this environment; interrupted/empty weights were not treated as valid. Run `Download Models.bat` to finish these downloads before attempting a fully offline run. The two shipped configurations reference the intended models and the normal run also downloads missing weights.
- The real MMS model forward pass, real-audio CTC alignment and Qwen evaluator inference have not been verified here because those weights are unavailable. The CTC algorithm and evaluator failure behavior have automated coverage. See `validation/speech_check.py` to repeat the real model checks after downloading the weights.
- **No user footage or master script has been supplied.** `input/script.txt` is intentionally blank. Recognition accuracy, retake quality, pacing, full-batch runtime, and acceptable confidence thresholds must be assessed against the user's content.
- **RTX 5070 hardware is not installed yet.** CUDA configuration targets matched PyTorch 2.9.1/cu128 packages with Blackwell support and includes a runtime kernel test; performance and memory use on the user's future GPU have not been measured.
- **Premiere Pro import was not exercised.** XML structure and frame/channel relationships were checked programmatically. Test a short representative sequence in the user's exact Premiere version before using a long production assembly. After Effects receives the edit through the Adobe workflow rather than direct FCP XML import.

## Reproduce

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m hinglish_cut doctor
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -m hinglish_cut demo
.\.venv\Scripts\python.exe -m hinglish_cut prepare --config config.cpu.json
.\.venv\Scripts\python.exe validation\speech_check.py
```

The speech sample comes from https://huggingface.co/Oriserve/Whisper-Hindi2Hinglish-Swift/blob/main/audios/f89b6428-c58a-4355-ad63-0752b69f2d30.wav and is only used for local validation. It is not included in the source-only release archive.
