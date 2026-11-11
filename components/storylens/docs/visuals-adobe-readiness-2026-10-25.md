# Smart Visuals Adobe readiness — 25 October 2026

## Scope and current state

Read/plan audit of saved files only. No searches, models, renders, queue actions, service changes, Adobe interaction, installs or shared integration edits were performed. The suite owner retains panel/bridge/server, host adapter, packaging and Adobe UI ownership. No changes were made to original outputs or prior evidence.

The last Bisla job `f8096e4721ba` completed on **24 October 2026 at 02:04:08 IST**, with one saved passing identity choice. It is no longer queued. The project remains `partial`; completed research is not complete coverage or native insertion acceptance. No queued/running entries were found in the saved Smart Visuals job journals at inspection time; this does not establish other services/GPU jobs are idle.

## Exact saved choice manifest

- Project: `A:\Full Drive\remove silence\output\visuals\20261024-003114-115cb1\001-0000-5d6d33916d58-Shorts-12\visuals-project.json`
- Project SHA256: `51e3c532fc049c5168384c02b8d8b7979614e23151033ff519c995396702c415`
- Full manifest: `A:\Full Drive\remove silence\docs\visuals-asset-choice-manifest-2026-10-25.json`
- The JSON lists every slot, exact media ID, original URL, source page, local file, stored visual fingerprint and separately measured raw-file SHA256, dimensions, timing, provenance, saved evaluation, profile source, chosen state and XML source paths.
- **44 choice occurrences across 16 banks; 29 unique local assets/content hashes.** Repeated team mentions reuse assets, so 44 is not a distinct-image count.
- All 29 unique assets exist. All 44 stored image fingerprints match recomputed 96×96 RGBA pixel fingerprints. The project’s field named `sha256` is **not a file-byte hash** for images; this audit separately records actual raw-file SHA256. These readings establish present-file identity and consistency with saved deduplication fingerprints, not a prior raw-byte baseline, likeness, rights, factual relevance or visual quality.
- All 44 choices have saved passing checks and valid profile-route constraints where a profile was used. These are prior local-model receipts, not a new visual review.
- **0 selections; 0 selected rendered clips.** Nothing is accepted for timeline insertion.
- Saved sample: 404 × 720, 30 fps, 47.433 seconds, original audio on black, five-option short-form setting.

| Slot | Keyword | Bank | Seconds | Saved choices | Selected |
|---|---|---|---|---:|---|
| 0 | Kolkata Knight Riders | identity | 1.00–3.02 | 5/5 | No |
| 1 | Delhi Capitals | identity | 3.36–6.04 | 5/5 | No |
| 2 | Kolkata Knight Riders | identity | 6.80–8.56 | 5/5 | No |
| 3 | Kolkata Knight Riders | identity | 8.68–11.62 | 5/5 | No |
| 4 | Chennai Super Kings | identity | 14.04–15.52 | 5/5 | No |
| 5 | Chennai Super Kings | identity | 15.56–18.56 | 5/5 | No |
| 6 | Suresh Raina | evidence | 19.76–21.34 | 0/5 | No |
| 7 | Suresh Raina | identity | 19.76–21.34 | 5/5 | No |
| 8 | Gautam Gambhir | evidence | 26.70–27.46 | 0/5 | No |
| 9 | Gautam Gambhir | identity | 26.70–27.46 | 3/5 | No |
| 10 | Jacques Kallis | evidence | 29.62–32.62 | 0/5 | No |
| 11 | Jacques Kallis | identity | 29.62–32.62 | 2/5 | No |
| 12 | Manvinder Bisla | evidence | 35.56–38.20 | 0/5 | No |
| 13 | Manvinder Bisla | identity | 35.56–38.20 | 1/5 | No |
| 14 | Jacques Kallis | evidence | 39.86–41.88 | 0/5 | No |
| 15 | Kolkata Knight Riders | evidence | 44.84–47.32 | 3/5 | No |

## Bisla result and remaining gaps

- Bisla identity (slot 13): `web:829fce3a56ba6819`, `references/282637676da6f07e82c2.jpg`, stored 96×96 RGBA fingerprint `282637676da6f07e82c2150d9170f8b6401a0ee7c8cb1c8d1ece18f0fdb64e16`. Source: https://www.timesnownews.com/sports/cricket/meet-manvinder-bisla-player-who-won-2012-ipl-trophy-for-kkr-played-for-india-in-u19-world-cup-article-109369858 .
- Its latest saved comparison uses the genuine named profile route https://www.cricinfo.com/cricketers/manvinder-bisla-27280 and cached numeric CDN headshot `cache/visuals/media/040542d42848247b1a50.png`. Saved local judge: `storylens-planner:9b-q6`; `same_person=yes`, KKR uniform `match=yes`, confidence `clear`. The earlier article containing “high-profile” is archived as a rejected reference; it is not this receipt.
- Bisla is **1/5**, not fully resolved: four additional identity choices and the separate factual bank are missing. No new human visual approval or native check was performed.
- Empty evidence banks: Raina 71-run claim (slot 6), Gambhir first-run claim (8), Kallis/Bisla partnership (10), Bisla 89-run claim (12), Kallis 69-run claim (14). These are saved transcript/planning claims, **not verified cricket facts**. Do not silently repair numbers or use a portrait as proof.
- Other shortfalls: Gambhir identity 3/5; Kallis identity 2/5; KKR trophy evidence 3/5. Seven banks meet five choices; nine are incomplete.
- Logos prove team identity, not a specific historical match, score or victory. The Delhi Capitals bank also needs historical-team-name/logo review against the intended event before acceptance; this audit does not establish the event year.
- Saved model notes for Bisla include both `quality_ok=true` and a face-visibility concern. Preserve both and require manual inspection; do not describe the saved yes as certainty.
- Prior downloads encountered inaccessible sources/expired certificates; do not weaken TLS or fabricate missing options.

## Contracts to report to suite owner — no shared edits

1. **Manual banks: two long, five short.** `pipeline.run` currently accepts only `options_per_moment` 2 or 5, and collection uses that setting. `review_ui.py` still prints `/5` and computes readiness against five, even for a two-choice project. A future two-option example would be mislabelled; no new example was generated in this audit.
2. **Raw assets versus baked presentation.** The references are plain downloaded images with their source pixels. `render_slot` currently calls `popup_card(..., slot["label"])` for photos, adding a name label/frame; that conflicts with the new no-added-lettering requirement. Do not use that legacy popup render as the plain-asset Adobe contract. Source logos/jersey text are part of the original image, not added lettering.
3. **Bank handoff is not implemented by the old selected-only contract.** `references.capcut_spec` returns `options: []`, `selected_only: true`, and only slots with a saved `clip`. `write_outputs` likewise exports selected rendered clips into XML. Both omit the unselected choice bank. The new panel must explicitly consume the raw-asset manifest and preserve the owner selection; do not auto-select option 1.
4. **Native editability.** Existing popup/cutout motion is baked into media by the local renderer. An XML containing that media does not prove native asset layers/keyframes, correct alpha, in/out timing, scale or motion in Premiere. Native adapter decisions and acceptance belong to suite owner.
5. **Media types.** All 44 current choices are images. B-roll is videos only; keep its candidate bank separate. Smart Visuals legacy code can handle video, but that is not evidence these image banks satisfy a B-roll contract.
6. **Image hash semantics differ from file hashes.** Original `sha256` is a normalized 96×96 RGBA fingerprint for images (`references.py`), whereas video entries use file bytes. The suite handoff must use the separately measured raw-file SHA256 when verifying actual imported bytes and preserve the original fingerprint without relabelling it as an integrity baseline.
7. **Identity and source fields must survive.** Keep entity key + QID, media ID, raw original spelling, source page, asset URL, actual local hash, license metadata, bank role, timing, profile/uniform receipts and explicit selection. Display names alone are insufficient. Preserve all original saved outputs.
8. **No ready insertion yet.** Existing `VISUALS_SEQUENCE.xml` has no chosen visual overlays. An XML file on disk, prior prepared CapCut spec, or a complete research status is not a live Adobe acceptance receipt.

## Evidence and its limits

- `cache/app/visuals-jobs/8768/f8096e4721ba.json`: completed final Bisla retry and prior diagnostics.
- Current project JSON and the hash-checked manifest above: latest data state.
- `output/visuals/reliability-evidence/validation.json`: earlier snapshot says Bisla queued and 43 entries; retained unchanged as historical evidence, **superseded for current status** by this audit.
- `output/visuals/reliability-evidence/unit-checks.txt`: prior 60 focused tests passed; no new tests run.
- `compact-picker-final.jpg` and `raina-csk-options.jpg` in that evidence folder: earlier live UI samples, not proof of the final completed Bisla result or current Adobe panel.
- Prior interruption/draft-preservation checks are recorded there. Native Premiere/CapCut playback, layer insertion and final motion remain unverified.

## Safe next tests — plan only

1. Suite owner reviews the shared Adobe contract first; keep the existing Premiere instance and do not open AE. No models/renders or searches until separately authorized and the shared queue permits them.
2. Inspect existing full-size saved Bisla, Raina, Kallis and Gambhir images in the panel, checking person/team/era and absence of newly added lettering. Resolve the quality concern through visual review.
3. Load this preserved short-form manifest into the choice panel; check five-target banks, explicit user selection and No visual. Verify incomplete banks stay honest. A long-form saved or later authorized two-option sample must display 2, not 5.
4. After owner selection, suite owner inserts one existing image at a time into Premiere through the actual panel. Verify file hash/source identity, spoken-time placement, correct duration, no unwanted label/card, alpha where relevant, and safe scaling. Record actual host receipts and screenshots. No automatic insertion is authorized by this read/plan task.
5. If animated insertion is requested, inspect the actual host result for smooth movement and distinguish native keyframes from baked media. Do not require an export or open another Adobe host.
6. Address empty factual banks separately using the local pipeline only under new search/model authorization. Retain raw speech; uncertain names, numbers and event dates must remain explicitly unresolved.
7. Repeat on a different real video only after the first scoped panel acceptance. Never infer all-video reliability from this file audit.

## Bounded implementation checkpoint — 25 October 2026

The coordinator subsequently released the raw manual-bank work, deferred it, then explicitly released this same narrow scope again. The read-only findings above remain historical evidence. The following changes supersede the earlier statement that these feature hooks were missing; shared/native integration is still pending.

Changed implementation paths only:

- `hinglish_visuals/source_bank.py` — new deterministic SOURCE-bank API, schema `storylens.smart_visuals.source_bank`, version 1.
- `hinglish_visuals/review_ui.py` — displayed target and ready/partial status now use saved `options_per_moment` (2 long, 5 short). Existing choices and incomplete banks are preserved. Legacy projects without the setting retain five. No redesign.
- `tests/test_visuals_source_bank.py` — 10 CPU-only synthetic contract tests. They do not use or demonstrate semantic local-agent planning.

No shared panel/server/bridge/host adapters, collectors, captions, publishing, packages, runtime/model configuration, originals or legacy rendering paths were modified. No service restart, search, inference, GPU work, render or Adobe action was started. The existing legacy pop-up name/card route remains unchanged and must not be used for the plain-source handoff.

### Integration hooks for the suite owner

Import from `hinglish_visuals.source_bank`:

```python
build_source_bank(project_file, selections=None)  # read-only manifest in memory
export_source_bank(project_file, new_target, selections=None)  # exclusive new JSON file
selected_source_assets(manifest, project_file)  # validate snapshot, return raw image records
```

`selections` maps saved slot indices to media IDs, **not display positions**. Omitted slots preserve an existing saved manual choice; `None` explicitly leaves a slot unreviewed; `''` explicitly records `no_visual`; an offered media ID selects only that exact bank's image. Previously null `chosen` cannot prove an explicit No visual decision, so it is unreviewed. This new API does not persist changes to the original project; the suite must retain the returned selection state rather than conflating null/unreviewed with rejection. It never automatically chooses the first option or inserts into an editor.

Every bank retains entity key/QID and raw name, role (identity/evidence), exact spoken text, unverified requested claim, source queries, frame/second anchor, target/shortfall and explicit decision. Stable bank/asset IDs are deterministic and independent of selection. Every eligible image retains source-page/download provenance, original credit/license metadata, prior model verdict/context, actual file-byte SHA256, and the separately labelled historical normalized-image fingerprint. Existing saved model verdicts are not new reviews, factual guarantees or rights clearance.

Validation rejects out-of-project/absolute/contradictory source bindings, missing/unreadable/unsupported sources, non-passing checks, invalid saved profile routes, fingerprint changes and mismatched subject bindings. Unsupported videos remain unavailable in this image-only contract; B-roll's video banks remain separate. Rejected entries retain their ID/reason; incomplete and empty/no-match banks remain present. Selecting an unavailable/foreign ID fails without writing an artifact or choosing a replacement. Duplicate bank/media identities and invalid timing are rejected. The old normalized `sha256` is not used as a raw-file integrity baseline.

Before returning selected sources, the hook rereads the original project and files and compares the full typed manifest, project digest, identity, timing, bytes and selections. Changed/stale/tampered manifests fail with an action to re-export. Raw handoff records specify `presentation=plain_source`, `add_text=false`, `add_card=false`, `auto_insert=false`; they reference original downloaded files and include the saved verification/provenance. The hook never invokes `render_slot`, crops, cards, name labels, inference or a host. Native placement/motion remains exclusively suite-owned. Existing source lettering (for example a jersey sponsor or logo) stays in the original bytes.

### Golden artifact and CPU evidence

- `output/visuals/reliability-evidence/source-bank-v1-golden.json`: actual SOURCE-bank v1 export of the preserved Shorts 12 project, with **16 banks, 44 choice occurrences, 29 unique files, 16 unreviewed decisions, zero selections**. It was generated by the production deterministic exporter, with no new semantic decisions.
- Golden manifest SHA256: `0e65fbc79707de4f12cd00a935b366e49333de2c6ead778041b66f0c3cfc3756`.
- Original project SHA256 still `51e3c532fc049c5168384c02b8d8b7979614e23151033ff519c995396702c415`; original bytes and credits were not rewritten. The revalidation hook returns an empty selected list, as required.
- `output/visuals/reliability-evidence/source-bank-v1-validation.json`: counts, hashes, unchanged-source and no-new-model/search/render/host flags.
- `output/visuals/reliability-evidence/source-bank-v1-cpu-checks.txt`: **42 tests passed**, covering the 10 source-bank tests plus existing recovery/reference/grounding components. These use tiny synthetic fixtures and mocked semantic/source decisions; they are **not actual local-agent acceptance**. Selection fixture tests are not owner selections of the real 44 entries.
- TDD failures were recorded before implementing the count/API contract and before fixing the lineage/version-type cases: `tmp/visuals-source-bank-red.txt` and `tmp/visuals-source-bank-lineage-red.txt`.
- The earlier 9-test passing log `tmp/visuals-source-bank-green.txt` is preserved unchanged. No old acceptance evidence is relabelled.

Golden export/file checks do not demonstrate that the current live panel consumes this schema, carries the user choice correctly, or inserts the same pixels/anchors into Premiere. Those remain pending actual suite integration and native acceptance. Bisla remains only 1/5; the five empty evidence banks and uncertain historical claims remain unchanged.

## Subscription-independent production-route audit — static/files only

Inspected Smart Visuals source plus its immediate configured model clients without starting a runtime or calling a model. The raw-source export requires neither a model nor a Codex/ChatGPT session; it is local Python/file validation. The normal semantic route is CLI/application -> `pipeline.run` -> local transcription -> local summary/visual planning/name resolution/ranking -> external retrieval -> local pixel checks -> manual banks. The typed SOURCE export preserves that saved result and performs deterministic bookkeeping only.

Effective saved model role selection at this audit:

| Role | Local Ollama alias | Saved repository/revision |
|---|---|---|
| Planning/meaning | `storylens-meaning:14b` | `Qwen/Qwen3-14B-GGUF`, `530227a7d994db8eca5ab5ced2fb692b614357fd`, `Qwen3-14B-Q4_K_M.gguf` |
| Vision | `storylens-planner:9b-q6` | `unsloth/Qwen3.5-9B-GGUF`, `3885219b6810b007914f3a7950a8d1b469d598a5`, `Qwen3.5-9B-Q6_K.gguf` |

These are saved registry/configuration records, **not a fresh runtime/version attestation**. The fallback manifest records Ollama `0.40.5`, native API, runtime `b11011`, planning alias/revision above; these are also saved metadata, not a current server query.

- `brain.OllamaBrain` and `evaluator.VisionModel` default to `http://127.0.0.1:11434/api/chat` and disable environment-proxy use. No OpenAI/ChatGPT account token, Codex service, subscription check or external LLM endpoint was found in those direct production paths.
- `open_brain(auto)` explicitly logs an Ollama-start failure and falls back to local `LocalBrain` / bundled `LocalLLM`; it is a **different local backend**, not a cloud answer. The currently saved fallback manifest selects the imported local 14B model. Exact-backend acceptance must record the actual branch instead of assuming the alias.
- The local semantic adapter's `/v1/chat/completions` path is an OpenAI-compatible API on loopback; that protocol name is not use of OpenAI's hosted API. Native llama.cpp uses an ephemeral local server credential. It must not be logged or granted outside loopback.
- Manual review collection calls `open_evaluator(..., 'vlm', ...)` and requires a real local VLM. Strict identity/team/document checks reject type-only fallback approval. Legacy non-review modes still expose auto/CLIP/off paths and must not be substituted for this bank's acceptance.
- Transcription is delegated through `hinglish_broll.pipeline.transcripts_for` to the configured semantic speech backend (`swift` in that route); its full downstream runtime was not revalidated here. Local speech/model/runtime availability must be checked in the suite benchmark.
- `openai/clip-vit-base-patch32` is the name of locally executed CLIP weights, not a cloud inference request. Its model-folder helper can fetch missing weights from Hugging Face unless offline; required artifacts must be provisioned before claiming offline readiness. No weights were downloaded now.
- Internet retrieval remains external: Agent Reach's public adapter uses hosted Exa search and Jina/web reads; DDGS uses Google/Bing/Brave; Wikipedia/Wikidata/Commons, source publishers and optional configured stock APIs serve assets. Their network availability, quotas, credentials and licenses are **separate from the local LLM brain**. Source-capture tooling also needs its local browser runtime. Saving repositories alone does not remove these dependencies. No Codex built-in search tool is an implemented runtime fallback in the inspected adapter; an upstream help string mentioning such a tool is only text.

### Route gaps to the suite owner — report only, no out-of-scope patches

1. Planning caches include model name/system/data/schema and some runtime branches include revision, but Ollama planning/Vision caches do not consistently bind the installed model digest/runtime version. Reusing an alias after changing weights may reuse older cached decisions. Record model digest/version and cache lineage before actual acceptance.
2. Existing JSON answer caches, progress logs and saved evaluations are useful evidence but not a complete per-job ledger of provider/version, prompt/tool request, executions/retries/outcome, cache origin and Codex intervention flags. The new SOURCE artifact truthfully marks no new inference/review, but cannot invent missing old receipts. Suite-owned logging needs redacted structured receipts; never log local bearer tokens, stock keys or session secrets.
3. Default model resolution rejects `:cloud` names; the shared resolver returns an explicitly non-default requested model before that check. This is a **potential configuration guard gap**, not evidence of an actual cloud call in the current configuration. The suite should enforce a local-only provider policy and verify the loaded alias/digest. No shared model code was changed here.
4. Automatic local-backend fallback is announced but can change speed/model capability. For baseline acceptance, select and log the configured local branch explicitly; use any fallback only as an explicitly labelled recovery result. No handwritten replacement plans or cloud fallback may make a failing semantic run appear successful.
5. Future local-controller tooling must still preserve the owner workflow: deterministic code handles hashes, timing, binding, checkpoints and retry bounds; the configured local models handle semantic extraction/identity/context/selection recommendations. SOURCE export must not turn deterministic fixture answers into evidence that the local planner succeeded.

## Scheduled local short/long benchmark plan — not started

Suite owner schedules serialized resources and retains exclusive host ownership. Premiere Pro and After Effects must **never** be open together. No blind closure/restart/save of an unsaved owner project. No new model/inference/render/native work was started for this checkpoint.

1. **Short first:** use an owner-approved existing spoken sample through the normal Storylens request, short-form target five. Let the configured local planner identify subjects/claims and tools retrieve/check sources. Preserve failed names, team mismatch, unavailable fact evidence and partial results. Record cold versus cache-hit lineage, exact local provider/model digest/runtime, prompt/tool requests and redacted outcomes. The older Shorts 12 result can be a comparison, not fresh-agent success.
2. Observe total and stage elapsed time, cache hit/miss, downloads/retries, peak laptop RAM/VRAM/CPU, model failures and remaining shortfalls. No SLA or throughput claim exists yet. Run one controlled continuation/error case without stopping unrelated jobs or synthesizing successful answers; preserve checkpoints.
3. Through the actual integrated panel, manually choose one of the local-generated bank options, optionally choose No visual for another, export the typed bank, and have the suite hook revalidate original bytes and timeline binding. Suite alone verifies actual insertion in its reserved Premiere host. A ready JSON file is not acceptance.
4. **Long next, only after short acceptance:** select an owner-approved representative long talking-head input, using its real length and names/claims; use target two. Keep the local model responsible for semantics and verify the UI shows 2/2 or honest shortfall, not /5. Profile memory and context/retrieval/recovery growth; do not pre-supply model answers, force ideal selections or silently swap to a shorter source to pass.
5. Repeat any repaired failing flow with the same normal app request and actual configured local models. Record operator interventions separately. No publishing, new account grants, spending or unrelated generation is part of this Smart Visuals scope. Even successful short/long samples would be representative evidence, never a zero-breakage guarantee.

## Production review/result connection checkpoint — 25 October 2026

The coordinator next released the feature-owned connection from ordinary completed results to the SOURCE manifest and explicit decisions. This checkpoint adds **no shared transport, server/panel/host adapter, inference or cache-policy change**. Protected final-review locality/cache/telemetry findings remain queued; they were not silently repaired.

Changed in this checkpoint: `hinglish_visuals/source_result.py` (new), `hinglish_visuals/report.py`, `hinglish_visuals/review_ui.py`, and `tests/test_visuals_source_result.py` (new). The prior `source_bank.py` and 42-test evidence remain preserved. No code changes were made to `pipeline.py`, shared files or the legacy renderer.

### Ordinary production path

`pipeline.write_outputs` already saves `visuals-project.json` and calls `report.write_report`. That existing call now runs `ensure_source_result` for a completed/partial manual-review project whose in-memory data matches the saved file. It emits a versioned immutable manifest under the project's **new** `source-banks/` directory and a feature-owned `active.json` pointer. Reopening a valid result reuses the active snapshot and its decisions. A collecting or unbound/unsaved report does not advertise a raw manifest. A stale/bad snapshot is shown as Source assets unavailable using shared plain-message/Technical details presentation; it is not silently rebuilt as though decisions had survived.

The feature review exposes a **Source assets** JSON link plus `window.storylensVisualsSourceBank.request()`. That request captures only the actual existing review-control draft (media IDs or empty No visual values); it never chooses a candidate itself or sends a request automatically. The existing **Save & rebuild/editor controls retain their legacy rendered-clip route**. The new raw hook is separate: the suite must connect its authenticated transport and typed panel; it must not treat the legacy save as saving raw decisions, or its XML as the raw-asset bank. Raw manifest state is not painted as a legacy rendered choice. This separation is intentional while shared integration remains suite-owned.

### Exact feature API and request contract

Import from `hinglish_visuals.source_result`:

```python
ensure_source_result(project_file)
apply_source_request(payload)
```

The first function returns the active manifest descriptor and emits the initial unreviewed bank only if none exists. The second validates the active snapshot and applies only explicit incoming decisions, retaining all other states from that manifest. It writes a **new immutable decision manifest** and updates only the new active pointer. Old snapshots, original project bytes, legacy `chosen`/`clip`, source pixels, credits and XMLs are preserved. It returns selected raw records with `auto_insert=false` and `native_acceptance=false`; it does not insert or render anything.

Payload fields are:

```json
{
  "type": "smart_visuals.source_bank.select",
  "version": 1,
  "project_path": "absolute visuals-project.json path from this result",
  "base_manifest": "absolute manifest_path returned by this result",
  "base_manifest_sha256": "exact manifest_sha256 returned by this result",
  "choices": {"saved slot index": "actual clicked media ID, or empty string for No visual"}
}
```

An empty choices mapping makes no new decisions; omitted slots retain the active bank's state. It is not permission to select the first item. An explicit `null` value resets only that slot to unreviewed, as supported by the core API. A foreign/unavailable media ID, stale open review, changed byte binding, changed saved project/model lineage or unsupported request fails before advancing decisions. Reopening an older review cannot overwrite a later active decision. Slot and file counts remain 2/5 as configured, with honest empty/partial banks.

The module provides an in-process critical section. The suite transport still owns authentication, allowed-project validation, cross-process serialization and native action authorization. The payload is **not** a new HTTP route. No listener or arbitrary agent execution was added. Invalidation covers the exact saved project (including any changed saved model/provider/digest receipt), not a model alias changed externally without a receipt; effective runtime/cache identity attestation remains the shared gap already recorded above.

### Current concrete artifact/payload and future local run

- `output/visuals/reliability-evidence/source-result-v1-golden-descriptor.json` contains the exact emitted descriptor, a concrete empty-choice selection payload, existing input path, explicit planned settings, normal-app request text, and no-execution flags. **The selection payload and future request were not executed.**
- Actual emitted manifest: `output/visuals/20261024-003114-115cb1/001-0000-5d6d33916d58-Shorts-12/source-banks/source-bank-v1-8421aaa56e2e0a8fc18973321c0bf17a754de0b0dc2082572cdd691d98447b2e.json`.
- Manifest byte SHA256: `8421aaa56e2e0a8fc18973321c0bf17a754de0b0dc2082572cdd691d98447b2e`. Its JSON data equals the previous golden artifact. The old text-mode export used platform line endings; the new immutable snapshot uses LF bytes, so those artifact byte hashes differ. This does not change any source image or decision.
- The current descriptor records **0 selected**, all 16 decisions unreviewed, and `native_acceptance=false`. All prior top-level files in the real project folder were hashed before/after and remain unchanged. Only the new feature-owned directory/pointer/snapshot was added; the existing report was not regenerated or overwritten.
- The actual selected source is still `A:\Full Drive\remove silence\All Shorts\Shorts 12.mp4` (file exists). Planned normal-app request: run Smart Visuals using its audio on black, configured local planning/Vision, five real-image options per spoken subject, correct team/event context, honest missing matches, manual choices, and raw banks without added labels/cards or automatic placement.
- Concrete planned pipeline settings recorded in the descriptor are `output_format=instagram_vertical`, `brain_choice=ollama`, `evaluator_choice=vlm`, `review_options=true`, `options_per_moment=5`, `black_background=true`, `presentation=popup`. Popup here is the preserved legacy project setting; the SOURCE handoff bypasses its renderer and adds no label/card. The suite must use the **normal Storylens request** for semantic acceptance, not inject a hand-authored plan or run this deterministic result-only hook as a substitute. The future run must get a **new actual result/base manifest**, not reuse the old bank and claim new planning succeeded.
- Effective saved local aliases were read again as `storylens-meaning:14b` and `storylens-planner:9b-q6`; no model/server query was made. Their actual provider/digest/runtime/cache lineage must be recorded in the scheduled run by suite-owned hooks.

### CPU/component evidence and pending acceptance

`output/visuals/reliability-evidence/source-result-v1-cpu-checks.txt` records **50 passing tests**: the prior 42 plus eight new result/production integration tests. Tests use synthetic saved state, tiny fixture images, mocked legacy XML output and a Node VM DOM fixture. The actual review SCRIPT is executed in that fixture: it starts with no decisions, produces only the clicked media ID, and then produces empty string for No visual. Transport throws if called; no background model/network/native work is allowed. The resulting synthetic click payload is exercised through the production feature API. This is meaningful component evidence, **not a real user/local-model/native acceptance receipt**.

Tests additionally cover the ordinary existing `write_outputs` -> report -> manifest path, unchanged legacy return/credits/evaluation outputs, explicit persistence/reopen, stale open-review rejection, unchanged project/source bytes, two/five targets, invalid-choice non-advancement, changed source or saved model lineage, collecting/unsaved report suppression and shared error presentation. TDD red evidence: `tmp/visuals-source-result-red.txt`; earlier intermediate passing component logs are preserved in `tmp/visuals-source-result-green.txt` and `tmp/visuals-source-result-component.txt`.

No searches, inference, GPU work, media rendering, host interaction, service restart or publication was started. No mocks or fixed decisions were installed in runtime. Current running services may still have older imported modules; the suite alone schedules a normal reload and resource release. Remaining acceptance: authenticated shared transport and typed manual panel -> genuine configured-local-model normal-app short request -> actual owner selection -> original raw image insertion and timing/source verification in the suite's reserved Premiere instance. Long-form follows short acceptance. Premiere and After Effects must never be open together.

## Leased completed-job transport helper — 25 October 2026

Suite handshake in `docs/plugin-work-in-progress-2026-10-25.md` reserved exactly two new paths to this owner. Both were checked absent before creation:

- `hinglish_app/visual_source_transport.py`
- `tests/test_visual_source_transport.py`

Only those implementation/test paths were added in this phase. This readiness note and dedicated CPU evidence were updated separately. No edits to `editor_panel_http.py`, `server.py`, panel JS, host adapters, existing source-result helpers, model/runtime code or protected final-review findings. No listener, token, permission grant or new arbitrary-path media endpoint was created. All mutable test job/results/decisions were isolated temporary fixtures; no actual application job/result or owner decision was changed.

### Suite integration contract

```python
from hinglish_app.visual_source_transport import VisualSourceTransport

transport = VisualSourceTransport(state)  # existing AppState: root + snapshot(engine_job_id)
descriptor = transport.describe(engine_job_id, project_path=None)
updated = transport.select(engine_job_id, source_request_payload)
media = transport.resolve_media(engine_job_id, project_path, active_manifest_sha256, asset_id)
```

Use the **engine/application job ID**, not a panel wrapper ID or standalone research/recheck journal. The route must first use the suite's existing authorization/license/context binding and then supply its trusted AppState. The helper itself does not authorize users, select Adobe hosts or install HTTP routes. Route errors should use existing `user_messages.failure(error, feature='Smart Visuals')` and `exception_status(error)` so ordinary messages and redacted Technical details remain separated. Do not expose tracebacks or add token/security settings.

`describe` accepts only an actual snapshot with matching job ID, `mode=visuals`, `status=complete` and a saved result folder/page under the canonical application `output/visuals` root. It does not accept client-supplied job objects. A single-result `report.html` binds its exact sibling `visuals-project.json`; a multi-result `index.html` binds only the child projects explicitly named by its `result.json` receipt. It never recursively treats arbitrary JSON files under output as results. A broad output root, missing/foreign project, wrong mode, running job, changed/escaping path or unsaved/collecting review fails before source-bank state is created. Multi-result callers must choose one receipted project explicitly.

The descriptor contains the core active source-bank fields plus `job_id` and typed `banks`. It retains identity/provenance/timing/manual-decision metadata and honest 2/5 target/shortfall state. Only supported **raw** PNG/JPEG/WebP choices are exposed as transport choices, with their checked media descriptor; other formats stay in `unavailable_choices` without rewriting the original manifest. All descriptors remain `auto_insert=false`, `native_acceptance=false`. Availability is a source-file/contract state, never model correctness or native acceptance.

`select` takes the existing exact payload emitted by `storylensVisualsSourceBank.request()` (`type`, integer version, project path, base manifest path/hash, explicit choices). It binds the project to this completed job again, checks current baseline through the core helpers, and validates both new and inherited selected media against the transport allowlist before calling `source_result.apply_source_request`. An empty update cannot smuggle a previously selected unsupported image into a handoff; explicit No visual can still clear it. Invalid/stale/foreign choices do not advance the active pointer. The result includes typed banks and only actual selected raw-source records; it never calls an editor, infers a replacement or picks option 1.

`resolve_media` accepts **offered asset identity + job + project + active manifest hash**, not an arbitrary media path from the request. It rebinds the actual job/result and active source manifest, checks membership, canonical project containment, image MIME/extension, file length and raw-byte SHA256, then returns `{asset_id, media_id, path, sha256, bytes, mime}` for the suite's controlled response. Source paths inside a bank are not authorization to expand the existing `/api/panel/media?path=...` route. The suite must wire a separately bound call to this helper, retain existing auth, and serve only the returned descriptor. Route streaming/file-lifetime and any subsequent native import remain suite-owned acceptance surfaces.

Every operation holds a **separate short per-project CPU/file lock** under `cache/app/visual-source-locks`, with an in-process lock and Windows byte lock / POSIX flock using the existing project transaction pattern. This is not the GPU or publishing lock. Cross-process contention is bounded (default five seconds; controlled constructor limit), and a blocked file transaction returns a keep-choices/try-again message rather than starting duplicate work. Both baseline comparison and apply run inside that transaction. Calls that bypass this transport do not inherit its cross-process guarantee; the shared route must consistently use it for raw decisions.

### Initial TDD/CPU gate and limits

- `tmp/visual-source-transport-red.txt`: missing-helper failures before implementation.
- `tmp/visual-source-transport-green.txt`: initial eight transport tests passed.
- `tmp/visual-source-transport-allowlist-red.txt`: initial functional-gate regression for an inherited unsupported choice, followed by the scoped allowlist repair in the leased helper only.
- `output/visuals/reliability-evidence/visual-source-transport-cpu-checks.txt`: **59 tests passed** (nine new transport tests plus the prior 50 feature/component tests).
- Tests cover completed-job/result binding, foreign/outside/arbitrary project rejection, active path/hash binding, unavailable choices, explicit No visual, source changes, multi-result receipt restrictions, raw MIME/hash membership, and stale-owner updates. Two actual spawned CPU test processes submitted different decisions from the same baseline; exactly one saved and the other was rejected as stale. All fixtures are temporary and synthetic. No real local model answer or host receipt was used or manufactured.

The initial helper loop is complete. No extended adversarial/final-review locality/cache/telemetry repair pass was initiated; the coordinator's protected findings remain queued. There is still **no wired route, deployed service, genuine local-agent run, live panel media check or native insertion acceptance** from this phase. Suite owns the next authenticated route/JS wiring and serialized genuine local-model application run, followed by the one-host native gate. Existing unresolved Bisla/scorecard/historical-claim limits remain unchanged.

## Separate bounded post-implementation tester/security phase

After the 59-test implementation handoff, the coordinator explicitly requested a small final probe of this helper only. The following phase was performed against the unchanged handed-off helper, **after** the initial TDD/allowlist repair loop. No implementation/test files were edited, no broader project or protected locality/cache/telemetry audit was resumed, and the 59-test suite was not rerun merely for this phase.

| Fixture probe | Expected | Actual |
|---|---|---|
| Job changes from complete to running after the review baseline is issued | Reject selection; preserve pointer and asset | ValueError rejection; both preserved |
| Same completed job receives a different project's path under output | Reject foreign binding before using that project | ValueError rejection; original pointer and asset preserved |
| A raw filesystem path is supplied as the asset identity | Reject instead of serving a path | ValueError rejection; pointer and asset preserved |
| Stored manifest subject identity is changed without a matching sealed baseline | Reject media resolution | Snapshot-change rejection; pointer and original asset preserved |
| Two spawned CPU fixture processes submit different decisions from one baseline | Exactly one saves, one rejects as stale | Focused test passed and asserted the saved/rejected pair |

Evidence: `output/visuals/reliability-evidence/visual-source-transport-final-probe.json` records each expected/actual outcome, preservation result, diagnostics and helper/test SHA256. `visual-source-transport-final-concurrency.txt` records the separately rerun **single** cross-process test. The final helper/test hashes match the initial handoff checkpoint. No new product defect was exposed in these performed cases and no post-implementation product repair was made.

The first probe harness attempt stopped before any helper action because TEMP pointed to a restricted sandbox directory. The unchanged product probes were rerun with TEMP/TMP set to the authorized workspace `tmp`, matching the earlier CPU-test setup. This was a harness setup correction, not a hidden product fix or permission escalation; it is recorded in the ledger.

Limits: temporary synthetic data and source fixtures only; no actual job mutation, model/network calls, media rendering, native UI or service restart. These checks do not establish exhaustive security, symlink/race resistance, route streaming/file-descriptor lifetime safety, authenticated context/host binding, genuine local-model quality or native insertion. Those suite/final-review surfaces remain pending; any subsequently discovered protected final defect requires a new owner request before repair.

## Actual local-agent E2 run — read-only audit

Chat `542f7a0a2f764b90` / engine `4666cad90fe1`, profile Gaming, original `A:\Full Drive\thisis.vineet\e2\e2(1).mp4`. The normal visible-chat request and retry/terminal receipts are in `output/plugin-validation/visuals-normal-chat-*` and `visuals-first-dispatch-*`. The suite's terminal snapshot confirms engine **complete**, chat **needs_review**, `research_complete=true`, `partial=true`, `review_required=true`. The earlier running snapshot is historical, not the final state.

Actual result: **0 qualified choices / 2 five-target subjects; 0 selections; no native insertion**. The saved plan retains the speech's housing context, but “PG” was resolved to **Project Gutenberg / Q22673 / free digital library**. The wrong name then appeared in housing searches. The other subject was generic “Flat” -> apartment. There were 165 saved retrieval-candidate occurrences, 40 candidate-check entries and 38 saved Vision rejections; these are not 165 useful or unique images. No accepted thumbnails/images exist to inspect or approve. Credits correctly say `(none)` because nothing was used.

Observed artifact interval: job creation 05:34:22 IST to saved partial research 05:41:43 IST, about **440.3 seconds**. This is one actual short-source observation, not a promised runtime/SLA. The black-background request was missing from the actual dispatched options; saved `black_background=false`. The suite exclusively owns that argument propagation repair and same-chat repeat. Nothing in this audit changes/retries the job.

### PG root-cause evidence and limits

- Input quote remains **“To main kahaan ruka hoon? PG mein.”** Its saved meaning already says **“PG (paying guest) accommodation.”** Thus the trace does not support an acronym transcription error or word-anchor corruption as the primary cause. Audio/ASR was not rerun; this is based on the actual stored quote/meaning, not a claim of perfect recognition.
- Only two **exact query-derived** Wikidata cache files were read (PG and Flat), with no brain-cache sweep or network call. Raw source responses and hash/index are preserved in `output/visuals/reliability-evidence/e2-4666cad90fe1-resolution/`. The PG source response includes six acronym candidates; Project Gutenberg is the sixth, alias PG. The current `fits_kind(..., 'place')` accepts all six, including media-rating and unit-of-mass candidates. This filter does not establish accommodation compatibility.
- In the inspected `resolve_entity` control flow, the automatic exact-name shortcut is **brand-only**. This saved entity is kind **place**, so the chosen QID passes through the local brain's JSON `id` selection (fresh or cached), then `Web.entity` returns the canonical label. There is no deterministic “PG means Project Gutenberg” mapping in this route.
- The pipeline subsequently replaces raw naming words in planned visuals/searches with that accepted canonical label. This explains the observed **“typical Project Gutenberg room in North India”** and duplicated Project Gutenberg query terms. The primary trace is **contextually wrong model-based entity selection accepted by a weak type/context gate, then deterministic propagation**, not a manual replacement or an established ASR/anchor defect.
- The job does **not** preserve indexed raw per-call plan/resolver replies. No raw model answer has been fabricated or labelled as captured. The model-selection branch is a control-flow inference supported by the saved kind/QID and source candidates. A fresh-versus-cache determination is not available from the inspected artifacts; model aliases/inventory do not resolve that gap.

### Model, quality and bank evidence

The saved planner alias is `Ollama storylens-meaning:14b`. Suite inventory observed local Ollama `0.40.5` and a loaded 14B Q4_K_M model with digest `3e063cc851850dd66d654e180af6da339f1c603b6a11eb774a3bac69a57a8609` during dispatch. Thirty-eight saved rejection records name `storylens-planner:9b-q6 (looks at the pixels)`. These support an actual local-model workflow, distinct from the earlier fixtures, but do not bind each inference to a fresh request/model digest or prove cache misses. Retrieved workflow memory explicitly records `cache_hit=true`; that is workflow-reference reuse, **not** evidence that every planning/ASR/Vision response was fresh. No raw per-call cache lineage was established here.

The saved quality report gives **95/100, passed=true** while `visuals.references_coverage` is **false, hard=false**. The offered-file and offered-Vision checks pass over zero offered assets. This is a technical/hard-rule outcome, **not semantic success or five-choice coverage**. Job/chat partial-review flags are the meaningful disposition. Recorded search failures also include malformed headers, Agent Reach NoneType concatenation, latin-1 encoding and a source 403; their precise causes are not repaired or guessed here.

The automatically emitted SOURCE manifest has two `no_match`, **unreviewed** banks, zero choices and zero selected assets. Pointer hash and source-project SHA256 bindings match. With no image records, there is **no actual offered-asset byte binding or native media handoff to validate**. “No visual” is the safe available owner choice; it has not been manually applied on the owner's behalf. No selected replacement asset, successful visual preview or native acceptance is claimed.

### Minimum semantic repair lease proposal — not implemented

Proposed only: `hinglish_visuals/planner.py`, `hinglish_visuals/pipeline.py`, new `tests/test_visuals_context_resolution.py`. Pass actual naming quotes, adjacent moment meaning and story constraints to local entity disambiguation; reject incompatible canonical candidates or preserve unresolved/no match before canonical query propagation. Preserve full creator guidance, country/source constraints and original word anchors. Do not hardcode PG to Paying Guest; PG in an ebook/library context can legitimately mean Project Gutenberg.

Minimum regressions: the recorded housing PG/candidate case must not accept Gutenberg or rewrite housing queries to it; a legitimate Project Gutenberg abbreviation remains resolvable; context-free PG can remain uncertain; a specifically named accommodation/place retains its city/country; generic physical classes are not silently presented as verified named places or factual furnishing claims. CPU fixtures remain labelled; any authorized fix must repeat the **same normal app request through the actual configured local models**. Black argument wiring and quality acceptance presentation remain suite-owned; protected cache/locality/telemetry findings remain untouched. No files have been leased or edited for this proposed repair yet.

Detailed read-only audit: `output/visuals/reliability-evidence/e2-4666cad90fe1-readonly-audit.json`. Original project SHA256 is still `93741bdfa2a3e674a7cf16c4027c2dc4e52b4f3ef11ecd9b46a772d898fbe7d6`. No product edits, job/source changes, model/search/render/GPU/native calls, retries or manual asset approvals were performed by this audit.

## Scoped semantic-resolution repair and clarification handoff

The coordinator subsequently granted the **initial semantic repair** lease for `hinglish_visuals/planner.py`, `hinglish_visuals/pipeline.py` and new `tests/test_visuals_context_resolution.py`. Collision checks found the test path absent and no competing file owner in the suite handoff. The actual failed E2 project, raw targeted source responses, first-run quality evidence and missing raw-resolver/freshness limits remain preserved. No genuine run was started by this feature owner.

### Fresh production resolution

Fresh `pipeline.run` now calls `resolve_visual_entity`, passing a bounded context built from the actual naming quote/mention, its line and neighbouring phrases, moment meaning/visual category, recent story and source country. The full summary/source constraints are sent to the model without pruning; the existing creator-profile injection remains unchanged. No shared brain, evaluator, model-preference, cache, renderer or transport code was altered in this repair.

The additional structural gate rejects non-physical candidate types for requested physical places (digital libraries/services, classifications, units), and does not treat a country as an individual room. These are type contradictions, **not an acronym expansion dictionary**. No positive QID is supplied by controller code. Known incompatible physical candidates can remain unresolved without extra searches. A generic physical-class bank retains raw naming/meaning instead of inventing a uniquely identified building.

When a contextual model decision is needed, it receives the supplied candidates, original naming and full constraints in one bounded structured call with `think=false`. It must return `referent=named/generic/ambiguous`, actual booleans `compatible` and `constraints_match`, a reason, and an allowed candidate ID for named resolution. Generic/ambiguous decisions do not adopt a QID; invalid booleans or foreign IDs cannot become truthy approval. Canonical metadata is checked again for structural contradiction. Only a compatible accepted **named** identity may change visual/search naming. The raw entity name, original quote, mention and phrase/word anchors stay unchanged. Existing callers that omit `resolution_context` retain their previous contract, including the historical recheck path; no blanket recheck repair or all-video guarantee is claimed.

### Explicit ambiguity, not silent no-assets success

A later direct coordination request explicitly required preserving functional question state. That request authorized a focused follow-up after the first bounded probe; it was not an unsolicited repair of a frozen final finding.

`resolve_entity(..., resolution_context=..., resolution_outcome={})` now provides typed functional outcomes:

- `entity_key`, `original_name`, exact `quoted_words`/`spoken_mentions`, `known_meanings`, country;
- `referent` (`named`, `generic`, `ambiguous`), `status` (`resolved`, `generic`, `unresolved`, `needs_clarification`), reason and accepted canonical identity when present;
- `needs_clarification` and a plain `clarification_question` only when the supplied context genuinely remains ambiguous.

Genuinely bare “PG” with an ambiguous local decision yields **“What does \"PG\" refer to in this line?”**, with its original quote retained. A definition already supplied by the existing meaning, such as **PG (paying guest)**, is not asked again. This uses definition evidence in the current meaning rather than a PG-to-housing rule. Ebook/library PG remains a valid named resolution when the local decision/candidate are compatible. Model failure or a rejected incompatible candidate is not automatically blamed on an unclear user request.

The fresh pipeline preserves these outcomes in `visuals-resolution.json` per new output folder. If clarification is genuinely needed, it raises `VisualClarificationRequired` **before asset collection** rather than reporting a successful empty bank. The exception carries `.resolution` typed data. Under the application's existing `STORYLENS_VISUALS_CHECKPOINT` environment, a separate sibling `visuals-clarification.json` is also written into that job's working directory, with `resolution_file`, questions and outcomes. It deliberately does **not** create/alter a resumable media-success marker or trigger a search/recovery to evade the question. Normal non-question projects include `resolution_outcomes` and `needs_clarification=false` in the saved project.

**Suite wiring remains required:** read `cache/app/jobs/<engine-id>/visuals-clarification.json` on this explicit outcome, retain the typed question, put the chat into clarification-needed state and ask the owner. The CLI currently conveys the plain question through its normal error boundary; this feature lease does not add shared server/chat UI handling. Do not treat that stop as successful semantic acceptance, silently answer it, or auto-retry with a guessed expansion. Preserve original creator guidance and supplied country/source constraints on continuation.

### TDD, bounded final probe and frozen state

- `tmp/visuals-context-resolution-red.txt`: initial missing contextual API/helper failures; `tmp/visuals-context-resolution-green.txt`: eight contextual-controller tests passed.
- `output/visuals/reliability-evidence/visuals-context-resolution-cpu-checks.txt`: initial **67** combined checks passed. The first bounded four-case final probe is preserved in `visuals-context-resolution-final-probe.json`.
- The explicitly requested typed-question follow-up began with three failing regressions in `tmp/visuals-clarification-red.txt`; its eleven focused tests pass in `tmp/visuals-clarification-green.txt`.
- `output/visuals/reliability-evidence/visuals-resolution-clarification-cpu-checks.txt`: **70 combined CPU/component tests passed**. Recorded housing candidates cannot adopt Gutenberg; legitimate ebook context remains available; generic classes/ambiguity do not become exact places; constraints, real booleans, naming/anchors, typed question receipts and context-free compatibility are exercised. Model replies in positive tests are labelled synthetic controller fixtures and are not installed into runtime.
- `output/visuals/reliability-evidence/visuals-clarification-final-probe.json`: six final safe cases after the requested follow-up, all expected outcomes. It checks malformed referent type, rejected source constraints, incompatible post-lookup metadata, truthy-string rewriting permission, known housing meaning without a redundant question, and bare-acronym clarification. **No new final defect found in these cases; no post-probe product repair performed.** Hashes identify the frozen revision.

Protected cache/locality/telemetry findings, per-call digest/freshness gaps, shared quality scoring and suite black-argument wiring were not repaired here. No search/model/GPU/render/native call, service restart, actual job/cache-data mutation, manual asset replacement or native acceptance was performed. The negative first-run project still hashes to `93741bdfa2a3e674a7cf16c4027c2dc4e52b4f3ef11ecd9b46a772d898fbe7d6`.

**Next gate remains suite-owned:** after its sole B-roll heavy run is terminal and resources are released, repeat the **same visible normal Storylens Smart Visuals request/chat** with actual configured local models and the suite's argument contract. Inspect the resulting real decisions/uncertainty and any requested question; do not inject these unit-fixture replies or preselect replacement assets. The 70 checks and final probe are not semantic or native acceptance, and zero-breakage is not promised.

## Third normal-run retrieval audit — no product changes

Actual job `8f1392b1d630`, same chat `542f7a0a2f764b90`, reached a partial result at `output/visuals/20261025-062650-e79081/001-0000-e2-1-`. The contextual repair retained PG as paying-guest accommodation, without Gutenberg or a redundant question; black background also propagated. **Zero assets across two banks remain a failed asset-coverage result**, irrespective of the technical 95 score. No native import is warranted.

Two concrete downstream issues explain the remaining gap. PG has only a two-character name/label and no aliases: `Entity.names()` excludes it, leaving `locked()` no proof names and rejecting non-official results before Vision. Its saved bank has zero candidates/checks, while targeted reads of the three exact query-cache files contain 30 results each (including accommodation leads for the contextual queries). These cached leads are unverified; they do not prove fresh retrieval or image suitability. Apartment has 90 candidates and 20 checked/rejected. All 20 failed identity uncertainty; three passed type, moment and quality but were rejected because bedroom pixels could not prove a uniquely identifiable self-contained apartment. Generic illustration and exact named-identity requests currently share that strict identity contract. Car/street/exterior rejections are appropriate and were not overturned. Seventy candidates remained unchecked under the existing 20-candidate cap, not a recorded timed budget exhaustion.

The third receipt contains no recorded malformed-header, latin1, Agent Reach NoneType or 403 failure. Earlier provider exceptions cannot be assigned as this run's cause. Photo moments use web/Wikimedia; missing stock video is not a demonstrated bug. SOURCE pointer hash matches, with two empty unreviewed banks; no offered-asset byte/native binding can be validated. Per-call inference freshness/digest remains unproven.

Minimum proposed retrieval lease, **not implemented**: typed generic/named handling in `gather.py`, `web.py`, `references.py`, `evaluator.py` and scoped regressions. Permit bounded short-name contextual retrieval and evaluate generic illustration without requiring unique-building proof; retain source/country constraints and strict named-person, team-kit, landmark and fact checks. Do not hardcode PG, accept arbitrary acronym results, or call a generic room the speaker's actual accommodation. Suite owns any authorization, next actual-model app run and shared quality/UI work. Protected cache/locality/telemetry findings remain untouched. This audit performed no searches, model/GPU/render/native calls, retries, job changes or product edits.

Detailed evidence: `output/visuals/reliability-evidence/e2-8f1392b1d630-retrieval-readonly-audit.json`. Original project SHA256: `5c8153f9a6ae5f3d8204ec095fa2d389909cfc8438abadac4477ba8414bdaad8`.

## Bounded generic-reference initial repair — frozen CPU handoff

The subsequent explicit initial-repair lease covered only `hinglish_visuals/gather.py`, `web.py`, `references.py`, `evaluator.py`, dedicated tests and this handoff. Implemented an **optional typed generic-class illustration method**. It is built only from an explicit matching local resolution outcome (`status=generic`, `referent=generic`, real `needs_clarification=false`, no named QID/canonical adoption), with retained original naming, quote, defined meaning and country. Person, brand, event, logo, map, fact/document and team-kit requests retain their strict/default routes. A malformed or absent optional resolution record does not enable this method.

The generic retrieval path allows a short name only alongside source-owned class/category wording and the requested country/directional-country wording. A definition already supplied for this mention, such as `PG (paying guest)`, is scoped to this request; there is no global PG expansion or lookup table. Source-less, wrong-region, arbitrary acronym/logo and Gutenberg leads are not approved by the short-name exception. Ordinary `Entity.names()` and `locked()` behavior is unchanged unless this typed method is explicitly supplied. Search signatures include the new method only when active, preserving default callers' signatures.

The optional evaluator mode uses a separate schema requiring actual boolean `class_visible`, `category_ok`, `fits_moment` and `quality_ok`. It asks whether the physical class is visibly illustrated, not whether bedroom pixels prove a uniquely named building. Source class/location evidence is checked independently before inference; a source failure does not spend a model call. Missing, false or truthy-string class/type/moment/quality answers cannot approve. There is no identity-answer flip or weakened exact-person/team/fact rule. Source evidence is bound into this method's check context through collection and recheck; accepted option metadata explicitly says `scope=illustration`. It never states that the source property is the speaker's residence, selects an option, or inserts a clip automatically.

**Important unresolved boundary:** the actual third run classified Flat/apartment as **named** `Q188507`. This repair deliberately does not reinterpret that recorded local decision as generic. Therefore its strict identity checks remain in effect, and the earlier apartment identity-only rejections have not been overturned. A correct class-vs-named resolution for that actual input needs a separately scoped resolver follow-up or an actual local-model decision in the next normal run; `planner.py`/`pipeline.py` were outside this lease. Likewise, source evidence may be insufficient and correctly leave a generic bank empty. No five-choice or all-video guarantee is made.

### Evidence and boundaries

- Initial TDD: `tmp/visuals-generic-retrieval-red.txt` captures the missing requested API failure. The optional-metadata regression then failed on `resolution_outcomes=None` in `tmp/visuals-generic-metadata-red.txt`, before that initial input-handling repair. Positive model answers are synthetic CPU controller fixtures only, never substituted into production.
- **58 CPU/component checks pass**, including nine dedicated generic-method tests, contextual resolution, actual collector wiring with isolated local images, existing source/identity rules, wrong-kit/fact regressions and default evaluator behavior. Evidence: `output/visuals/reliability-evidence/visuals-generic-retrieval-component-checks.txt`. The B-roll wrapper still forwards its ordinary VisionModel call unchanged; the default schema and Sound-imported image helpers remain intact. This is component evidence, not live B-roll/Sound acceptance.
- **Final adversarial review: 12 checks, no new confirmed failure in the checks performed.** Probed truthy class answers, omitted quality, type-only fallback, source-region mismatch, document/team exclusions, source-metadata binding, source failure before model invocation, imports with HTTP requests denied, and both preserved negative-project hashes. Product code is frozen after this review. Evidence and exact code SHA256 hashes: `output/visuals/reliability-evidence/visuals-generic-retrieval-final-probe.json`.
- Both earlier real negative projects remain byte-for-byte unchanged. The 12 existing protected findings and their implementations were not repaired. No shared server/panel/host, cache subsystem, telemetry, model preference, creator knowledge or quality-scoring edits were made.
- **Live validation is not run:** suite exclusively schedules the next visible normal local-model workflow after its other work, and owns Adobe hosts. No model/search/GPU/render/native action, service restart, job interruption/retry or manual asset approval occurred here. Do not count these fixtures as semantic or native acceptance. Import/AST checks passed without initializing models or HTTP requests.

Import-safe handoff is ready at the recorded hashes; suite may use the new code for its next ordinary worker. Remaining apartment classification, actual source coverage, live Vision decisions and native acceptance must be reported separately.
