# Sound training and online sources — 30 October 2026

## Actual state

The installed 14B model is Qwen3-14B Q4_K_M; Qwen3.5 is the separate 9B Vision model.
A separate NF4 training copy completed real QLoRA training on 304 text lessons,
including ten online-retrieval policy lessons. Seventy-six optimizer steps changed
adapter weights. This does not train audio perception or grant internet access.

The adapter failed its generated-answer acceptance check despite lower held-out
loss. The train scenario assigned overriding priority instead of protecting speech;
the empty-street scenario asserted absolute silence. The original serving model is
unchanged. Do not describe this adapter as an improved production model. A better
scenario-based corpus/evaluation revision remains outstanding; no further run has
been started. Receipts and the full comparison are under
`output/sound-training/20261030-qwen3-14b`.

## Runtime connection

`hinglish_sound/online_sources.py` provides bounded missing-source retrieval for
both sound pipelines. Local candidates are considered first. A job may issue up to
three distinct fallback searches. Downloads become candidates for the existing
ranking/timing/mixing path; they are not automatically approved just for downloading.

- Mixkit: targeted public website search and observed download dialogs; no key,
  login bypass or whole-catalog harvesting. One water ambience file was downloaded
  and decoded successfully. Its music path has not been live-validated.
- Wikimedia Commons: keyless API; accept explicit supported CC0, CC-BY or public
  domain declarations and preserve source/author/license. A rain recording downloaded
  and decoded. A decoded recording is not an auditioned or approved mix.
- Freesound and Jamendo: disconnected because owner cannot obtain API access.
  No unsupported authenticated website download mechanism has been implemented.
- Pixabay: manual import only; no verified automatic audio connector.
- ElevenLabs: key encrypted with Windows DPAPI, excluded from training/prompts/reports.
  Account check returned missing permissions. Generation remains disabled until
  allowance and permitted use can be established. No generation credits spent.
- Epidemic Sound and Artlist: excluded at owner's request.

Cached assets are stored separately in `library/sound-online` and
`library/music-online`, with provenance sidecars. Individual file licenses and
service conditions still apply; a YouTube/Instagram destination alone does not
establish non-commercial use.

An initial irrelevant Mixkit click test was moved out of the working library into
`output/sound-provider-validation/unapproved-download`. The subsequent physical
source filter rejected generic clicks for water queries. Keep this rejected test
out of source selection. Validated water-download evidence is in
`output/sound-provider-validation/website-download-filtered.json`.

## Validation scope and remaining work

Fifty-six focused automated tests passed, including optional provider failure,
bounded retries, source filtering, licenses, URL allowlists and integration into
candidate ranking. These are supplementary checks. No Storylens video, timeline,
editor export or live model tool-use workflow was run. Existing app processes were
not restarted; freshly imported modules are needed to use the new connection.
No eighth video or other video job was started.

Training improvement and full application acceptance remain unfinished. Do not
claim that all websites are connected or that model weights make arbitrary browser
downloads possible. Preserve the separately paused sound-engine repairs and other
saved owner guidance.

Official references reviewed:
- https://mixkit.co/license/
- https://mixkit.co/terms/
- https://commons.wikimedia.org/wiki/Commons:API
- https://freesound.org/docs/api/resources_apiv2.html
- https://developer.jamendo.com/v3.0/tracks
- https://elevenlabs.io/docs/api-reference/user/subscription/get
- https://elevenlabs.io/docs/help-center/legal/can-i-publish-the-content-i-generate-on-the-platform

## Continued sound-only teaching, 30 October

The owner requested continued repair of failed training checks and supplied three
talking-head references by its.mee.ananyaaa. Their identities, all 2,815 decoded
frames, extracted audio and uncertain mixed-audio classifications are preserved
under `output/sound-training/20261030-revision2/references`. Visual timing and
classifier similarity do not establish exact heard effects or separated layers.
Three source-qualified teaching cards were added to shared sound memory while
preserving the earlier tutorials. This retrieval change is separate from training.

Revision 2 performed 50 real optimizer steps on 400 examples, exported a GGUF
adapter, and loaded it in an isolated CUDA runtime. It was not deployed: complete
JSON responses still invented timestamps and mishandled decay and unsupported
audio identities. Evidence is in that revision's `decision-review.json` and
`runtime-gate-comparison.json`. A prior schema-misconfigured comparison is retained
separately and is not acceptance evidence.

Revision 3 completed a fresh-base run with all 304 original lessons plus 48
applied decision scenarios, explicitly exposed three times each (448 rows).
It uses stronger grounded-timing instructions and structured teacher decisions.
Eight new questions and the eight previous regression cases are excluded from
training. Supporting corpus, runtime, retrieval and provider tests: 73 passed.
See `output/sound-training/20261030-revision3/checklist.txt` for current status.
No training-loss improvement alone establishes creative improvement.

At the owner's explicit instruction, the competing preparation and assistant
continuation were cancelled. Live service checks found no active preparation or
app job; saved outputs and remote posts/schedules were preserved. Receipt:
`output/sound-training/20261030-revision2/queue-cancellation.json`.

The owner subsequently supplied three files in
`A:/Full Drive/Styles/Sound Design Tutorial` and explicitly ordered that their
training start only after current failures are resolved. Their paths and status
are saved in revision 3's `next-reference-training-queue.json`. They have not yet
been analyzed in this follow-up. The requested goal is dynamic sound choice and
purposeful overlapping layers, not a fixed five-layer template.


Correction follow-up: revision 3 still failed semantic checks despite complete JSON and improved decay handling. Explicit corrective training subsequently completed under `output/sound-training/20261030-remediation`: 608 rows and 152 optimizer steps. Eight fresh core decision checks and three real file selections passed with the improved brief; the baseline also passed, so a weight-only advantage is not established. Twenty earlier evaluation cases were explicitly converted to supervised corrections and are not unseen evidence.

The owner-ordered three files in Styles/Sound Design Tutorial are new short references (about 52 seconds combined), not duplicates of the earlier long tutorials. All 1,327 frames were decoded; eight half-second contact pages and three full-size timeline frames were inspected. Mixed-audio CLAP hypotheses and zero-segment Whisper outputs do not establish exact source identities or separated layers. Visible page-flip/clock/riser/whoosh/reverb labels and staggered unequal-duration clips inform source-qualified teaching, not a claimed exact sonic reconstruction. Evidence: `output/sound-training/20261030-tutorial-timeline/reference-study.json`.

Actual continuation loaded and verified all 320 saved LoRA tensors, then trained 170 rows (16 new scenarios repeated four times plus 106 earlier rehearsal examples), two epochs and 44 optimizer steps. Development validation exposed one physical-action tail cutoff. A separate 92-row, 12-step continuation corrected that case; new bowl/latch duration questions retain tails beyond movement, while a genuinely short contact remains short. Latest artifact: `output/sound-training/20261030-timeline-tail-correction/adapter.gguf`.

Five timeline cards and source/effect/duration distinctions are connected through existing shared planner/Vision retrieval. This guidance update is separate from the actual 14B weight updates; Vision weights were not trained. All original lessons, source records and core rules remain intact. Supporting software checks: 85 passed. Final safe artifact/integration probes: nine passed, no new breaking points in those probes. Real candidate inference produced 17 complete decisions (four fresh, thirteen regressions) and three correct production file choices. These are not audible-mix acceptance or proof of superiority over the base model.

Known development limitation: the source-gain answer correctly rejects independently lowering music in a mixed source, but one explanatory sentence incorrectly includes a separately added paper effect in that gain change. Other fields can repeat boilerplate or call supplied facts unknown. The live application still uses the original model; the candidate has not been merged/registered/activated, and no new rendered mix or native-editor playback was performed. Remaining work is explicit in `output/sound-training/active-work.json` and the latest `completion-status.json`.


## Sound candidate activation and owner-video demo — 30 October 2026

The owner explicitly resumed the unfinished mixing fix and supplied the July 9 travel video. The trained Qwen3-14B adapter is now merged, Q4_K_M quantized and registered as storylens-sound:14b-trained, activated only for Sound Design. Original model/adapters/configuration backups remain. The separate-source/Foley/master gain explanation passed a real local-model check after shared runtime guidance correction. This follow-up did not perform another weight-training run.

Live validation exposed additional production problems: continuous-source micro-snippets, unbound source roles, poorly identified recordings outranking confirmed physical sources, and emotion-only search intents. Red-first fixes added typed scene schema, one bounded model-authored duration correction, sound-only adaptive context allocation without dropping full guidance, known physical/source mismatch rejection and source identity before novelty. Invalid delivery-only intents are omitted. 138 affected tests passed.

Actual final job 13b4e04d33a5 rendered the full 798-frame/26.6-second source video with eight effects, up to four overlapping layers, original stereo retained and no new music. Result: output/sound/20261030-133810-110422/001-vineet_2919_2026-07-09_12-29-09_39372793/report.html. Friendly playable copy and evidence: output/sound-training/20261030-owner-video-demo/QWEN-TRAVEL-FINAL.mp4 and RESULT.md. One waterfall Foley layer was omitted because no remaining matching candidate passed. Numeric mix, all-frame decoding and editable-stem/XML checks passed; these are not an artistic quality rating. The in-app browser API failed with browser.user is unavailable, so visible playback, independent listening acceptance and native-editor playback are unverified. The local model remains imperfect; weights-only superiority is not proven. Exact physical-contact synchronization remains sampled. Earlier paused work is preserved separately.
