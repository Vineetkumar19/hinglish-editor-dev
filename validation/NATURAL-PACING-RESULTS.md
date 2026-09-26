# Natural pacing correction — September 17

User reported rushed edits and insufficient gaps in the PG batch.
Output: `output/phase2/20260917-031115-544956`.

- Same 21 selected takes retained; script ordering and retake selection unchanged.
- Duration increased from 31.60 to 39.47 seconds (1184 frames at 30 fps).
- Normal padding now requests 0.18 seconds before / 0.35 after speech;
  paragraph boundaries request 0.25 before / 0.55 after.
- Pauses shorter than 0.65 seconds within a selected span are preserved.
- Original source pauses limit these handles. Adjacent words are protected;
  discarded neighboring speech is not reintroduced simply to pad a transition.
- Short attached sentence endings can extend a selected span to punctuation.
  This recovered `bataoonga.` in the final paragraph of this batch.
- No playback-speed changes, synthesized silence or black-frame gaps were added.

Checked the saved XML bounds, file references, lack of reused frames, decoded
preview frame count, audio duration, unchanged selected take IDs and retained
word bounds. `pacing-validation.json` records padding between clauses; these
are transcript-based timing measurements, not measurements of perceived silence.
Most joins retain about half a second of source padding, paragraph breaks about
0.8 seconds; continuous speech retains its available source timing.

The Wi-Fi, AC and chair passages still have their original transcription-review
flags. No Premiere import test or human listening certification is claimed.
Natural is the new default; tight and relaxed remain available via pacing config.
