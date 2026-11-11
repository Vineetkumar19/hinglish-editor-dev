# Local documentary sample driven by narration

This trial lives in `output/reference-analysis/local-documentary-synced`.
Its output is `LOCAL_SYNCED_60S.mp4`, with a watchable `report.html` and receipts.
It preserves the first minute of the supplied Dale Steyn reference's voice and
music at their original speed. It uses the existing approved cricAddict and
vineet documentry edit animation software.

## What chooses the edit

Local Ollama Qwen3:8B chooses the scene boundaries, effects, photo cues, English
copy and optional sound effects. It receives the locally saved style rules and
examples retrieved from the local editing-DNA database using multilingual E5.
The recorded model requests and responses show its actual choices. There is no
cloud-generated replacement storyboard or new cloud animation in this sample.

The implementation translates those choices into the existing renderers. This
engineering adapter, like the existing renderer code, was written with Codex.
That differs from a local model inventing new animation code or having its model
weights trained on these reference videos. The saved learning is reusable local
reference memory, not weight fine-tuning.

## How synchronization works

1. A local Whisper model transcribes overlapping ten-second windows. Short
   windows recovered words and names that the earlier long-window pass missed.
2. A separate local MMS acoustic aligner refines suitable word boundaries.
   Numbers and uncertain tokens retain their Whisper acoustic timing.
3. Every word has a stable ID. The director selects IDs for scene starts, photo
   reveals, statistics and sound cues instead of inventing times or durations.
4. The frame scheduler resolves those IDs at 30fps. No evenly spaced photo-entry
   fallback exists. Unknown or misplaced IDs fail validation.
5. The adapter remaps existing reveal phases to the selected cues. Asset gates
   prevent later photos leaking through backgrounds. Text gates prevent a later
   numerical statistic appearing early because it shares an earlier note row.
   In the paper evidence rig, the photograph and the three note highlights have
   independent clocks. A later statistic therefore cannot delay the portrait.
6. The export is decoded to check duration, frame count and audio-clock offset.
   Frames around the cues and a timing audit are saved for review.

The frame schedule can be within 33.3ms of the measured acoustic onset, but the
ASR and alignment themselves are estimates. A reveal starts on its cue and
finishes over time. This does not promise human-certified millisecond accuracy.

## Available media and limits

The verified separate photos in this small trial are of Dale Steyn and South
Africa. The model must use contemporaneous original reference footage inside
the existing TV/film designs when other named players are mentioned. On a
locally annotated Sachin/Rohit cue, the adapter holds an original reference frame
whose baked caption names that player, until the next named-player cue. This
avoids inheriting the original edit's slightly late player-caption switch. It
does not generate a replacement photograph or infer a match/year. This
avoids labeling a Dale Steyn photo as Sachin Tendulkar or Rohit Sharma. These
source depictions are not a separately verified face-recognition result.

This is a specific local sample, rather than a claim that every app feature has
already received the new timing compiler. General editing defaults and the
saved animation designs remain unchanged.

## Repeat locally

Use the project's Python environment from the project folder:

```powershell
.venv/Scripts/python.exe tools/prepare_local_synced_demo.py
.venv/Scripts/python.exe tools/recover_synced_speech.py
.venv/Scripts/python.exe tools/local_documentary_synced.py
```

The first two workers reuse completed preparation. The director makes a fresh
local model request. To re-render an already saved, valid local plan:

```powershell
.venv/Scripts/python.exe tools/local_documentary_synced.py --render-only
```

Ollama must be running with the existing `qwen3:8b` model installed. The speech,
alignment and E5 models must already be cached locally. Processing is sequential;
the local LLM is unloaded before rendering. No ChatGPT subscription or cloud
inference is required to execute these saved workers with the existing models.

The original reference files and earlier sample videos are preserved. The
current trial folder is reused when running these commands, so retain a copy
of a trial's receipts before intentionally starting a fresh comparison.

Interrupted inference does not imply a completed edit. Completed model drafts
can be repaired by the same local model without supplying a replacement creative
plan:

```powershell
.venv/Scripts/python.exe tools/local_documentary_synced.py --repair-draft
```

Text lengths, available media slots, named-player coverage and all misplaced
cue IDs are reported together. The offline director receives the errors and
chooses its own corrections. English text is constrained to the existing slot
lengths. Requests keep the source transcript and useful memory under the local
runtime's input limit; the complete preparation remains on disk.

For the current sample, a smaller local English interpretation step separates
the speech meaning from internal timing IDs. Qwen performs both the English
interpretation and the display-copy generation. Literal numeric note headings
can be matched mechanically to their measured spoken digit token; this does not
introduce a new fact, invented time or replacement creative choice.

```powershell
.venv/Scripts/python.exe tools/local_synced_english_bridge.py
.venv/Scripts/python.exe tools/local_synced_plain_labels.py
.venv/Scripts/python.exe tools/local_synced_fact_check.py
.venv/Scripts/python.exe tools/local_documentary_synced.py --render-only
.venv/Scripts/python.exe tools/review_local_synced_export.py
```

The bridge is a correction for this prepared sample. It does not claim a new
general production integration for every feature or source video. A reasoning
mode experiment exhausted its token budget without a final answer; that output
was rejected. Its failure receipt is retained alongside other invalid drafts.

Strict sampling constraints distorted the local display copy in an earlier
attempt. Plain local generation now supplies labels; slot counts and lengths
are checked afterward. Extra labels are taken in their returned order up to
the required slot count. Overlong labels are shortened by Qwen itself.
The local factual correction rejects the unrecognized ASR word "Bataki" and
statistics spoken before the evidence panel. No cloud replacement text is used.
Local labels on the existing book page are measured and fitted to its original
inset, preventing clipping without changing words, scene choice or animation.
