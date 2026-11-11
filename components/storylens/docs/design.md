# Hinglish Auto Cutter

Build requested on 2026-09-07. Reference: the user's nine-page Hinglish Video Auto Cutter Research PDF. Its editor API instructions are reference material and are superseded by the user's explicit XML-only requirement.

## Product contract

A local Python application accepts a folder of 15–20 or more video takes and a UTF-8 Hinglish script. It produces an editable Final Cut Pro 7 xmeml version 5 XML with original media paths and linked audio/video, a readable evaluation report, and an auditable JSON edit decision list. No editor API, cloud inference API, account, or API key is used. Model/package downloads need internet on initial setup; cached models work offline.

## Architecture

1. PyAV inspects video and decodes the first audio stream to a temporary 16 kHz mono WAV on disk. Process files sequentially and cache analysis by source fingerprint, model configuration, and pipeline version.
2. Silero VAD marks speech. Divide long speech into bounded windows (maximum 25 seconds), preferring natural gaps. Transcribe windows with Oriserve's Hinglish Whisper model through Transformers. Keep Latin Hinglish; never translate the master script.
3. A multilingual romanized MMS CTC model aligns the *observed transcript*, not the desired script, to each audio window. A small NumPy Viterbi decoder avoids the upstream aligner's Windows C++ build dependency. Preserve unalignable words as coarse spans with explicit flags. WhisperX's default Hindi dictionary is not suitable for arbitrary Roman Hinglish.
4. Token sequence alignment finds candidate word spans across all takes for each script sentence. A bounded beam search chooses candidates in script order without reusing source words. It penalizes uncertainty and permits missing lines explicitly. Matching is lexical and tolerates spelling aliases; it is not a claim of semantic equivalence. Report close competing takes.
5. Cuts preserve complete aligned words and VAD speech, add configurable handles, and remove only sufficiently long gaps unsupported by both word alignment and VAD. Outward frame rounding protects phonemes. First release requires uniform constant frame rate media and rejects VFR/mixed rates; pre-conform such sources externally. Support integer and NTSC rational rates.
6. Reconstruct the actual retained audio at quantized cut boundaries and transcribe it afresh without the master script as a prompt. Evaluate text coverage, missing/extra negations, numbers and configured important terms, alignment issues, ambiguity, repeated source spans, and timeline continuity. Retry one conservative cut retaining the entire chosen sentence span. Optional local Transformers causal LM checks intent/entities using structured JSON, with malformed responses treated as uncertain. No LLM is required to run the structural evaluator; without one semantic verification remains explicitly incomplete.
7. Always provide a draft XML for review when some sentences match. Only mark a run ready when every line passes all required checks. Never omit failed lines from the report or silently call incomplete output ready. Human review is still needed; timing and model judgments are estimates.

## Scope and limits

Single speaker talking-head takes with embedded audio; retain all channels of the first audio stream in XML. This is script sequencing, not multicamera clock synchronization, B-roll selection, denoising, grading, or final rendering. Roman Hinglish spelling can be customized with aliases; Hindi output is romanized for matching. A sentence spanning separate files should be divided into shorter script lines. Negations must never be erased by normalization. The semantic judge is optional because GPU/RAM are not yet known.

## Verification

Test out-of-order takes, retakes, nonreuse, missing script lines, altered numbers/negations, unalignable tokens, silence vs word protection, CTC repeated labels, file URL escaping, linked stereo audio, NTSC rates and frame rounding. Generate short synthetic media to exercise decode, metadata, XML and actual audio assembly without claiming Hinglish recognition quality. Real speech accuracy and editor import require the user's footage and installed editor.
