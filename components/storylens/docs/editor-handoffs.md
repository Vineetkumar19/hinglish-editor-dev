# Local editor handoffs

Completed feature cards and Caption Studio show Premiere Pro, CapCut and DaVinci
Resolve logo buttons. The Profile button opens the full retained creator settings.
Quality checks continue internally; result cards no longer expose report buttons.

## Finished media

CapCut Desktop 9.6 receives a new native local project containing the exact
finished render (five seconds for still images). This preserves the caption
appearance, zooms, sound and transitions. Those effects are baked into the video.
No cloud upload or CapCut panel installation takes place. The project index is
backed up before adding a project; existing projects are never overwritten.

Premiere downloads editable FCP 7 XML and opens the installed application. Use
File > Import. Resolve retains its scripting import into an open Resolve project.
An export being ready does not prove the target editor imported it successfully.

## Editable captions

The exact bundled custom font files can be installed for the current
Windows user with `.venv\Scripts\python.exe tools/install_caption_fonts.py --install`.
Without `--install`, the tool only inspects. It checks each file against
`hinglish_captions/fonts/sources.json`, retains existing font files and registry
entries, and records the installed hashes in
`output/editor-handoffs/caption-font-installation.json`. Windows' existing Arial,
Impact, Times, Segoe, Georgia, Bahnschrift and Trebuchet fonts are reused.
Restart an editor if its font list was already cached. Installing fonts does not
by itself preserve the design in an SRT export.

`tools/prepare_editor_font_instances.py` creates static Light, Regular, Bold and
Black faces from the verified Inter variable reference, without changing its
outlines. These have distinct Windows legacy family slots and real typographic
family/weight names, preventing Black from being substituted by another weight.
The original and previously installed font files are preserved. Install these
faces with the same installer, then restart Premiere to refresh its font cache.

Caption Studio's Premiere logo prepares native editable word graphics and opens
the resulting `.prproj` with one click. CapCut offers Finished video and Editable words.
The Premiere button saves the current text, timings, colors, size and placement
before opening the native project. An MP4 render or download is not required.
Finished-video handoffs still require a current finished render. An export that
is already running must finish before another handoff starts.

CapCut word mode uses clean source picture and a separate native text track with
one block per saved word, plus a downloadable one-word SRT. Font files, selected
word colors and basic positioning are carried in the native project. Complex
Storylens typography, gradients, choreography and animation are not reproduced
exactly in this editable mode. **The owner requires matching caption designs;
this remains unfinished.** Choose Finished video to retain the exact appearance.
Do not present the simplified editable version as a matching design.

Premiere word mode now supplies a native `.prproj`, with clean source picture
and separate native text graphic clips. Font face, size, tracking, colors,
gradients, outlines, saved cue placement and sampled position/scale/opacity/focus
curves come from the existing caption renderers. Words remain editable text.
The source graphic canvas matches the sequence dimensions; paragraph boxes span
the canvas to prevent long-word wrapping. Row baselines account for descenders.
Playback requests quarter resolution, and only one project opens at a time.
Premiere limits 720-by-1280 sequences to half resolution (360-by-640 playback);
the generated project does not enlarge footage just to enable the quarter option.
The clean-video XML and one-word SRT are retained as manual alternatives.
Resolve caption behavior is unchanged.

Caption 1's 20-second sample has 45 independently editable word graphics, the
saved blue gradient and Inter Medium/Bold faces. The full support row above
REFLECTIONS and the three rows around MARBLE were inspected in Premiere. The
owner's permanent spacing rule uses equal visible-ink gaps above and below the
main word (`caption_one_reference.json`, `alignment.ink_gap`), shared by browser
preview, rendered captions and native graphics. A live Caption Studio button
test opened this native project in Premiere, where Inter Bold text was selected
in the native inspector.

All 14 selectable styles have native word/font/geometry/motion extraction.
Decorative cards, colored strips, selection frames, wipe masks and separate
glow/shadow copies are not all converted into native layers. The handoff shows
a limitation notice for styles with those decorations. Do not claim full visual
parity for those styles or for CapCut; finished video remains the exact-appearance
alternative. Renderer extraction is thread-local and regression-checked to leave
normal preview pixels unchanged.
Premiere can pause for several minutes while loading a project on this machine;
the native loading performance issue remains unresolved.

## Smart Clean and Script Edit on saved timelines

The Premiere CEP/UXP source now exports the active sequence for these modes
instead of passing whole source files and discarding the owner's existing trims.
Storylens prepares an analysis movie, runs its local editing tools, and maps the
kept intervals back onto the original source video/audio clips in a new XML.
Script edits requiring review are not silently imported as approved results.
UXP active-sequence export requires the previously documented Premiere 26.2 API.

In Storylens, Choose footage from CapCut > Use saved timeline reads a saved
straight-cut project and snapshots it as XML. Save in CapCut before selecting.
The output returns as a new native project with separate editable cuts and camera
audio. It does not change an unsaved in-memory CapCut timeline. Linked source
paths rewritten by CapCut into draft placeholders are resolved within the project.

Current cut round trips accept contiguous straight video cuts with linked camera
audio. Extra tracks, transitions, speed changes, framing/crop or processing
references outside the supported neutral metadata stop with a useful message.
Export layered projects as MP4 for processing when retaining the entire picture
is required. Unsupported features are never silently discarded.

## Validation on 22 October 2026

Live Storylens UI checks verified the profile popup, SVG tool/play icons, three
editor buttons, caption playback and an unsupported-timeline error. A real local
Smart Clean run on a saved CapCut sequence kept 44.1 seconds and removed 7.1;
the generated native project contains 22 video segments. It opened and played
in CapCut with live audio meters and separate editable clips. A separate native
caption project opened with 65 text blocks and the first word's editable text
inspector. Exact styled finished-video playback was verified in CapCut previously.
Premiere recovered on retry. Its native project now has 65 separate caption blocks
and a 44.1-second Smart Clean sequence with separate camera video/audio cuts;
picture playback and live audio meters were verified. The revised in-app Premiere
panel remains uninstalled and unverified. The caption demo was placed using
Timeline start; use Source timecode when retaining the original leading gap.

Focused regression checks cover source trim/audio mapping, path restrictions,
project-index preservation, handoff reuse, subtitle intervals and local APIs.
These checks supplement the live evidence, not replace it.

## Caption readability correction, 23 October 2026

Caption 3 now keeps a compact 8-pixel full-ink gap at its 720-pixel design width,
scaling with the owner’s chosen caption size. Supporting rows use a minimum
40-pixel size and neutral tracking. The preview and renderer share these rules;
the previous silhouette-nesting step no longer pulls headers into the main word.
The native importer explicitly writes the document shadow flag. This prevents
Caption 1’s 100% black shadow from appearing on clean Caption 3 words. Caption 1
retains its own shadow. The flag was identified by toggling Shadow in Premiere
and comparing its saved native files; those on/off fixtures cover the regression.

The owner approved the compact Caption 3 result on 23 October 2026. Its native
reference is `output/editor-handoffs/9a192159705fb9/CAPTIONS-001.prproj`, with
live evidence in `tmp/caption3-compact-premiere-proof.png`. The corresponding
10-second Storylens project is `output/captions/live-10s-caption_3/`.
Preserve this approval when validating other styles. Caption 4, Caption 5,
Typography 5 and Documentary Echo require the same real preview/button/native
inspection sequence; they are not verified merely because Caption 3 passed.
The repeatable owner instruction is retained in AGENTS.md and the local model's
`caption-approved-repeat-validation` workflow-memory section.


### Caption library update, 23 October 2026

The owner retired Typography 1, Typography 2 and Quiet Minimal from both new and saved-report pickers. Eleven choices remain; Caption 1 is the new default. Legacy rendering definitions remain available to reopen existing projects.

Documentary Echo, Kinetic Documentary, Documentary Outline, Typography 3 and Typography 4 use the approved close-framed entrance settling from 1.18 to 1.0 over 2.1 seconds after the anchor word starts. The entire composition moves uniformly, preserving each design and its existing word reveals. Python rendering, browser preview and editable Premiere word keyframes share this motion profile. Live sample evidence and limitations are recorded in `output/editor-handoffs/live-caption-validation.json`.


### Caption 2 fade and Caption 3 frame — 23 October 2026

Caption 2 keywords now fade at their composed position, without the lateral entrance or keyword blur. The approved shared zoom is retained in both browser and export. Saved reports receive the current preview engine.

Caption 3 Premiere imports include the original animated dotted selection frames on a separate transparent QuickTime layer beneath the individual native word graphics. Saved caption size and position apply to both. The frame itself is not a native editable shape; regenerate the import from Storylens after changing its geometry. Source footage remains unchanged. A ten-second sample was rendered in Storylens, opened through its Premiere button, and checked during native playback at half resolution (720p). Evidence is recorded in output/editor-handoffs/live-caption-validation.json.
