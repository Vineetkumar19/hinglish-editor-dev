# Meaning repair evidence — 19 September 2026

Normal `Run Phase 2.bat` now uses `matching_backend: meaning`, Swift speech
recognition and natural pacing. Phase 1 and the original cutter were not edited.

## Actual Rapido batch

Result: `output/phase2/20260919-151923-995388`.
12 source videos; 19 spoken sections selected in the intended script order;
51.1 seconds, 1,533 video frames. `Sun` remains unmatched. The price phrase
is retained with an explicit listening flag because ASR writes `saath`.

The inspected source ranges include the **entire** `alag struggle` opening,
`Her single ride par`, separate second/third/fourth rider phrases, both
morning/evening clauses, and the complete next-episode and follow endings.
The earlier abandoned `Aur phir vah` is not selected. The script was not edited
to force agreement, and no script prompt was supplied to transcription.

`check_rapido_meaning_output.py` confirms all expected source ranges, no reused
frames, existing media links, XML in/out values and decoded preview frame count.
`recheck_active_selection.py` confirms the final default code produces the same
selected ranges and cuts, reusing cached judgments without starting the model.
The output's `final-code-check.json` records this check.

## Earlier real failures

`meaning-history.json` records targeted checks against saved source transcripts
from the Nightlife and PG batches, using the new matcher:
- The later complete Nightlife attempts at 5.272s and 13.472s are selected.
- Washing-machine and fridge negative answers retain `nahin` and use distinct
  non-overlapping source intervals.

These are selected regression cases, **not** full revalidation of every edit in
both historical batches. Previous full exports remain untouched.

## Experiments and limitations

The prior whole-paragraph context falsely approved individual clauses, and
short phrase filtering hid the correct emphatic occurrence. Those paths were
removed. Comparisons use the current idea only; close partial candidates can be
checked independently. Pause boundaries alone cannot trim arbitrary middle words.
Explicit quantity/negation/ordinal guards still constrain model decisions.

Independent Turbo recognition worsened several mixed Hindi/English phrases
in this batch. It was not promoted; Swift remains the normal speech backend.
Both models can still mishear words. A larger model alone was not a solution.

The local Qwen3 4B judge is pinned to revision
`a06e946bb6b655725eafa393f4a9745d460374c9`, running through checksum-checked
llama.cpp `b11011`. The model is fallible; its reasons/scores are not accuracy
measurements. Contrast experiments are in `meaning-model-contrasts.json`.

90 software checks pass, including complete phrase boundaries, missing cues,
explicit changed quantities, overlap rejection, retake preference, pacing, XML,
preview generation and review application. A generated 10,000-word transcript
checks bounded candidate growth only. These tests do not establish speech
accuracy or natural listening quality.

Not verified: manual Premiere import, subjective listening approval, RTX 5070
performance, or end-to-end editing quality on a representative 40–50 minute
recording. Long-form quality must not be claimed from this short-video repair.
