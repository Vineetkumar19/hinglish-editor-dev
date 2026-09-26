# Actual thirteen-video paragraph edit

Generated September 15, 2026; final checks completed September 16.

Output: `output/phase2/20260915-234737-279794`.

The previous implementation chose one clip for an entire paragraph. That lost
the other sentences and allowed a small language model to falsely approve
incomplete or unrelated matches. The current default assembles each paragraph
from individual source clauses and does not use that model to certify coverage.

## Observed result

- The user's actual 13 recordings total 115.10 seconds.
- All six script paragraphs have selected spans: 21 clauses in script order.
- Edited duration is 32.7667 seconds, 983 frames at 30 fps.
- Premiere XML is 1080x1920; the playable preview is 540x960.
- Earlier repeated attempts are excluded for the opening response, Highway,
  enjoyment invitation and Instagram sentence. Selected source starts are
  respectively 3.572, 24.760, 5.272 and 13.472 seconds in their recordings.
- XML in/out points match the saved cut decisions. No source frames are reused.
- All referenced media files exist within the portable result folder.
- Decoded preview video frames and audio duration match the XML edit.
- The six edited paragraphs were transcribed again. Their transcripts retain
  the selected speech, with known ASR misspellings still present.
- A decoded preview frame was inspected: upright, vertical, full source frame.

## What is not established

- This is not a human listening certification or a test of importing into Premiere.
- ASR still mishears words such as Madurai, cafe, tumhe and baad. Review flags
  remain visible; no accuracy percentage or guaranteed meaning claim is made.
- Zero recognized fillers were removed in this batch. The code removes eligible
  timed um/uh/erm tokens, but cannot detect a filler that the ASR omitted.
- Heavily paraphrased clauses without enough wording evidence are offered as
  meaning-based alternatives for manual listening/selection. Fully automatic
  meaning-only assembly remains a limitation.
- Clean+ now respects explicit model removal vetoes. The former 12/12 safety
  claim must not be treated as proof of model accuracy.

## Reproducible checks

`validation/check_paragraph_output.py` checks this batch's coverage, known later
takes, source bounds, no-reuse rule, portable paths, XML and decoded preview.
Its measured result is saved as `validation.json` inside the output folder.

`tests/test_paragraph_coverage.py` covers multi-file paragraph assembly, missing
clauses, incomplete later attempts, spoken numbers, meaning-only candidates,
explicit cleanup vetoes, export playback and applying saved review choices.
The full regression suite passed; those tests are engineering checks, not a
substitute for reviewing the actual video.

Original `hinglish_cut` source remains unchanged from the pre-Phase-1 backup.
