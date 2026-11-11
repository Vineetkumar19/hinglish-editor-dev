# B-roll producer → typed candidate bank — 25 October 2026

## Status and ownership

**Producer integration passes component checks. Genuine local-agent and native
acceptance remain pending.** No live request was submitted in this stage.

Before editing, the coordinator's task map reserved `hinglish_broll/` and its
dedicated tests to this owner. `pipeline.py`, `conform.py` and `verify.py` matched
the previous feature baseline; the original 35-test file and golden fixtures
also matched. No competing feature-file change was observed. The explicit
producer-integration release superseded the older map's read/plan-only row.
The coordinator-owned task map was read, not edited.

Changes are confined to the B-roll feature, dedicated tests and this evidence:

- `hinglish_broll/pipeline.py`: source/preview check wiring, exact interval
  quantization, source-bound prepared cache identity, option packing and typed
  manifest finalization.
- `hinglish_broll/producer_contract.py`: snapshots, deterministic check
  provenance, paired receipt binding and finalization helpers.
- `hinglish_broll/candidate_manifest.py` and `candidate_selection.py`: optional
  source/prepared receipt references and their validation; the original v1
  golden fixtures remain unchanged.
- `tests/test_broll_producer_manifest.py`: explicit CPU/component fixtures.

No shared panel/server/host adapter, installer, packaging, catalog, publishing
file or protected final-review finding was edited. `conform.py`, `verify.py` and
the local planner implementation remain unchanged. No job/service restart,
stock/search call, model inference, GPU job, media render or Adobe action ran.
The existing interrupted job and source files were preserved.

## Actual producer path

For normal **review-options** B-roll generation:

1. Existing local planning/ranking chooses candidates. The producer does not
   invent keywords, source choices or positive Vision answers. Full creator
   guidance and the existing configured local LLM/Vision route stay in place.
2. The chosen original interval is aligned to the exact sequence-frame grid
   **before** its actual checker call. The interval checked is the one prepared,
   rather than a nearby unquantized time.
3. Original bytes are streamed into a fingerprint and guarded against changes.
   The actual source crop is calculated with the same centered crop function
   used by the existing checker/conformation path.
4. The existing local checker evaluates the source. Its real flags are copied
   unchanged; bookkeeping adds candidate ID, `producer_stage=original`, file
   identity, exact interval and crop. A failed/malformed three-frame review does
   not become a successful receipt. Existing bounded blur-window handling stays.
5. Only a passing source check proceeds to normal preparation. The prepared
   cache name includes the source content hash so a changed source path cannot
   silently reuse the former preparation. No old file is deleted or overwritten
   to manufacture success.
6. The actual encoded preview is fingerprinted and its canvas/rate verified.
   The same configured local checker evaluates its active prepared interval.
   This is a real second checker call in production, not a controller-created
   success flag. It is recorded as `producer_stage=prepared`.
7. Both snapshots must remain stable. `checked_window_receipt` binds the actual
   original/prepared hashes, source crop/window and prepared verdict. The
   paired producer record also stores original/prepared verdict hashes. A
   source or preview mutation, failed check or missing evidence aborts that
   option; no image/text substitute is produced.
8. Ordinary option packing retains `source_path`, `original_offset`, prepared
   `source_in/source_duration`, canvas and `checked_window`. IDs cannot be
   relabelled onto another candidate's receipt.
9. Ordinary `write_outputs` saves the project, then finalizes
   **`BROLL_CANDIDATES.v1.json`**. The typed manifest contains both original and
   prepared `producer_checks` JSON-pointer/hash references. Selection validation
   checks these records again, not only the final positive preview verdict.

The receipt records actual checker outputs; it does not prove every frame or
uncached inference. Upstream cache-hit/model-version lineage is still not fully
exposed by the checker. The saved `judge` and exact verdict references are kept;
no unknown provider/version/cache fact is invented. Actual acceptance must log
that lineage and verify the configured local brain as described in the earlier
contract audit.

Source and prepared Vision checks add work. The component duration below is not
a prediction of laptop inference, search or rendering time. Measure the actual
serialized workflow before drawing performance conclusions.

## Choices, unsupported state and existing artifacts

`finalize_candidate_bank(project_file, *, content_format=None, media_reader=None)`
is now exported from the feature pipeline. It writes the new candidate manifest
and reads an existing `BROLL_OWNER_SELECTIONS.v1.json` if one exists. It does not
create an owner-decision sidecar merely because generation finished.

Fresh typed choices remain **unselected**. Existing legacy `chosen/clip` fields
may still describe a machine-suggested preview; they are not promoted to owner
decisions. Shared/native integration must consume the typed explicit-selection
route, not treat a legacy preview or whole-result import as user approval.

The finalizer uses an explicit argument, then saved `content_format`/profile,
then the existing short/long duration distinction. Long-form caps are two;
short-form caps are five. The shared suite still needs to propagate an explicit
panel format where it differs from a saved profile; that shared change is not
made here. The known 35.7-second short source resolves to short form normally.

No-match and incomplete banks remain explicit, including unstarted recovery-plan
slots. Legacy unbound options are never backfilled with successful receipts.
Reading/finalizing a bank does not resume its worker or rewrite its collection
status. Receipt data is checkpointed per new option; the full typed artifact is
written during finalization. The existing reader can inspect a saved partial
bank without launching its job.

Legacy placement-quality diagnostics and review/native consumers remain separate
from candidate-bank readiness. They were not altered to hide a lack of matches
or to equate a suggestion with an owner-selected insertion. Shared UI and native
planned-time receipt work remain suite-owned.

## TDD evidence — component only

The initial producer tests reproduced one check instead of two, no typed
finalizer/option hook, continued preparation after a source mutation, and a
passing source incorrectly surviving a failed prepared check. A later targeted
RED test reproduced option identity relabelling. All are retained as regression
checks.

Final recorded checks:

```text
tests.test_broll_producer_manifest
tests.test_broll_candidate_manifest
tests.test_broll_editable.EditableBrollTests.test_conform_retains_leading_and_trailing_handles
```

**52 tests passed, 0 failures/errors, 2.919 seconds.** That includes 16 new
producer component tests, the original 35-test contract/golden suite and one
relevant legacy CPU/mock regression. Model calls and conformation/preview work
are explicit mocks over synthetic byte/metadata fixtures. This is not a local
model or live application result.

Evidence is in `docs/broll-producer-integration-evidence-2026-10-25/`:

- `validation.json` and `unit-tests.txt`: exact checks, source hashes and limits.
- `untouched-runtime-files.json`: conform/checker/planner baseline matches.
- `normal-app-short-payload.json`: the next **unsubmitted** normal request.

The original 35-test source and all three golden files are byte-for-byte
unchanged. Before/after hashes also match for old job `c1145994598a`, its marker,
recovery journal and partial project. The interrupted “only two apartment clips”
record is still unverified; no status was rewritten and no prior failed result
was reclassified as completed.

## Exact next normal short workflow — suite release required

Do **not** start this until the suite releases serialized heavy resources. Never
stop another job or open a second Adobe host to accelerate it. Use the normal
Storylens request path and preserve the application's full creator context;
do not supply model JSON, manually selected footage or canned success answers.

The known source is:

`A:\Full Drive\thisis.vineet\e2\e2(1).mp4`

Earlier read-only inspection recorded 46,011,692 bytes and SHA256
`a47789ede6d5ed07c752bdf7ecd974baefb176af8c12d73aa435e81bbe9f9a9c`,
1080×1920, 30 fps, 35.711995-second original / 35.7-second sequence. Reconfirm
availability before the authorized run; this stage did not re-analyze the video.

Use the payload saved with the evidence, whose essential normal fields are:

```json
{
  "mode": "broll",
  "profile": "general",
  "input_path": "A:\\Full Drive\\thisis.vineet\\e2\\e2(1).mp4",
  "source_paths": [],
  "script": "",
  "format": "source",
  "device": "cuda",
  "density": "medium",
  "preview": true,
  "broll_review_options": true,
  "broll_options_per_moment": 5,
  "broll_count": 10,
  "broll_black_background": true,
  "broll_brief": "Collect relevant video-only choices for the important spoken moments. Preserve the spoken meaning. Leave insertion to my explicit selection; do not substitute images or text."
}
```

These are workflow constraints, not creative answers. Actual speech must drive
the local model's terms and source choices. Audio-over-black avoids crediting
the already-edited source's existing pictures as newly discovered footage.
Its explicit black/brief settings differ from the interrupted blank-brief request;
the suite must still check for duplicates before submitting. Do not restart or
rewrite the old job to make this new test appear complete.

Verify actual model/provider/version, each source and prepared check, crop/time
mapping, cache lineage, retries/interventions, coverage/no-match states, final
artifact and low-resolution full playback. A current stock credential failure
must remain visible; no new provider-key probe was made here. Do not count a
cached or mocked decision as fresh local reasoning. The suite must then exercise
one explicit owner choice through its native insertion adapter and obtain the
actual host receipt. A source/preview check alone is not that receipt.

The genuine local-model short run, subsequent approved long-form benchmark and
Premiere timed insertion remain **pending**. No Codex-free runtime guarantee or
zero-breakage claim is made from component tests.

## Read-only actual-run audit — 25 October 2026

The suite subsequently started production job `7c03db6fbd88`, output
`output/broll/20261025-044757-2498b9`. This audit read existing job files, code,
cache metadata and two existing prepared thumbnails only. It did not start
inference, network requests, rendering, another job or an Adobe host, or change
the running job. No semantic repairs were applied during the suite's run.
The machine-readable partial snapshot is
`broll-producer-integration-evidence-2026-10-25/runtime-semantic-audit.json`.

### Retry and meaning findings

Keyword discovery made three guard attempts, each with five negative-phrase
violations. `keywords.discover.check` searches `str(row)`, which includes the
explanatory `meaning`, not only the actual search terms. Five rows use wording
such as “lack of” in that explanation. The deterministic repair concatenates
all three attempts, normalizes keywords/queries and retains those meanings.
Consequently `final_hard=15` is a **current post-repair checker count over
duplicate rows**, not fifteen distinct invalid searches in the final plan.
The guard return is ignored and the function builds slots from attempted answers.
All ten persisted visual/query sets avoid the negative regex; five persisted
meanings still trigger it. This is neither a clean guard pass nor proof that
fifteen final searches are invalid. It is an unfixed checker/receipt inconsistency
that also caused redundant planning attempts.

The exact ten saved subjects, in timestamp order, are Indian city street,
apartment interior, room interior, bed, wardrobe, water heater, kitchen pan,
refrigerator, washing machine and room interior. Full quotes, queries and times
are in the audit JSON. The opening street is an establishing interpretation,
not a noun in its timed opening quote. Bachelor is mapped to a room in a phrase
containing unclear “party mein”; “pan” remains a possible ASR ambiguity, not an
auditor-confirmed correction. The clear “chaar divaaren” phrase has no empty-room
slot. These require semantic acceptance, rather than manual replacement answers.

An actual apartment rejection describes a living room with sofa, coffee table
and wall art but rejects it because apartment interior is not identifiable.
This is a visible inconsistency in the stored model judgment. Generic interiors
still receive rental/absence narrative, unlike the canonical physical-object
branch. Its video was not independently inspected, so this audit does not
automatically approve that candidate or weaken the actual quality checks.

### Actual progress and candidate bindings

At the saved observation the job was running at 70%, checking bed candidate2/9.
The street slot had four saved options from twelve checked candidates; apartment
had zero after six rejections; the bachelor/room slot had zero after ten.
The fourth slot was still collecting. The remaining six planned slots were
not yet saved in the project. Five is a cap, not a claim of five qualified
choices for every subject. No final typed bank, preview or export XML existed
at this observation. `collection_complete=true` on an individual slot means
its search budget ended, not that it has five options or the whole job passed.

All four saved choices have successful original/prepared checker records.
Read-only SHA256 verification matched both actual media files and both paired
verdict digests to their checked-window receipts. This establishes byte/window
binding for those four options, not independent semantic correctness. Existing
thumbnail inspection showed a road/traffic shot and a crowded outdoor square;
single thumbnails do not establish full playback, exact location or native
timed insertion. The last observed job is partial, not a completed acceptance.

### Corrected runtime and freshness account

The actual primary planner route is `pipeline -> hinglish_visuals.brain.open_brain
-> OllamaBrain`, caching under `cache/visuals/brain`. The earlier route audit's
description of `hinglish_broll.llm.LocalLLM` describes the available local
fallback, **not an established execution path for this job**. The default
configured planner is `storylens-meaning:14b`; original/prepared checks name
`storylens-planner:9b-q6`. The suite's request receipt records loopback Ollama
0.40.5 and installed tag digests. That inventory is not per-call proof of the
loaded digest, inference freshness or a particular cache hit.

Both primary planning and Vision cache keys include model tags and request
content but omit the active weight digest/provider version. Primary planning
sets transient `last_usage.cache_hit`; this job does not persist a per-call
receipt for it. Two keyword answer cache files created within the run have
identical answer hashes; that supports fresh writes, not a complete call-level
lineage. Vision receipts bind actual checked media and verdicts but do not say
whether their model answers came from fresh inference or cache. Fresh/reused
inference must remain unknown where the record does not establish it.

The log explicitly reports reuse of the completed transcript, forty previously
verified internet videos as retrieval leads, and nineteen candidate pictures.
Those are legitimate reuse, not fresh ASR/discovery claims. Pexels rejected the
saved credential and was skipped in this run. The auditor made no new key probe.
`recovery_attempts=1` is recorded; the count alone does not establish why or who
restarted a worker. Codex supplied workflow constraints at submission, not
creative model answers. Direct `/api/jobs` execution does not by itself validate
the normal chat assistant's tool/argument selection.

Only submit-to-observation elapsed and the suite's sampled stages are available;
exact phase/model-call durations are unknown. See
`output/plugin-validation/broll-runtime-observations.json`. Current reliability,
final playable result, normal assistant orchestration and native manual-choice
insertion remain **unverified**. This audit identifies concrete repair targets;
it does not silently fix them or reclassify this active run as successful.

## Test-only keyword guard reproductions — 25 October 2026

Following the suite's bounded instruction, a collision check found no existing
`tests/test_broll_keyword_guard_regression.py` or its dedicated fixture folder.
Only that new test module, `tests/fixtures/broll-keyword-guard/` and this evidence
were added. Product files, shared evaluator, current source/job and actual model
answers were not modified. No network, model, GPU, render or native action ran.

The dedicated six-test execution completed in **0.267 seconds: four passed,
two expected behavioral failures, zero errors**. This is an initial failing
integration/TDD reproduction, not successful implementation or live acceptance.
Output: `broll-producer-integration-evidence-2026-10-25/keyword-guard-red-tests.txt`.
An initial harness run could not write to the system temporary directory; the
test harness was corrected to use a verified workspace test-only temporary root
before this meaningful behavioral result. No product permission change was made.

- Valid physical wardrobe search, with the observed absence explanation kept:
  expected one call; actual three. This reproduces the unnecessary retry.
- Stubborn actual negative search followed by deterministic physical repair:
  expected the final receipt to validate the resulting physical search while
  retaining historical failures under `tries`; actual `final_hard=3` duplicates
  stale explanation violations, although the output contains one physical slot.
- Controls passed: actual negative **keyword** prompts a correction; actual
  negative **query** still prompts a correction even with a physical keyword;
  physical “closed shops” stays allowed; copied raw model bytes retain their hash.

The raw cached answer is copied verbatim with SHA256
`0a5af4e21e4cc43aef153ccaae33c8239ccbdf933f047594aef281bd6e450d4a`.
Its provenance document states the unresolved exact attempt/digest lineage.
The wardrobe test explicitly copies one row, replaces its search fields with
physical terms and uses a test-local word index; it does not relabel the raw
answer. Other scripted responses are synthetic inputs to the real guard, not
claimed successful local-model results or footage selections.

### Minimum proposed post-terminal product lease (not granted/executed here)

Request **`hinglish_broll/keywords.py` only**, plus this dedicated regression
module/fixtures and scoped evidence. Do not edit `hinglish_eval/guard.py` or the
shared evaluator. Bound the initial fix to validating the actual keyword/query
search fields instead of explanatory meaning, retaining genuine negative-search
correction, and producing an honest post-normalization final result without
duplicate stale violations. Preserve raw attempt history, creator context,
word anchors, legitimate discoveries from retries and all footage judgments.
Wait for the active job to become terminal and the suite to release this lease;
do not hot-patch it while collecting. Re-run the six tests and affected keyword
checks, then let the suite perform one serialized real application validation.

History check: AGENTS.md's standing final-adversarial protection applies to
findings from that review. Searches of the B-roll handoff/review artifacts found
these exact two defects first recorded in this initial live-run audit, with no
matching protected final-adversarial classification found. This is bounded
history evidence, not permission to repair unrelated protected findings. No
repair has been performed, and a contrary owner history must stop the proposal.

Separate provenance proposal, not included in this lease: the suite should bind
each planner/check receipt to cache hit/miss, cache key, effective model tag,
active digest/provider version and bounded timing when actually available.
Preserve “unknown” for legacy records and any unobservable execution details;
never backfill a cached verdict as fresh inference. This touches shared runtime
code and requires a separate suite-owned design/lease. The inconsistent generic
interior judgment also remains an observed semantic issue, not manually overridden
or fixed by these test-only changes.

## Initial terminal failure repair — 25 October 2026

The suite reported job `7c03db6fbd88` terminal failed, with built-in recovery
also failed (`recovery_attempts=2`, no result). Persisted logs show the same
`'str' object has no attribute 'get'` in the original run and recovery. They
do not contain the original Python stack; the exact stack was reproduced in
isolated tests through the actual `pipeline.write_outputs ->
producer_contract.finalize_candidate_bank` path. The producer serializes
`profile.name` as the string `short`; finalization incorrectly called
`project.get('profile', {}).get('name')`. The earlier component fixture used
a dictionary profile, missing the production representation.

After the terminal notice, a collision/hash check confirmed both proposed
product files unchanged since the read-only audit. Under the suite's explicit
initial-repair lease, changes are limited to:

- `hinglish_broll/producer_contract.py`: read a string profile or legacy
  dictionary profile, honor explicit content format, retain duration fallback
  when absent, and retain the typed format validator for unknown values.
- `hinglish_broll/keywords.py`: validate negative search wording in the actual
  keyword/queries, excluding explanatory meaning. Genuine negative searches
  still require correction; historical violations stay under attempts, while
  successful physical repair no longer reports duplicated explanation errors.

No source, recovery/job/project/status, actual model answer, shared evaluator,
host adapter or protected final-adversarial finding was edited. No job was
restarted, and no model/network/GPU/render/native operation ran in this repair.

### TDD and bounded checks

The new `tests/test_broll_profile_finalization_regression.py` first reproduced
the exact AttributeError for short/long strings and the real output-writing
boundary (mocked media/host boundaries). Its final red run was four tests,
three error outcomes including subtests, 0.166s. Legacy dictionary and absent/
explicit format controls passed. It now verifies repeat finalization produces
the same bank and never creates owner approval or overwrites its source project.

The earlier six keyword tests were red before product changes. After both
minimal fixes, **72 focused tests passed, zero failures/errors, 2.734s**:
new keyword/profile tests, existing keyword tests, the producer/typed bank
contracts and the existing trim-handle component check. A system-temp permission
problem in that old handle test was resolved for the runner by pointing its
temporary directory inside the workspace; its product/test source was unchanged.
These are local CPU/mock/file checks, not actual model, playback or native proof.

A final safe isolated probe rejected an unknown profile with structured
`broll_format_invalid`, kept the saved project bytes intact and created no
successful bank. No new breaking point was found in that bounded probe. The
previous real semantic and provenance failures remain explicitly unresolved.

Logs and hashes:
`broll-producer-integration-evidence-2026-10-25/initial-integration-repair-validation.json`,
`initial-repair-green-tests.txt`, `profile-finalization-red-tests.txt` and the
preserved `keyword-guard-red-tests.txt`.

### Further initial acceptance gate — additional feature lease required

Read-only bank construction against the failed saved project (without writing
a manifest or approving clips) now shows **ten slots, nine saved options, one
typed-selectable option and eight duration rejections**. Eight prepared files
have stream duration **0.000325520833 seconds** shorter than their declared
frame-rounded preparation duration at 30fps, timebase1/15360. For example the
first street preview declares6.033333333333333s versus measured6.0330078125s.
The strict `declared > prepared.duration + 1e-6` condition in
`candidate_manifest._candidate` rejects these. The washing-machine option has
equal5.4s durations and passes. Thus the earlier suite observation that all
then-current candidates were blocked is a historical snapshot; the terminal
saved project now has one passing candidate. Neither state is acceptance.

Minimum additional product lease: **`hinglish_broll/candidate_manifest.py`**,
with dedicated boundary tests/evidence. Define a bounded frame/timebase-aware
comparison for preparation metadata without permitting a real active over-trim,
changing model verdicts, rewriting old receipts or fabricating available footage.
That file was **not** changed under the present crash-file lease. This is the
suite's already-observed initial integration issue, not a newly repaired final
adversarial finding. The suite should resolve/release that gate before spending
another real retry merely to obtain an otherwise blocked bank.

When authorized, the suite alone retries the **same normal request** in
`normal-app-short-payload.json` through its ordinary application endpoint, after
confirming no active duplicate worker. Preserve the failed run's receipts and
reuse valid saved progress using the product's own recovery rules; do not
manually mark the old job successful. Keyword-source repair will not retroactively
rewrite this saved plan or its historical model-checks. Fresh planner acceptance
and per-call lineage therefore need separate honest evidence if the resumed
run reuses its plan. Normal assistant dispatch, semantic quality, final playback
and explicit native manual-choice timed insertion remain suite acceptance gates.

## Bounded encoded-duration repair and release — 25 October 2026

The parent subsequently granted the additional **initial** lease for
`hinglish_broll/candidate_manifest.py` and duration-boundary tests. The pre-edit
SHA256 was `57e80956198b31e9df3e519b55cc9258d5bd961bee2a1145e385685e668fc261`;
the exclusive lease and collision check preceded its edit. Only that product
file changed in this stage. This is the already-observed initial runtime defect,
not authorization to fix protected final-adversarial findings.

### Actual cause and strict acceptance rule

Read-only inspection of the first prepared MP4 showed181 frames at30fps,
181 packets with a uniform512-tick presentation grid at1/15360, all packet
durations512 ticks. The complete frame extent is92672 ticks (181/30 seconds).
The MP4 movie clock is1/1000 and its one edit segment is6033 movie ticks;
rescaling that segment to the video timebase gives92667 ticks, the recorded
stream duration. The five-tick discrepancy is edit-clock rounding, not five
missing frames. All eight affected real files subsequently passed the same
actual header/packet proof and matched their captured byte hashes.

The reader now performs bounded CPU header/packet inspection only when a
nominal frame extent is slightly longer than the muxed stream duration. The
exception is limited to a single-video/no-audio MP4/MOV/M4V with one normal
positive edit segment, a parsed movie clock of at least1000Hz, matching
average/base/sequence rate, a complete zero-origin uniform packet grid, matching
frame/packet counts and constant packet durations. The edit duration must equal
the floor of the exact rational frame extent in that parsed movie clock; its
rounded video-tick value must equal the actual stream duration. Ambiguous/VFR,
missing/truncated timing, extra/missing packets and unexplained tick drift do
not justify extension. Inspection is bounded to100,000 packets and atom-count/
file-bound checks. This does **not** globally widen a numeric epsilon.

The typed media identity retains the original measured `duration`, with optional
`frame_duration` and `frame_timing` recording the justified encoded-frame extent.
The declared duration can exceed the measured value only when it agrees with
that proven complete frame extent. Active prepared intervals still cannot exceed
the lesser of the declaration and proven available extent. Actual original
ranges still use the original's measured bound. Receipt construction follows
the same prepared bound. Files, old checked-window receipts, quality verdicts,
crop checks and source/prepared SHA bindings are not rewritten or weakened.

### Evidence and honest remaining limits

The new `tests/test_broll_duration_metadata_regression.py` first ran red:
eight tests, eight failing recorded-file subcases,0.316s. The raw metadata fixture
records the eight real candidate IDs/byte hashes; the unit media and checker
verdicts remain explicitly synthetic. The tests cover the actual differences,
one-extra-tick drift with matching reported stream ticks, missing/VFR proof,
unknown/invalid/mismatched rates, full extra frames, active prepared/original
overruns, rational30000/1001fps timing and receipt-end bounds.

After implementation, **82 focused CPU/component checks passed, zero failures/
errors,3.026s**, including the prior72 checks and unchanged35 contract/golden
tests. Log: `broll-producer-integration-evidence-2026-10-25/duration-integration-green-tests.txt`.
Eight separate final safe parser probes accepted version0/1 timing headers and
rejected truncated/out-of-file atoms, duplicate tracks, zero clocks, multi-edit
lists and nonunit edit rates. No new breaking point was found in those bounded
probes; protected findings were left unchanged. No post-review product fix ran.

Read-only construction against the actual saved project now yields **nine
selectable options, zero typed-duration rejections, ten keyword slots**. All
owner choices remain **unselected**. These nine options occupy only three slots:
four street, four pan and one washing-machine. Seven slots still have no saved
qualified footage. This is not a five-option-per-keyword claim, new semantic
approval, new inference, actual application completion or native import receipt.
Actual code inspection and read-only file verification cannot establish those.

Evidence: `broll-producer-integration-evidence-2026-10-25/duration-repair-validation.json`.
The failed job, its recovery/checkpoint and project hashes still match the
prior repair snapshot. No failed artifact was rewritten and no new bank was
written into that failed output by this feature task.

**Feature lease released to the suite.** The suite alone may now run the same
normal request serially, letting the product resume its saved work, then verify
the resulting typed bank, playback and one explicit timed native choice.
Do not label the saved old plan/model-checks fresh or repaired when reused.
Normal assistant orchestration, per-call model/cache/digest lineage and the
observed sparse/inconsistent semantic choices remain separate acceptance gates.
No network/model/GPU/render/Adobe action or live retry was started here.

## Residential semantic proposal prepared while suite retries

See `docs/broll-residential-criteria-proposal-2026-10-25.md` for the actual
apartment input, verbatim negative local response, bounded physical-criteria
proposal and fresh local acceptance plan. Six negative replay/invariant checks
passed in0.371s; these do not establish pixel suitability or a semantic fix.
The smallest proposed product lease is `hinglish_broll/verify.py` only; it is
not granted/executed here. The observed categorical inconsistency is established;
the suspected effect of absence/rental narrative is not causally proven.
All released product hashes remain stable, and no model/network/media/job/native
action ran. The suite's active normal retry remains the sole live workflow.

The suite later granted the initial `verify.py` criteria lease, after that retry,
while Smart Visuals held the sole heavy-job slot. The bounded B-roll hook is now
implemented and released: full context/guidance and all independent vetoes remain;
negative residential answers are not re-asked for approval. New request-contract
tests first failed4/5; the complete focused set then passed108 checks in2.788s.
Ten final negative/scope probes found no new breaking point. Product freeze and
exact evidence are recorded in the proposal document's subsequent implementation
section and `residential-criteria-implementation-validation.json`. No live model/
network/media/job/native operation ran here; fresh exact-source comparison and
ordinary chat/native acceptance are still suite-serialized future gates.

## Saved normal run: six-empty-moment diagnosis

The ordinary-chat run `a87c39c6a791` completed its review with7 options across4/10
moments; six remain empty and quality remains review-required. The new read-only
audit `docs/broll-six-empty-moments-audit-2026-10-25.md` classifies all six using
actual plans/provider outcomes/queue filters/source and prepared checks. None
proves worldwide stock absence. It records legitimate quality/availability
failures, regional-person verification limits and specific contradictory model
aggregates without overriding them. All six reconstructed queues match actual
attempt order. Two room banks are identical, but their check windows/context
differ and their verdicts cannot be reused by source ID.

The exact717.985s downstream phase includes downloads, preparation, hashing,
QA and preview; it is not pure model time. Stage-arrival timings and their limits
are preserved in `six-empty-moments-audit.json`. Pexels's saved-denial short
circuit is distinguished from a newly observed HTTP401/403. Proposed file leases
and meaningful regression cases are documented for an optional deferred
unselected aggregate preview, completed per-run retrieval reuse, and narrow
semantic diagnostics. No product/cache/media/job change, source-window extraction,
network/model/GPU/native action or blind full rerun was performed. Protected12
and shared locality/provenance remain untouched; no optimization is implemented
or accepted by this audit.

## Authorized initial preview-performance repair

The suite later leased pipeline.py/report.py only for deferred unselected manual
review previews. Implemented and frozen: existing generated source audio remains
playable, independent checked options and all QA/bindings/exports remain, explicit
Save & rebuild and nonreview keep real rendering, and actual preview start/end
events use the existing progress callback. Source-less/nonblack cases fall back
to the current render; saved owner sidecars/earlier explicit requests are not
treated as new unselected banks. Deferred old aggregate files are preserved but
hidden by the report.117 focused CPU/mock checks passed in4.112s, with real
runtime/media/native acceptance and elapsed savings unverified.

Root/suite must review the state-aware result/UI contract before using this
path: server.py869 still collects preview.mp4 by file existence and can expose
a retained stale aggregate despite the report's deferred state. It was not edited
outside the lease. See `docs/broll-deferred-preview-2026-10-25.md` and
`deferred-preview-validation.json` for hashes, red/green evidence, exact fields,
two final negative probes and live gates. No further semantic, inference-cache,
provider/key, media/job/native or protected12 change was made. Feature lease is
released for suite integration review; no restart or live run was started here.
