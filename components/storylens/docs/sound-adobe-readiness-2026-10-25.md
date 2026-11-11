# Sound Design → Premiere readiness

Read-only source/evidence snapshot, 25 October 2026. No feature code, shared panel, bridge, host adapter, installation or package changed for this assessment. No tests, inference, renders, imports, UI automation or host actions were started. Only this document was created. The suite owner controls shared integration and native validation. Premiere is the one designated open Adobe host; do not launch After Effects.

## Readiness decision

**Automatic sound generation and editable export exist, but autonomous creative quality and the current Premiere panel round trip are not accepted end-to-end.** Both panel choices exist. However, **recommendation is presently a view of already generated soundtrack stems, not a distinct ranked music-and-SFX recommendation workflow.** Music is implemented in the underlying engine and can appear in that view; it would be inaccurate to call it SFX-only, or to call it a finished music-candidate browser.

For a first reliable Adobe deliverable, implement a clearly typed, manually selected candidate contract before extending long-form automation. Reuse the existing mixer/exporter for auto. Preserve natural duration, actual source/action/environment relevance, overlap, speech ducking, original audio exactly once, shared mastered stems and all creator guidance.

10–15 minute input is the target. There is no owner-approved processing-time budget. No long-form throughput or RAM/VRAM acceptance claim is supported yet.

## Current contracts

| Boundary | Existing contract and behavior | Evidence / limitation |
| --- | --- | --- |
| Shared context | `PanelContexts.save`: `host`, `project_id`, `sequence_id`, `script` (string, up to 20,000 characters), `content_format` (`short`/`long`), and native timeline XML or supported clip snapshot. Context ID hashes host/project/sequence. Saved under `cache/editor-panel`. | [editor_panel.py](<A:/Full Drive/remove silence/hinglish_app/editor_panel.py:20>). Adobe FCP XML capture is preferred. Snapshot fallback rejects unsupported tracks/gaps/speed/effects and explicit separate audio; do not generalize that fallback to arbitrary edited projects. |
| Panel run | `POST /api/panel/run`: `{mode:"sound", context_id, script, content_format, settings:{sound_action:"recommend"|"auto"}}`. `PanelService.start` persists the supplied script into context and calls the ordinary application job engine. | [editor-panel.js](<A:/Full Drive/remove silence/hinglish_app/static/editor-panel.js:40>), [editor_panel.py](<A:/Full Drive/remove silence/hinglish_app/editor_panel.py:239>). This is video/timeline plus shared script, not script-only generation. |
| Sound settings | Both modes set `sound_remove_music=false`, `sound_music=true`, `sound_effects=true`. `panel_auto_import` distinguishes the modes; `panel_sound_action` is stored in the payload. | [job_payload](<A:/Full Drive/remove silence/hinglish_app/editor_panel.py:90>). The sound worker command does not receive a separate recommend-only switch. Existing music remains while added music is enabled: an explicit preserve/replace/no-new-music decision is needed in the proposed contract. |
| Worker input | Main server invokes `hinglish_sound --input <timeline> --script <saved shared script> --device …`, with style/density/music flags. Script corrects recognition and supplies semantic context. | [server.py](<A:/Full Drive/remove silence/hinglish_app/server.py:572>), [CLI](<A:/Full Drive/remove silence/hinglish_sound/__main__.py:10>). Full source alignment remains necessary; a shared script alone does not supply reliable timeline timestamps. |
| Recommend completion | Full generation finishes first. `sound_choices` reads generated `SOUND_SEQUENCE.xml`, deduplicates audio paths, copies those WAV/media files into `panel-sound-options`, and returns `{id,path,name,keyword,start,end,kind:"audio"}`. | [sound_choices](<A:/Full Drive/remove silence/hinglish_app/editor_panel.py:285>). These are selected/baked clips, not multiple alternatives per beat or per music section. Original audio is currently included too. |
| Candidate audition | Each card contains an `<audio controls>` element pointing to `/api/panel/media?path=…&token=…`, with an Add button. | [editor-panel.js](<A:/Full Drive/remove silence/hinglish_app/static/editor-panel.js:39>). The card label does not render `start`/`end`; no typed music/SFX/original distinction, excerpt in/out, level, role, reason, licence or candidate group is exposed. The media route streams the full file with HTTP 200, not a dedicated short audition/range contract. |
| Manual import | Card click passes the **path only** into `/api/panel/import`. Asset branch returns `{type:"assets",paths:[path],expected:{project_id,sequence_id},insert:true}`. | [prepare_import](<A:/Full Drive/remove silence/hinglish_app/editor_panel.py:193>). Planned candidate timestamps are not carried into this manifest. |
| Current Premiere asset insertion | Shared adapter imports into a new bin and places audio on the last audio track using `overwriteClip` at the current playhead. Requires a spare audio track. | [premiere-panel.jsx](<A:/Full Drive/remove silence/editor_plugins/shared/premiere-panel.jsx:9>). This is **at-playhead placement**, not the recommendation's planned timestamp. Overwrite and overlap policy, idempotency and native receipt checks belong to the suite owner. Do not patch this shared file here. |
| Auto completion | `auto_import=true`; prepare/import the finished sound result through the existing Premiere handoff. Panel calls its native import when the manifest is ready. | [PanelService](<A:/Full Drive/remove silence/hinglish_app/editor_panel.py:263>). Returned `complete` precedes successful native receipt. Local generation is not a native acceptance receipt. |
| Editable export | `sound-plan.json`, `sound-decisions.json`, `model-checks.json`, `sound-sources.json`, `CREDITS.txt`, `sound/full-mix.wav`, mastered editor stems and `SOUND_SEQUENCE.xml`. Video preview only for duration ≤300s. | [pipeline.py](<A:/Full Drive/remove silence/hinglish_sound/pipeline.py:119>), [XML exporter](<A:/Full Drive/remove silence/hinglish_sound/xml_export.py:49>). Longer work can have playable audio and XML without an MP4 preview. |

### Music really is implemented

The automatic pipeline scans local music libraries separately, retrieves up to five instrumental candidates for each music section, asks the local model for a choice, checks vocals/energy, selects an energy-appropriate source passage, mixes the bed and exports it. See [pipeline.py](<A:/Full Drive/remove silence/hinglish_sound/pipeline.py:377>) and [music.py](<A:/Full Drive/remove silence/hinglish_sound/music.py:6>).

`sound-decisions.json` retains offered music paths and the model's selections. `sound-plan.json` retains selected paths, source offsets, reasons, time bounds and evaluation. **The recommendation UI does not expose those alternative music paths as ranked choices.** It reads the exported XML instead; the exported music WAV is the mastered combined music bus, normally starting at zero for the whole sequence, not each original music candidate/excerpt.

Read-only XML audit performed for this document, without calling `sound_choices` (that function writes copied media):

| Existing result | Unique audio paths that current `sound_choices` would expose | Meaning |
| --- | --- | --- |
| `output/sound/20261025-000748-861726/001-0000-d5752e39-vineet_2919_1678460747_305` | 30: one original-audio stem, one full-sequence background-music stem, 28 effects | Concrete evidence that music can be exposed. Also evidence that recommendations include original audio and offer one selected/baked music bus, not ranked track alternatives. |
| `output/sound/20261025-005000-b148bf/001-ten-second-source` | Seven: original audio plus six effects, no added music | Effects-only spotting is implemented. Do not report that this particular preview demonstrates automatic background-music selection. |

## Existing automatic behavior to retain

1. Local ASR/word alignment plus shared script; sampled local Vision; measured events from other Storylens editing features. Sparse frame observations are contextual evidence, not exact contact timing.
2. Story/delivery/acoustic identity; explicit music/effects-only/voice-only sections. Scene layers get budget before new optional spoken-word accents; already authored accents remain.
3. Typed natural duration and audible sound-family guidance. Authored non-ambience effects can extend to eight seconds, ambience to 30 seconds, bounded by the real source. Actual clicks can remain brief. No time stretching and no arbitrary one-second minimum.
4. Cross-folder physical retrieval, subject metadata matching, source/material grounding, owner bans and tone exclusions; embedding/CLAP matching; model may choose `-1`. Unsupported/missing sounds are skipped, not substituted with wildlife or clicks.
5. Layer grouping, distinct roles, explicit recurring-source reasons, source excerpts and energy-peak synchronization. Five concurrent effects plus the music bed is the current bound; at most two overlapping ambience layers. Energy peak alignment is not verified semantic contact.
6. Bounded pan/filters/fades/speech-pocket/ducking. Processing is baked into separate editable audio stems; it is not a native live effects/keyframe recreation. Arbitrary pitch/reverse/reverb/music-stem arrangement is not implemented here.
7. Original stereo mix retained once when requested. The XML exporter replaces original audio tracks with that preserved/processed base, then adds music/effects. Mastered stems use the common gain/limiter envelope and reconstruct the mixed preview within measured PCM tolerances.

Relevant source: [layers.py](<A:/Full Drive/remove silence/hinglish_sound/layers.py>), [retrieval.py](<A:/Full Drive/remove silence/hinglish_sound/retrieval.py>), [processing.py](<A:/Full Drive/remove silence/hinglish_sound/processing.py>), [mix.py](<A:/Full Drive/remove silence/hinglish_sound/mix.py:224>), [spotting.py](<A:/Full Drive/remove silence/hinglish_sound/spotting.py>).

Configured local roles are `storylens-meaning:14b`, `storylens-planner:9b-q6`, `storylens-embedding:8b-q6`, CLAP `laion/larger_clap_general`; planning thinking is off, context 12,288. Saved reference knowledge is retrieval, not weight training. Library evidence from the last run: six music tracks and 2,216 effects; coverage is uneven despite the effect count.

## Measured evidence and its limits

| Evidence | Measured | What it does not establish |
| --- | --- | --- |
| Guided motorcycle trial | 82.9882964s for one real 14B planning call; 8,255 input/3,245 output tokens; 22 model-authored layers; 27/27 mix checks; stem reconstruction error .000091553 PCM | Used existing video analysis/catalogue and a separate guided runner. Not a normal fresh-video benchmark, production planner replacement, native playback acceptance or SLA. |
| Thirty-second recovery | 554.337786s wall time for 30.0667s; reused saved work; one guard attempt per stage, no full-project redos; 28 effects/six music sections; 34/34 mix checks | No stage-time split or measured RAM/VRAM. This bypassed normal repeated-redo behavior and is not a 30–40s performance acceptance test. Owner rejected its click-heavy design. |
| Initial ten-second direction check | 390.602785s, using saved source and some analysis; discovered concrete library/selection/evaluator failures | Development/repair observation; not an optimized steady-state baseline. |
| Final ten-second cache-only rebuild | 59.811032s, with **new Qwen chat calls blocked**, six effects including five-second water bed; 11/11 mix checks; IAB reached 10/10s, ended=true, no media error | Not fresh inference or pure render time. Still initializes/reuses native analysis tools; no phase profile, no native editor playback or artistic approval. |
| Prior compatibility mix | 82 mix checks; mastered stems reconstruction .00012219 PCM, peak about -2dBFS | Engineering fixture/remix, not a newly accepted AI-authored score. |
| Last scoped regression run | 154 `test_sound*.py` checks passed in 3.121s | Earlier task evidence, **not rerun for this read-only assessment**. No claim that unrelated concurrent changes have been revalidated. |

Evidence locations:

- [Delivery/review JSON](<A:/Full Drive/remove silence/output/sound-natural-direction-20261025/delivery-review.json>) and [cache-only receipt](<A:/Full Drive/remove silence/output/sound-natural-direction-20261025/result.json>).
- [Recovery receipt](<A:/Full Drive/remove silence/output/sound-website-repair-20261024/recovery-result.json>).
- [Per-call model timing](<A:/Full Drive/remove silence/output/sound-comparison-20261024/retry2-sources/qwen-generation-timing.json>).
- [Guided motorcycle scope](<A:/Full Drive/remove silence/docs/qwen-guided-bike-result-2026-10-24.txt>), [natural-direction scope](<A:/Full Drive/remove silence/docs/sound-natural-duration-and-scene-direction-2026-10-25.txt>), [prior compatibility evidence](<A:/Full Drive/remove silence/docs/sound-design-ready-2026-10-24.txt>).

The owner's approved ChatGPT physical motorcycle take is a direction/reference, not evidence that local Qwen matches it on arbitrary uploads. Native Premiere/CapCut sound playback remains unverified by this feature thread. The suite's current clean/import/playback work and shared host receipts remain with its owner.

## Smallest next changes — proposal only

### 1. Concrete manual music and SFX candidates

1. **Feature-owned recommendation manifest** derived from the existing offered candidates and approved evidence, not by scraping finished XML. Distinguish `kind: music | sfx`; exclude original/dialogue stems. Return multiple eligible choices per music section and SFX event, while allowing an explicit no-match.
2. Each option needs a stable candidate/event/section ID, source identity/hash, name and credit/licence pointer, actual source path, `timeline_start/end`, `source_in/out`, `audition_path`, role/type, natural duration, proposed level, reason, relevance/evaluator status and evidence precision. Preserve exact timestamps as numbers; source offset is not timeline start.
3. Prepare short playable **candidate excerpts**, using measured source passages for music and actual source duration for SFX. Do not let music auditions require downloading a whole 10–15 minute mastered bus. Keep original sources immutable and expose full tracks separately when appropriate.
4. Run recommendation only through analysis/retrieval/audition preparation; do not render/mix a whole automatic soundtrack before the owner can hear alternatives. Persist chosen candidate IDs and explicit rejections.
5. **Suite-owned integration**: render separate timestamped Music/SFX candidate groups, transfer selected typed entries rather than path-only assets, choose “at planned time” versus explicitly “at playhead,” provide safe separate-track/overlap behavior, project/sequence guards and duplicate prevention, then verify a native receipt and playback. Do not call an at-playhead overwrite timestamped insertion.

This is the smallest path to a reviewable recommendation feature. It does not require replacing the sound engine or shared-script framework.

### 2. Automatic editable soundtrack

Retain the existing engine's plan/mix/XML contracts. Before calling it ready: obtain owner authorization for the preserved final-review findings; establish unique/complete picker IDs, validate cross-category subjects/actions and musical phrase continuity, and inspect a real native result. Clarify source-music preservation versus added music in the panel. Keep original audio once and retain separate mastered clips with offsets/overlap/ducking baked correctly. The automatic result should remain a reviewable new timeline/copy, never overwrite the owner sequence silently.

General inference must select environment/source/action/emotional sounds without per-video human lists. It must also report missing real-world coverage honestly. Adding more UI clicks does not solve physical Foley or music coverage. Do not promise exact private Epidemic behavior or perfect future-category generalization.

## Profile 30–40 seconds before claiming 10–15 minutes

Future coordinated validation, **not executed now**:

1. One owner-supplied 30–40s realistic timeline with its actual shared script, original speech/music, a sustained physical source, an emotional turn, a cut/motion event and overlapping sounds. Start no competing GPU job; measure any queue time instead of killing others.
2. Trace monotonic start/end for enqueue, GPU-lock acquisition, host capture, library scan/index, ASR, forced alignment, Vision sheets, prosody, story/palette, layer composition, embedding retrieval, each picker/repair, each candidate evaluation, optional separation, mix/master/stems, preview rendering, manifest preparation, native import receipt and native playback. Record output-token counts, model identity, cache hits/misses, dropped layers and retry causes.
3. **Cold**: new media with no analysis cache, runtime/model load status recorded, existing indexed library clearly distinguished from first-library indexing. **Warm**: exact same input/settings/model/creator/reference hashes with cache reuse. A changed script or camera edit is neither an identical warm hit nor wholly cold; label it.
4. Record wall time and active processing separately, per-process private/working-set RAM, GPU allocated/reserved memory where supported, device VRAM sample/peak, CPU/GPU utilization, source dimensions/fps, and preview resolution. **No measured peak RAM/VRAM is available in the saved sound receipts.**
5. Native owner verifies speech remains intelligible, source audio once, suitable music, source-relevant sustained Foley, varied accents, natural tails, layer overlap, editable timing/levels and correct reopened project media. Mix checks alone do not judge storytelling.
6. Report measured totals with cache conditions; ask for the acceptable long-form processing budget before offering an SLA. Do not multiply 83 seconds or 554 seconds into a guaranteed long-form ETA.

Code-derived scaling concerns, not measurements: temporal Vision currently makes about one 12-frame contact sheet per six seconds (approximately 100/150 sheets for 10/15 minutes). Story analysis chunks at 35 lines; speech composition at 24 anchors, other events at 80; file picks at eight effects/four music sections. Audio mixing retains full-duration float32 buffers: one 48kHz stereo buffer is approximately **230.4MB for 10 minutes / 345.6MB for 15 minutes**, with several additional buffers/temporaries and model memory. Actual peak can be much higher and must be measured. Preview MP4 is skipped above 300s.

## Cancellation, checkpoints and bounded long-form work

Current sound jobs lack a dedicated durable cancel/checkpoint/resume contract. Normal `AppState.jobs` and `PanelService.jobs` are process-memory dictionaries; dedicated persistent/recovery handling exists for B-roll/Visuals, not Sound. Content-addressed ASR/Vision/model/library caches and saved final plans are useful reuse, but are **not** a sound job checkpoint or a reliable saved UI receipt. `--refresh-export` rebuilds an existing final plan; it does not resume incomplete planning.

Current retry layers: model guard defaults to three attempts; normal app may add three whole-feature evaluator runs; Vision permits two structured-response attempts; model chat timeout is up to 3,600s. The demonstration runners forced one guard attempt and bypassed whole-project redo, so that behavior must not be attributed to ordinary panel jobs. The GPU lock waits without a sound-specific cancellation check.

Proposed minimum, split by ownership:

- **Sound feature**: immutable job fingerprint (source/timeline trims, fps, exact script, complete creator-profile hash, model/settings/reference/library versions); atomic per-stage and per-section receipts; save evidence/analysis/candidates/owner selections/plan/stem receipts before moving on. Final files committed atomically; keep prior preview/receipt on failure. Store failure category and intended continuation point.
- **Sound feature**: bounded scene/paragraph/section planning, global IDs and original timeline timebase, overlap/handle regions for transitions and tails, continuity across chunk boundaries, deduplicate overlapping events, maintain ducking and coherent music source offsets across sections. Do not use independent per-chunk loudness mastering that causes level jumps; preserve the shared final gain or a measured equivalent.
- **Suite owner**: stable job handle, durable panel/API status, cancel request and acknowledged terminal state, cooperative token into queue wait and stage/section boundaries; terminate only the owned worker when necessary. A model request or native import that cannot be interrupted must report “cancellation requested” rather than pretend it has stopped. Check active host/context again before any later import.
- **Both, coordinated**: resume only matching unfinished sections, invalidate dependent stages on genuine input/version changes, never duplicate audio placement on import retries. Full creator guidance stays saved and included in required planning context; only the owner-approved optional-prose per-call fallback may omit optional retrieved text. Long input must be partitioned or stopped clearly, not silently truncate script/profile.

## Open findings — retain; no fixes authorized by this assessment

| Status / trigger | Expected → actual | Impact / evidence |
| --- | --- | --- |
| **Confirmed prior final review:** picker returns two `moment:0` rows, omits `moment:1` | Unique selection/`-1` per ID → cardinality/bounded-ID schema still permits duplicates; omission is classified soft | Can leave uncovered events or poor selection. Preserved in `delivery-review.json`; this assessment does not repair it. |
| **Confirmed creative limitation:** play the completed 10s water-park result | Context-led natural variety/action Foley → one 5s water bed, three .2s pops, .3s whoosh, .5s comic drums; exact sliding Foley absent | Automatic quality remains incomplete; owner listening approval pending. Same delivery evidence. |
| **Source-confirmed integration gap:** manual Sound card Add | Timestamped candidate placement → candidate time is discarded; host overwrites at playhead | Suite-owned native behavior, not runtime-reproduced here. Exact paths/branches above. Also no native overlap/idempotency acceptance claim. |
| **Source-confirmed product gap:** recommend mode | Music and SFX alternatives without choosing/rendering full score → complete auto generation, then selected stems including original audio | Recommendation mode is incomplete, music is not absent from the engine. Read-only XML audit above. |
| **Unverified scale/recovery:** restart/cancel a long sound job | Durable state and bounded continuation → no Sound-specific checkpoint/cancel implementation found | Do not advertise unattended 10–15 minute readiness. No disruptive restart/cancel probe was run. |

## Commands for the next authorized validation

Listed for coordination; **none were executed in this read-only task**:

```powershell
.venv\Scripts\python.exe -m unittest discover -s tests -p 'test_sound*.py'
.venv\Scripts\python.exe -m unittest tests.test_editor_panel tests.test_editor_panel_http
node --test tests/editor_panel.test.cjs tests/editor-panel-cep-context.test.cjs
```

Use the configured project Node runtime if `node` is not on PATH. Loopback HTTP fixtures need permitted local socket access. Unit fixtures synthesize media and are not a replacement for the owner's realistic timeline test. Shared panel/host checks, packaging, clean/import/playback and any installation remain with the suite owner; do not run them concurrently from this feature thread.

Sound-specific regression anchors: `tests/test_sound_natural_duration.py`, `test_sound_website_context.py`, `test_sound_composition.py`, `test_sound_arrangement.py`, `test_sound_editor_master.py`, `test_sound_editor_layers.py`, `test_sound_output_http.py`. Preserve their source-audio-once, overlap, excerpt/PCM, shared mastering, invalid processing and full creator-context contracts.

**Next action:** await coordination on the candidate-manifest contract and ownership split. No implementation, heavy validation or Adobe interaction is authorized by this read/plan handoff.


## Coordination / blockers at this checkpoint

Read/plan deliverable is complete. No permission/login/Allow prompt was encountered; no Adobe application was inspected or controlled. No running or saved job was changed. Future implementation remains pending coordinator release and the suite owner's shared-contract decision. Native host acceptance remains pending its reserved Premiere session. The acceptable 10–15 minute processing budget is still unspecified; request it when needed for a performance acceptance decision, not as a reason to interrupt this read-only handoff. Standing final-review findings need a subsequent owner request before repair. No persistent/security access, spending, publishing, deletion or unattended host actions are authorized by this document.

## Subsequent bounded implementation release — 25 October 2026

Coordination subsequently released **only** independent feature-owned candidate/timing modules, dedicated Sound tests and evidence. That stage is now implemented in `hinglish_sound/recommendations.py` and `hinglish_sound/recommendation_runtime.py`. The earlier source analysis of the shared panel remains accurate: **it has not been connected to this new entry point**. Existing automatic Sound Design behavior, protected final findings, server/UI, bridges, native adapters and packaging were left untouched by the stage.

The new v1 manifest offers ranked actual music/SFX source alternatives from already prepared rankings and cached evidence, with stable source/window/credit identity, exact proposed times/levels, full creator context, explicit rejection/no-match, partial-music coverage, cooperative cancellation/checkpoints and injectable monotonic receipts. Default cached-only gating prevents accidentally invoking an embedding model through an uncached ranker. No full soundtrack mix/render is required. The module also provides a read-only source-verification hook for eventual suite-owned import.

[Integration contract and evidence](<A:/Full Drive/remove silence/docs/sound-candidate-evidence-2026-10-25/README.md>) includes the [golden manifest](<A:/Full Drive/remove silence/docs/sound-candidate-evidence-2026-10-25/golden-manifest.json>) backed by four tiny real playable sine-wave WAVs. It is explicitly synthetic metadata/ranking evidence, **not** a real recommendation or creative acceptance demo. 37 isolated checks passed in 2.903s (20 new, 17 existing focused regressions). No models, heavy GPU work, renders, downloads, Adobe UI or publishing occurred.

Final safe review found a **new unmodified checkpoint limitation**: changing a saved group's intent text can survive resume despite unchanged input fingerprint and verified source bytes/times. Record/reproduction is in [final-review.json](<A:/Full Drive/remove silence/docs/sound-candidate-evidence-2026-10-25/final-review.json>). Do not treat checkpoint semantics as authenticated or enable untrusted external checkpoint ingestion. Protected older automatic-picker/creative findings were not repaired.

Remaining suite hooks: timed cached-analysis preparation, candidate-ID-based private audition serving, group/selection UI, shared plain-language errors, planned-time native insertion with source windows/levels/overlap and duplicate prevention, native receipts/playback, then separately authorized profiling. The existing media endpoint accepts output-only paths; do not widen it to arbitrary raw paths. Native and long-form readiness remain unverified. Stop at this ownership/resource boundary pending coordination.

### Subsequent owner local-brain acceptance requirement

The 37 isolated checks/golden tones are component evidence only. Actual acceptance must run normal app semantic planning/selection/tool calls through the configured local models, without hand-authored model answers or Codex/cloud replacements. The independent module has no OpenAI/Codex/ChatGPT runtime/session dependency, but the shared entry point/local-agent tool registration and packaged/native validation are still pending. No actual local-agent acceptance or subscription-expiry continuity test was run in this released stage.

An additional static/pure-function audit records two more unmodified findings: caller telemetry metadata is not sanitized before receipt/sink storage, and the shared explicit non-legacy model override returns before local-only cloud-suffix validation. No real credentials, model calls or remote inference were used. Current configured sound defaults are loopback/local; optional asset APIs/licences and commercial app licensing are separate runtime dependencies. See [local-runtime-audit.json](<A:/Full Drive/remove silence/docs/sound-candidate-evidence-2026-10-25/local-runtime-audit.json>) and the now-three-item [final review](<A:/Full Drive/remove silence/docs/sound-candidate-evidence-2026-10-25/final-review.json>). Do not pass provider secrets/raw headers into the unsanitized instrumentation hook or equate its docstring with redaction.

Genuine short-then-long laptop acceptance, model/provider/version and redacted request/tool receipts, cache lineage/intervention flags, stage timings/RAM/VRAM and native placement/playback remain on the coordinated acceptance plan. No new heavy work or shared/native changes were started. No zero-breakage or long-form speed claim is made.

### Protected repair queue / integration boundary

The final-review repair boundary has been explicitly reaffirmed. Feature modules/tests stay frozen at the delivered 37 isolated checks. [Proposed repair cycles](<A:/Full Drive/remove silence/docs/sound-candidate-evidence-2026-10-25/proposed-repair-cycle.md>) separately cover checkpoint semantics, telemetry sanitization and suite-owned locality policy, with reproduction, regression proposal and integration-safe workaround. No new repair is implemented or authorized by that document. Fresh recommendation integration may continue without semantic checkpoint resume; protect timing metadata from raw secrets and retain cached-only ranking until actual local-agent dispatch/resource release. No owner wake-up or repeat approval request was made here.

### Fresh local-analysis component handoff

The subsequent bounded stage adds `hinglish_sound/recommendation_pipeline.py`:
normal media/shared-script/full-context inputs can invoke the existing local
ASR, temporal Vision, prosody, story/layer planning and prepared library ranking
without a full automatic mix first. The suite-owned normal route is still not
connected here. Exact invocation, model/receipt boundaries, 58 passing CPU
component checks and TWO NEW UNFIXED final-review findings are in
[the pipeline handoff](<A:/Full Drive/remove silence/docs/sound-recommendation-pipeline-2026-10-25/README.md>).
The frozen 37-check files remain unchanged; no semantic checkpoint resume,
protected repair, inference/GPU/library scan/render/native/browser action was
performed. Physical-layer action-interval overrun and intentional-silence status
remain open; actual local-agent, creative and native acceptance are pending.

### Explicit source-window audition component

A subsequent independent stage adds `hinglish_sound/audition.py` for an explicitly
selected candidate from a verified manifest/hash. It creates/reuses a checked,
bounded raw audio-only excerpt inside that existing output job, with exact
source/window/credit identity, private snapshot, atomic receipt and ordinary
failure/cancellation messages. The suite still owns auth, job routes/UI/serving
and native integration. [Callable contract and evidence](<A:/Full Drive/remove silence/docs/sound-audition-2026-10-25/README.md>)
records 79 passing component checks (21 new audition checks), unchanged protected
files and ONE NEW UNFIXED final-review I/O-bound limitation. No real owner
audio/model/GPU/network/library scan/browser/Adobe/service action or live app
acceptance occurred. No existing manifest timing was changed.
