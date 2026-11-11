# Six empty B-roll moments: saved-run audit

Scope: read-only analysis of completed ordinary-chat job **a87c39c6a791**,
`output/broll/20261025-060011-4048d8`. No product, logs, saved verdicts, thresholds,
media, caches or jobs were changed. No network, model, GPU, render, restart or
native-editor action ran. The suite's other heavy work remains untouched.

The run completed with **seven options across four of ten moments**, leaving
six empty. Completion means the review was built; it does not establish semantic
acceptance. The result's quality report remains failed/review-required. Every
negative original/prepared check is preserved. None of these six empty groups
proves that relevant footage is unavailable across the internet.

Evidence: `docs/broll-producer-integration-evidence-2026-10-25/six-empty-moments-audit.json`.
It includes actual plan/quotes, attempts, check records, provider counts, exact
progress-event boundaries, current-code filter reconstruction and uncertainty.

## What happened to each empty moment

Counts below are retrieved leads / queued candidate attempts, not successful
searches or model inference calls. Original/prepared checks may include multiple
windows for one attempted candidate. Filtering was replayed on the CPU using the
frozen ranker and current0.22 setting, without changing it. All six reconstructed
queue orders match the actual saved attempted IDs; per-call configuration was
not separately archived.

| Moment and speech time | Leads / attempts | Established cause | What remains unknown |
|---|---:|---|---|
| North Indian,5.00–6.00 |47 /5 | Unverifiable regional-person target; two window-locator failures and three original checks rejecting obscured views or dominant people/presenters. | Origin cannot be established from a face, turban, dress or inferred ethnicity. No accepted regional identity; not evidence that all relevant stock is absent. |
| Bachelor → room interior,6.00–7.26 |57 /10 | Commercial/CGI/dark/ambiguous rooms; one unavailable download. One original residential window passed but its prepared check added a single-man/occupant requirement and per-frame subject/presenter vetoes. | Criteria revision reached both calls. Narrative overconstraint is observed in the reason, but actual pixel/crop ambiguity remains unresolved; no manual pass is justified. |
| Bed,16.24–16.54 |36 /9 | Wrong object/sofa, watermark, overly tight bedding/person framing, one failed download. Two originals passed then prepared checks failed. Two other original answers have positive object/frame/quality evidence yet `related=false`. | A duvet/pillow alone does not prove a bed; do not broaden aliases to force coverage. Other all-positive-frame/negative-aggregate answers require a controlled model consistency check, not a boolean flip. |
| Water heater,18.28–18.72 |24 /2 | No direct lead survived current eligibility/scoring. Two web leads were attempted: static product graphic and unavailable download. | Only two attempts do not prove stock absence. A named water-heater/boiler-ignition lead remains untested; title relevance is not actual object/quality proof. |
| Refrigerator,20.34–20.78 |42 /5 | Wrong scene, watermark, overlay and failed window location. One original refrigerator interior passed; its prepared answer describes the refrigerator with every per-frame/quality/identity check true but `related=false`. | Source/prepared consistency and exact pixels need review. Preserve the negative result; do not call this a lack of available fridge footage. |
| PG → room interior,28.36–28.88 |57 /10 | Same57-lead/ranked bank as bachelor; commercial/CGI/ruin/dark or ambiguous rooms repeated. The residential web window here passes top-level context/relevance but fails actual overlay/presenter/subject frame checks. One unavailable URL was skipped using the existing recent-failure record. | This is a different source window from bachelor, and its failure is **not** the earlier single-man comparison. No evidence permits reusing an older positive verdict. |

The North Indian candidate described as regional wedding attire was **not**
accepted: `no_dominant_presenter=false` in every frame. Its attire-based regional
description is still not verified origin and must not be presented as such.
Retain the actual narrated country/setting as context while leaving an unknown
person's identity unknown.

### Provider versus selection versus actual absence

Pexels was skipped once for the saved credential, limiting the search to other
enabled providers. The selected credential has an existing denial marker,
predating this run. `StockClient._get` checks that marker **before** network;
401/403 can create it. Thus the run's message is evidence of a saved-denial
short circuit, **not proof of a new HTTP401 response in this run**. No key was
printed, probed, replaced or unblocked, and no protected cache repair is proposed.

All six empty groups nevertheless had leads from Pixabay, Commons, web and/or
website sources. A source being retrieved does not mean it is downloadable,
qualified, licensed for the intended use, or visually related. A provider-level
“no results” message for one search does not mean every provider was empty.

Water heater is the clearest filtering limit:24 leads,11 acceptable by the
ranker's broad predicate, five in the scored pool, but **zero non-extraction
direct leads** in its queue. Only two web extraction leads were tried.
`pixabay:3802` names water heater/boiler ignition and has cosine0.26509, but
specificity−0.05938 and the vertical-orientation adjustment exclude it under
the unchanged criteria. It is a possible **unchecked lead**, not a missing
accepted clip. Do not lower the global threshold, approve its title or replace
the required live-action object with a product graphic.

The other queues were: North Indian3 non-extraction+2 extraction; bachelor8+2;
bed7+2; fridge3+2; PG8+2. “Non-extraction” includes website previews and does not
guarantee a fast direct stock download. The review-mode code already permits
reusing a candidate ID for another keyword; no global used-ID suppression caused
these six empty moments.

### Actual contradictory checks versus legitimate vetoes

Preserved examples:

- Bed `pixabay:34474`, original1.00–1.30s, and `web:2f93674897753674`, original
  12.433333–12.733333s: all three subject/quality/presenter/overlay checks and
  identity/quality/text flags true, positive description/reason, but `related=false`.
- Fridge `pixabay:79665`, prepared1.00–1.433333s: the same aggregate inconsistency.
  Canonical-object context is derived from `related` and frame facts, so its
  resulting `context_compatible=false` is deterministic bookkeeping, not another
  independent raw model rejection of the story.
- Bed `pixabay:363408`, prepared: `seen` describes duvet/pillows without
  establishing the requested bed. The strict observed-object guard rejects it.
  That is a separate grounding/ambiguity issue, not the same aggregate defect.
- PG `web:3c206d9faa4963ed`, original24.766667–25.266667s: top-level relevance,
  context and identity true, but intrusive text false and all frame overlay
  checks false, with an additional presenter/visibility veto. Its upbeat reason
  does not override those genuine negative fields.

Do not treat the unconditional `context_basis` wording (“Canonical physical
object observed…”) as an independent proof of visibility when `related` or
quality checks failed. That existing label is not another successful model call.
No diagnostic or boolean has been rewritten in this audit.

## Where time and repeated work are established

The exact source is431 progress events in
`cache/app/progress-events/job-a87c39c6a791.jsonl`, SHA256
`5ade4044bc3c73ac836fcb33ad262f06502216add7f4611c638b68314a1abde4`.
The suite's timing receipt is
`output/plugin-validation/coordination-broll-a87c39c6a791-timing.json`.

- Startup/speech/planning:109.127s.
- Retrieval/candidate-picture phase:128.134s.
- **Mixed downstream download/preparation/hash/check/preview phase:717.985s
  (11m58s). This is not pure local-model time.**
- Final quality/status boundary:0.117s; total event elapsed955.362s.

There were79 candidate-begin events and76 original/prepared check records
(63 original,13 prepared). There are additional window-locator operations and
possible cache hits not represented by those check counts. Do not equate them
to76 or79 fresh model calls, retries or failures. Thirteen prepared checks are
not optional: six rejected windows that their original checks had passed.
Removing this second check would hide real or unresolved final-crop problems.

Progress intervals, including intervening file/queue work, were62.137s for
apartment,68.680 North Indian,136.068 bachelor-room,137.991 empty room,40.889 bed,
17.859 wardrobe,60.819 heater,23.026 fridge,71.887 washer and98.627 PG-room.
These are stage-arrival windows, not isolated per-feature GPU timers. The last
PG interval includes full output/preview packaging.

The largest individual mixed interval was54.931s after water-heater candidate2,
which ends in an unavailable download. Other long intervals include42.782s for
the last washing-machine candidate and35.259s around the bachelor residential
web candidate. The final PG candidate-to-quality window is28.139s: the URL was
already marked recently failed, and the interval also includes final preview/
packaging. It cannot be reported as28.139s of downloading or model inference.

Both room slots have **byte-equivalent retrieved and ranked JSON candidate
lists**, the same ten attempted IDs and repeated commercial/CGI/ruin candidates.
That establishes repeated lead/ranking work. Their check intervals and speech
context differ, and the web window differs36.5667s versus24.7667s. The earlier
source is60fps while its prepared video is30fps; intended timestamp/crop agreement
does not prove identical sampled pixels. Reusing a negative/positive verdict
by candidate ID or scene label would be unsafe. Existing picture-vector caches
and the failed-source short circuit already avoid some repeated work; this
audit cannot price the remaining portion without direct timing receipts.

No per-call load, inference/token, download, frame-extraction, hash or encoding
durations are established. Saved answers and model tags lack complete per-call
cache-hit/active-digest lineage. No protected provenance/locality repair ran.

## Smallest safe ordinary optimization proposal — new lease required

**Proposed files: `hinglish_broll/pipeline.py` and `hinglish_broll/report.py`,
plus dedicated tests/docs. No source changes are authorized or made here.**

For a newly collected **unselected review bank**, defer the whole-sequence
aggregate preview until explicit Save & rebuild/preview. Keep original audio-
over-black accessible and every independently prepared, checked option playable.
Do not skip original/prepared QA, byte/window/crop binding, native selection or
editor exports. Emit preview start/end through the existing progress callback
so its actual cost can be measured separately. Nonreview behavior and explicit
owner rebuilds keep their preview behavior.

This removes work that is not required to evaluate independent choices before
selection. The28.139s tail bounds include other work, so they are **not a promised
saving**; this proposal will not by itself solve the six semantic empty groups
or eliminate the717.985s mixed phase.

Required regressions before implementing:

1. Unselected review produces honest deferred/source-audio UI with playable
   option videos, no fake completed preview and no aggregate render call.
2. Explicit Save & rebuild renders one real current preview; ordinary nonreview
   output remains unchanged. A previous selected preview cannot masquerade as
   the current unselected/revised bank; preserve files without false freshness.
3. Candidate/selection counts, raw negative answers and all quality/window/hash
   requirements remain unchanged. No failed option gains acceptance.

Secondary optional optimization, separate lease on `pipeline.py`/`ranker.py`:
within this run only, deep-copy a **completed** identical lead/ranking result
using the actual effective embedding-text/query/country/orientation/provider/
guidance/policy inputs as the key. Record reuse, retain diversification, never
reuse partial/error results or actual footage verdicts. Existing provider/vector
caches may already make this cheap; there is no established runtime saving.
This is not authorization for a shared inference-cache or protected locality fix.

## Semantic follow-up proposal, without a blind full rerun

Proposed file: **`hinglish_broll/verify.py`**, dedicated checks/evidence only,
after an explicit new lease. First classify a contradictory aggregate as such in
diagnostics, preserving every raw negative boolean and the rejected state.
Clarify generic-room nonclaims about incidental occupants/marital eligibility
and tidiness while retaining all real presenter, overlay, identity, geography,
object-visibility and explicit physical-state vetoes. Do not broaden pillows,
duvet or a sofa into a bed, infer regional identity, flip a boolean, add pressure
retries or clear caches.

A future suite-serialized local comparison should target the exact saved bed,
fridge and room windows/crops with explicit consistent physical criteria and
actual sampled-frame inspection. It must record what the local model really
returns, including uncertainty or further rejection. No full35.7s rerun is
needed merely to inspect those already identified failures. Correct handling
of the unverified regional-person keyword needs its own bounded planner decision;
no invented human identity or manually authored successful coverage is allowed.

Provider credentials remain an external availability issue, while genuinely
missing stock remains unproven. Fresh semantics, actual elapsed savings and
normal/native acceptance still require later serialized validation. All12
protected findings remain unchanged. This audit releases no product repair
or heavy-job permission and has not added a new model call.
