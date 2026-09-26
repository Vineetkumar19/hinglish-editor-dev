# PG batch: export crash and repeated answers

Final output: `output/phase2/20260916-213105-511026`.
Final artifact check completed September 17, 2026.

## Reproduced cause

The actual eleven-video batch failed with `An edit reuses source frames`.
One selected word ended at 4.38 seconds and the next started at 4.38 seconds.
At 30 fps, independently rounding their ends outward assigned frame 131 to both
cuts. They now share the nearest frame boundary. This changes boundary
quantization by less than one frame; it does not disable overlap validation.
Coarse timestamps with real overlap are excluded during candidate selection.

Repeated standalone Nahi answers were also being treated as later retakes.
Questions now retain their short answers; short cues and intentional scripted
repetitions are excluded from retake supersession. Quoted sentences and brief
connective fragments now split without merging unrelated script sentences.

## Actual result

- All eleven sources processed through the normal Phase 2 entry point.
- Draft: 21 selected sections, 948 video frames, 31.6 seconds.
- No overlapping source frames; every XML media path exists.
- Decoded video preview and timeline audio durations match XML.
- Wi-Fi, AC room, and the chair sentence remain **unverified context passages**.
  Their raw source passages are included next to the matched neighboring
  sentences and are explicitly flagged for listening. No automatic meaning
  certification is claimed for these poorly transcribed passages.
- Re-transcribing the difficult audio with whole-clip context, beam search and
  alternate language settings did not reliably fix ASR. Original transcripts
  were not overwritten with script wording to manufacture a match.

`check_pg_output.py` verifies this output's cut bounds, no-reuse rule, file paths,
decoded preview, answer placement and three explicit review flags. Results are
saved in `validation.json` beside the XML. Regression tests cover the touching
word boundary, coarse timing conflicts, question/answer grouping and anchored
recovery with fact conflicts rejected.

Premiere import and human listening have not been performed. The original
`hinglish_cut` implementation, input script and raw source media were not edited.
