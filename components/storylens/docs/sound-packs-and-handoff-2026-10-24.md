Sound Design update — 24 October 2026

Owner packs from A:\Editing\Sound Packs were copied into library/owner-sound-packs,
with SHA256 provenance sidecars. Original packs remain intact. Both the multipart
RAR's nested ZIP and the Omnia 7z were extracted to a separate managed directory.
There are 1,282 playable imported effects; 2,203 total playable effects including
the existing collection. Mac resource forks are unreadable metadata, not extra
effects. Duplicate content is reused. No additional music track was confidently
identified; the six existing music tracks remain available. Licence metadata is
owner-supplied/unknown, never relabelled CC0.

The two new reference videos were sampled visually, transcribed locally and
analysed through Demucs non-vocal residuals and local CLAP windows. These are
approximate composite descriptors, not verified source identities or counts.
Both reference profiles and script-led guidance are saved alongside, rather than
replacing, the prior selected E7 reference. The sound policy retrieves both on
new generations. This is reference retrieval, not model-weight training.

Source music removal uses isolated Demucs 4.0.1 / official htdemucs inference.
The UI defaults to Remove existing music (keep voice); unchecking preserves the
original mix. A failed separator stops with a shared plain-language error rather
than falling back to attenuation. Original sources remain intact. Exact sample
count and start origin are preserved. Demucs may retain music/effect leakage or
introduce vocal artefacts; listening approval is separate from timing checks.
Separation receipts survive remixing, and exports use the same dialogue stem
without doubling the original source audio.

The Sound Design report now has the shared editor buttons, direct timeline/full
mix downloads and same-origin remix calls on nondefault service ports. CapCut
gets independent voice/music/effect lanes using exact microsecond placements;
Premiere gets stereo lanes in SOUND_SEQUENCE.xml. Sound handoff cache signatures
include source plans and audio contents. Existing projects are preserved.

SoundCraft's available source confirms overlapping per-clip mixing, inserts,
automation and buses, not a built-in video understanding/directing AI. Its Rust
engine is not installed/integrated. Epidemic's official tutorial describes a
multi-layer draft with music, ambience and effects plus individual volume/fades,
trim/move and XML exports. Neither that tutorial nor the prior browser bundles
expose the private sound-selection AI. Relevant source evidence remains in
docs/soundcraft-deep-review-2026-10-24.txt and docs/epidemic-layer-mixer-code-2026-10-24.txt.
Official references: https://github.com/storytold/soundcraft and
https://www.epidemicsound.com/tools/studio/tutorial/.

Evidence: output/sound-new-samples-2026-10-24. The actual CapCut app opened the
previous 44-effect comparison as a layered timeline; screenshot retained.
The report's Premiere preparation completed. Actual File > Import of the XML
created 47 items (44 effects, music, video and sequence), and the sequence opened
with the original picture and stereo audio lanes. The dedicated Storylens
Sound Design Review 20261024 project was created in output/editor-handoffs/d84c48375be676;
the imported timeline was subsequently saved at the owner's request to close
Premiere and free memory (50,982-byte native project, 15:41:31). Native full
playback and listening acceptance were not checked. Screenshot retained as
premiere-imported-project.png. This checks the previous result's native handoff;
the new isolated-dialogue path has separate regression checks and sample
separation evidence. A new comparison was submitted through the real Storylens UI with
High density and source music removal. Its GPU queue is shared with the owner's
active Motion Graphics job on port 8881. Do not stop that job or call the queued
comparison finished. Other Storylens instances remain running.

106 focused checks passed (sound plans, overlaps, source relevance, timing,
excerpts, XML and CapCut projects); the local HTTP report/range test also passed.
These checks do not establish subjective sound quality or exact reference parity.
