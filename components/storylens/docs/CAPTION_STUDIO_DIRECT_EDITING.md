# Connected Caption Studio and direct editing

Open generated caption reports through localhost using `/caption-output/`.
The old local-file page sent a `null` Origin to `/api/bridge`, which correctly
rejected it. The new same-origin route serves only files resolved inside
`output/captions`, supports video byte ranges and rejects path traversal and
junction escapes. Bridge authentication and the null-Origin rejection remain.
Opening a caption report from the app now opens its connected URL. Newly
generated file reports also offer an explicit connected-page handoff that
carries the current draft in the local URL fragment.

The studio supports:

- Dragging CAP blocks and their start/end handles. Resizing a block scales its
  internal word timing proportionally; it does not change the audio. Fine sync
  changes belong on the separate WORD track or individual start/end fields.
- Dragging WORD blocks and either edge, bounded by adjacent words and the
  containing caption.
- Selecting a caption on the video, dragging it horizontally/vertically,
  corner resizing, two-pointer pinch resizing and wheel resizing. Position and
  position is saved per caption. Resizing any group applies the same scale to
  every caption group, with sizes from 8% to 400%.
- Strict spoken-word visibility using real half-open word intervals, with no
  next-word fallback or previous-word hold across gaps. Typography 1–5 use
  `styled_spoken`: individual words retain the preset's font, role, position,
  color and motion while their visibility follows their own start/end times.
  Whole-phrase template animation and simple single-word text remain optional.
- Local draft recovery, a reversible Restore saved action, and a current MP4
  download after Save & export. Restoring after export uses the latest saved
  state. Style-only or spelling-only edits preserve the original word times.

The renderer receives the same caption timings, word timings, colors and per-
caption transforms that the studio sends. Strict mode renders only the active
word. SRT and ASS strict-mode events also use individual word intervals. MP4
export uses the actual overlay canvas dimensions, including changed aspect
ratios; original audio is stream-copied. This computer retains NVENC encoding.
Manual retiming does not establish that every word aligns correctly to the
voice; the user can inspect and adjust it directly.

## Actual user project and preservation

The original saved project at
`output/captions/20261018-091908-b22ac7/001-0000-e11e1551-Rog Music`
is unchanged. Its previous report, project, subtitles, XML and MP4 are backed up
under `output/validation/caption-studio-editing/original-project`. The original
Chrome tab was never controlled or reloaded. Its unsaved browser state was not
accessible and cannot honestly be described as recovered.

A separate connected copy is at
`output/captions/connected-caption-studio/Rog Music`. It carries the visible
Bahnschrift choice and yellow `dekhta`/`Kissi` words. The 40% vertical position
and 55% size are approximate reconstruction from the screenshot. This is
recorded in `editor_recovery` rather than called exact browser-state recovery.
The first word start was corrected from 0 to 1.68 seconds using the earlier
saved forced-alignment control; the audio bitstream matches that control.

## Validation

68 focused tests passed, including actual aspect-ratio MP4 rendering, retained
audio, exact empty word gaps, small-size export pixels, timing rejection,
spelling-only timing preservation, byte ranges, traversal rejection and retained
Origin protection.

Real browser checks exercised direct caption dragging, shrinking caption 2's
edge, a 15% size, resizing with the on-video corner, and draft restoration after
refresh. Temporary interaction changes were restored afterwards. A real click
on Save & export produced the MP4; Download MP4 saved it to
`C:\Users\Vineet Kumar\Downloads\captioned-preview.mp4`.

`output/validation/caption-studio-editing/real-export-check.json` verifies all
462 frames, original audio packet hashes, downloaded/exported file hashes,
17 timed subtitle events, an empty music intro and post-lyric gap, and sampled
overlay pixels equal to the selected word/color/position/size renderer output.
The export uses NVIDIA NVENC. No new model download or training was performed.

## Linked sizing, script clearance and styled word timing

Typography 5 support rows clear the measured ink bounds of the red script,
including ascenders and descenders. Browser and video rendering both reserve
the complete composition when hiding unspoken words; the surviving word is
not reformatted into a generic caption. Typography 1 word indices include its
decorative echoes and repeated tokens. Its eight composition variants are
covered by timing tests.

The shared size applies to numeric controls, sliders, wheel, corner dragging,
pinching and resize keys. Typography project rebuilding also enforces that
shared scale while retaining independent positions and word timing.

61 focused checks passed. Actual browser checks resized one group to 65%,
verified all four groups and all five preset selections stayed at 65%, then
returned the review copy to its original 100% scale. All five presets showed
only `tarah` at its active word timestamp. The real styled export, its original
audio, all 17 subtitle events, and sampled frames are checked in
`output/validation/linked-timed-typography/real-export-check.json`.

## Original template animation: cumulative lyric groups

The existing `Original template animation` (`phrase`) option reveals each word
at its saved start time, keeps it through gaps and the rest of that group,
and clears the group at its end before the next group builds. Typography 1
and 2 no longer reveal words on a fixed short schedule or fade the completed
group before its end. Typography 3–5 retain their original word entrances.
The original fonts, colors, positions, composition and shared resizing remain.
Changing a typography preset preserves the selected word-display option.
The separate `styled_spoken` and `spoken` options remain available unchanged.

63 focused tests pass, covering cumulative holds, final group boundaries,
all eight Typography 1 compositions, and both separate spoken-word modes.
The browser checks all five presets at partial-build, full-hold and next-group
timestamps. `output/validation/original-template-group-hold/` contains the
checks and a backup of the preceding saved project and export.


### Typography 5 reference correction

The owner's resumed reference request supersedes the clearance behavior
described above. Typography 5 now shares font origins so the white supporting
lines interlock with the Great Vibes ascenders and descenders. The earlier
clearance description remains here as historical context. The preview and
export use the same compact geometry and reference-specific anchors.
