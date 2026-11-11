## Naming reconciliation — 4 November 2026 (latest)

The owner authorized descriptive source renaming and matching app names. This supersedes the old instruction to leave source filenames unchanged, for this migration only. The six actual caption files match existing registered SHA256s; no new caption source was present. Stable original numbers and renderer IDs are retained. 04 is a historical duplicate and 07 is absent; neither is replaced by another style. Original approval/review states and all rendering geometry remain unchanged.

Current mapping and reversible receipts: `A:/Workflow_Automation/style-reference-refresh/naming-manifest.json`. Main Auto Captions now also lists the existing Serif Circle and Kinetic Gold families previously hidden by its five-family filter. This is catalogue restoration, not new creative approval or a claim of exact native render parity. Consult `$motion-graphics-videos` for the eight separately studied motion references and their source-bound measurements.

# Caption style references

The owner's reusable style reference folder is `A:\Full Drive\Styles`.
Saved at the owner's request on 2026-10-22 for future caption and style tasks.

Subfolders: `Photos`, `Videos`, and `Motion Graphic videos`.
Keep the source references in that folder unchanged. New tasks can identify
individual examples from this folder rather than uploading them again.

Current caption preference: Kinetic Documentary has no background stripes,
keeps white lettering, and defaults to 90% of the measured reference size.
The normal caption editor size control remains available.

Added screenshot presets: `documentary_outline` (hollow white hero with bold
support) and `documentary_echo` (solid white hero with a faint outline echo).
Both use the same 90% default size and support normal caption editing.

## Numbered reference series (2026-10-22)

The owner supplied eight videos and requested Caption 1 through Caption 8,
in the left-to-right order in `image(20261022-054808).png`. The exact source
paths, hashes, order, and review state are stored in
`hinglish_captions/reference_catalog.json`.

Work through these references one at a time. Caption 1 is the leftmost
Discover Stunning family dinner `(1).mp4` clip, featuring the curly-haired
speaker and tight white/blue Inter lettering. Its template ID is `caption_1`.
Caption 1 uses Inter 3.19 Bold and Medium, bundled with the full font license.
Its motion was revised after native 30000/1001-fps video-1 frame inspection:
supporting runs slide from the left, blue words rise independently, and the
`absolutely / explode` composition uses a shorter vertical travel. Translation
and opacity progress linearly, then hold still until the cue cuts. Recipe
entrance durations and simultaneous word groups are shared by the browser and
MP4 renderer in `caption_one_reference.json`. There is no added zoom, spring,
camera movement, or exit fade. The 30-second sample uses source-like word beats;
saved manual timing edits are preserved. Frame measurements and fit confidence
are in `tmp/caption1-motion`; these are sampled motion checks, not a claim of
pixel identity for every reference frame.

Latest owner correction: "one big word" means one large word in the middle of
the three-line design, NEVER an exclusive frame or lines replacing each other.
The small top line remains when the main word enters, and both remain when the
small bottom line enters. Hold all three together until the next caption group.
Caption 1 keeps the reference's support-left / main-up directions with only
12 px travel and smooth starts/stops over 650 ms for support and 750 ms for the
main word. Do not shorten that motion to fit individual spoken-word durations.
Each line starts on its first spoken word. Glyphs use stable masks and fractional
translations. Browser glyph assets are reused during playback.
The active demo is the 30-second Taj Mahal script with real generated narration
and 65 speech-engine word timestamps, adjusted with the same tempo as the audio.
It exports at 60 fps. Its narration and timing are bundled in
`hinglish_captions/demo_media/caption1-taj.wav` and `caption_one_taj_words.json`.
The demo uses timed compositions with overflow continuation slides, keeping every narration
word and its original timestamps. The earlier source measurements remain as
reference data; the active motion settings are `smooth_motion` and the demo
layouts are `demo_phrases` in `caption_one_reference.json`.

Latest alignment correction (screenshots 1000263688/3692): use two centered
lines when the main word contains at least eight letters; omit its third line.
Shorter main words keep the cumulative three-line layout. Align the top and
main left edges, and tuck the footer inside the main word's visible ink bounds
with matching right edges. A wide header must never determine the footer edge.
Latest owner correction supersedes the earlier footer fitting approach: never
shrink supporting text to fit, and do not remove overflow words. Carry overflow
to a NEW caption slide at its first word's actual narration time. Keep the
normal 46 px support size, tight line gap and main-word right-edge alignment.
Measure visible ink when positioning the footer; lowercase endings without
tall ascenders must not leave a larger gap merely because the baseline matches.
For the Taj demo: "Every detail / INVITES / you to" continues with "slow / DOWN";
"Some / PLACES / are more" continues with "than / BUILDINGS"; "They become /
STORIES / that the" continues with "world / REMEMBERS". Every original word
and timestamp is retained. Two-word continuations use a header and main word.
The owner specifically removed "glows softly", "at the carved", and "beneath"
from the MARBLE, CLOSER, and SHINES caption displays. Preserve the narration,
word timestamps and editable transcript. The display-only omitted indices are
explicit in the demo recipes; do not delete spoken audio for typography fixes.
Captions 2–8 are pending. Keep the prior typography styles available until
their corresponding numbered reference is reviewed.

Typography 5 spacing investigation was paused when the owner changed the
order to video 1 first. Its proposed changes were set aside under `tmp` and
its existing behavior restored; it has not been presented as fixed.

The owner explicitly requires confirmation of each numbered caption style before
work or export begins on the next one. Caption 1 is awaiting confirmation.


## Current owner decisions (supersedes the historical display omissions above)

Caption 1 is approved: the owner said "Perfect loved it ... Name it caption 1."
Keep the approved name **Caption 1**, full 65-word narrated Taj Mahal script,
18 visible continuation slides, saved geometry and speech timestamps. Do not
hide or remove words to obtain a layout. Earlier MARBLE/CLOSER/SHINES display
omissions and the old two-line tail suppression are superseded: "glows softly",
"at the carved", "beneath", "changes with the light", and "in the water" all
remain visible in their speech-timed slides. Caption 1 is no longer awaiting
confirmation. Its approved artifact hash is in reference_catalog.json.

The owner next requested resuming the work that was paused before Caption 1:
**Typography 5**, its red Great Vibes script and compact interlocking white
support. Resume that existing style, using Photos/Screenshot 2026-09-28
191534 through 191704 as the typography references. This is not authorization
to build all numbered captions at once. Captions 2-8 remain pending.

Measured reference faces are Great Vibes (about 82 px in the cropped examples)
and Arial (26 px). Supporting lines share origins with the script: their
vertical regions may overlap the calligraphy. The earlier rule requiring
script clearance is superseded for Typography 5. Keep all words and their
timings; keep ordinary size, position, font and color editing available.


## Caption 2 review (owner authorized after approving Typography 5)

The owner approved the resumed Typography 5 sample and explicitly requested
Caption 2 next. Caption 2 is now `caption_2`, using the second source in
reference_catalog.json (the NY-cap speaker with lime captions). Caption 3 and
later styles remain pending until the owner approves Caption 2.

The source contains 507 native frames at 30 fps. Analysis contact sheets,
font fits, per-frame measurements and native on-screen appearance times are in
tmp/caption2-reference. Caption 2 uses lime Inter lettering, floating white
support, word-level blur reveals, a measured settling zoom/growing zoom,
the moving outline paper plane, a drawn red strike-through for the matching
"your Content is failing" composition, a red recording dot, and two stacked
warning cards with the light Inter face. Source-level behavior and the full
Taj Mahal compositions are in caption_two_reference.json; browser and MP4
use the same composition roles and time curves. The lateral entrance settles
over 200 ms; its blur reveal uses a separate 300 ms clock.

The primary review is output/share/Caption-2.mp4: 30 seconds, 60 fps,
65 visible Taj Mahal narration words, unchanged speech timestamps and audio.
The long opening uses one supporting header and a complete footer to prevent
colliding floating headers. No words are hidden or deleted. An internal
reference-timing study also checks the source's original caption events and
intentional caption-free gaps; it is not the primary all-words narration demo.
The normal demo is /caption-output/template-demos/caption_2/report.html.
Size, position, word colors, fonts, timing and ordinary MP4 rebuilding remain
available through the existing caption editor.

The exported MP4s, audio packets, native frame counts, all-word row coverage,
preview/export clock parity and approved Caption 1/Typography 5 hashes were
checked. Live editor validation is blocked by the current app connection.
Exact pixel/frame identity with the reference is not verified. Do not describe
this as a verified end-to-end app workflow until it is checked live.

## Caption 2 owner revision: settling zoom and tighter footer

The owner likes the opening slide's large-to-small settling motion and now
requires it on every Caption 2 slide. This supersedes the growing zoom and
static focus compositions described above. All known and new compositions use
the opening settling curve, remaining at their final scale after one second.
Keep the existing word onsets, blur and lateral entrance timing.

The warning-card appearance in screenshot 1000263839.jpg is rejected. Replace
its cards with the same white header, lime main word and white footer pattern,
retaining every word. The narrated replacement is "Every detail / Invites /
you to slow down." The third line must sit higher and slightly overlap the
main lettering, as the main word overlaps the header. Anchor it to visible
letter bodies with a ten-percent overlap; descenders must not push it down.
Supporting font sizes stay unchanged. Browser preview and MP4 share these
rules. The previous configuration is retained in tmp/caption2-revision.

Caption 2 remains under owner review. Caption 3 is not authorized yet.

## Latest owner decision: Caption 2 approved; begin Caption 3

The owner said: "Perfect loved it... Just remove that click icon . And move
to caption 3". This supersedes the pending Caption 2 review above. Remove the
paper-plane/pointer outline from all Caption 2 compositions, preserving its
approved settling zoom, overlap, full 65 words and original speech timing.
Caption 3 is now authorized; Caption 4 still requires a new owner approval.

Caption 3 uses the third video in reference_catalog.json, the 640 x 1136
Solution Wagon motion-graphics reference (1481 frames at 30 fps). The source
frames, font comparisons and entrance/zoom measurements are in
tmp/caption3-reference. Its caption design uses heavy Inter, black and vertical
grey gradients, compact support, soft-focus reveals, a settling camera zoom,
character wipes inside dashed selection boxes, corner handles, and large
numerals when the actual text contains a number. No pointer icon is added.

The Caption 3 template is caption_3. Its primary sample retains all 65 Taj
Mahal narration words and their exact existing timestamps, with the same voice
at 60 fps for 30 seconds. Its light paper demonstration background makes the
source's black and grey letters readable; that background is separate from
the transparent caption layer. The source's branding, illustrations, clocks,
characters and promotional ending are not part of the caption template.
Preserve supporting font sizes; wrap a complete supporting line when needed.
All known and generic compositions retain every word. Ordinary font, size,
position, word colour, timing and MP4 editing remain available.

The browser and MP4 share composition data and motion curves. Check the actual
export against the renderer, original narration, timestamps and approved
Caption 1/Typography 5 files before presenting it. The app connection currently
blocks live editor validation. Keep that limitation explicit; do not claim
verified end-to-end application playback or pixel identity with the source.

## Caption 3 owner revision: compact three-line captions

The owner explicitly loves Caption 3's camera movement and requests retaining
its zoom-in/zoom-out timing. The approved zoom curve and camera intervals are
captured in tests/fixtures/caption_three_approved_camera.json. New continuation
slides share their original camera clock rather than restarting that motion.

The crowded 8-9 word, four/five-line compositions are superseded. Use at most
five words and three visible lines: plain black header, exactly one large grey
shaded main word, and one short plain footer in a dotted frame. Never remove
words. Move overflow to a new slide at its original spoken onset; very short
continuations use a header and main word when there are no remaining footer
words. The narrated sample now has 17 slides and the original 65 word times.

The main word increases to 108 px at a 720 px design width. Support stays at
32 px above and 34 px below. Tighten the main gap to 3 px and the footer gap
to 10 px. Reduce frame padding to 10 px horizontally and 6 px vertically;
the frame follows the footer's complete width, not the changing word reveal.
Use a smooth quintic camera-independent box entrance: a small centred width
settle, 5 px upward travel, continuous dotted perimeter draw and smoothly
fading handles. Draw it with antialiasing and use subpixel transforms. The
same motion functions drive browser preview and MP4. Short function words
must finish revealing before the slide cuts. Keep all saved transcript words,
colours, positions, audio and timestamps during pagination.

Coordinate the whole composition's exit with the last spoken word. A short
footer such as "at" must be fully readable while the header, hero and dotted
frame still hold in focus. Cap the shared exit duration at one quarter of the
last word's available slide time (25 ms minimum, 160 ms maximum). Do not let
the old fixed 160 ms exit dissolve the main word before that footer appears.

Caption 3 remains under review; do not start Caption 4. The source measurements
and previous 10-slide design remain in the revision checkpoint. Live editor
validation is still required before claiming the application is verified.

## Latest owner decision: Caption 3 approved; begin Caption 4

The owner said: "Perfect awesome... Now caption 4". This supersedes the
pending Caption 3 review above. Preserve the approved 17-slide Caption 3
export and its camera motion. Its approved SHA256 is recorded in the catalog.
Caption 4 is authorized. Caption 5 still requires the owner's next approval.

Caption 4 uses reference 4 in reference_catalog.json: 720 x 1280, 709 frames
at 30 fps, approximately 23.66 seconds. Native frames and motion contact sheets
are saved in tmp/caption4-reference. Its caption pattern has high-contrast
italic serif emphasis, a small offset italic header, a right-aligned italic
footer, black ink on light grey, soft-focus entrances and exits, and slow
camera movement. This is a caption template: reference hospital photos,
doctor/brain illustrations, decorative stars, arrows and end branding are
separate video content and are not inserted into the narration captions.

The installed Times New Roman Bold Italic face is the closest measured local
hero substitute (approximately 0.64 glyph-mask overlap for "you're", 0.61 for
"Spoken"); support uses Times New Roman Italic. These are approximations,
not a verified identification of the source's original typeface. The reference
uses variable placements and longer illustrated scenes; do not claim pixel or
millisecond identity between that video and the new Taj Mahal narration.

The new caption_4 style uses up to five words and three lines. It retains all
65 Taj Mahal words, their original speech timestamps and AAC narration in a
30-second 60 fps demo. Main type is 138 px at the 720 px design width; long
main words fit the safe width while support stays 52 px above and 42 px below.
Overflow continues at its actual spoken onset. Footer positions follow visible
glyph bounds with a 3 px gap. The header sits 2 px above the main glyphs.
There is no dotted box in this different reference's pattern.

Focus transitions use continuous quintic easing, adaptive reveal windows for
short final words, subpixel rise/scale, and a shared readable exit. The camera
eases between 1.0 and 1.09 over 1.8 seconds with a 7 px drift. Browser and CPU
export use the same role selection, pagination constraints and motion clocks.
Ordinary font, size, position, color, timing and MP4 editing remain available.

Caption 4 is ready for rendered-video review only after export verification.
Keep approved Captions 1, 2, 3 and Typography 5 byte-for-byte unchanged. The
current app connection fails, so live editor playback remains unverified;
do not call this an end-to-end verified Storylens workflow.

Caption 4 export review passed: all 1800 frames decode at 720 x 1280 / 60 fps,
65 spoken-word snapshots match the production renderer (maximum mean pixel
error 1.829 from video compression), audio packets match the original sample,
and the approved Captions 1-3 / Typography 5 hashes remain unchanged. All 90
caption regression tests passed. The narrated review is output/share/Caption-4.mp4.
Caption 4 awaits owner approval; do not begin Caption 5 yet.

## Caption 4 owner revision: align and tighten uneven gaps

The owner said the rest of Caption 4 is perfect and asked to fix only the odd
gaps, then emphasized: "Make the alignment of gaps perfect". Preserve the
existing typography, words, 19 cue boundaries, original narration times,
individual reveals, camera curves and camera clocks. Do not begin Caption 5.

Supersede Caption 4's percentage-based horizontal support offsets. The header's
visible left edge aligns to the main word's visible left edge; the footer's
visible right edge aligns to the main word's visible right edge. Measure actual
glyph silhouettes for vertical spacing, using a 3 px target at the 720 px design
width. The g in "glows" must not push an entire right-hand footer below its
descender. Small headers over "slow" and "world" must follow the nearby letter
body rather than a distant tall ascender. Keep headers above the body of a
slanted capital, avoiding an inline-looking header inside its empty triangle.

Browser and MP4 apply the same silhouette spacing rule; font-outline profiles
are cached so spacing stays fixed during word reveals. Saved previous Caption 4
code, profile, export and verification remain in tmp/caption4-gap/before.
The app connection remains unavailable, so live editor validation is blocked.

Spacing revision export checks passed: all 65 original word timestamps and
the original audio remain intact, 1800 frames decode at 60 fps, and per-word
export snapshots agree with the revised renderer. The four reported spacing
examples pass visible-ink alignment and non-touching gap checks. Fifty-eight
caption regression checks passed. Caption 4 remains under owner review.

## Latest owner decision: Caption 4 approved; begin Caption 5

The owner said: "Move to next style" after the revised Caption 4. This
supersedes its pending review above. Keep the approved Caption 4 export hash
7d4d201c089377c776047a5a887be1d5392594577fa1e172c10bd662d27ffe00
and its typography, optical spacing and motion. Caption 5 is authorized;
Caption 6 still requires the owner's next approval.

Reference 5 is the fifth video in reference_catalog.json: a landscape source,
714 x 408, 574 frames at 30 fps, about 19.13 seconds. Native frames, an
undistorted contact sheet, font comparisons and measured red-number motion
are saved in tmp/caption5-reference. Its type uses heavy Inter Black, compact
black support, red and cyan blue emphasis, a condensed comeback keyword,
oversized actual numerals, and close word clusters that build with speech.
The bundled Inter Black font matched the reference BHAI glyph mask at roughly
0.95 overlap. Impact supplies the similar condensed face; that separate face
is an approximation rather than a verified original font identification.

The source's U9MYNAME watermark, meme illustration, months and decorative
corner marks are separate video content. Do not add them or any extra words
to the sample narration. Caption 5's transparent caption layer is separate
from its flat white demonstration background. No click/pointer icon is added.

The new caption_5 template keeps all 65 original Taj Mahal narration words,
speech timestamps and AAC narration, in 19 compact slides and a 30-second
60 fps portrait review. Use at most five words and three role rows, placing
short support on either side of an emphasis word when the complete cluster
fits; otherwise use compact stacks. Overflow continues at its spoken onset.
Main Inter is 104 px, condensed emphasis 112 px, ordinary support 40 px,
selected support emphasis 58 px, and actual numerals 240 px at design width
720. Main words may fit the safe width; retain support sizes. Gap is 5 px.
Scale by min(width, height * 1.75) to retain the landscape source's proportions
as well as the portrait demonstration. Never center around changing visible
word bounds: the full cluster anchor must remain stable as words arrive.

Source-informed entrances use a 330 ms cubic settle, 42 px main rise and a
0.9-to-1 scale. Condensed words slide 38 px horizontally with a 180 ms fade;
support has a short 180 ms rise. Adapt reveal windows so even short final
words fully appear before their slide ends. Hold the complete phrase until
the next cue, as in the reference. Do not add a camera zoom absent from this
reference. Browser and MP4 share roles, composition rules and motion clocks.
Font, position, size, per-word color, timing and MP4 editing stay available.

Exact source frame identity is not verified. The app connection still fails,
so live Storylens editor playback remains unverified. Rendered-video review
and regression checks cannot substitute for that live application validation.

Caption 5 rendered-video review passed: all 1800 frames decode at 720 x 1280
and 60 fps for 30 seconds; 65 word snapshots match the production renderer
within video compression error; audio packets and original word timestamps
are unchanged. All 99 caption regression checks passed. Approved Captions
1-4 and Typography 5 remain byte-for-byte unchanged. The review export is
output/share/Caption-5.mp4. Caption 5 awaits owner approval; do not start
Caption 6 yet.


## Caption 2 restoration to the approved review (2026-10-22)

The owner rejected the later smoother/slower retune and requested the exact
Caption 2 previously approved with "Perfect loved it... Just remove that click
icon . And move to caption 3". The approval in reference_catalog.json identifies
output/share/Caption-2.mp4 by SHA-256
2173773bf5f17413fef398e81ce9d55a0b97fd024a66ec567a08e01076d07394.
This original file is intact. Its bytes were copied back to the canonical
caption_2/captioned-preview.mp4 and a fresh caption_2_approved review project.
The new review project isolates the original settings from older browser drafts;
the demo manifest opens that project for Caption 2.

The approved profile and browser/export motion were restored from the saved
pre-retune report: main slide 200 ms with cubic-out movement, text resolve
300 ms, fade 240 ms, and the original measured group scale curves. Keep the
approved composition, overlap, word roles, fonts, speech timestamps and
pointer-free version. Black/white background choices must not retune motion.
The rejected 650 ms motion is preserved under output/validation for audit;
it is not the current Caption 2. Do not use it as the approval reference.

The restored MP4 hash matches the approval exactly. Thirteen focused checks,
including preview/export motion parity, passed. Seven rendered-frame samples
match the preserved MP4 within compression error. Live editor validation is
still blocked by the unavailable app/browser connection; do not call this a
verified end-to-end app result. Current Save & export requires the running
app's caption capabilities to match the embedded preview profile.


## Caption 2 medium entrance and Caption 3 optical spacing (2026-10-22)

The owner's later instruction explicitly requests a main-word entrance between
Caption 2's original 200 ms and the rejected 650 ms version. Use 400 ms with
the approved cubic-out curve. All other Caption 2 profile settings, including
font, size, overlap, support reveals, fade, camera zoom and word times, stay
as in the approved baseline. Preserve output/share/Caption-2.mp4 and the
caption_2_approved review as the historical approved version. Current review:
caption_2_medium, with a fresh project identity to avoid old browser drafts.

The owner clarified that the attached gap screenshots show Caption 3. They
read "the Yamuna", "Carved / Flowers", and "Imagine a / Monument". Adjust
Caption 3's supporting header only: measure actual column silhouettes above
the main word, and move the header down until the closest visible letters
have the existing 3 px design clearance. Keep already-tight lines, main-word
and footer baselines, camera motion, word timings, fonts and colors unchanged.
Compute from the whole line so word reveals cannot cause layout jitter.
Current review: caption_3_compact. The original approved Caption 3 MP4 remains
preserved. These revisions await owner review; do not mark them approved from
test results. Screenshot byte download and live app validation are blocked
in this session. Rendered checks and motion/layout parity tests are supporting
evidence only.

### Caption 2 owner correction — 23 October 2026

This correction supersedes the earlier upper-left header interpretation.
Align support rows to the RIGHT edge of the main text. Show at most seven
words in a frame; overflow starts a new frame at its original word time.
When a main word has more than eight alphanumeric characters, use only the
top support line and main line; move the following words into a new frame.
Keep the exact fonts, keyword fade and shared settling zoom. Reserve enough
horizontal room for the opening zoom so long rows cannot clip. Preserve
chosen caption size and position. No words may be dropped or reordered.
The owner approved the smoother Caption 3 dotted frame and requested the
Caption 2 demonstration next. Caption 2's corrected review is in
output/captions/caption2-right-aligned-review and awaits owner approval.


## First Klickpin caption reference — active review, 23 October 2026

Owner requests two source styles, one at a time. Only the first unnumbered
Klickpin video is in progress. Do not start the `(2).mp4` style until owner
approval. Reproduce captions only, excluding corner ornaments and stickers.
The first approximation was rejected: do not treat it as an approved design.
Match individual word directions and timing instead of assigning one generic
entrance. Preserve staggered support around Overthinking, Decide and Reality.
Include text-linked underlines and large faint echo lettering. Exact source
font identity and frame parity are still unverified; do not claim exactness.

Split the dense Perfect/Saal composition into two slides: Perfect with
“idea ka wait karte karte log”, then Saal with “nikaal dete hain”. Tighten
visible line gaps and maintain real spaces between supporting words.
Horizontal maximum seven words; vertical maximum four, with compact balanced
reflow and the same text roles/motion. Do not replace Saal with nikaal as hero.

Owner explicitly permits a 50-second browser preview. The provided first
source is 21.67 seconds, so the new preview repeats it to fill 50 seconds.
This does not increase the small Premiere validation limit. Current local
review: output/captions/kinetic-gold-50s-review/report.html. It is a draft,
not finalized and not globally selected by default. Preserve Caption 1–5 and
all previously approved styles. Await this owner's feedback before moving on.

### First style motion follow-up — 23 October 2026

Owner likes the current design and requests only three refinements: independent
smooth movement of the faint echo lettering, a natural curved underline sweep,
and complete on-screen bounds for Confidence including its shadow. Keep the
accepted typography, alignment and compact spacing. Revision 4 adds a gentle
shadow drift/settling scale and a tapered curve revealed along its length.
The entire echo composition reserves horizontal margins in both orientations.
The underline stays with its keyword when a vertical caption is paginated.

Owner explicitly requests a Premiere check again. Use the isolated 10-second
kinetic-gold-premiere-motion-review project; retain the 50-second browser review.
Foreground words remain native editable graphics. Echo lettering and brush
strokes travel on an independent transparent decoration track. Browser bounds
were checked live in horizontal and vertical; native inspection is still pending.

The owner's subsequent vertical screenshot identified undersized inline text and
an overlong, right-offset stripe. Revision 5 enlarges each vertical inline page to
use the available width (still at most four words), then fits and centers the
stripe beneath that actual page. This was verified in the live Storylens preview
with “Baad aati hai”. Native vertical review uses the separate 720×1280,
10-second kinetic-gold-vertical-motion-review sample. The first horizontal
project opened successfully in Premiere; complete visual/native parity has not
yet been signed off. Do not infer final style approval from that import alone.

### Owner approval and second reference — 23 October 2026

Owner said “awesome perfect..move to next caption” after the vertical correction
and the native vertical sample opened. Kinetic Gold revision 5 is approved and
is now available in the Cinematic list. Preserve this accepted design. The
720×1280 project opened in Premiere at half preview resolution with native word
tracks and the visible animated underline. Complete frame-by-frame native
parity was not exhaustively checked; do not claim that it was.

Proceed to the second `(2).mp4` reference only now. It is a different 49.73-second
vertical video: small white sans-serif captions interspersed with italic serif
emphasis and text-linked circles/underlines. Study its own timings and motion;
do not carry the gold first-style typography into it. Show a separate draft in
Storylens for approval, preserving horizontal seven-word and vertical four-word
limits and export support.

### Second reference correction — 23 October 2026

The owner rejected the first second-style adaptation. The source supplies design,
alignment and motion only; preview captions and speech must be English or Hinglish.
Rebuild the close stacked sans/italic-serif compositions, measured upward blurred
row entrances, traced green/red ovals, and tapered S-shaped underlines. Do not add
corner artwork. Preserve the approved Kinetic Gold style and Caption 1–3.

Current review: output/captions/serif-circle-english-v2-review/report.html, 49.75
seconds of English narration, 36 captions. Vertical has at most four words;
horizontal at most seven. The second style remains a review-only draft awaiting
owner approval. Its four-line compositions include the English equivalents of
the supplied screenshots, with separate spacing corrections for longer English
words. Shared row baselines prevent neighboring words from drifting vertically.

Font silhouette comparisons favored Playfair Display Bold Italic with tight
tracking, and Inter SemiBold/Inter Display SemiBold Italic. Official font files
were downloaded, bundled with provenance and license, and registered for the
current Windows user. This is a measured visual identification; original project
font metadata is unavailable, so exact font identity is not independently proven.
Premiere's installed-file checks pass for all three faces. Native Premiere visual
and motion parity for this second style has not yet been verified; do not claim
frame-identical reproduction or final approval.

Live validation: the revised 49.77-second video reached its natural end in the
running Storylens browser. Inspected vertical mixed-font and red-circle layouts,
horizontal red-serif emphasis and compact text spacing. Four focused renderer,
pagination, timing and editable-color checks pass. Font handoff preflight verifies
all three installed faces. MP4 export and native Premiere visual parity remain
unchecked for this draft; browser playback does not establish those results.

### Fifteen-second Premiere test and font repair — 23 October 2026

Owner requested a 15-second native test, then reported the Resolve Fonts warning
for Inter-SemiBold. The installed-file preflight alone did not prove Adobe face
resolution. An exact-outline/metric copy now uses the unique family Storylens
Circle Sans SemiBold (PostScript StorylensCircleSans-SemiBold); export maps only
the bundled Inter-SemiBold face to that copy. No glyph outlines were changed.
The alias was registered for the current user and Premiere was restarted after
saving both test projects. The corrected project reopened without the font
warning, displaying white sans and Playfair serif words, native blur/position/
opacity keyframes, and its independent traced annotations at quarter resolution.
Current native review: output/editor-handoffs/bea8f297bfef5f/CAPTIONS-001.prproj.
The 15-second Storylens MP4 rendered successfully. Preserve the second style's
draft status; this check does not establish exhaustive source-frame parity.

The test also fixed CPU caption renders waiting for unrelated GPU jobs, and
creation of missing overlay output folders. Native export cache signatures now
include the font manifest and adapter so font fixes invalidate old projects.

### Owner approval — Serif Circle — 23 October 2026

After the font repair and native playback, the owner said “yes its great .. save
it”. Serif Circle is approved and available in Cinematic. Preserve this accepted
design, typography, compact spacing, row entrances and traced annotations.
The 15-second native sequence reached 00:00:15:00 at quarter resolution after
restart, without a missing-font warning. The Premiere project was saved. Do not
alter this approved style while developing another caption style. Approval does
not establish exhaustive frame-by-frame parity beyond the reviewed sample.

### Caption 2 replacement requested — 23 October 2026

The owner explicitly requested replacing the previously accepted Caption 2 with
the supplied family-dinner-ideas reference (16.9 seconds, 720x1280, 30 fps).
This new instruction supersedes preservation of the old Caption 2 design only.
The owner selected “Match this reference exactly” when asked about the previous
four-word vertical limit: preserve the source groups, including split headers,
two-word lime lines and the two warning-card rows. Preserve all other approved
caption designs, including Kinetic Gold and Serif Circle.

Prior profile and regression checks are retained in docs/caption-two-before-
reframe-2026-10-23.json and docs/caption-two-tests-before-reframe-2026-10-23.py.
Revision 7 restores the measured source compositions, uses Inter Bold plus the
thin Inter warning-card face, sampled lime #E1FF5D, upward blurred word reveals,
and the shared zoom clock from the first word. The opening settled lime ink box
is checked against native source frame 45 within four pixels. Source onsets,
later motion curves and exact visual parity still require owner review; do not
claim that a handful of matched samples proves every frame identical.

Review: output/captions/caption2-reframed-reference-review/report.html. Captions
use the supplied English words and source audio. Keep the replacement pending
approval; do not apply any part of its typography to the other accepted styles.
Animated cards/annotations now have a separate transparent Premiere layer while
words remain native, but the revised Caption 2 native workflow is not yet tested.

Owner follow-up: the first attached screenshot means the warning-card layout.
Remove that layout and retain its spoken text in the lime caption typography as
two consecutive groups. Revision 8 adds soft tinted bloom and white support glow,
an independent dark offset shadow, a correctly larger/right-shifted paper plane,
and a tapered red strike. The “you are unsure” footer uses the regular face.
Glyph comparison of native Understand lettering favored bundled Inter Bold with
tighter tracking; exact original project/font metadata is still unavailable.
The owner has not approved this revision. Do not mark it finalized.

Validation of revision 8: 22 focused reference/legacy regression checks pass,
including preserved word order/timing, source opening ink bounds, editable main
word color, both orientations, and independent glow/shadow decoration layers.
The old layout checks run against the saved prior profile rather than asserting
that its superseded three-row rules describe the replacement. Main-font glyph
comparison is recorded in tmp/caption-two-replacement-study/main-font-comparison.jpg.

Latest owner request: animate the cursor/click with the source motion, use it
two or three times, once per fifteen seconds. The new fifty-second review repeats
the reference words/audio to demonstrate three arrivals at 2, 17 and 32 seconds.
Each follows the same source trajectory/rotation, settles, presses/releases once,
and fades. The cursor has an independent clock so crossing a caption boundary
does not restart its entrance or inherit a new caption's zoom.
Current review: output/captions/caption2-glow-cursor-review/report.html.

Owner's next instruction supersedes the preceding cursor request: “remove the
mouse cursor .. rest is perfect check on premier pro”. Revision 9 disables all
cursor/plane events and retains the accepted glow/shadow/typography/strike.
The remaining Caption 2 design is owner-approved. Run the isolated fifteen-
second caption2-glow-premiere-15s review through Storylens's native handoff.
Do not claim native parity until the actual imported result is inspected.
