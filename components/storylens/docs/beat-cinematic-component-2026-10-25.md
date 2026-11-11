# Beat + Cinematic component checkpoint — 25 October 2026

## Scope and ownership

Bounded assignment: inspect/test `hinglish_beats/detect.py` and
`hinglish_cinematic/planner.py`, repair demonstrated normal-flow planner/detector
gaps, and provide dedicated component tests and a synthetic golden plan.

Only **`hinglish_cinematic/planner.py`** needed a production-code change.
`hinglish_beats/detect.py` is unchanged. Added:

- `tests/test_beat_cinematic_component.py`
- `tests/fixtures/beat_cinematic_component/golden_50s_10shots.json`
- This component document and a pointer in the owned readiness document.

No service, renderer, server, UI, native adapter, installer or publishing code
was changed. No Adobe application was inspected or operated. No model, GPU,
video encoder, render/service job, network asset, database or credential was
used. The only generated media was tiny synthetic PCM WAV data in test temp
directories; byte-copy identity tests also used small binary fixtures.

The suite owner retains shared integration, deployment and native acceptance.
Never open Premiere and After Effects together. The separate publishing queue
assignment remains planning-only.

## Concurrent-edit checkpoint

Immediately before the planner edit, both assigned modules matched the initial
read hashes. No concurrent source edit was observed at that pre-write check.
This is a point-in-time hash check, not a global file lock.

| Module | Before | Final |
| --- | --- | --- |
| `hinglish_beats/detect.py` | `70096f6cfe5c605f2603557fcfe6aec85e5869d7b50d492268eff58f5520b664` | Same, unchanged |
| `hinglish_cinematic/planner.py` | `875b8c149e34402d39b5fa6c579ceb1c5f4c796aa4337b75737ecf7e36ff5d1b` | `96798c835d6fb693a178930837d451bb8e33abc0c1415c1c7de7208d0f89d874` |

## Baseline and demonstrated gaps

The first isolated baseline was **15/15 passing**, in 0.811 seconds:

- All eight `tests.test_cinematic.CinematicPlanningTests`.
- Seven explicitly selected decoder/PCM tests from `tests.test_beats.BeatTests`.
  Service/HTTP/Resolve/native/render cases were excluded.

New tests then reproduced these requested-flow problems before repair:

1. A valid 50-second, 10-shot path through real nonuniform attacks was rejected.
   Greedily accepting early attacks and thinning afterward could produce a
   too-long gap despite another feasible set of actual beat points.
2. When two input attacks mapped to the same output frame, the later weak one
   could overwrite the stronger one. A concrete 12-second example chose cuts
   `[0,90,210,360]` instead of the more salient `[0,120,240,360]`.
3. Different file paths containing identical source content could be treated as
   enough distinct sources to fill a 10-shot budget. A focused test with 50
   metadata rows sharing one content identity incorrectly succeeded.
4. One isolated usable sample could let a mostly unusable source pass initial
   inspection and supply a low-average-quality window.
5. Nearest-frame rounding extended a selected 50-second music range to
   **50.01663333333333 seconds** at 30000/1001 fps, requiring source audio after
   its selected out point or padding.
6. The planner did not explicitly describe contiguous original music ranges
   for the component handoff, although the existing renderer's intended music
   flow was continuous.

The first new-suite run had 14 tests: two failures, six errors and one temporary
golden-fixture skip. Several errors were masked behind the first beat-layout
failure. Focused sparse-attack tests then independently reproduced duplicate
content acceptance and fractional-frame music overrun. No test failure was
reported as success.

## Repairs within the existing planner

### Feasible attack grouping

`boundaries()` now searches actual detected attack frames with a frame/shot-
constrained dynamic program. A sliding maximum keeps the search approximately
O(attack count × shot budget). It uses the highest feasible number of shots up
to the budget, then measured onset strength to select among feasible paths.
Equal-score ties are deterministic. Internal cuts are never generated on an
invented uniform grid; opening and closing remain explicit music endpoints.

Minimum/maximum shot spans are enforced on output frames. Quantizing the same
attack frame preserves its strongest supplied observation. If no valid path
exists, planning stops with the existing actionable beat/shot error.

This is **attack salience**, not a newly implemented musical downbeat/phrase
detector. The unchanged detector still measures spectral-flux/RMS attacks and
labels that limitation. Phrase/downbeat understanding remains unproven.

### Source identity, diversity and quality

`inspect_shot()` now adds:

- `source_id`: the resolved input video path.
- `content_sha256`: streaming SHA256 of the original file bytes, with a
  cancellation check per chunk. The original file is only read.

`assemble()` groups canonical paths, exact content hashes and explicitly supplied
same-clip IDs transitively. The no-reuse budget counts those source groups, not
different names for the same content. Existing no-reuse behavior stays default;
opt-in reuse tracks used source windows by group. Output shot records retain
`source_id` and `content_sha256` for auditability.

Supplied `source_id` must mean the same input clip/time coordinate system, such
as a known proxy of that clip. It must not be a broad shoot/category ID or a
shared root-stream ID for independently trimmed inputs. Exact hashes detect
byte copies, not visually similar re-encodings. Legacy metadata without hashes
has only the path/supplied-ID evidence it actually contains.

The assembler now requires a mean measured window quality of **0.2** by default,
matching the existing inspector's input visibility floor. `min_quality` is a
bounded 0–1 planner option. `best_window()` keeps its old unrestricted default
for direct callers, while the assembler supplies the threshold. A low-quality
window stops instead of silently freezing or adding a placeholder. This number
is a heuristic over exposure/detail/contrast/usability, not a calibrated semantic
or aesthetic score.

The existing measured quality/motion ranking and longest-interval-first source
assignment are retained. They do not establish that a take is the user's
semantic favourite or that assignment is globally optimal for every mixed pool.

### Original music coverage

The final output frame is floored within the selected audio span, so an
incomplete source frame does not request extra music. This can shorten a target
by less than one output frame; the plan states its actual frame count/duration.
Music remains normal speed, with the existing rejection of retimed music.
Explicit source in/out bounds are checked.

The existing `music.path` and `music.source_in` fields remain. Additive fields:

```text
music.source_out    = selected original in + actual frame-covered duration
music.continuous    = true
music.speed         = 1.0
music.ranges[]      = {start_frame, end_frame, source_in, source_out}
```

With existing `split_music=true`, ranges follow the visual cut boundaries but
source ranges remain contiguous and in their original order. With it false,
there is one full continuous range. No music removal/reordering or automatic
caption, B-roll or effect stage was added. Assembly still returns `effects=[]`.

## Golden synthetic 50-second plan

Fixture: `tests/fixtures/beat_cinematic_component/golden_50s_10shots.json`.
It is marked `synthetic_only:true`; its media paths are not real generated
videos. It does not represent an approved reel or a native timeline receipt.

Inputs: 50 metadata candidates, 20 seconds each; explicit 10-shot cap; 3–6-second
allowed shot spans; normal-speed source windows; music source 12.5–62.5 seconds;
actual supplied attack times expressed relative to a nonzero timeline placement.
The fixture's measured qualities make clips 40–49 the strongest ten candidates.
The output is **1,500 frames at 30 fps**, exactly **50 seconds**, with no gaps.

Cut frames:
`[0,120,285,450,600,735,900,1050,1185,1350,1500]`.

| Timeline seconds | Selected source ID | Source in–out seconds | Measured mean quality |
| --- | --- | --- | --- |
| 0–4 | clip-40 | 6–10 | 0.85 |
| 4–9.5 | clip-49 | 6–11.5 | 0.94 |
| 9.5–15 | clip-48 | 6–11.5 | 0.93 |
| 15–20 | clip-45 | 6–11 | 0.90 |
| 20–24.5 | clip-42 | 6–10.5 | 0.87 |
| 24.5–30 | clip-47 | 9.5–15 | 0.92 |
| 30–35 | clip-44 | 6–11 | 0.89 |
| 35–39.5 | clip-41 | 6–10.5 | 0.86 |
| 39.5–45 | clip-46 | 6–11.5 | 0.91 |
| 45–50 | clip-43 | 10–15 | 0.88 |

These durations are 4, 5.5, 5.5, 5, 4.5, 5.5, 5, 4.5, 5.5 and 5 seconds:
there is no fixed five-second fallback. Original music ranges cover 12.5–62.5
continuously. Every source trim stays in the fixture's strong 6–15-second region.
The original source metadata and beat input remain unchanged.

## Final scoped verification

**33 tests passed, zero failures/errors/skips, 3.720 seconds** in the final run:

- 18 tests in `tests.test_beat_cinematic_component`.
- Eight existing `CinematicPlanningTests`.
- These seven existing `BeatTests`:
  `test_real_decoder_detects_attacks_within_one_frame`,
  `test_three_nested_densities_and_optional_clip_budget`,
  `test_trim_placement_and_ntsc_frame_rounding`,
  `test_silence_never_produces_grid_or_effects`,
  `test_stereo_uses_mono_analysis_without_double_markers`,
  `test_rejects_bad_timing_density_and_partial_range`,
  `test_effects_separate_and_bounded`.

The new checks cover 40/50 input pools and a 10-shot cap, strongest in-bounds
windows, source-ID/content-copy diversity, impossible/no-beat stops, same-frame
salience, mean-window-quality rejection, fractional output frames, source music
bounds, split/unsplit original music continuity, no automatic extras, original
byte preservation/cancellation and exact golden-fixture equality. Tiny irregular
PCM attacks were detected within one 60-fps frame; silence produced zero markers.

Execution used `.venv/Scripts/python.exe -m unittest -v` with those explicit
classes/methods and workspace-local TEMP/TMP. No full test discovery was run:
the existing render/HTTP test classes create services or encode video and are
outside this assignment. Passing these tests is not Storylens/native acceptance.

Final test source SHA256:
`915347cdb5206172ce2f8de59050e1c2e67a6329579b95c4abd83c3a00ddec82`.
Golden fixture SHA256:
`b4f6989c3436596c97485bd15ee537ac8ec7fa4f7e134344028073ecd3e47fbe`.

## Final review limits and suite handoff

Source review after the green run did not trigger additional code repairs.
Protected final-review findings from other tasks remain unchanged.

1. No semantic favourites, actual downbeat/phrase recognition or creative
   selection approval is established. Quality/motion/attack salience and exact
   byte identity are the measured evidence available.
2. Source-to-interval assignment remains the existing greedy heuristic. The new
   dynamic program solves beat-path feasibility, not a globally optimal joint
   source/window/beat assignment. This is a source-review limitation, not a newly
   reproduced failure in the tested 40/50-source cases.
3. The new byte fingerprint is exercised on binary fixtures; no new real-video
   `inspect_shot` decode was run. Fresh production inspection will incur an extra
   sequential source-file read for exact hashes. Saved older plans are not
   rewritten or silently upgraded.
4. The additive music range/source-ID metadata is available to the suite. The
   existing renderer still uses its own existing fields/paths. Native song
   continuity, sample-accurate output audio, actual AV endpoints and manual
   editability need suite-owned renderer/export/native verification.
5. The current XML renderer references prepared shot copies and a prepared
   soundtrack. It must not be described as a verified raw-source, full-handle
   native timeline. The suite owner must evaluate original-media relinking,
   trims/handles, timing, sizing and nondestructive music editing as required.
6. No service restart, deployment/install, UI demonstration, song/video render
   or Adobe host check occurred. New source is not proof that an already running
   process has loaded it. Shared integration and any later host lifecycle stay
   exclusively with the suite owner.

Next bounded owner check: integrate this plan contract into an isolated existing
service/renderer acceptance fixture, preserve original song and source hashes,
then inspect the native editable result in the one reserved Adobe host. Do not
start both hosts or auto-apply the other editing tools. If musical phrase quality
is insufficient, record that separately from the now-tested frame/identity
component behavior rather than claiming downbeat understanding.

## Subscription-independent runtime audit and local-agent acceptance gap

Additional coordinator requirement received after the component checks: the
finished workflow must run without a Codex/ChatGPT session or subscription.
Development assistance and synthetic component evidence do not establish that
the configured local assistant can select and execute the workflow.

Source-only audit of the two owned modules found no OpenAI SDK, cloud inference,
HTTP model call, session token or remote model fallback. Beat analysis is local
PyAV/NumPy transient analysis. Shot inspection uses local PyAV/OpenCV image
measurements; this is **not the configured semantic Vision model**. Beat-path,
quality-window and source-identity decisions are deterministic Python. The
metadata fixture was authored for component testing, not supplied by Qwen or
reported as local-model acceptance. No weights were trained.

Read-only caller inspection found `BeatService._run -> analyze` and
`CinematicService._run -> inspect_shot -> assemble -> render`. Those service
bodies do not themselves invoke the configured LLM or Vision. The cinematic
service reads saved ReelMimic context for optional pacing defaults; this audit
does not establish how that saved context was originally generated. Its optional
`verify_license` callback can stop editing if product subscription verification
fails. That is a separate product licensing dependency, not evidence of a
ChatGPT dependency; its implementation and external requirements were not audited
in this bounded assignment. Shared assistant orchestration, render dependencies,
installation/startup, licensing, retrieval providers and runtime receipts remain
with their owning components. No claim is made that the entire application has
been audited for cloud dependencies.

**Pending acceptance:** have the actual configured local assistant receive the
owner's ordinary request, select the music/source inputs and parameters through
normal application tools, execute the measured controllers, recover from a real
failure if encountered, and produce the reviewable result without Codex supplying
semantic answers. Any configured Vision-based semantic ranking must be exercised
as such; these quality scores cannot stand in for that model. No handwritten
successful tool result, cloud fallback or fixture substitution counts.

Suite-owned serialized benchmark proposal, not started here:

1. Short: one 10-second music excerpt and a small real source pool, requested
   through the actual local assistant. Check real attacks, bounded source trims,
   original music continuity and a useful failure when no beat path exists.
2. Representative owner case: 40–50 real short clips, strongest/diverse ten,
   illustrative 50-second reel. Keep meaningful selection review separate from
   geometry and beat-timestamp checks.
3. Longer laptop case: increase the aggregate source pool duration toward the
   service's existing one-hour input limit while retaining the same output
   request. Measure inspection/hash cost, memory and queue behavior; do not
   invent a completion-time guarantee or silently exceed product limits.

Record exact configured model/provider/version and settings, redacted prompt and
tool requests, actual execution/retry/outcome, cache/reference lineage, and any
human/development intervention. Also measure queue wait, local inference,
inspection/hash, planning, rendering, wall time and peak memory separately.
Distinguish a cold run from reused analysis. A cached plan must retain its origin.
No such local-agent benchmark was run by this component assignment. The existing
service plan files do not alone prove that full trace contract. If the local
agent fails, preserve the original request and failure, repair in the owning
component, then repeat the same flow through the local agent. One Adobe host
only, with exclusive suite scheduling; no concurrent GPU/render/native jobs or
live publishing are authorized here. Reliability remains measured, not a
zero-breakage promise.

## Read-only caller inventory and next gates — 25 October 2026

This is source/configuration inspection only, following the 60 passing isolated
queue checks. No application, model, network, renderer, media, canonical database
or Adobe operation was run. Production findings below are frozen for owner
assignment; no dispatcher/producer/service repair was made.

### Existing gaming chain

- `hinglish_app/assistant_plan.py:4,374,502` declares `gaming` and `shorts`.
  `assistant_distribution.py:141` asks the local brain for a bounded gaming →
  Shorts → distribution recipe, with two plan-validation attempts. The
  highlights-only route at line 101 explicitly excludes unrequested publishing.
- `assistant.py:606–694` retains original paths, dispatches sequential existing
  `state.create_job` calls, saves each completed result and passes the resulting
  highlights MP4 to the next Shorts step. `assistant_media.py:25` collects actual
  `GAMING_HIGHLIGHTS.mp4`/saved short outputs, rather than synthesizing success.
  Explicit numeric Shorts shortfall pauses before distribution.
- `server.py:439,504` serializes the normal job under the work/GPU locks and
  launches `python -m hinglish_niche gaming`. Its CLI calls
  `hinglish_niche/gaming.py:215`. Gaming `candidates` at line 88 calls
  `brain.json` for transcript-grounded moment IDs, scores, kinds and reasons.
  Deterministic `validate_moments`/`select` keep bounded, nonoverlapping moments
  scored at least 6; they do not invent gameplay from loudness. `render` exports
  selected footage and optional approved memes. `gaming-project.json` records
  original path/duration, selected source-second moments, memes and output path.
- `hinglish_shorts/pipeline.py:77,142` consumes that finished MP4, transcribes it,
  calls local `find_shorts` plus title review, renders selected clips and saves
  `shorts-project.json`. Its `pieces` are seconds **within the highlights MP4**,
  not automatically original-stream coordinates. `find.py:366` has up to three
  passes for complete unused moments; a target is not a promise of N results.

### Models, bounds and recovery

On-disk active role settings select `storylens-meaning:14b`
(Qwen3-14B Q4_K_M) for planning and `storylens-planner:9b-q6`
(Qwen3.5-9B Q6_K plus projector) for Vision. This does not establish what a
running process actually loaded. `hinglish_visuals/brain.py:153` resolves current
preferences, tries local Ollama, and in auto mode can fall back to bundled local
`LocalLLM` (`hinglish_broll/llm.py`); no cloud LLM fallback appears in this route.
Record the actual backend/model and cache lineage during acceptance, not just
the configured preference. Gaming has no semantic Vision call: its 64×36 visual
change bins are measured cues, not the 9B Vision model.

Gaming scans audio in five-second bins and one tiny frame per five seconds.
VAD/ASR uses cached bounded windows (`hinglish_semantic/analysis.py:14`,
`hinglish_clean/detection.py:67`); full words/lines, cue lists and candidate lists
still grow with source duration. LLM transcript windows are 300 seconds with
40-second overlap; dense gaming windows can split on context/JSON failure.
Configured Ollama context cap is 12,288 tokens; bundled client default is 8,192.
Gaming target is 1–30 minutes in the engine, 10–15 in its dedicated chat recipe;
it may output less when strong moments are insufficient. Optional inserted memes
also affect output timing. No inspected gaming duration cap or file-size allowance
is evidence of tested three-hour throughput or laptop memory use.

Chat Stop means **after the current step** (`assistant.py:291`); normal gaming/
Shorts subprocesses do not receive a cancellation callback. ASR windows, signals
and model responses can be cached, and completed chat outputs are durable, but
gaming candidate/partial-render stages are not a durable resumable job graph.
`assistant_pipeline.checkpoint` chiefly gates completed Shorts/publishing
preparation, not interrupted gaming rendering. Do not promise immediate stop or
automatic mid-render continuation.

### Beat/Cinematic dispatch and smallest missing milestones

1. **Assistant bridge:** Beat/Cinematic APIs exist at `server.py:1572–1603`,
   backed by `BeatService`/`CinematicService`, but neither is in the normal
   assistant `TOOLS`/schema or accepted `create_job` modes. Audio attachments
   are accepted but excluded by the assistant's ordinary video `MEDIA` filter.
   Smallest bridge: explicit music/clip roles, typed arguments and a controller
   invoking the existing services, durable result IDs, cancellation and result
   handoff. Keep measured beat/window arithmetic in the controllers. Qwen must
   actually select the supplied inputs/settings through that route in acceptance;
   existing APIs alone do not prove local-agent use. Semantic Vision/take ranking
   would be additional explicit work, not something these measurements provide.
2. **Gaming lineage before queue commit:** current projects lack the queue
   contract's root content hashes, immutable completed-highlights identity/version
   and exact frame/timebase remap through concatenation and meme inserts.
   Smallest producer milestone is that durable remap, then composition of each
   selected short's highlight-time pieces into original-source moments. No path
   guess or approximate timestamp match should replace this. The separate legacy
   `publish(make_shorts)` branch (`assistant.py:537`, `Publisher.prepare_file`
   at `service.py:212`) can explicitly use original-stream `shorts_source`; it
   must not be mistaken for the completed-highlights recipe. Owner decides that
   route's correction separately.
3. **Serialized acceptance:** after the assigned bridge/remap, one small real
   local-agent flow with backend/tool/receipt evidence; only then a representative
   owner-supplied long recording with measured memory, queue wait and phase times.
   No fabricated three-hour source or performance SLA. Existing Beat plans are
   disk-written but service lookup is memory-only; Cinematic can reopen completed
   receipts but not resume interrupted analysis/render. Beat analysis has no
   cancellation endpoint. Cinematic has cancellation, checks during shot decode
   and rendering, 1–100 input clips, ≤10 minutes each and ≤1 hour aggregate, with
   an 1,800-second per-FFmpeg-call timeout. Restart/cancel behavior must be tested
   as those actual contracts, not assumed from saved JSON files.

The queue proposal/Store hooks remain a separate completed component gate, not
service activation or local-model acceptance. Existing authorization-binding
and native-editability review limits remain unchanged.

## Gaming lineage producer handoff — 25 October 2026

Implemented in `hinglish_niche/gaming.py`, new
`hinglish_niche/gaming_lineage.py` and `hinglish_shorts/pipeline.py` only.
Selection/model calls and encoder/concatenation commands remain the existing
ones. `gaming.render(..., lineage_parts=collector)` records actual prepared-part
order, trims, original/insert roles and pre-render asset stamps. `gaming.run`
captures the original identity, then calls `capture_highlights` after the
existing render has finished. It saves **new-job-only** `gaming-lineage.json`
and the same record at `gaming-project.json.lineage`. `write_new_record` uses an
exclusive atomic create and refuses to replace an existing receipt.

Producer schema/API:

- `source_record(sha256, observed_clock)` creates root identity
  `id="sha256:<whole-file hash>"`, `state`, `duration_frames`, rational
  seconds-per-frame `timebase` and a verified-CFR flag. `file_identity` streams
  bytes, checks file stamps and supports cancellation of its own observation.
- `build_highlights(root, parts, output_sha256, output_evidence)` compares actual
  H.264 access-unit hashes from prepared parts with the completed stream-copy
  output in presentation order. It records the real output PTS clock and ordered
  `segments` (`start_frame`, `end_frame`, root/insert kind, source hash and trim;
  supported roots also have `source_start_frame`). Inserted memes never receive
  fictional original-stream coordinates.
- Completed parent records have `schema_version=1`, `state="complete"`,
  `approval="not_asserted"`, `root_source`, `highlights` (whole-byte output
  identity, frame count/rate), `clock`, `segments`, and
  `mapping_version="gaming-map-v1:<canonical-record SHA256>"`. Identity/version
  checks are stale-data guards, not signatures or creative approval.
- `load_highlights(path, record=None)` verifies the completed parent bytes once
  per producer/rebuild run. Old sources without a sidecar are unavailable; no
  prior project is backfilled. New Shorts projects retain the immutable parent
  at `gaming_source_lineage`. Explicit rebuilds use only that saved record.
- `capture_short(context, source, target, frame_plan, fps)` observes the finished
  Short and calls pure `compose_short`. The producer passes `render_short`'s
  **actual `facts.frames` and `facts.fps`**, not unquantized speech pieces. The
  result follows the existing `source_frames` selection/hold algorithm against
  the observed parent clock. Each new item saves `lineage` with selected
  `highlight_frames`, separate `insert_frames`, `short_sha256`, output rational
  rate, a `gaming-short-map-v1` digest and `queue_manifest`.
- A complete `queue_manifest` matches the already implemented planner/Store
  asset schema: immutable final `asset_id/content_sha256`, completed root and
  highlights identities/version, parent `mapping_version` and ordered original
  `[start_frame,end_frame)` `source_moments` with rational timebases. The pure
  queue-consumption fixture passes. A **service adapter still must extract the
  selected item manifests**, prepare actual local-model metadata, attest media
  and account bindings, and call Store atomically. No live queue integration was
  activated by this producer milestone.

Explicit limits: exact v1 requires zero-origin CFR H.264 originals at the gaming
renderer's 30 fps and original/output frame-aligned trims. Rate conversion,
off-grid trims, changed media, packet mismatch, corrupt/old mappings, insertion-
only Shorts or unsupported clocks return `state="unavailable"` with a code and
message, `approval="not_asserted"`, and no queue manifest. Existing video
rendering is preserved; an unavailable record is not dedup-ready. Actual packet
evidence is bounded at two million units, still grows with duration, and adds
hash/demux I/O. Original identity is checked before and after highlights
production. No three-hour throughput, RAM, semantic quality or decoder-level
original-frame fidelity benchmark was performed. Helper cancellation does not
make the existing gaming renderer immediately cancellable.

Gate: **37 CPU fixture/regression checks passed, 0.538 seconds**, using:
`tests.test_gaming_lineage` (21 tests), `tests.test_shorts.RuleTests` (7),
`tests.test_shorts.TimingTests` (5), the three `GamingTranscriptionTests` methods
for cache/strict rejection/gaming-only skipping, and
`tests.test_shorts_output_collection` (1). Command was
`.venv/Scripts/python.exe -m unittest` with those explicit selectors and workspace
TEMP/TMP `tmp/gaming-lineage-tests`. An initial regression attempt used the
restricted Windows temp location and failed on permissions; the same checks
passed after confining temporary files to the workspace. No unchanged suite was
rerun solely for this documentation.

Final safe review was limited to producer hooks, saved-field/version boundaries,
write-once behavior, unsupported-input rejection and synthetic packet/sampler
agreement. No further defect was reproduced within that exercised contract.
This is **not an actual FFmpeg render, local-model workflow, reference comparison
or native-editor acceptance**. No owner streams were hashed or decoded. The
next suite gate is one real local-agent-produced short sample with measured
packet/trim behavior; unsupported real cuts must stay unavailable, not be
silently certified or repaired under the separate dispatch lease.

## Beat/Cinematic assistant bridge — initial build and frozen final review

Implemented only in `hinglish_app/assistant_plan.py`, narrow creative branches
of `hinglish_app/assistant.py`, new `assistant_creative_tools.py` and dedicated
`tests/test_assistant_creative_tools.py`. No server/routes, core services,
renderer, native code, queue, model weights or running instance was changed.
There was no real model request, GPU operation, media render or Adobe launch.

API/wiring:

- Normal assistant tools now include `beats` and `cinematic`. Explicit creative
  requests bypass deterministic quick routing and call the configured local
  brain, under the existing creator context and shared GPU lock. The dedicated
  creative schema is separated from the original general-planner schema to
  avoid adding these arguments to unrelated prompts.
- `source_catalog(attachments)` exposes actual supplied IDs/names and typed
  music/clip roles, without model-authored paths. MP3/FLAC/AAC/AIFF attachments
  join existing WAV/M4A/OGG support. `plan_request(brain,text,history,attachments,
  memory)` preserves supplied memory, invokes the existing bounded context
  helper and permits at most two creative validation rounds. Client-internal
  retries remain that client's own behavior, not additional project rewrites.
- Options are `music_source_id`, `shot_source_ids`, optional `music_in/out`,
  beat density, rational output FPS, maximum shots, min/max shot seconds,
  retiming/reuse booleans, split-music choice and reel pace/aspect/resolution/
  framing. IDs must belong to supplied inputs; arrays are distinct and bounded
  to 100 sources, numbers finite and bounded, music range at most one hour.
  One creative operation is allowed; publication/other tools cannot be bundled.
- `execute(assistant,sid,parsed,selected,profile,progress,...)` invokes existing
  `state.beats.start/snapshot`, followed by `state.cinematic.start/snapshot`
  for a cinematic request. It does not route through generic `create_job`.
  Original song speed is one, music continuous by default, no retiming/reuse by
  default, effects always empty. Shot/onset/frame bookkeeping remains measured
  engine logic, not model arithmetic. No semantic Vision ranker was added.
- Durable receipts are `output/assistant-creative/<32hex-id>.json`, with a
  chat/profile-bound `creative_job` pointer, actual source IDs/paths/stamps,
  settings, model provenance, executions, service IDs, phase and result/failure.
  Model trace contains provider/tag, available revision/runtime fields, usage/
  cache evidence, validation-round count and redacted prompt inputs. It marks
  injected test brains as interventions. Prompt scope is explicitly before
  shared fitting/creator injection; final serialized prompts and complete
  client-internal retry metrics are **not** claimed as captured. Model revisions
  are not newly verified by this adapter.
- `followup` handles explicit “Show/Reopen my beat/cinematic result” and
  “Continue my cinematic reel” commands. Completed Cine results use the existing
  service's disk-aware snapshot. Completed beat JSON may be reviewed after its
  in-memory job is lost, but cannot be injected into a restarted BeatService to
  submit a new cinematic render. Existing result files are checked; no substitute
  media is fabricated. CPU HTML review pages are metadata views, not encoders.
- Submitting phases are saved before service calls. An interrupted/uncertain
  submission is retained for review and never automatically repeated. Show/
  reopen is read-only with respect to job submission. Beat Stop only detaches
  waiting (its engine may continue); cinematic Stop requests existing service
  cancellation. The controller's one-hour wait budget detaches, does not kill or
  resubmit the underlying job. Product license checks follow the existing
  service contract, separately from ChatGPT/Codex availability.

Initial focused gate: **35 passed in 0.561 seconds**: all 23 dedicated creative
boundary checks, six compatible `tests.test_assistant.PlannerTests`, and six
pure `PlannerContextBudgetTests` (excluding the AppState lifecycle diagnostic).
The dedicated checks exercise the actual `_respond` and `plan` functions with
injected brain/service boundaries, source IDs, creator context, one correction,
service payloads, continuous song/default manual effects, stopped/uncertain
submissions, saved-result reopen, actual Cine disk-snapshot logic without
constructing a service, secret redaction, and no network/subprocess/native work.
They are **not local-agent/application acceptance**.

Command used `.venv/Scripts/python.exe -m unittest` with
`tests.test_assistant_creative_tools`, then these six PlannerTests:
`test_shots_in_long_form_request_and_short_caption_options`,
`test_question_negation_and_multiple_edits_need_context`,
`test_clean_join_in_order_is_requested`,
`test_unknown_tools_and_options_and_paths_are_rejected`,
`test_question_prevents_execution_and_mixed_publication_rejected`,
`test_help_answer_cannot_dispatch_a_model_generated_edit`; and the first six
pure context-budget methods. TEMP/TMP was `tmp/assistant-creative-tests`.

A broader 39-check attempt also exposed four existing-test compatibility
failures, kept separate: three fake brains lacking a configured root hit the
8,192-token default on the general prompt, and one caption test expects legacy
Typography 1/2 names absent from the current selectable catalogue. Replaying
the general prompt with creative fields absent AND added tool names removed
still reproduced the context rejection; this is a baseline-shaped isolated
replay, not a full pre-change application run. No creator guidance was deleted,
no context helper was changed and no caption style was reintroduced. These
cases are not counted in the 35 passes or silently represented as fixed.

### Mandatory final safe review: TWO NEW FINDINGS, FROZEN

The subsequent review used only synthetic files and injected services, after
the green initial gate. No production repair was made after these findings:

1. **Cancelled cinematic receipt never reconciles to a terminal phase.**
   Start the injected cinematic job, request Stop, then return actual service
   status `cancelled` and ask “Show my cinematic result”. The report correctly
   says cancelled, but receipt phase remains `cancel_requested`. A new creative
   request is then blocked as “previous job pending or uncertain”. Start count
   remained exactly one. Needed owner decision/repair: reconcile known terminal
   service status without restarting or losing its receipt.
2. **A stale creative clarification can capture a later unrelated continuation.**
   Seed `creative_pending.request="Make a cinematic reel"`; ask the normal
   `_respond` route for Caption 4 and return a caption-file clarification; then
   attach a clip with “Here”. The creative pending request was not cleared by
   the intervening caption request. Observed planner texts were first
   `Add captions using Typography 4`, then
   `Make a cinematic reel\nUser follow-up: Here`. This review started **zero**
   services; it proves wrong planner input routing, not an observed unwanted
   render. Needed owner decision/repair: bind clarification to the active request
   and retire superseded runtime intent while preserving saved history/results.

This initial bridge must not be described as unattended-ready. These two
findings are explicitly protected pending owner assignment; the separate
publishing-binding, native-editability and producer-format limits remain
unchanged. No server was reloaded/deployed. Actual configured local Qwen tool
selection plus a small serialized real Beat/Cine render and native review still
belong to the suite's exclusive resource/acceptance gate, with one Adobe host.

### Shared-file reload checkpoint for the B-roll owner

Shared source writes are finished; no partial Python edit is in flight.
`assistant.py`, `assistant_plan.py` and `assistant_creative_tools.py` parse and
import in the scoped checks. A subsequent CPU-only checkpoint called the normal
actual `Assistant._respond` function with an injected B-roll planner/job/output
boundary. It completed with `mode="broll"`, the exact supplied video path,
five options per moment, unchanged planner attachment keys `name/kind`, and
**zero Beat/Cinematic starts**. Network/subprocess guards remained active. The
existing `HumanChoiceTests.test_chat_planner_passes_five_options_per_keyword`
assertions also passed by calling that pure method directly, without its
media-encoding setup. These are two additional checkpoint probes, not a repeat
of the 35-check suite or acceptance of actual B-roll generation.

Frozen shared source SHA256 at handoff:

- `assistant_plan.py`:
  `2871dec4d3bdfaf5ea68b0b1a1f727ecf84e5615de06c1ad15543f59c2b89a1d`
- `assistant.py`:
  `f35d37c449bcb411c67a9b5dc1ac8d88450426af73e5f28bbc4d9ea5809c54ba`
- `assistant_creative_tools.py`:
  `8ed4776f792d9d607c742bd49db6a7b7233181bc3806c986b138680c6ee10845`

The suite retains reload/service lifecycle ownership. This checkpoint is
import/B-roll-dispatch safe evidence only; it does not clear the TWO frozen new
creative final-review defects or the separately recorded baseline test cases.
No instance was reloaded or live request submitted by this component owner.

## Planning only: smallest local-Vision window-ranking milestone

No implementation or model/media execution is authorized by this proposal.
Sound/native B-roll work retains resource priority. Shared planner/service/bridge
sources and all frozen findings remain unchanged.

**Add one proposed module** `hinglish_cinematic/semantic_windows.py` and dedicated
CPU tests `tests/test_cinematic_semantic_windows.py` after an explicit lease.
Its job is bounded visual evidence/ranking; retain the current onset detector,
beat boundaries, exact-byte source grouping, timing math, rendering and exports.
This is not a replacement architecture, weight training or a vector database.

Current boundaries: `planner.inspect_shot` measures exposure/detail/motion;
`best_window` and `assemble` currently select using those measurements only.
`hinglish_visuals.evaluator.VisionModel.look(images,system,schema,prompt)` already
supports the configured local vision model and custom schemas. Reuse that API
directly with an owned session/injected factory; do not use its surrounding
CLIP-only fallback as if it were semantic Vision. The existing B-roll embedding
`Vision` class is a different tool and need not load a second model here.

Proposed typed boundary:

`assess_windows(sources, candidate_regions, brief, creator_context, look,
cancel, resource_policy) -> semantic_evidence`

- Controller-owned input regions have immutable source/hash/window IDs,
  source timebase and origin PTS, feasible source interval, measured quality and
  sampled evidence IDs. Vision returns only supplied region/frame IDs,
  visible subject/action/setting, shot scale/angle, ordinal suitability,
  confidence/uncertainty and evidence-backed reasons. It cannot invent paths,
  freehand cut timestamps, tool calls, subjects or source intervals.
- Preserve **actual decoded frame PTS/timebase**, orientation and pixel hashes,
  alongside requested sample times. `hinglish_broll.library.read_frames` returns
  requested times, so reusing that tuple as actual timestamp evidence would be
  wrong. A small observer inside the new module should reuse AV/orientation
  helpers while retaining the real frame metadata. Missing clocks fail closed.
- Start with at most two measured, temporally distinct candidate regions per
  supplied clip and three frames per region. Report coverage explicitly: “best
  among reviewed windows” is supportable; global best frame/action timing is not.
  A visible anchor must be one of those actual frames, never a guessed contact
  time. Deterministic code fits actual beat durations within reviewed regions
  while retaining that anchor; verify the selected exact trims afterwards.
- Keep exact-byte/same-source exclusion hard. Use observed setting/action/
  angle labels and optional cheap thumbnail hashes for a **soft diversity
  preference**, not verified person identity or guaranteed re-encode detection.
  Same person/setting is legitimate; do not invent ten different subjects.
  Quality floors and source bounds remain hard. Preserve counts/reasons when
  fewer than ten worthwhile distinct sources can fill the beat intervals.

**Bound the first comparison:** 50 source clips maximum, 100 reviewed regions,
one serial Vision call per clip with at most six small upright frames resident
(maximum edge 384), then at most ten exact-trim checks. Allow one additional
targeted structurally invalid reply correction **per job**, not per clip:
at most 61 inference requests and 330 decoded evidence images for a 50-clip,
10-shot case. These are work/memory-buffer caps, not a latency or VRAM promise;
the model still owns GB-scale memory. Do not preload an embedding model. Use
the existing shared GPU queue, one owner/client, and cooperative cancellation
between calls. A client timeout does not prove the backend stopped: save the
uncertain request, do not retry/unload another model automatically or claim
GPU release. The resource owner must reconcile that state.

Persist per-window source/content/frame hashes, actual PTS, prompt/schema/rubric
versions, creator-context digest, actual model tag and available runtime/model
revision, cache lineage, decisions/rejections and final interval assignment.
Cross-job cache reuse requires a reliable model signature; otherwise keep
reuse within the same job. Recheck source identity before applying annotations.
Invalid/missing Vision, unsupported timestamps, ambiguous evidence or an
infeasible assignment stops semantic mode with a useful error. An explicitly
chosen measured-only mode can remain available, with its actual method label;
never silently substitute it for a requested semantic result.

**Small future integration hooks, separately assigned:** the suite-owned
`CinematicService._run` invokes assessment after measured inspection; the
planner owner adds optional reviewed-region/score input to candidate fitting
and assignment. Do not disguise semantic votes as exposure/motion values or
let the existing unconstrained `best_window` move outside reviewed regions.
The bridge owner would add an explicit semantic/measured choice and provenance
label without touching the two frozen creative bugs. `render.export_xml` and
the original continuous song stay unchanged. Its current prepared-media XML
is not newly verified raw-source/full-handle editability.

CPU tests should cover immutable IDs, wrong/reordered/missing source bindings,
nonzero-origin and fractional/VFR PTS, invalid numeric/model replies, explicit
uncertainty, anchor/trim containment, exact-copy exclusion and soft diversity,
insufficient footage, cache invalidation, cancellation/timeout checkpoints,
all resource caps and no provider/network/model/render/native calls. They
establish contracts only. Later acceptance needs a real configured local-Vision
run and human comparison of meaningful selected motion/windows.

Read-only inventory confirmed **13 MP4 files** under
`input/phase1/instagram-vertical`; only names/sizes were inspected. Their actual
durations, content, diversity and suitability were not measured. They may be
labelled a small phase-one fixture, never 40–50-source acceptance. No files were
duplicated, old missing E-drive trials were not substituted, and no throughput
SLA or three-hour asset was invented. No new task or production file was created.
