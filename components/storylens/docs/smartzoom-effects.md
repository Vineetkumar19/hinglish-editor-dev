# SmartZoom sound and cut transitions

In SmartZoom, enable **Sound effects on zooms**, **Subtle overlays at cuts**, or both.
Both switches are off for a plain zoom edit. The chat understands, for example:

> Run SmartZoom on this video with varied zoom sound effects and subtle cut transition overlays.

The owner's current SmartZoom policy uses only basic Whoosh, Swoosh, Swish,
Woosh and Zoom from `config.zoom-sounds.local.json`. The collection is in
`library/zoom-approved/whoosh`: three supplied files and six selected online
variants. Missing approved files stop the sound step; the general library is
never silently substituted. The local CLAP model listens to these selected files.
The local language model chooses the individual files and overlay types. The tool
restricts sound choices to that collection and limits transitions. Each whoosh starts
at the exact movement onset and is stretched without changing pitch to its exact
duration, with short click-free edge fades. Nearby speech sets the quiet level:
the effect body targets 22 dB below speech, with a separate peak ceiling. It adds no music.

Short videos keep one smooth direction per actual shot, using the approved slower
entrance and a fixed focal point. Overlays occupy only a few frames around selected
real cuts. They do not change the camera path. Long videos retain major-point
pacing; overlays are only eligible when a zoom entrance matches an actual cut.

When effects are added to a recognized finished SmartZoom video, its saved camera
plan and original source are reused. The tool does not zoom the finished pixels
again. Export fingerprints also recognize identical copies in another folder.
Keep the original source and editor output folder available for this continuation.
Currently, add effects to one approved export per request.

For an A/B comparison, render the whoosh-only version first. Adding sound and
cut overlays to that recognized version locks its sound choices and rebuilds the
same mix from the original dialogue. The local model selects three or four soft
dissolves or feathered left/right wipes from a bounded menu. These blend actual
neighbouring footage for 0.3 seconds at selected cuts, at least six seconds apart.
They preserve the existing camera plan, total duration and clip order. Existing
approved light overlays remain locked when replacing sounds on older exports.

Outputs include the finished MP4, editable `ZOOMED_SEQUENCE.xml`, `zoom-effects.json`,
individual sound stems and the mixed WAV under `sound/`, and transparent MOV
overlays under `transitions/`. The review page lists the chosen sounds and times.

CLI: `python -m hinglish_zoom --input VIDEO --sounds --cut-overlays`
