# B-roll Adobe readiness — 25 October 2026

## Scope and ownership

This is a read/plan checkpoint, not a completed B-roll or native-insertion test.
Only this document was created during this checkpoint. No service was started,
stopped or restarted; no model, extraction, render, export or host action ran.
The existing Premiere instance was not inspected or controlled. No AE instance
was launched. Existing jobs, originals, failed trials and saved instructions stay
intact. `docs/PROJECT_TASK_MAP.md` was not edited.

The suite owner **Uploading Ai editor** owns shared panel/bridge/server changes,
host adapters, installation/packaging and Adobe host testing. Findings below are
handoff items, not authorization for competing feature/shared repairs. Preserve
one Adobe host and serialize heavy jobs. Do not stop other work to accelerate a
future B-roll test.
Never have Premiere and After Effects open at the same time. Before a later
authorized host launch, the suite owner must verify the other host is closed;
never blindly close, restart or save an unsaved owner project. Feature owners
remain read/plan-only until the shared/host reservation is released.

## Actual latest retest status

**Incomplete; no verified uninterrupted completion.**

| Evidence | Observed result |
|---|---|
| Job | `c1145994598a`, dedicated service port 8767 |
| Persisted job record | `cache/app/broll-jobs/8767/c1145994598a.json` |
| Persisted status/stage | `running`, 45%, `Checking room interior: 9/9 candidates, 0 choices saved` |
| Worker-attempt counter | `recovery_attempts=1`; not a completion receipt |
| Checkpoint | `cache/app/jobs/c1145994598a/broll-checkpoint.json` |
| Recovery journal | `output/broll/20261024-031225-b90409/recovery.json`, still `state=running`, no result |
| Project | `output/broll/20261024-031225-b90409/001-e2-1-/broll-project.json`, version 3, `collecting=true` |
| Live status read | Port 8767 refused the connection; no matching Storylens-8767 service or `hinglish_broll` worker was found in the read-only process check |
| Final artifacts | No `preview.mp4`, `BROLL_SEQUENCE.xml`, `BROLL_OPTIONS.xml`, `quality-check.json` or `CREDITS.txt` in this run |

The first local HTTP read was blocked by the shell sandbox. A permitted read-only
retry established connection refusal; it did not start anything. The saved
`running` flag is therefore stale operational state, not proof of a current job.
The cause of termination is **not established** by these receipts. Do not label
it a model crash, a GPU failure or a successful background completion.

The project/report last-write timestamps read as **24 October 2026, 03:14:13
IST**. The report exists because collection checkpoints write a partial review
page. Its existence does not establish finalization or complete playback.

### Source and saved local result

- Original: `A:\Full Drive\thisis.vineet\e2\e2(1).mp4`.
- Original exists, 46,011,692 bytes. Read-only SHA256 matches the earlier record:
  `a47789ede6d5ed07c752bdf7ecd974baefb176af8c12d73aa435e81bbe9f9a9c`.
- Saved sequence: 1080 × 1920, 30/1 fps, 35.7 seconds. The earlier measured source
  duration was 35.711995 seconds; do not confuse it with frame-quantized duration.
- `media_policy=videos_only`, `review_options=true`, five maximum choices,
  `requested_count=10`.
- This latest request used `audio_only_test=false`. The already-edited original
  remains underneath suggested cutaways; it is not an audio-over-black isolation
  demonstration. A future isolated quality test must select the appropriate mode
  through Storylens, keeping the original unchanged.
- The local summary and keyword-discovery receipts each contain one attempt and
  no recorded structural corrections. This is not proof of semantic accuracy.
- Ten moments were planned, but only two slot entries were persisted. Slot 0 has
  two locally approved video options; slot 1 has eight rejected candidates and
  is unfinished. The remaining eight planned moments were not collected.

| Planned subject | Speech start–end (seconds) | Saved collection |
|---|---:|---|
| Apartment interior | 2.14–3.10 | Complete, 2 options |
| Room interior / “bachelor ho” | 6.00–6.86 | Incomplete, 0 options |
| “Party work” | 6.86–7.78 | Not collected; questionable ASR/context interpretation, not an established occupation |
| Empty room | 14.96–16.24 | Not collected |
| Bed | 16.24–16.54 | Not collected |
| Wardrobe | 17.22–18.28 | Not collected |
| Water heater | 18.28–20.34 | Not collected |
| Refrigerator | 20.34–20.78 | Not collected |
| Washing machine | 21.20–22.60 | Not collected |
| Room interior / PG | 28.36–28.88 | Not collected |

Both saved options have nonempty downloaded source files and separate nonempty
prepared MP4s. These checks establish file availability only; no new decode,
playback or visual approval was performed at this checkpoint.

| Slot 0 option | Downloaded source file under `cache/broll/web-video/` | Prepared file under this project's `media/` | Prepared in / duration |
|---|---|---|---:|
| `web:6fae583c1519ba0d` | `adc98cb54037914beb92.mp4` | `broll-01-web-6fae583c1519ba0d-cf8adf37.mp4` | 0.0 / 3.966667 s |
| `web:57aeab2eb3fb2b2f` | `e8ef0817c2264e4362d3.mp4` | `broll-01-web-57aeab2eb3fb2b2f-92e200d2.mp4` | 3.0 / 6.966667 s |

### Separate evidence levels

1. **Component evidence:** 121 focused checks passed in the preceding development
   session. They were not rerun here. `attempt-5.json` records that count and its
   code baseline. All recorded `hinglish_broll` source hashes still match that
   baseline; shared `hinglish_app/server.py` has since changed. Do not attribute
   those shared changes to this checkpoint or assume the current host/service
   integration was covered by the earlier tests.
2. **Real local result:** partial saved collection described above. Earlier E2
   trials are preserved under `output/broll/e2-reliability-evidence/attempt-1.json`
   through `attempt-4.json`. They were rejected or stopped for relevance, shared
   search-budget and checker-consistency failures. They cannot substitute for
   acceptance of the final retest.
3. **Native insertion:** no Premiere panel import receipt, timeline verification,
   editable-trim test or playback verification exists for this latest result.
   This is reserved for the suite owner. CapCut and Resolve behavior is also not
   newly verified here.

## Existing video/project contracts

### B-roll generator

`broll-project.json` contains a `timeline`, source-grounded planned `slots`, and
per-slot `options`, `chosen`, `clip`, `source_in`, `source_duration`, checks and
collection status. Slot `start/end` are sequence seconds. An option's `clip` is
project-relative prepared footage; `path` is the downloaded/source-cache video.
Its source page, provider, license metadata, candidate ID and observed checks
must stay attached. `report_thumb` is a preview image, never insertion media.

The prepared video has target dimensions/rate and bounded trim handles. Its
`source_in` is relative to that **prepared clip**, not automatically relative to
the downloaded original. `render_choice` calculates `original_offset` and
`source_path`, but the review-option packing copies only source-in/duration and
canvas fields from its temporary candidate entry. The candidate retains `path`
and `offset`; an explicit prepared-to-original mapping is not carried through
the shared panel candidate row. Do not guess which coordinate system a trim uses.

Current legacy XML/native-project exports place selected slot clips at their
speech start/end and preserve independently editable clips with available
handles. `BROLL_OPTIONS.xml` is a **separate sequential browsing deck**, not a
speech-timed placement track. CapCut's optional alternatives are also sequenced
after the source. These browsing decks must not be mistaken for timed insertion.
No new export was created for this checkpoint.

### Shared panel: implemented pieces and gaps

Read-only inspection of `hinglish_app/editor_panel.py`,
`editor_panel_http.py` and `static/editor-panel.js` found:

| Requirement | Current code / handoff gap |
|---|---|
| 2 options per keyword for long form; 5 for short form | Panel `job_payload`, result choice slicing and `/api/panel/config` implement 2/5 from explicit `content_format`. The standalone Storylens page still defaults to 5 with a 1–5 selector; the generator default is 5 for either duration. The 180-second timing profile is not the same setting as panel content format. |
| Owner chooses whether to insert | Panel sets `panel_auto_import=false` for B-roll. However, the generator auto-populates `chosen/clip` with the first accepted candidate, and legacy exports consume those machine suggestions. There is no explicit owner-confirmed selection receipt in the project schema. A whole-result import can therefore use defaults the owner has not chosen. |
| Important script keyword and speech timing | `asset_choices` returns `id/path/keyword/start/end/name/kind`, but labels `keyword` from the whole slot text. It omits slot/candidate identity details, trims, original path/mapping, checks and credits. |
| Insert chosen option at its exact speech moment | A card sends only `asset=row.path` to `prepare_import`. The returned manifest is `type=assets`, `paths=[path]`, `expected={project_id,sequence_id}`, `insert=true`. It contains no speech timestamp, source trim, duration or target track. Timing fields from the choice row are not forwarded. Exact insertion cannot be claimed. |
| Videos only | The generator rejects non-video candidates and retains video quality checks. Shared `asset_choices` labels B-roll rows as video based on project filename without independently checking a video extension/type; shared asset import accepts both images and videos. Enforce the video-only B-roll invariant at the handoff boundary; no image/text fallback. |
| Exact source and later editing | Current candidate cards point to prepared, conformed clips. The downloaded source is preserved on disk but absent from the candidate handoff row. Importing only the prepared clip limits trim/reframe freedom to its baked crop and handles. Do not promise access to the entire original from that manifest. |
| Target safety and confirmation | Expected project/sequence IDs are included for native import. The UI expects an `ok` host receipt, but no latest-run B-roll insertion receipt exists. Native receipt behavior belongs to the suite owner. |

The individual generic asset manifest is also not a CapCut-project manifest;
the CapCut UI expects `type=capcut`. Flag this for the shared owner rather than
changing host adapters in parallel. The current shared host list is Premiere,
AE and CapCut; older browser export buttons also include Resolve. Do not expand
or launch hosts as a feature-owner workaround.

## Required candidate-to-host manifest agreement (proposal, not implemented)

Agree a versioned, typed **video-only candidate** contract with the suite owner
before host insertion. It should include:

- Stable result/job, keyword/slot and candidate IDs; exact spoken quote, intended
  visual concept and transcript anchor. Keep ambiguity explicit rather than
  treating an uncertain ASR interpretation as fact.
- Original local media path and fingerprint, source page/provider/credit record,
  media rate/duration/dimensions, plus a distinct prepared-preview path. Preserve
  originals and every failed diagnostic. A poster is never a substitute video.
- Sequence start/end in a stated timebase and target project/sequence identity.
  Preserve an explicit mapping between prepared source-in and original media
  source-in, usable media range and handles. Validate bounds and frame rounding.
- Local relevance/object/quality/watermark verdict references for the checked
  active interval. Original-media insertion must reproduce that checked crop or
  be separately validated; don't silently switch to unrelated source frames.
- Owner decision (`unselected`, selected candidate, or `no_broll`) separately
  from machine suggestions. Default to no insertion; generating suggestions
  alone must not add clips. No image/text substitution for an empty group.
- An explicit one-candidate insertion request and host receipt identifying the
  actual imported media, sequence, start/end, source in/out and inserted item.
  An API queue entry or prepared file is not a host insertion receipt.

Do not infer speech placement from filenames, the playhead or an options deck.
Keep clips independently trim/move/resize editable within the actual source
bounds; extending cannot invent footage beyond those bounds.

## Next bounded tests — pending, not executed

1. **Suite-owner decision first:** retain the stale job/checkpoint and decide
   whether the dedicated service may be resumed after inspecting the shared
   queue and current server changes. Do not launch a duplicate request or stop
   another job. If resumed, use the same source/settings/checkpoint and record
   the actual continuation count. This checkpoint does not authorize a restart.
2. **Local result gate:** one E2 job only, five maximum short-form candidates per
   keyword, video-only. Require all planned groups to reach a terminal collected
   or explicit no-suitable-match state; inspect intended sense, actual active
   video intervals, preserved originals, finalization and full low-resolution
   playback. Record gaps and uncertain speech. Keep any Pexels rejection visible;
   it was present in the saved run, not newly probed against Pexels today.
3. **Choice-only contract check:** using a saved completed bank, verify 2 long / 5
   short limits, no automatic insertion, no-B-roll selection, stable IDs and
   complete timing/source mappings. A changed format must not erase choices.
   Confirm corrupt/missing/non-video rows produce the shared plain-language error
   without triggering a substitute image or a heavy retry loop.
4. **One Premiere insertion, suite owner only:** owner selects one candidate in
   the already-open host. Verify expected timeline identity, actual insertion
   at the anchor and exact source in/out, with one native receipt. For slot 0 at
   30 fps, rounded target bounds are frames 64–93 (29 frames); an option with
   prepared in=3.0 seconds needs prepared frames 90–119, not a default zero in.
   Compare using the agreed original-media mapping if importing the raw source.
5. **Editable and no-duplicate check, same host/session:** trim/extend within
   available handles, move and resize the one clip, verify the source remains
   linked and independent, then inspect playback. Verify cancelling/no-B-roll,
   reconnecting and repeating a receipt do not insert duplicates or alter other
   tracks. Preserve the original sequence and prior evidence.

Component checks, a local review page, and native panel insertion must remain
separate acceptance records. The current state is **not Adobe-ready verified**
and **not proof of reliable one-go completion**. No cross-task repair or native
experiment was undertaken for this read/plan checkpoint.
