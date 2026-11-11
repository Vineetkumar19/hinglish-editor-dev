# Reference-guided local thumbnails

The earlier failed export had AI backgrounds disabled, no portrait and no
background. It therefore produced a flat canvas with a headline. Thumbnail jobs
now require a real visual source: local AI generation, supplied pictures or a
matching saved subject/reference pack. An empty text card is rejected.

Local AI backgrounds are enabled by default in the UI, chat dispatcher and CLI.
The CLI offers `--no-generate` for supplied-image/reference-only compositions.
The thumbnail planner can explicitly disable optional thinking for this bounded
three-concept task. It receives the thumbnail's story, profile, feedback and
reference rules instead of unrelated long-form video-editing memory.

## Mumbai Indians 2020 pack

`library/thumbnail-styles/mumbai-indians-2020/style.json` matches stories containing
both “Mumbai Indians” and “2020”. It provides the cricket profile, blue/gold
palette, verified hook choices and reusable player cutouts. It does not change
the selected channel/account for other work.

The user's nine source files were inventoried by SHA-256. One is an exact copy,
several are close variants, one MI version has visible corruption, and the
remaining examples include other teams and a technology thumbnail. This is a
small set of independent compositions. The chosen method is **saved reference
guidance and subject compositing; no model weights were fine-tuned**.

The clean MI example supplies the actual player imagery. The installed full
BiRefNet model prepares the cutouts. Z-Image-Turbo generates three stadium
backgrounds locally; the editor uses three deterministic layouts with short,
readable typography and preserves the supplied faces. The extracted captain
mask was visually checked and refined before generation. No new model download
or cloud image-generation service is required.

The supplied collage mixes kit eras. Its portraits are illustrative and are not
certified photographs of the 2020 final; the output project/report states this.
The historical hook claims use the official IPL match report:
https://www.iplt20.com/news/article/dream11-ipl-2020-final-mi-vs-dc-match-report

All originals remain untouched at
`A:\Editing\documentry edit\final videos\final thumbnails\mi`.
The prepared pack contains downscaled working assets inside the project.
Model weights and their caches stay under `C:\Ai Models`.

Use YouTube Thumbnails, enter the Mumbai Indians 2020 story and leave local AI
backgrounds enabled. Matching references supply the player imagery automatically.
Other stories need their own supplied subjects/reference pack when exact person
identity matters. Generated imagery and hook accuracy still need visual review.

Validation: `tools/check_thumbnail_localhost.py` requires the completed model
setup, submits a real editor job, checks all three actual generation results,
decodes the exported PNGs and verifies the original source hashes. Its receipt is
`output/validation/new-laptop/thumbnail-upgrade-inference.json`.

The real localhost job `b6a0c9d9d026` produced three backgrounds with the local
Z-Image worker (71, 67 and 49 seconds of denoising, excluding model loading).
All final exports were visually inspected and their bottom cutout edges refined.
All nine original hashes still match. The full regression suite passed:
648 tests, 25 skipped, 541.506 seconds; the four focused thumbnail checks also
passed after the final layout refinement.

Reviewed gallery:
`output/thumbnails/20261018-202144-e9fd49/report.html`.
