# B-roll residential criteria: bounded proposal, no product change

Status: proposal and negative-replay checks only. The suite owns the active
normal retry. No model/provider/network/media generation, job changes or
Adobe actions were performed here. Released source files remain stable.

## Observed case and limits

Initial job `7c03db6fbd88`, apartment slot1 at2.14–3.10s:

- Speech: “flat to mil hi jaega.”
- Physical search: `apartment interior`, `small apartment`, `room interior`.
- Meaning: “The lack of available flats for a bachelor in North India.”
- Named subject: empty; country/context: India and the original full surrounding
  speech. Direction: collect relevant video-only options, owner chooses insertion.
- Candidate: `web:57aeab2eb3fb2b2f`, source SHA256
  `aa715d5e3b34e62d13a8e196c47340954f262aa0f721d97f19b5371e3388e8f5`.
- Actual checked source interval12.2666666667–13.2333333333s; crop
  x656,y0,width608,height1080 into270×480.

The raw stored local answer says: “A living room interior with a sofa, coffee
table, and wall art.” It nevertheless returns `related=false`,
`context_compatible=false`, `identity_compatible=false`, and `subject_visible=false`
for all three frames. Real footage, no intrusive text, no dominant presenter and
no intrusive overlays are true. Its reason says the living room does not clearly
establish the specific subject “apartment interior”. The producer correctly
kept this negative answer rejected.

This is an **observed categorical inconsistency**, not proof that the original
pixels depict a suitable residential interior. The model's own description may
be wrong. Nor does the reason explicitly say “I rejected this because housing
is unavailable”: rental/absence framing is a suspected contributor, not a
demonstrated cause. The current generic prompt already says unavailable objects
may be illustrated and generic interiors need not prove rental status. Adding
another generic reminder alone may not resolve it.

The current checker passes the physical keyword, descriptive absence meaning,
full source context and editing direction together. Its existing generic
recheck requires `context_compatible=true`; this case is false, so it receives
one call and no such recheck. Canonical appliance/object checks have a separate
physical prompt, but apartment/room interior is not in that exact-object branch.
Do not expand the appliance dictionary or infer approval from “living room” in
`seen`: a description string is not independent three-frame evidence.

## Exact raw fixture and reproducibility

`tests/fixtures/broll-residential-criteria/actual-input.json` preserves the actual
slot fields, source hash, interval/crop and postprocessed verdict. The temporary
canvas values are explicitly reconstructed from the saved timeline because
`render_choice` adds them before invoking `Checker.check`.

`raw-local-verdict.json` is a byte-for-byte copy of
`cache/visuals/evaluator/a50cebe3e64ac612bb23a6b3d7b07b0e61dae0fd864c770946302e0a1c1cce76.json`,
SHA256 `d6930a38a68eca457ab5e4e339ac84e4ce2e30ce5724061220cd83014a3cead3`.
Every raw flag/observation matches the persisted check; its reason matches the
suffix before deterministic failure-prefix bookkeeping. This does not establish
which provider call/cache read produced it, the active weight digest, or that
another cache answer with similar wording concerns the same pixels. No positive
cache answer was substituted or treated as a new check.

`tests/test_broll_residential_verdict_replay.py`: **six checks passed,0.371s**.
They call the real checker with synthetic black frame inputs and replay the
stored negative answer. They verify byte preservation, continued rejection,
the single-call path, retained context/direction and frame/identity requirements,
negative per-frame vetoes despite synthetic top-level positives, preservation
of an explicit named identity, and `CheckUnavailable` on a synthetic timeout.
These are **negative replay/invariant tests**, not TDD proof of a semantic fix,
fresh inference, actual image inspection, or application/native acceptance.
Output: `docs/broll-producer-integration-evidence-2026-10-25/residential-negative-replay-tests.txt`.

## Smallest proposed product lease

Request **`hinglish_broll/verify.py` only**, plus dedicated tests/fixtures/docs.
No lease is needed for `hinglish_visuals/evaluator.py`, Smart Visuals defaults,
`subjects.py`, shared guard/model preferences, pipeline/receipt handling or
cache invalidation. No product lease is exercised in this proposal.

Within the B-roll `review_options=true` check path, propose a small typed
physical-criteria helper for the exact generic subjects **apartment interior**
and **room interior**, only when no explicit named identity is requested.
Keep the existing inference call and three-frame schema/validator. Distinguish:

- Required physical subject: visible residential indoor space. A visibly filmed
  residential living/sleeping area can illustrate a generic apartment/room;
  seeing a rental contract or proving bachelor eligibility is not required.
- Explicit physical states remain requirements: `empty room`, `closed shop`,
  `person sleeping`, a specific appliance or an exact named residence do not
  enter this generic family. A furnished room does not establish an empty room;
  a bedroom alone does not establish a sleeping person.
- Commercial salon/office/lobby, outdoor-only footage, floor plans, CGI, title
  cards, unrelated presenters and low-quality/overlaid frames remain rejected.
- Named identity and visibly conflicting geography/setting checks remain.
  Generic stock does not claim the actual narrated rental/address; nationality
  must never be inferred from faces. The narrated country and source context
  remain available as data, not removed to obtain a pass.
- Keep the **entire original context, user direction and creator guidance** in
  the normal local call. Mark descriptive absence/rental rhetoric as context,
  separately from the required physical depiction. Do not delete profile
  knowledge or edit the source transcript/plan to obtain an easier answer.

The helper should supply explicit bounded criteria in the B-roll request,
including a criteria revision, rather than rewriting the shared Vision system
or broadly converting every subject to a generic interior. The actual local
model must still return every subject/context/identity/quality boolean and all
three frame checks. **No deterministic flip from false to true**, positive
regex override, fabricated model answer or reused positive receipt is allowed.
A negative/uncertain model result still rejects that option. Keep the existing
bounded search budget and do not add repeated “please approve” attempts.

## Fresh local acceptance case after suite release

Only after the active retry is terminal and the suite releases the queue:

1. Preserve this raw input/verdict. Have the configured local checker inspect
   the same actual source bytes, exact source interval and final crop with the
   proposed explicit physical criteria. This is a controlled local semantic
   comparison, not a manually chosen final timeline insertion. Do not supply
   the desired boolean answer. Inspect the actual sampled images independently
   before claiming their meaning or clarity.
2. Record the actual new request/criteria revision and raw response. Because
   the request changes, normal cache keys should differ; do not clear caches,
   rewrite old answers or call a cache hit fresh inference. If per-call
   hit/miss/digest evidence is unavailable, retain that limitation. Installed
   inventory is not execution proof. No shared provenance/locality repair is
   part of this proposed lease.
3. If frames clearly depict a residential living room, the model should accept
   it as a **generic illustration**, without asserting rental status/address.
   If the actual pictures are ambiguous, CGI or unsuitable, rejection is valid:
   record `uncertain/no qualified match`, do not force this source to pass.
4. Negative controls must still reject actual salon/commercial footage, CGI/
   intrusive overlays, a room offered for “person sleeping”, a furnished room
   offered for “empty room”, and a different explicitly named place. Use real
   existing source examples when available; no source-identity substitutions.
5. Run the ordinary application request once with its unchanged full creator
   context. Let the local planner/search choose candidates; verify original
   and prepared checks, byte/window bindings, saved no-match states and final
   playback. Controlled checker comparison alone is not normal orchestration
   or end-to-end acceptance. Native manual selection/insertion remains suite-owned.

Distinguish useful outcomes: a provider/model timeout is an unavailable check,
a completed bounded search without a qualified shot is no-match, and a physically
clear residential shot rejected solely for unprovable rental status is a
criteria/model error. Do not turn any of these into a successful checked option.

## Protected boundary

The scoped AGENTS/review/handoff history search identifies this exact issue in
the initial real integration audit, with no matching prior protected final-
adversarial classification found. This is bounded history evidence, not an
exception to the owner's rule. If a prior protected classification is supplied,
leave this as a reproduction/proposal until the owner requests that repair.
All seven protected shared findings, cache/locality issues, old job evidence and
Smart Visuals behavior remain outside this proposal. No product source changed.

## Subsequent authorized implementation — 25 October 2026

The parent subsequently granted the **initial B-roll quality-correction** lease
for `hinglish_broll/verify.py` and dedicated tests/docs. The scoped implementation
is now complete and released back to the suite; the historical proposal above
records what was requested before that lease. Collision/hash checks immediately
before editing confirmed SHA256
`33ec53114f7ed6d2a66427a3b0127cfaa75c9d4cd876975f69e75dffe6d9bf1e`.
No other product source changed. Smart Visuals remains the suite's sole heavy job.

`ReviewPhysicalCriteria` and `_review_physical_criteria` supply structured request
data tagged **`broll-residential-v1`**, only for `review_options is True`, exact
generic apartment/room-interior subjects and no nonempty explicit identity.
The request describes visible residential space, permitted residential details,
commercial/CGI/presenter/overlay exclusions, nonclaims about rental status and
eligibility, and the narrated country/setting policy. The full original speech,
meaning and direction remain in the same request. The existing shared local
Vision/creative-guidance call is unchanged; no profile knowledge was removed.

All subject/context/identity/quality booleans and all three per-frame checks
remain independently required. This generic family does not use the appliance
branch's derived-context logic. No model boolean is changed by the new helper.
Its negative answer is not sent through the old generic “recheck” branch for
another chance at approval. Other subjects retain their existing paths. New
check bookkeeping labels the criteria revision; that is not an inference-
freshness, cache-miss, pixel-quality or model-training claim. No saved verdict,
cache, source/window/crop, old evidence or actual job was rewritten.

### TDD, component checks and freeze

`tests/test_broll_residential_criteria.py` first observed **five tests, four
expected failures,0.389s** for missing request criteria/revision and the unwanted
generic recheck. This is distinct from the earlier six passing negative-replay
invariants, which were not represented as red TDD or successful model answers.

After implementation, **108 focused CPU/component checks passed**, zero failures/
errors,2.788s: new request contract, prior negative replay, exact-subject relevance,
duration boundaries, keyword retries, profile finalization, producer/selection
contracts and handle preservation. No real inference/render/provider/native
operation was part of those tests. The synthetic frames and local-model boundary
fixtures do not establish how a fresh model will judge the actual apartment.

Ten bounded final probes retained each synthetic single-negative subject,
context, identity, footage-quality and overlay veto, and excluded empty room,
person sleeping, commercial/named descriptions and altered/instruction-like
keyword strings from the generic hook. None produced a positive model answer.
No new breaking point was found in those performed probes; the source was frozen
afterward. Protected12 and shared cache/locality/provenance issues were untouched.

Evidence: `docs/broll-producer-integration-evidence-2026-10-25/residential-criteria-implementation-validation.json`,
`residential-criteria-red-tests.txt` and `residential-integration-green-tests.txt`.
The previously released keyword/producer/duration product hashes remain unchanged.

**Lease released.** Fresh exact-source/window/crop local inference and the same
ordinary B-roll chat acceptance remain future suite-serialized checks after
Smart Visuals. The active job was not interrupted. The categorical inconsistency
and suspected causal mechanism remain hypotheses for actual pixel/model testing;
do not mark semantic quality, model freshness, normal orchestration, five choices
per subject or native timed insertion verified from these fixtures.

## Read-only ordinary-chat run audit — a87c39c6a791

The suite started a new ordinary Storylens chat request, with the same original
e2 source SHA, output `output/broll/20261025-060011-4048d8`. Request receipt:
`output/plugin-validation/broll-normal-chat-request.json`. Its request entered
through the visible chat UI; the local assistant chose the B-roll tool. This
differs from the initial direct-job test. The effective saved profile is gaming,
review options true, cap5, target10, black background true and no explicit
B-roll brief; the saved slot direction is empty. The original full speech/context
remains. No source/arguments/cache/job were changed by this audit.

Snapshot evidence: `docs/broll-producer-integration-evidence-2026-10-25/normal-chat-criteria-audit.json`.
At its observation the job was still **running94%**, checking washing-machine
candidate11/11 with one option saved. It was not terminal or accepted. Saved
options: apartment2, empty room3, wardrobe1, washing machine1; North Indian,
bachelor/room, bed, heater and fridge had zero. The final PG/room slot was not
yet saved. Five is a cap, not a guarantee. The new plan includes the correctly
timed four-walls/empty-room subject and no longer includes the former opening
establishing street or ambiguous pan subject. Summary and keyword guards each
record one attempt with zero hard/soft problems; that is rule-validation
evidence, not semantic correctness or fresh inference proof.

### Source/prepared disagreement is not missing revision propagation

Target `web:3c206d9faa4963ed`, speech6.00–7.26s (“bachelor ho, party mein”),
generic room interior, meaning “A single man living alone”, no named identity:

- Original check passes, describing a residential room with a person unpacking.
- Prepared check rejects, describing a room/fan/bedding and adding a “woman,
  not a single man” requirement. It also marks subject visibility and absence
  of a dominant presenter false in every frame, and rejects context/identity.
- **Both** actual stored checks carry `broll-residential-v1`. Frozen source
  hashes match the request receipt; source and prepared semantic fields are
  unchanged by the pipeline between those calls. Code inspection finds no
  missing revision/criteria branch propagation for this pair. Actual per-call
  prompt payloads are not archived, so exact provider input/honoring is not
  independently established by the metadata label.

The full source and prepared file hashes match their recorded checks. Requested
sample times map identically to source36.7566667,37.2,37.6433333s, with inferred
preparation origin33.5666667s. The original crop is656,0,608×1080; prepared is
270×480 with identity crop. However the source is60fps and prepared30fps.
`read_frames` chooses the first decoded frame at/after requested time minus20ms;
resizing, frame selection, crop rounding and compression can differ. Matching
requested times and crop intent are **not pixel equality**. No new frames were
extracted. Legitimate visual ambiguity or person dominance/crop loss cannot be
ruled out, and the negative prepared verdict was not overridden.

The stored gender/marital-status comparison appears to import the narrative
meaning into the generic room target. Current nonclaims mention bachelor
eligibility but do not explicitly list incidental occupant identity or tidiness.
This is a recorded caller-criteria limitation/model disagreement, not permission
to force an acceptance. Clutter alone need not make footage unreadable, but
actual occlusion or a dominant talking presenter must still veto the window.
The source lead thumbnail is a decor collage; it is **not** the selected checked
interval and cannot prove the prepared frames' suitability. A separate existing
checked apartment thumbnail shows a furnished living space at thumbnail scale;
that is not an all-frame or motion proof either.

### Geography, provenance and next boundary

The new plan also searches `North Indian`, `North Indian man`, `North Indian
person` for the5.00–6.00s phrase, with no named subject. Three checks rejected;
no accepted regional-person identity was established. One model description
refers to regional wedding attire; that is not verified origin. **Nationality,
ethnicity and regional origin must not be inferred from faces or clothing.**
The narrated country/source context remains valid data; an unknown person's
identity remains unknown. This concern must not be “fixed” by approving a
generic face or inventing provenance.

Exact raw-cache field/reason matches were found for both target verdicts, with
within-run file mtimes00:37:43/00:38:02UTC. That supports stored answer lineage
and new writes, not per-call fresh inference or the loaded digest. Primary
planning/Vision caches still omit active weight digest from their keys and do
not persist complete hit/miss execution receipts. The new request receipt
records Ollama0.40.5 and no loaded models at its initial observation; the older
05:01 loaded-Vision observation belongs to the previous run and is **not** this
pair's execution receipt. No provider endpoint was queried in this audit.

The application still reports Pexels rejecting its saved key, and explicitly
reuses verified internet leads and candidate pictures. No new key probe or
cache clearing occurred. Semantic improvement, every-subject coverage, final
playback, complete per-call provenance and native insertion remain unverified.
All12 protected shared findings remain untouched. Product source stays frozen;
any repair proposal/lease must wait for this job's terminal state and the suite.
