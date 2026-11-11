# Separate proposed repair cycles — not authorized for implementation

25 October 2026. This is a documentation-only queue. Feature modules and tests remain frozen at the delivered **37 isolated checks**. No repair test was added or executed for this queue; no feature/shared code, model, render, download or Adobe action was started.

The controlling boundary is [AGENTS.md](<A:/Full Drive/remove silence/AGENTS.md:586>):

> Do NOT fix failures found during this final adversarial review unless the owner subsequently asks. Preserve the findings and report them. This does not prevent implementing the requested behavior during the initial TDD loop.

The original implementation TDD loop ended before the three recorded review/audit findings. The later runtime requirement does not by itself make these recorded failures silently repaired. Each repair below needs a specific subsequent owner request, a separate failing-regression-first cycle, and the appropriate file reservation. No overnight confirmation is requested here.

Existing evidence stays authoritative: [final-review.json](<A:/Full Drive/remove silence/docs/sound-candidate-evidence-2026-10-25/final-review.json>), [test-results.json](<A:/Full Drive/remove silence/docs/sound-candidate-evidence-2026-10-25/test-results.json>), and [runtime audit](<A:/Full Drive/remove silence/docs/sound-candidate-evidence-2026-10-25/local-runtime-audit.json>). The older automatic-picker duplicate-ID and creative-coverage findings remain separate, protected and unchanged.

## R1 — checkpoint-semantic-fields

**State:** confirmed; proposed repair only. **Feature ownership:** `hinglish_sound/recommendations.py`, `recommendation_runtime.py` if needed, and dedicated Sound tests. The suite owns whether its integration enables resume.

### Concrete reproduction, already observed

1. Use the isolated recommendation test assets/request and create a `CheckpointStore`.
2. Call `recommend` once to save completed groups.
3. Edit only `groups[0].intent` in `recommendation-checkpoint.json`, for example to `TAMPERED DESCRIPTION`. Keep the request fingerprint, candidate IDs, source hashes, file bytes and source windows unchanged.
4. Call `recommend` with the same original request, rank snapshots and checkpoint store.

**Expected:** reject the changed cached semantics or rebuild the presentation from the validated timed request. **Actual:** `_verify_saved` accepts source identity, paths, timing and levels, then the caller copies the entire prior group; the modified intent is returned. **Impact:** a corrupted/edited local checkpoint can misdescribe valid audio alternatives. It is not proof of changed source audio, arbitrary execution, external access or a successful native import.

### Proposed regression, not implemented

`test_checkpoint_semantic_projection_matches_original_request`:

- Build and checkpoint a fixture, mutate the saved intent only, resume unchanged inputs, and require either a clear integrity failure that preserves the checkpoint or the exact original request-derived intent.
- Add cases for group role/evidence/timeline/decision and candidate reason/evidence fields. Any field that claims to describe the current request must be derived from or checked against trusted request data.
- Verify all-rejected/`-1` groups stay rejected, candidate source IDs/paths/windows remain stable, full creator context remains intact, and prior checkpoint bytes are not overwritten on rejection.
- Confirm valid resume remains cached-only: no ranking/model repair is started just to conceal the mismatch.
- Inspect display-critical credit fields in the same approved cycle: currently the credit sidecar hash is checked, but it should be established whether a changed cached credit display can survive. This is a proposed additional regression, **not another reproduced finding** in this queue.

### Minimal remediation proposal

The current `_verify_saved` already receives the original validated `slot` and kind. Compare a canonical request-derived semantic projection against the stored group before reuse, or rehydrate those semantic fields from the original slot rather than returning the whole cached group unchecked. Recreate display credits from the verified sidecar. Retain the existing source-byte/path/root/window/level checks and refusal to reuse mismatched request versions.

Do not describe a checksum stored beside editable data as authentication. A minimal local coherence repair does not make externally supplied checkpoints trusted. Authenticated/shared checkpoint ingestion would be a separate security design, not part of this proposal.

### Integration-safe workaround now

- Fresh recommendation integration can call `recommend(..., checkpoint=None)` with complete timed input and prepared cached rankings.
- Do not load semantic groups from existing checkpoint files, including the golden fixture's test checkpoint.
- On an explicitly requested retry, rebuild the recommendation manifest from the original persisted request and cached rankings/evidence, preserving the old checkpoint for diagnosis. Do not rerun a full automatic soundtrack or silently substitute model choices.
- Keep cooperative cancellation at the fresh-call boundary and preserve returned completed groups for review. Do not claim durable semantic resume until the separate repair is authorized and validated.

## R2 — telemetry-metadata-redaction

**State:** confirmed; proposed repair only. **Ownership:** feature timing hook is within Sound's reservation after approval; any shared/provider logging policy and its integration remain suite-owned.

### Concrete reproduction, already observed

Use only a synthetic marker:

```python
audit = Telemetry(sink=receipts.append)
with audit.stage("audit.synthetic_metadata", metadata={
    "authorization": "Bearer SYNTHETIC_FIXTURE_NOT_A_SECRET"
}):
    pass
```

**Expected:** a receipt/sink boundary used for provider/tool requests masks authentication fields. **Actual:** metadata is deep-copied without sanitization into both in-memory receipts and the optional sink. **Impact:** callers must not forward raw provider headers or tool payloads into this hook. No actual credential was used in the reproduction; the current feature-generated metadata contains only group kind/ID. The docstring is not a redaction mechanism.

### Proposed regressions, not implemented

`test_telemetry_redacts_secrets_before_receipt_and_sink`:

- Supply synthetic nested Authorization/Bearer, API-key, cookie, password, access-token and refresh-token fields; require redacted values in **both** receipt storage and sink output.
- Preserve useful numeric counters such as `prompt_tokens`, attempt, duration and cache state. Avoid masking all fields containing the word `token` indiscriminately.
- Check success, exception and cancellation receipts. Do not copy original exception payloads/headers into diagnostics.
- Verify the caller's original metadata and full creator context are unchanged; sanitize a logging copy rather than deleting saved guidance.
- If a redactor is injectable, verify its default is safe and sink errors/redactor failures cannot write the unredacted fallback. Test only synthetic markers.

### Minimal remediation proposal

Introduce a tested redaction/allowlist boundary before the first receipt is retained or sent to a sink. Prefer an existing suite-owned sanitizer if its contract fits, or provide a safe feature default plus an injectable sanitizer. Structured credential-key handling should be explicit; document the limits of free-text detection. Keep exact full creator context in the authorized local project/request, with a separate redacted audit copy. Do not promise that arbitrary secrets hidden in free text can always be detected.

### Integration-safe workaround now

- Limit this hook to explicit scalar timing/cache/attempt/status metadata and opaque machine-generated IDs. Do not forward raw request objects, prompts, headers, cookies, credentials, tool outputs or arbitrary exception text.
- Do not interpret `sink=None` as protection: receipts still appear in the returned manifest.
- Model/provider/tool request auditing must wait for the suite's approved redaction boundary, or use an already reviewed sanitized log facility. Do not disable logging claims by fabricating empty “redacted” evidence.

## R3 — explicit-model-locality-validation

**State:** confirmed validation-path issue; proposed repair only. **Ownership:** suite/shared-runtime owner. `hinglish_cut/model_preferences.py`, runtime dispatch/provider policy and shared call sites are outside this feature reservation. Sound will not patch them.

### Concrete reproduction, already observed

```python
resolve_model(root, "planning_model", "synthetic-audit:cloud", "qwen3:8b")
```

**Expected:** strict local-only validation rejects a cloud model suffix on every selection path. **Actual:** a non-legacy explicit `requested` value returns before the later nonempty/local-suffix validation. **Impact:** explicit override validation is not a complete local-only enforcement boundary. Examined configured Sound defaults remain loopback/local, and the owned runtime starter sets `OLLAMA_NO_CLOUD=1`. This reproduction constructed no model/runtime and made no network call; it is **not evidence that production actually used a cloud model**.

### Proposed regressions, not implemented

`test_resolved_model_is_validated_after_precedence` in the suite-owned policy tests:

- Cover configured/default and explicit non-legacy selections across planning, Vision, meaning and embedding roles; reject empty, whitespace, wrong-type and disallowed cloud selections consistently.
- Preserve valid installed local selections and model-role precedence. Do not silently replace a rejected selection with another brain.
- At the dispatch layer, test allowed loopback provider origins and reject disallowed remote endpoints/aliases before a call is made. Exact policy belongs to the suite; a name suffix alone is not a complete provider guarantee.
- Use fake transports for policy regressions. Later actual acceptance must use configured local model/provider/weight revision receipts and normal app tool calls with no cloud fallback, no manually supplied model answers and no Codex intervention replacing choices.
- Keep authorized external stock/search/download/licensing APIs distinct from the LLM provider policy. Do not break legitimate asset access by confusing “local brain” with “no external asset services.”

### Minimal remediation proposal

Resolve precedence first and validate the final model selection once on **all** paths. Enforce local provider/endpoint policy in the shared runtime dispatcher rather than relying only on the UI, a model-name suffix or a runtime starter that may not own every running Ollama process. Preserve explicit failures and progress rather than silently selecting a cloud/fallback model. No policy implementation is authorized in this feature thread.

### Integration-safe workaround now

- The independent recommendation route can remain `CachedRankingIndex`-only with `allow_live_ranking=False`, so it cannot implicitly construct a model on ranking cache miss.
- Do not introduce arbitrary provider URLs or per-feature model overrides from model outputs or client payloads. The suite must own/verify the configured local dispatch path for its actual semantic stage.
- Keep real local-agent acceptance **pending** until the suite's runtime policy and serialized actual model tests are complete. Cached fixtures do not establish fresh reasoning or subscription-expiry continuity.

## Release / acceptance gates

| Gate | Current state |
| --- | --- |
| Delivered feature modules/tests | Frozen at 37 isolated checks; no repair code applied |
| Fresh Music/SFX recommendation integration | May continue with suite, without semantic checkpoint resume and without raw secret-bearing telemetry metadata |
| R1 checkpoint semantic repair | Proposed; needs specific subsequent owner request and bounded feature reservation |
| R2 telemetry sanitization repair | Proposed; needs specific subsequent owner request and feature/shared logger ownership agreement |
| R3 shared local-only policy repair | Proposed; suite-owned; no implementation authority transferred here |
| Genuine local-model acceptance | Pending serialized short then representative long runs through normal local tools; exact provider/model/revision/cache/intervention receipts required |
| Adobe/native acceptance | Suite-reserved; exactly one Adobe host, never Premiere and After Effects together |
| Time/resource guarantee | No long-form SLA or zero-breakage guarantee; acceptable processing budget and measured cold/warm RAM/VRAM baseline still absent |

Next authorized action for this feature thread is documentation/checkpoint handoff only. Preserve source media, prior results, all guidance and every recorded failure. Do not wake the owner or request the same boundary approval again from this thread; coordination will obtain/route any subsequent repair authorization.
