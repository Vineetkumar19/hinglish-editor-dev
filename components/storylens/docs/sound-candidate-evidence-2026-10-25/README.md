# Sound recommendation v1 integration fixture

## Status

Bounded feature implementation, 25 October 2026. **Not wired into the panel or automatic pipeline. No real model, GPU job, mix, render, download, Adobe interaction or publishing occurred in this stage.**

- [Golden manifest](<A:/Full Drive/remove silence/docs/sound-candidate-evidence-2026-10-25/golden-manifest.json>)
- [Golden timed request](<A:/Full Drive/remove silence/docs/sound-candidate-evidence-2026-10-25/golden-request.json>)
- [Prepared ranking snapshot](<A:/Full Drive/remove silence/docs/sound-candidate-evidence-2026-10-25/prepared-ranking-snapshot.json>)
- [Source/format verification](<A:/Full Drive/remove silence/docs/sound-candidate-evidence-2026-10-25/fixture-verification.json>)
- [Final review and remaining finding](<A:/Full Drive/remove silence/docs/sound-candidate-evidence-2026-10-25/final-review.json>)

The four WAVs in `fixtures/` are **three-second, 8kHz mono sine-wave test assets**. Their semantic titles, ranking scores and scene evidence are synthetic integration data. They are not real water/horse recordings, accepted soundtrack choices, listening-model judgments or music-quality evidence. All five exposed candidate windows reference actual playable local files whose bytes, credits and bounds were checked. Do not present their fake semantic labels as a production recommendation demo.

The fixture contains two ranked opening music alternatives, a music group that stays rejected (`decision:-1`), two explicitly partial music alternatives (3s source versus a 4s request; no looping), one source-filtered SFX alternative and an explicit ranking-cache miss. It never includes source/dialogue/generated soundtrack stems.

## Feature-owned API

New code only:

- `hinglish_sound/recommendations.py`
- `hinglish_sound/recommendation_runtime.py`
- `tests/test_sound_recommendations.py`

Existing automatic Sound Design, `director.py`, `pipeline.py`, shared panel/server/UI, bridges, host adapters, XML importers and packaging were **not edited by this stage**. Earlier protected duplicate-picker and creative-quality findings remain unchanged.

```python
from hinglish_sound.library import Asset
from hinglish_sound.recommendations import (
    CachedRankingIndex, recommend, verify_candidate_source,
)
from hinglish_sound.recommendation_runtime import (
    CancellationToken, Telemetry, CheckpointStore, write_json_atomic,
)

# Prepare these from existing indexed Asset records, cached ranking results and
# cached facts. Do not construct Brain/Listener or run automatic Sound Design.
music_index = CachedRankingIndex(assets, cached_query_hits, facts=cached_facts)
sfx_index = CachedRankingIndex(assets, cached_query_hits, facts=cached_facts)
audit = Telemetry()  # monotonic clock and receipt sink are injectable
token = CancellationToken()
manifest = recommend(
    root, timed_request, music_index, sfx_index,
    limit=5, token=token, telemetry=audit,
    allowed_roots=prepared_library_roots,
    checkpoint=CheckpointStore(owned_job_folder),
)
write_json_atomic(manifest_path, manifest)

# Later, suite resolves a selected ID from its own saved manifest, not a
# client-supplied arbitrary path. Immediately before a separately authorized
# native action, this feature guard rechecks the immutable source snapshot:
receipt = verify_candidate_source(
    root, selected_candidate, allowed_roots=prepared_library_roots,
)
```

`recommend` is independent of full soundtrack generation. Its inputs are **already timed sections/events and prepared rankings/evidence**, not a script-to-scenes inference service. It makes no creative model calls and does not select a winner. An actual existing `SoundIndex` can be used only with the explicit `allow_live_ranking=True` integration/resource release, because `SoundIndex.search` may invoke an embedding model on cache miss. Default calls require a `prepared_only=True` cached snapshot; `CachedRankingIndex` raises a typed cache miss instead of starting a model. Custom dependencies marked prepared-only must honor that contract; this flag is not a sandbox for arbitrary injected Python code.

### Timed request contract

The request preserves exact `script` and complete JSON `creator_context`. It requires:

- `timeline: {id, duration, fps}`: stable captured timeline ID, positive duration, positive rational/numeric frame rate ≤240. Units are seconds unless explicitly called frame rate.
- `library_revision`: caller-provided version of the prepared asset/ranking inventory. Refresh it when library or ranking inputs change. This component cannot detect unreported changes to the caller's query snapshot merely from a stale revision string.
- `music_sections[]` and `sfx_events[]`: stable unique IDs within each kind, `start`, `end`, nonempty audible `intent`, proposed `level_db` (-60…+6), evidence `{kind, precision, confidence, description}`. `role` is an optional text label. Music can specify `mood`; SFX requires a supported `sound_type`.
- Optional `decision:-1` preserves owner/saved group rejection. `rejected_source_ids[]` rejects specific content hashes, including `sha256:`-prefixed hashes. Explicit `banned_paths` and the existing saved Sound Design owner bans are combined; taste memory is only read.
- Optional typed `processing` is validated by the existing Sound processing validator. It is a proposal, not baked or executed by recommendation. Unsupported executable fields are rejected.
- Optional cached `passage_selector(asset, slot)` returns `source_in`, optional `source_out`, and `basis`. With checkpoints it requires an explicit `passage_revision` in the request. The default is source head, **not a claim of optimal acoustic passage**. No new music passage analysis occurs here.

Music search does not silently broaden a specified mood, and known vocals are excluded from instrumental choices. SFX checks use the existing subject guard and cached scene grounding; speech alone does not establish literal physical Foley. Wrong-kind/unregistered assets, dialogue/source/generated stems, outside-root paths, banned recordings, duplicate content within a group and clips that cannot cover the required SFX duration are rejected. Unknown semantic identity still needs human review; no fresh CLAP evaluation is performed by this entry point.

### Output contract

`schema="storylens.sound-recommendations"`, `version=1`. Root status is `ready`, `no_match` or `cancelled`; root groups retain their distinct states. `ready` means alternatives exist for review, **not selected, mixed, imported or semantically accepted**. An all-rejected request can have root `no_match`; each group's `rejected` state and `decision:-1` remain explicit.

Each group has `id` (`music:<input-id>` or `sfx:<input-id>`), kind, requested timeline span, intent/role/evidence, rejection state, `reason_code`, `candidates[]` and source-rejection diagnostics. Group states are `candidates`, `no_match` or `rejected`. A cache miss uses `ranking_cache_missing`; unsupported physical evidence uses `unsupported_source_evidence`. These are machine reasons for the suite's shared plain-language/error helpers, not strings to show unformatted to the owner.

Each candidate includes:

| Field | Meaning |
| --- | --- |
| `id`, `group_id`, `kind` | Stable within unchanged request/source/window/credit identity. Rank changes alone do not change IDs. A changed source, source path, credit metadata or window produces a different candidate ID. |
| `rank`, `rank_score` | Prepared ranking order/score. Scores are not probabilities or calibrated confidence. |
| `source` | Canonical absolute path, SHA256, size/stat snapshot, available source bounds, chosen `in`/`out`, selection basis and credit hash. Bounds use the conservative minimum of cached-index and demux-reported duration; no full acoustic decode or exact semantic-hitpoint verification. |
| `credits` | Immutable snapshot of provided licence/source/author/attribution metadata and sidecar hash. Missing metadata stays `unknown_owner_supplied`; provided metadata is not independently licence-verified by this module. |
| `timeline` | Proposed actual start/end for this source window. It can overlap other groups; no placement is performed. |
| `role`, `sound_type`/`mood`, `proposed_level_db`, `reason`, `processing` | Source-backed proposal, including any validated processing. No gain/ducking/EQ is baked here. |
| `confidence`, `evidence`, `listening` | Preserved supplied evidence confidence/description/precision and cached audio facts. Not newly inferred certainty. Every candidate has `review_required=true`. |
| `coverage`, `loop` | Music shorter than requested is explicitly `partial` with a shorter actual timeline span; `loop=false`. SFX is not stretched or silently truncated to fill an authored event. |
| `audition` | Actual playable source `path` plus seek/stop `in`/`out`. `rendered=false`: this is **not** a newly encoded short audio file. Client must honor the window instead of playing the whole song. |

The root capabilities explicitly say no mix, rendered auditions, native import or automatic selection. Original audio remains outside these alternatives and must remain once in the eventual native workflow.

## Timing / cancellation / checkpoint hooks

`Telemetry.stage(name, kind="stage"|"call", cache="hit"|"miss"|"unknown"|"not_applicable", retry=0, metadata=…)` takes two injected monotonic readings and emits an optional receipt sink. Failures and cancellations are recorded by type; script/profile contents are not automatically logged. Retry values describe observed caller attempts, not a retry scheduler. Current receipts cover recommendation groups, ranking calls, source identity/probe work and checkpoint hits. They do **not** measure queue/ASR/Vision/model/render/import stages that were not run. Parent spans contain child work; do not sum nested span durations as end-to-end time. No RAM/VRAM sampler or processing SLA is supplied.

`CancellationToken` checks before/after ranking, between candidates and at 1MiB file-hash chunks. It cannot interrupt an opaque blocking ranker or demux call until control returns. A cancelled response retains only completed groups. `CheckpointStore` atomically writes completed groups and the full request/version/config fingerprint; partial in-flight groups are not promoted to completed. Resuming is an **explicit caller action** with the same inputs and a fresh token; the component schedules nothing automatically.

Resume rechecks source bytes, credits, candidate identity, path roots, timing and level bounds. Changed script/profile/library/passage/settings/limits/bans invalidate checkpoint reuse without deleting the old progress. The caller must persist the original request/full creator context separately and provide a single writer per checkpoint directory. Checkpoint storage currently rewrites the completed-group JSON, so large-section checkpoint I/O is unbenchmarked; do not advertise long-form efficiency from these hooks.

**Known final-review limit:** edited checkpoint group descriptions can survive source verification. The saved fingerprint is an input-version guard, not an authenticated semantic record. Do not accept external/untrusted checkpoints or claim full checkpoint semantic integrity; see `final-review.json`. This was recorded and left unfixed under the standing review rule.

## Suite integration still required

1. Capture Premiere timeline/shared script and obtain bounded, timed analysis/evidence plus prepared query rankings. Keep complete creator guidance; do not invoke the full automatic soundtrack just to obtain manual alternatives.
2. Resolve candidate IDs server-side from a saved manifest, not arbitrary paths from a browser. Run `verify_candidate_source` before import; check active project/sequence again through the suite's existing guards.
3. Serve private source-backed audition windows with appropriate seek/range behavior, or separately authorized short-excerpt preparation. The current `/api/panel/media` accepts only output paths; these raw library candidates are intentionally not made accessible by changing that route here.
4. Show separate Music/SFX groups, ranks, time spans, coverage, source identity, reason and no-match/rejected states. Use the shared error catalog/presentation helpers, with diagnostics separately. A 3s source for a 4s section must be visibly partial.
5. Transfer selected source in/out, timeline start/end, levels and supported processing in a typed timed native manifest. The existing path-only at-playhead overwrite is insufficient. Preserve overlap/separate tracks, speech ducking, original audio once and shared mastering when a final mix is later requested.
6. Save source/selection/native receipts, protect retries from duplicate placement, then validate actual editable native results/playback in the one reserved Adobe host. No current native acceptance, fresh-video timing, long-form performance or autonomous creative improvement is claimed by this component.

Protected older final-review findings (duplicate automatic-picker IDs and uneven creative coverage) remain outside this implementation. New request-group uniqueness validation here does not repair that older picker.

## Tests actually executed

Meaningful tests were written first and observed failing: absent modules, then preservation, checkpoint source boundaries, source-credit identity, live-ranker release and pre-import verification contracts. The first command also exposed a restricted system TEMP location; subsequent runs explicitly used the workspace `tmp` directory. No security setting was changed.

Latest executed command:

```powershell
$env:TEMP='A:\Full Drive\remove silence\tmp'
$env:TMP=$env:TEMP
.venv\Scripts\python.exe -m unittest tests.test_sound_recommendations tests.test_sound_natural_duration tests.test_sound_website_context
```

**37/37 passed in 2.903s:** 20 new recommendation/runtime checks, 11 existing duration/source checks and six existing website-context checks. These use cached/fake rankings, temporary files, mocked model calls and small synthetic audio. No full `test_sound*.py` rerun was performed in this stage because some existing cases render synthetic video, beyond the current no-render release. Prior 154-check evidence remains historical, not a new claim.

Five golden candidate sources/windows were subsequently verified against their actual WAV headers, bytes and credit snapshots. Five safe final-review probes ran; one new semantic checkpoint finding is recorded and left unchanged. Live panel/host, native import, 30–40s model profiling and 10–15 minute scale acceptance remain pending suite release.

## Subsequent local-runtime / subscription-independence audit

The owner's later requirement is explicit: genuine acceptance must use the configured local LLM/Vision and normal app tools, and the installed feature must work without a dot/Codex/ChatGPT session. The synthetic golden fixture and 37 isolated checks **do not satisfy local-agent acceptance**. They verify deterministic contracts only.

Static audit found no OpenAI, Codex or ChatGPT SDK/API/session dependency in the two new modules. They are ordinary installed Python code; `hinglish_sound*` is already included by the repository's package discovery. They do not need this development chat to process a prepared request. That is a source-level dependency result, not proof of the packaged installation or unattended local-agent orchestration.

The existing automatic sound route uses loopback Ollama for planning and Vision, configured local embedding adapters and installed CLAP/native tools. Examined configured roles are `storylens-meaning:14b`, `storylens-planner:9b-q6` and `storylens-embedding:8b-q6`; no automatic hosted OpenAI/ChatGPT fallback was found in that route. `local_runtime.ensure` sets `OLLAMA_NO_CLOUD=1` when it starts its installed runtime. Installed models, local Python/native dependencies, creator knowledge and media must remain available without Codex. Optional Freesound/stock APIs, their credentials/licences/network, first-time open-source downloads and commercial Storylens licensing are separate dependencies, not cloud LLM brain fallbacks.

Two additional **unfixed audit findings**, both demonstrated without any real secret or model/network call:

1. **Telemetry metadata is not redacted.** Passing a synthetic `authorization` value into `Telemetry.stage(metadata=…)` retains it unchanged. Current feature-emitted metadata contains only group kind/ID, but the hook must not receive raw provider headers/tool payloads until a redaction boundary is implemented. Its docstring is not an enforcement mechanism. Expected redaction versus actual unchanged receipt is captured in `final-review.json`.
2. **Explicit model override locality validation is incomplete.** `resolve_model(..., requested="synthetic-audit:cloud", legacy_default="qwen3:8b")` returns early without applying the later cloud-suffix rejection. Current configured defaults examined are local, and no cloud request was made or observed. This is a shared-helper validation gap, not proof of actual remote fallback; it is outside this feature reservation and was not repaired.

Together with the checkpoint semantic-field weakness, the final record contains **three findings**. Protected older automatic-picker/creative findings remain separate and unchanged. Details: [runtime audit](<A:/Full Drive/remove silence/docs/sound-candidate-evidence-2026-10-25/local-runtime-audit.json>) and [final review](<A:/Full Drive/remove silence/docs/sound-candidate-evidence-2026-10-25/final-review.json>).

Exact local-agent acceptance gaps:

- The new entry point is not registered in the normal panel/server/local-agent tool route. The suite must connect the shared-script/timeline request to **actual local-model-authored** timed sections/events and real source queries. No synthetic or hand-authored answers may replace model decisions in acceptance.
- Manual mode: the local model/tool chain proposes source-backed music/SFX alternatives; the owner chooses. Auto mode: the configured local model chooses supported candidate IDs and contextual placement; deterministic controllers handle bounds/arithmetic/validation/state. A `ready` manifest alone proves neither path.
- Normal-route receipts still need actual provider/model/weight revision, redacted prompt/tool requests, execution/retry/outcome, cache lineage and intervention flags. The new generic timing hook can record caller-supplied phase/call metadata but does not fabricate missing model receipts. Do not log credentials through the current unsanitized metadata field.
- After serialized resource release, test an owner-supplied short case cold and warm with actual configured models and no Codex replacements, then a representative 10–15 minute laptop case. Record queue, ASR/alignment, Vision, retrieval, planning/selection/retry, mix/render/import separately, along with RAM/VRAM, cache conditions and native receipt/playback. No acceptable budget or zero-breakage guarantee exists.

No inference, GPU-heavy task, render, host action, download, account grant or publishing was started for this audit. No code was changed after final-review probes. Await coordinated integration/resource release and owner-approved follow-up on the recorded failures.

## Frozen delivery and separate repair queue

Coordination has explicitly confirmed the AGENTS.md final-review boundary. The delivered feature code/tests remain frozen at 37 isolated checks. The [separate proposed repair cycle](<A:/Full Drive/remove silence/docs/sound-candidate-evidence-2026-10-25/proposed-repair-cycle.md>) records concrete reproductions, proposed failing regressions, minimum remediation and current integration-safe workarounds for all three findings. It is **not implementation approval**. Fresh suite integration can proceed without loading semantic checkpoints, with cached-only ranking and strictly limited non-secret timing metadata; actual production local-agent/native acceptance remains pending the suite's reserved resources and shared policy work.
