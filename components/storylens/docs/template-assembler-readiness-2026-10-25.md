# Template Assembler readiness and integration handoff

Recorded 25 October 2026, Asia/Calcutta. This update is READ/PLAN only: source and
saved evidence were inspected; no code, installation, security setting, Adobe
window, project, render or running job was changed. No tests were rerun.

Filesystem checkpoint, 25 October: this file was verified with both `Get-Item`
and `Get-FileHash` at the literal path
`A:\Full Drive\remove silence\docs\template-assembler-readiness-2026-10-25.md`.
The executor's working directory was `A:\Full Drive\remove silence`. Before the
queue-planning append below, it was 18,348 bytes with SHA256
`4C63F50F86FA0E20EAACA3600090CAE2F1316B43D2DD572E79AC6E17C3CE3C04`.
The coordinator's filesystem namespace was not independently accessible here;
the reason its shell could not find the file is unverified. This is an existing
local file, not an unsaved chat artifact. The following append changes its size
and hash; the final filesystem checkpoint is reported with the completion.

## Current coordination boundary

- Latest voice scope explicitly supersedes indiscriminate 11-tool acceptance.
  The current feature list is the requested camera/shared-script/Smart Clean,
  Sound alternatives, video-only B-roll, ranked AE AEP assembly and screenshot
  originals, selective long-form typography/full short captions, gaming
  highlights → selected N shorts → publishing preparation/queues, and the paired
  Beat/Cinematic workflow. Other existing features are deferred and preserved.
  This thread still owns only template readiness and the separate publishing
  **plan**, not that whole feature list or any shared implementation.
- Beat/Cinematic ownership has not been assigned here. Its handoff requirement
  is salient song beats/phrases plus strongest/diverse sources from roughly
  40–50 short videos, typically up to 15–20 seconds each, into an editable reel.
  The 50-second/10-cut/5-second example is illustrative, not fixed spacing.
  Keep the song continuous by default with nondestructive beat markers or
  segmentation; no audio removal/reordering or automatic captions, sound,
  visuals or B-roll. Do not start a competing implementation or acceptance loop.
- The latest coordination instruction says Premiere is open and reserved by the
  suite owner, **Uploading Ai editor** (`01a147ee-67b7-7310-bcfc-76a5fc16139d`).
  This update did not independently inspect live UI. Older evidence saying
  Premiere was closed describes the earlier validation session, not current UI.
- The suite owner exclusively controls shared panel/bridge/server integration,
  shared host adapters, packaging/installations and Adobe UI for now.
- This feature owns the contracts and evidence under
  `editor_plugins/template-assembler`; shared integration changes require a
  scoped handoff. Do not independently install, restart, save, close or operate
  either editor. A future AE check must wait for a coordinated host switch.
- **Final hard constraint: Premiere and After Effects must never be open at the
  same time.** Before any later authorized launch, the suite owner must verify
  that the other host is closed. Never blindly close, restart or save an unsaved
  owner project to make that condition true. This feature owner must not perform
  that host preflight or switch while its assignment remains READ/PLAN only.
  Do not start concurrent heavy GPU jobs. Dynamic Link can consume RAM in Adobe
  background processes; that does not authorize opening both hosts. Its actual
  host behavior must be checked within the suite owner's reserved acceptance
  window before describing the Premiere path as compatible with this constraint.
- Preserve the original AEP library, saved projects, previous findings and jobs.
  No publishing, uploads, spending, account grants, deletion or security changes
  belong to this handoff. The separate gaming highlight/publishing workflow is
  outside this feature. Coordination owns `docs/PROJECT_TASK_MAP.md`.
- The later unattended-continuation preference does not expand this READ/PLAN
  assignment. No Allow prompt was inspected or clicked here. Future in-scope
  prompts must be identified exactly; ordinary reversible approvals are subject
  to tool/policy limits. Never auto-approve an unidentified prompt, persistent or
  security access, secret exposure, spending, deletion or live publication, or
  bypass a sandbox/host/user-only approval. Record an exact blocked action,
  target, reason and pending/denied/uncertain status, then continue independent
  authorized work without unnecessary overnight interruptions.

## Requested behavior

The user supplies Envato AEP projects ranked 1–10, or a longer ordered list.
Choose each project's actual Main/Render composition, place those compositions
consecutively to a target duration, preserve animation speed, and trim the final
placement at the target endpoint. Repeating the same order is an explicit
option, not the default. Extra templates after the endpoint remain unused.

Canonical source library:
`A:\Editing\AE documentry style editing templates`.

The implementation uses native Adobe composition metadata and deterministic
frame arithmetic. No local LLM, Vision model, web search or rendering is needed
for assembly. Template footage, fonts, plugins and expressions are preserved;
their creative correctness is not established by placing the main composition.

## Owned files and entry points

| File | Existing responsibility |
| --- | --- |
| `editor_plugins/template-assembler/model.js` | ES3-compatible `SLTemplateModel.rank`, `choose`, `plan`; also CommonJS-exported for planner tests. |
| `editor_plugins/template-assembler/host.jsx` | `SLTA` native operations, metadata catalogue, JSON replies and dispatch. Includes `model.js`. |
| `editor_plugins/template-assembler/index.html`, `panel.js`, `panel.css` | Separate CEP panel: ordered rows, composition choices, target/options, list dialogs, cached Premiere reads and result messages. |
| `editor_plugins/template-assembler/Template Assembler.jsx` | Resizable AE ScriptUI fallback using the same native engine. This was the actual native validation route. |
| `editor_plugins/template-assembler/CSXS/manifest.xml` | Separate extension `com.storylens.templateassembler.panel`, version 1.0.0; AEFT/PPRO host declarations, CEP runtime and host script. Host ranges are declarations, not evidence of every version working. |
| `editor_plugins/template-assembler/errors.json` | Packaged subset of the shared `hinglish_app/error_catalog.json`; it is not the authoritative catalogue. |
| `editor_plugins/template-assembler/Install.ps1` | Existing per-user source-panel installation/backup and explicit unsigned-CEP option. Packaging/installations now belong to the suite owner. Do not run it in this read/plan scope. |
| `tests/template_assembler.test.cjs` | Six previously passing deterministic planner checks. |

The separate CEP panel currently calls `window.__adobe_cep__.evalScript` directly.
It does **not** expose the unified suite's typed `postMessage`/HTTP bridge contract.
No shared `/api/panel/templates` endpoint is claimed to exist. The suite owner
must decide the wrapper/action mapping; do not replace shared host adapters with
this standalone file or wire it into an unrelated motion-rendering tool.

## Planner and native payload contracts

`SLTemplateModel.plan(rows, options)` takes an explicitly ordered array. A row
contains the source path/name and a selected `comp`; inspected rows additionally
carry `folderId`, `comps`, missing-footage details and source stamps.

```json
{
  "action": "build",
  "name": "Documentary assembly",
  "rows": [
    {
      "path": "<absolute source AEP path>",
      "name": "<project filename>",
      "folderId": "<native AE imported-folder ID>",
      "sourceBytes": "<measured file length>",
      "sourceModified": "<measured modification time in milliseconds>",
      "comps": ["<all inspected composition records>"],
      "comp": {
        "id": "<native AE composition ID>",
        "name": "Main",
        "folder": "<imported composition folder path>",
        "duration": 40,
        "fps": 25,
        "width": 1920,
        "height": 1080,
        "pixelAspect": 1,
        "workAreaStart": 0,
        "workAreaDuration": 40
      }
    }
  ],
  "options": {"seconds": 600, "fps": 25, "workArea": false, "repeat": false}
}
```

The bracketed strings above describe types, not an executable fixture. Native
IDs and file stamps must come from real inspection; never fabricate them.

- `options.seconds` is seconds; the UI accepts minutes:seconds, and a bare UI
  number means minutes. Target range is 1–10,800 seconds.
- Omit `options.fps` to match the first selected composition. Target frames are
  `round(seconds * fps)`; each usable source span is floored to output frames.
  Thus exact duration means the nearest representable output frame. No time
  stretching or source frame-rate override is used.
- Output dimensions and pixel aspect follow the first composition. AE fits
  other compositions proportionally; mixed-size visuals need native checks.
- The returned plan has `fps`, `frames`, `duration`, dimensions, `unused`,
  `repeated`, and segments with `rowIndex`, `cycle`, `startFrame`, `endFrame`,
  `frames`, `sourceIn`, `trimmed`.
- Composition-name ranking is heuristic. `Main`, `Render`, `Final`, `Master`,
  render-queue membership and unused top-level compositions influence ranking;
  placeholders are penalized. Close/low-confidence choices stay unselected.
  Manual selection remains necessary; do not promise automatic correct choice
  for every Envato layout.

### AE native behavior

`SLTA.inspect({path})` imports the whole source AEP into a folder in the active
AE project, then returns actual composition metadata. Inspection therefore adds
native project items; it is not a side-effect-free file-header read. It does not
open/replace the source project or issue a project save. An in-session cache
checks an imported folder ID and marker before reuse.

`SLTA.buildAE(payload)` revalidates composition IDs and imported-folder ancestry,
then builds a separate master composition and source-comp layers. Layers use
explicit in/out points and source offsets. Preview resolution is quarter; source
animation speed and source project files remain unchanged. Repeats reference
the same source comps, so editing that comp affects all of its occurrences.

AE success replies are JSON strings containing `ok`, `host`, `name`, `compId`,
`plan`, native `layers` and `saved:false`. IDs belong to the inspected project;
they are not portable between AE projects. A unified bridge should additionally
guard its project/context identity before inspection and before build.

### Premiere native behavior and cache boundary

The panel's Premiere read path uses AE's saved catalogue. The native
`SLTA.dispatch({action:'inspect', ...})` in Premiere deliberately returns
`template_inspection_required`; it does not launch the AE interface.

`SLTA.buildPremiere(payload)` imports selected original AEP compositions by name
with `app.project.importAEComps`, into new bins. It uses
`ProjectItem.setScaleToFrameSize`, source in/out points, a new sequence seeded
with the first clip, sequence settings and sequential insertion. It checks the
actual sequence timebase and video-track placement bounds. Success reports
`sequenceId`, `plan`, native `clips` and `saved:false`.

This path is source-prepared, **not live-verified**. In particular, all audio
endpoints and the overall sequence end need separate inspection; current code's
placement receipt checks video track 0. Do not infer complete AV timing from it.

Premiere's import is name-based. Duplicate names within one source AEP stop with
a composition-choice error. Linked AEP compositions are not native Premiere
text/effect layers. They link to the original source AEP, not to later edits made
only inside an unrelated combined AE project.

### Catalogue and saved-list formats

- `SLTA.dispatch({action:'info'})` returns host/version, `ae` and the actual
  `catalogFolder`; use that folder rather than hard-coding a user profile.
- Catalogue location is `Documents\Storylens\template-assemblies`. File names
  use a 32-bit rolling hash (`h = (h * 31 + charCode) >>> 0`) of a lowercase,
  forward-slash-normalized absolute source path, encoded in hex plus `.json`.
  Entries include path, inspected comps, folder ID, missing footage, source
  byte length and modification milliseconds. Path/size/time checks reject stale
  entries; the current time tolerance is 1,500 ms. This is not a content hash.
- `assembly-<timestamp>.json` receipts share that directory. Do not treat every
  JSON there as a template entry or bulk-import the directory.
- Saved ordered lists are version 1: `name`, `options`, and ordered `files` with
  `path`, `compName`, `compFolder`. They do not contain portable AE item IDs.
  Loading requires reconnecting composition metadata. Preserve list order
  through that reconnect; do not sort it again by name or choose randomly.
- Native errors are JSON strings with `error:true`, `code`, `details`. The UI
  maps shared catalogue codes to plain-language messages and collapsible
  diagnostics. Integrators should retain original diagnostics separately.

## Existing evidence and its limits

All paths below are under `output/template-assembler-evidence`.

| Evidence | What it establishes |
| --- | --- |
| `native-ae-inspection.json` | Two real AEP imports, actual comp metadata and unchanged original project path. Slideshow required manual choice; Main was identified. |
| `native-ae-build.json` | Initial successful native assembly receipt; some label encoding was corrected later. |
| `native-ae-final.json` | Final 600-second AE composition, 24 fps, 14,400 frames, 27 consecutive placements; final placement 598–600 seconds. Mixed-size scales 100% and 200%. No save issued by this feature. |
| `native-600-second-timeline.jpg` | Actual AE timeline screenshot; not a generated success mockup. |
| `native-errors.json` | Short-list and unreadable/empty-project calls stopped; project item count remained 537. |
| `final-source-review.json` | Validation gaps and two preserved unresolved findings. |
| `delivery.json` | Historical standalone pass; explicitly false Premiere-live and CEP-loaded flags. Its old live-window description is superseded by current coordination. |
| `Storylens-Template-Assembler-20261025.zip` | Earlier source package. Historical SHA256 in delivery receipt is `46b3e7e30ecaaeece7b4e23d312f614487fb4220c2319ffedb02855692a266de`; suite owner should establish current source/package parity before any future installation. |

The native pass used the **ScriptUI fallback and real host calls**, not the
dockable CEP panel. It was a two-template repeated-list slice, not all ten ranked
templates or every source project. No render-quality, uninterrupted playback,
save/reopen persistence, local-model improvement or Premiere success is implied.
The six historical planner checks are supplementary evidence and were not rerun
in this read/plan update.

## Outstanding checks and preserved findings

1. Dockable panel discovery/loading and real panel-to-host replies remain
   unverified. During the earlier AE session, Extensions showed only its prior
   Flex GUI Pro entry; no restart of the unsaved project was performed.
2. Native Save ordered list / Load ordered list dialogs, rank/choice restoration
   and current-context reconnect need a real roundtrip.
3. Premiere Dynamic Link import, sequence settings, source fps conversion,
   proportional sizing, video and audio endpoints and editability remain pending.
4. Native project save/reopen checks require an explicitly approved scratch
   project path and owner-controlled host lifecycle.
5. Source fonts, plugins and expressions were not repaired. A missing-font notice
   occurred; the owner's earlier expression-error banner remained. Do not equate
   these template prerequisites with an assembler render-quality pass.

Do not repair these recorded findings without a new scoped authorization:

- Malformed saved-list JSON with `version:1` and valid `files` but missing
  `options` can replace the in-memory rows before its error appears. This was a
  source-review finding; saved files are not deleted. Keep malformed inputs
  out of the owner's real list until an isolated approved recovery check.
- The zero-length/unreadable `Light Leaks.aep` probe returned the generic native
  error rather than the intended empty-file-specific message. Native item count
  stayed unchanged. Preserve the original receipt and source file.

## Safe fixtures and the next bounded native check

### Fixtures already available

Use the two previously inspected sources read-only; do not rename or overwrite:

1. `A:\Editing\AE documentry style editing templates\envato doc\Upload\Project\Historical_Documentary_v6.aep`
   — `Slideshow`, 32 seconds, 24 fps, 3840×2160.
2. `A:\Editing\AE documentry style editing templates\envato doc\The Fog of History Logo\The Fog of History Logo.aep`
   — `Main`, 14.04 seconds, 25 fps, 1920×1080.

At 24 output fps, the usable second span is 14 seconds. A **40-second** target
without repeats should place Slideshow at 0–32 and Main at 32–40. Reversing the
rank should place Main at 0–14 and Slideshow at 14–40. These are expected fixture
results, not new native passes. Six planner tests also contain synthetic
40/50/520/90-second records; they are metadata fixtures, not saved AEPs.

Do not rerun `tools/validate_template_assembler.jsx`,
`tools/build_template_assembler_native_check.jsx` or
`tools/verify_template_assembler_native_result.jsx` blindly. They import/add native
items, depend on session globals, and the last helper targets historical comp ID
6321. They are evidence-producing development helpers, not safe universal tests.

### Next check while Premiere is reserved/open

The suite owner can allocate one short **panel/load-list/cache-read** check in
Premiere. It should open only the dockable panel, establish the host reply, load
a valid two-row ordered list, read current cached metadata and confirm rank,
selected names and the 40-second plan. **Do not press Build yet**; no Dynamic
Link import, AE interface launch, rendering or project save belongs to this first
check. If catalogue entries are stale or the panel is absent, record that blocker
and stop rather than opening AE or restarting Premiere independently.

Owner action needed: the suite owner must explicitly reserve the Premiere UI
window and choose an appropriate scratch/current-project context. Any required
Premiere restart must be coordinated with the human after they preserve their
work. This thread takes no UI action under the current read/plan instruction.

### Following checks, in order

- After the suite owner coordinates closing Premiere and opening AE: validate
  docked AE panel loading, the native save/load roundtrip, and one 40-second
  two-template assembly in a scratch project. Record actual bounds and ensure
  the list's manual choice and rank survive; no video render is needed.
- After AE metadata is fresh and its interface is closed under a coordinated
  switch back to Premiere: validate the same 40-second Dynamic Link assembly,
  actual video/audio ends, size fitting and a later approved save/reopen.
- Only then expand to the owner's ranked 1–10 set and the 10-minute target.
  Keep full-source durations, optional ordered repetition and last-item trim.

## Dependency handoff to the suite owner

This feature supplies existing payload/receipt shapes, the pure planner, native
AE/PP implementation and saved evidence. The suite owner owns deciding how the
shared panel exposes it, loading its namespace without collisions, project/context
guards, source/cache validation, shared error presentation, version compatibility,
packaging and eventual host tests. The standalone extension remains available;
no integration/removal/migration was performed in this update.

Do not present the AE 600-second receipt as the missing docked-panel or Premiere
verification. Preserve the current findings and originals when scheduling the
next bounded check.

## Separate potential assignment: per-channel replenishment plan only

This section answers the coordinator's later planning request. It does not
transfer publishing ownership or authorize implementation. No publishing code,
database, campaign state, credentials, worker, scheduler, browser or remote
service was touched. Only source text was read. The template assembler is not
being expanded into a gaming editor or publishing pipeline.

### Source observations

Inspected source text: `hinglish_publish/store.py`, relevant portions of
`hinglish_publish/campaign.py`, `hinglish_publish/campaign_boundaries.py`,
`hinglish_app/publishing_times.py`, `hinglish_niche/profiles.py`, and matching
account/recovery declarations in `service.py`, `providers.py`, `local_browser.py`
and publishing test sources. No stored account credentials or live profile
configuration was opened, and no imported application object was constructed.

| Existing component | Observed boundary relevant to the proposal |
| --- | --- |
| `Store.add_batch` | Uses `BEGIN IMMEDIATE`, draft jobs and existing-identity reuse. Identity is file fingerprint + platform + optional non-general profile; actual account ID is absent. Short-slot allocation uses a profile-wide last due time and one fixed clock. It is not yet a per-account, varying-minute append contract. |
| `Store.claim` | Claims ready work; YouTube may be claimed ahead of its public release time. Do not confuse pre-upload eligibility with the public release date. |
| `Store.recover` | Converts uploading work to needs-review rather than repeating an uncertain upload. Preserve that safety boundary. |
| `campaign.prepare` / `campaign.slots` | Existing cricket-oriented workflow, fixed daily clock, source selection/transcription/short preparation. It does not establish the requested gaming stream → one completed highlights edit → N selected shorts lineage. Even `plan_only=True` still enters GPU/model/transcription paths and writes campaign state; it is not safe to call for this read/plan assignment. |
| `publishing_times.window` / `choose` | Existing configurable release window, preservation of explicit clocks/match-saved instructions, one-time minute choice, retry reuse and durable `release-times.json`. `choose` writes a file; do not call it as a read-only probe. Its caller-supplied key/folder must include the full destination partition to avoid conflating accounts. The shown lock is process-local. |
| `profiles.valid_profile` / `account_key` | Current profile vocabulary is general/cricket/gaming. Account aliases are platform plus profile. An alias is not a verified remote channel/account ID and cannot serve alone as the queue partition. |
| Provider/browser guards | Source code checks actual destination against the job, retains remote IDs/checkpoints, and uses needs-review/reconciliation for uncertain submissions. Browser Reel bindings currently use account handles in several paths; stable remote-ID resolution remains a dependency, not an invented capability. |

`Store(root)` itself creates schema/directories, `recover()` mutates state, and
constructing a publisher can engage application behavior. None was executed.

### One bounded module contract for later ownership approval

Proposed isolated files, **not created**:

- `hinglish_publish/channel_queue_plan.py`: pure planning/validation, no I/O,
  provider/client imports, rendering, account switching or worker startup.
- `tests/test_channel_queue_plan.py`: in-memory snapshots, fixed clocks and
  injected deterministic time-choice fixtures; no database or network access.

Suggested entry point:
`propose_replenishment(snapshot, finished_candidates, selection, destination, policy, now, slot_choices)`.

It returns an append-only proposal with new logical entries/delivery specs,
existing-entry matches, blocked candidates, proposed release instants and commit
preconditions. It does not enqueue or authorize anything. A later publishing-owner
adapter must commit an accepted proposal to the **existing canonical store**.
Do not create a second queue database, competing JSON queue or new scheduler.

Inputs must freeze these identities:

| Input | Required meaning |
| --- | --- |
| `profile_id` | Immutable per-request creator profile, validated against the existing profile vocabulary; never inferred from whichever profile is currently selected in the UI. |
| `platform` | Explicit supported platform for each delivery. |
| `account_id` | Verified stable YouTube channel ID or Instagram account ID, supplied by the publishing owner's account preflight; display names/handles alone are insufficient. Missing/ambiguous IDs block commit. |
| `connection_ref` | Opaque existing connection/binding reference; no access token, password or credential body in queue plans. Rebinding never silently retargets saved entries. |
| `batch_id`, `request_id`, `revision` | Durable replenishment identity, idempotent retry key and expected snapshot revision; ownership of their persistence belongs to the canonical publishing writer. |
| `selected_short_ids`, `requested_n` | The exact user-selected set; require unique valid IDs and cardinality N. No extra selection, generation or filler clips. |
| `finished_candidates` | Existing finished media descriptors: asset ID, content hash, approved completion state, highlights parent ID/version, original-source lineage and validated source moments. |
| `snapshot` | Existing jobs, reserved dates, status, authorization/remote-submission evidence and receipts, including earlier weeks and uncertain work. No secrets. |
| `policy` | Canonical timezone `Asia/Kolkata`, daily cap 1, release window 17:00–21:00 local, explicit start rule, approved missed-slot rule and authorized destinations. Explicit user clock/match-saved instructions remain higher priority. |

Logical partition is `(profile_id, platform, account_id)`. A second occupancy
constraint on `(platform, account_id, local_date)` prevents two profiles bound
to the **same actual destination** from each scheduling a separate daily short.
Different channels remain independent. This separates editorial provenance from
the real destination's one-per-day limit.

N counts distinct selected shorts, not platform deliveries. Selecting N shorts
for two explicitly authorized platforms can produce up to 2N delivery entries,
each with its own partition and receipt. It must not silently double the user's
requested media count or add a long-video publication.

### Source lineage and duplicate rules

The upstream gaming contract is exactly:
**one ~3-hour source → one completed ~15-minute highlights edit → N selected
shorts from that finished edit**. This queue planner consumes the final manifests;
it does not choose highlights, transcribe the stream, render, or cut more shorts.
The highlight owner must supply the mapping from each short's highlights-time
pieces back to root-source moments. A missing/invalid mapping is an explicit
`lineage_unverified` blocker for source-moment deduplication, not permission to
claim deduplication worked.

Proposed duplicate evidence:

1. Full file SHA256 identifies exact media, independent of filename/path.
2. A canonical root-source ID/content hash plus ordered frame-based source
   intervals identifies the same moments after re-encoding or moving a file.
   Preserve source timebase/remap provenance; do not compare unrelated stream
   seconds as if they belonged to one source.
3. Exact matches already queued/submitted/scheduled/published/uncertain for the
   same destination reuse the existing reference; do not mint another job.
   Default destination dedup also catches a duplicate submitted under another
   editorial profile mapped to that same account.
4. Partial/near-overlap is a `potential_duplicate` review result under an
   explicit owner-approved rule, not silent deletion or an invented fuzzy match.
5. Posting the same selected short to a different explicitly authorized platform
   or account is a separate delivery, not automatically a duplicate there.

An append receipt should separate `selected_n`, `new_n`, `already_present_n`,
`blocked_n` and per-platform delivery counts. If two of seven selected shorts
already exist, report that fact and five new entries; never secretly generate
two replacements or say seven new jobs were created.

### Daily window, persistence and weekly appends

- Calendar dates and the one-per-day cap are evaluated in `Asia/Kolkata`;
  persist both the canonical zone/local date and exact aware UTC/offset instant.
  The 17:00 and 21:00 endpoints are allowed, subject to a preparation lead time.
- Allocate new entries after existing destination reservations and the latest
  reserved release date. Include earlier-week jobs, drafts with retained intent,
  scheduled remote receipts and uncertain submissions. Never shift existing due
  times to squeeze a weekly batch into the calendar.
- A local `cancelled` label alone does not prove an uncertain remote post was
  cancelled. Release its occupied slot only after the publishing owner's
  explicit cancellation/remote-reconciliation policy confirms it is safe.
- Each new day's minute varies within the window and is selected once, then
  persisted before the entry can become executable. Retries/restarts must reuse
  the saved instant; they must not reroll because the process restarted or the
  latest `now` changed. Prefer a different minute from adjacent planned days
  while valid choices exist; this is variation, not an engagement claim.
- Reuse the existing `publishing_times` policy/choice behavior through an
  owner-controlled adapter. The pure planner accepts existing/injected choices;
  it must not call the disk-writing helper. The adapter's key and storage scope
  must include profile, platform and verified account ID. Cross-process append
  coordination cannot rely on the helper's process-local lock alone.
- On the same day, choose only a future minute with the existing helper's
  preparation allowance (currently at least two minutes). If no valid minute
  remains before 21:00, propose the next free local day; do not release now.
- Repeating the same weekly request returns the existing batch/entry references
  and previously saved minutes. A new week's accepted batch appends after the
  old tail and preserves every old ID, due instant, job status and receipt.
- Do not implement this by calling today's `Store.add_batch` and then patching
  returned due dates: its identity omits actual account ID, its slot scope is
  broader, and a returned ID may be an existing job. A publishing-owner-approved
  atomic append API is required before this proposal can be committed safely.

### Commit and restart safety requirements for the owner adapter

The pure output should include a snapshot/revision precondition and stable
proposal/request identity. The future canonical writer must recheck partition,
account binding, source identity, destination-day occupancy and duplicates under
one transaction/serialization boundary, then append all accepted entries and
their exact release times or append none. Concurrent weekly requests using a
stale snapshot must replan, not overwrite one another. Schema/index/commit
changes remain publishing-owner work and are not authorized here.

The logical replenishment queue should expose existing execution jobs rather
than replace their state machine. Proposed actions include:

| Situation | Safe planning/action boundary |
| --- | --- |
| Draft/unapproved | Reserve/report planned intent; never treat the entry as upload authorization. |
| Ready + future public release | Preserve `release_at`. Eligibility to pre-upload is platform/authorization-specific; YouTube can prepare privately ahead of its release date. |
| Restart after a provably unsubmitted interruption | Reuse the same job, source identity and saved slot; the execution owner decides whether the unfinished stage is safely resumable. |
| Upload/submission started, outcome unknown | Keep `needs_review`/reconcile action and reserve the slot. No second upload, new destination, new ID or reschedule based merely on a timeout. |
| Remote ID/receipt exists | Reconcile/read the remote object first and preserve it. A local queue row is not proof of a remote schedule or publication. |
| Known scheduled/published | Preserve receipt and original exact schedule; the replenishment operation appends around it. |
| Missed slot, clearly unsubmitted | Produce a missed-slot/reschedule proposal. Move it only if an explicit standing missed-slot policy authorizes that change; otherwise block for review. No catch-up burst, midnight posting or cascade shift of existing weeks. |
| Account mismatch/reconnection | Block that delivery. Do not default to general, use a currently active account or relabel old jobs. |

New local status/proposal names above are **conceptual**. Do not write them into
the existing execution store without the publishing owner's mapping to current
states and receipt rules. This plan authorizes no real publication, including
private staging uploads, browser Share/Submit, account changes or scheduling.

### Bounded test plan for a later isolated implementation

Tests should pass only in-memory data, a fixed aware `now` and injected saved
minute choices. They must fail if a provider/network/client/worker/credential
lookup or file/database write is attempted by the planner.

1. Two accounts with the same profile/platform get independent queues and tails.
2. Gaming/cricket destinations cannot bleed into each other; two profiles bound
   to one actual account share its destination-day occupancy constraint.
3. Exact N selection is enforced; two platforms create separate deliveries for
   the same N media; duplicate selections do not create replacement shorts.
4. A weekly append leaves an earlier snapshot's IDs, times and receipts byte-for-
   byte equivalent; replay of the same request adds nothing.
5. Exact media hash and the same remapped source moments deduplicate across new
   filenames/re-encodes; near overlaps return review evidence, not silent removal.
6. All new slots are one/day, aware and within 17:00–21:00 Kolkata; variations are
   persisted/reused. Test boundary instants, late-day overflow and UTC conversion.
7. Restart preserves assigned times. Missed-unsubmitted and uncertain-submitted
   cases produce different explicit actions; neither creates a duplicate upload.
8. Published/remote-scheduled/uncertain/cancelled-but-unreconciled entries retain
   receipts and conservative reservations. Rebinding blocks instead of retargeting.
9. Competing proposals with the same snapshot carry detectable stale preconditions;
   the owner adapter must later prove actual transactional behavior separately.
10. Incomplete highlights, invalid source remaps and unavailable stable account IDs
    stop before any executable proposal; the planner never invokes
    `campaign.prepare(plan_only=True)` as a shortcut.

These are planned tests, not tests written or passed. A pure planner pass would
not establish the canonical commit, browser scheduling or remote receipt path.

### Ownership/action gate

No implementation starts until the suite/publishing owner explicitly assigns
the new module/tests and owns the commit/schema integration. The owner must
provide a credential-free account-binding snapshot, a completed highlights/shorts
manifest with original-source remaps, exact user-selected N/destinations and
the missed-slot policy. These are interface dependencies, not a request to access
credentials or launch source-generation/publishing work overnight.

The next publishing step is owner review of this isolated pure-planner contract.
It does not require Adobe, a GPU, a live database, a worker or a remote action.

## Later bounded Beat + Cinematic component assignment

The coordinator subsequently assigned only `hinglish_beats/detect.py`,
`hinglish_cinematic/planner.py` and dedicated component tests/docs. This does not
transfer shared UI/service/render/native ownership or publishing implementation.
The scoped work is now documented in
`docs/beat-cinematic-component-2026-10-25.md`. The beat detector stayed unchanged;
the existing planner received test-demonstrated beat-path, source-identity,
measured-quality and music-bound repairs. Final isolated result: 33 tests passed
in 3.720 seconds, with a saved synthetic 50-second/10-shot plan under
`tests/fixtures/beat_cinematic_component/golden_50s_10shots.json`.

This checkpoint used no Adobe, model, GPU, video encoding, online asset or
render/service job. Native/render acceptance remains the suite owner's handoff.
The earlier template and publishing findings remain recorded and unmodified.
