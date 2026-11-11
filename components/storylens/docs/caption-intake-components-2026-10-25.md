# Caption intake component handoff — 25 October 2026

**Component implementation only. Live local-agent, running Storylens and Adobe
acceptance are pending. Do not mark this workflow production ready.** The final
run executes 40 checks: **38 pass, two reproduced final-review failures remain
unfixed**. They are explicitly marked expected failures so their reproductions
remain runnable; `OK (expected failures=2)` is not a clean acceptance gate.

This bounded task added only `hinglish_captions/reference_intake.py`,
`hinglish_captions/font_intake.py`, their two dedicated test modules and this
dedicated evidence/documentation. No shared caption renderer, accepted profile,
server/UI, native adapter, font installer, panel package or task-map change was
made. No watcher, model, network request, download, actual font installation,
render or Adobe operation was started. The suite retains native resource ownership.

## Existing folder and preparation route

`ReferenceIntake` reads the existing `reference_library.folder/discover/digest`
functions. It uses the existing `auto_caption_references.json` configuration,
whose owner input folder is `A:/Full Drive/Styles/Videos`. It creates no second
input folder. Its durable bookkeeping lives alongside existing reference caches:

- `cache/captions/reference-library/intake-state.json`
- `cache/captions/reference-library/intake-jobs/<SHA256>/`
- `cache/captions/reference-library/font-intake-state.json`
- `cache/captions/reference-library/font-assets/<SHA256>/`

The latter directories contain state/intermediates, not another reference intake
source. Nothing scans automatically on import or constructor invocation.

| Suite hook | Component contract |
| --- | --- |
| App startup | Construct one `ReferenceIntake(root, serial=existing_queue_adapter)`, then call `startup()`. This enumerates/debounces only. |
| Existing folder refresh / filesystem hint | `notify(source)` validates the hint; coalesce hints and call `scan()` after the stable-write interval. `notify` starts no analysis. Default debounce is two seconds; zero-byte/changing files do not queue. |
| Existing queue worker | Call `run_next()` after scanning. The injected `serial(work)` must wait for `work()` and return its completed receipt synchronously. Do not pass a fire-and-forget queue submitter/Future-returning function. |
| GPU ownership | **Do not acquire `gpu-work.lock` around this callback.** The unchanged `reference_library.prepare` acquires its existing GPU lock internally. Queue scheduling and short state-file transactions are separate from that GPU lock. |
| Crash/retry | Claims and progress checkpoints are durable. Active claims block another intake instance. Expired claims resume after the configured lease; stale claim results cannot overwrite a newer result. Default lease is one hour; adapters must report progress/renew before it expires and must not schedule concurrent expired work. Temporary failures use persisted bounded exponential backoff. |
| Unsupported motion | Adapter maps existing unsupported-renderer errors to terminal `UnsupportedMotion`. No renderer result or generic fallback is created. `retry` refuses unsupported assets until a compatible renderer/re-preparation integration is explicitly supplied. |
| Application presentation | Map `message` through shared error presentation; put `technical_details` in collapsed diagnostics. State-file corruption/path/setup errors still raise; suite boundary must map them to the shared catalog. No existing UI route was changed here. |

SHA256 is the asset identity across rename, duplicate filename, service restart
and replacement. Replacement queues new bytes while retaining the old result.
Preparation results are copied opaquely, retaining source/slot, accepted pattern
fields, approximation labels and model receipt fields the existing callback
supplies. No accepted Hyperframes profile is rewritten. New source bytes still
require a compatible renderer; collecting reference evidence is not weight training.

**Checkpoint boundary:** the component passes `ref['intake_checkpoint']` into the
existing callback and preserves checkpoint receipts. The existing production
`reference_library.prepare` does not consume that field to skip a completed
Vision/planner stage. Actual stage-level resume therefore requires suite-owned
adapter integration and acceptance; the synthetic resume test alone does not
establish production inference reuse.

## Font contracts

`FontIntake` has no default network, resolver, installer or native preflight
implementation. The suite must supply those adapters explicitly. Its default
metadata parser reads name IDs from existing `tools.install_caption_fonts.names`
without calling that script's installation function. A read-only check against
bundled Great Vibes confirms exact family/style/PostScript parsing.

| Operation | Input/result contract |
| --- | --- |
| `propose(request)` | Exact `family`, `style`, `postscript`, `origin`. Only a supplied/licensed manifest is sufficient to attempt resolution. Vision/unknown proposals persist one `needs_review`, `review_count=1`; repeated renders do not repeatedly resolve them or substitute another font. |
| `register_local(path, manifest)` | Source must be within explicit `allowed_roots`, TTF/OTF only. Manifest needs exact parsed identity, font SHA256, source provenance and a free licence object `{id,path,sha256}`. File bytes, parsed names and licence proof must agree. |
| `resolve(id)` | Injected `resolver(request)` returns exact identity, approved source URL, filename, SHA256 and `{id,source,sha256}` licence proof. Source selection is durably checkpointed before `downloader(url)->bytes`. Download callback must bound network/read time and data size, validate redirect destinations and return only verified bytes, never execute content. |
| Source policy | Initial URLs must be HTTPS within narrow official raw GitHub namespaces (google/fonts, googlefonts, rsms/inter), with no credentials, queries, fragments or traversal. Paid/proprietary, unknown origins/licences, changed hashes and mismatched names stop for review. This is an allowlist, not a claim that all official/free fonts are supported. Trusted manifests remain required; a font URL alone is not licence proof. |
| `install(id)` | Explicit injected `installer(asset)` only. Verify the approved source again, then require a receipt `{installed:true,scope:'user',path,sha256,postscript}` and independently verify installed bytes/names inside explicit `install_roots`. Receipt presence/file presence is not host readiness. An active claim prevents duplicate installs; an interrupted install with uncertain outcome requires review rather than automatic retry. |
| `check(id, targets=...)` | Injected `preflight(asset,targets)` returns target receipts with `recognized:true`, exact PostScript and SHA256. Supported targets: `hyperframes`, `premiere`, `aftereffects`. Incremental checks permit exactly one Adobe host at a time. Global `ready` requires all target confirmations. The adapter must actually inspect the intended runtime; fabricated recognition is never acceptance. See the stale-receipt finding below. |
| `startup()` | Recover expired font-source claims without source actions; review uncertain interrupted installation. Resolution retries preserve trusted source selection and backoff. |

Tests inject JSON bytes as fake fonts, temporary copy callbacks and fake native
recognition. No fake font was registered with Windows or either Adobe host.
Golden fixture `ready` states are **not** actual font availability evidence.

## Test history and evidence

The first run failed with both new modules missing. After implementation, all 24
initial cases passed. Added lifecycle tests then reproduced one replacement
failure and three errors (interrupted claims and parser error handling). Those
were repaired and 30 passed. Two further regressions reproduced changed-source
status and duplicate installation; those were repaired. The affected existing
reference-library tests were included, including its known-reference no-model
cache path. Final review added two explicit expected-failure reproductions;
production code was not changed after that review.

Command:

```text
.venv/Scripts/python.exe -m unittest tests.test_caption_reference_intake tests.test_caption_font_intake tests.test_caption_reference_library -v
```

Evidence under `output/caption-intake-evidence`:

- `component-validation.json`: 40 executed,38 pass,two known failures, zero
  unexpected failures/errors; source hashes and explicit acceptance flags.
- `component-tests.log`: complete verbose component/affected-library result.
- `reference-*.golden.json`: committed queued,retry,prepared,unsupported examples.
- `font-manifest.golden.json` and `fonts-*.golden.json`: synthetic exact metadata,
  review, verified, installed, partial and all-target fake preflight states.
- `build_component_receipts.py`: reproduces those fixtures using fake callbacks;
  it does not start runtime services. Temporary path values are labelled fixture
  paths. These are state-contract examples, not owner media or installation inputs.
- `local-runtime-audit.json`: bounded static audit, configuration and planned
  short/long benchmarks. No runtime SLA has been measured.

## Final safe review — remaining findings, not repaired

1. **Stale font readiness after a failed full preflight.** Confirm all three
   targets; make the next full preflight throw an unavailable-host error; then
   check only Hyperframes. `ready_for` initially clears after the error, but
   stored prior target receipts remain. The last partial check can restore
   global `ready` using old Premiere/AE confirmations. Reproduction:
   `test_review_finding_failed_full_preflight_should_invalidate_prior_target_receipts`.
   **Do not treat this component's global readiness as authoritative until this
   finding is authorized for repair and actual host/session freshness is verified.**
2. **Valid alias cannot replace a removed first source filename.** Register a
   font, register identical bytes under another filename, remove the first file,
   then install. Asset aliases are retained, but canonical `asset.path` still
   points to the missing first file. It conservatively becomes `needs_review`
   instead of selecting the verified alias. Reproduction:
   `test_review_finding_verified_alias_should_survive_removal_of_first_filename`.
   Keep the registered source available pending an authorized repair.

Per the owner rule, both findings are recorded without post-review production
fixes. Existing Photo Collector/native findings are unchanged by this task.

## Local-only brain requirement and acceptance gaps

The new components import no Codex/ChatGPT/OpenAI client, have no subscription
check and require no active chat session. The inspected default caption route
uses existing `prepare -> see -> VisionModel` and
`prepare -> open_brain(root,'ollama')`, both configured local Ollama paths. The
explicit `ollama` route fails when unavailable rather than choosing cloud
inference. At audit, read-only effective configuration selected planning model
`storylens-meaning:14b` and Vision model `storylens-planner:9b-q6`. These are
configuration names, **not proof of installed version, health or executed use**.
No inference was performed in this bounded stage. This is not an audit of every
other Storylens feature or an independence guarantee for the whole application.

The deterministic components own hashes, timing, bookkeeping, validation and
retries. Semantic reference/font choices must come from actual configured local
models and legitimate metadata in the finished route; Codex-authored fixture
answers do not count. External font/search/download licences/network may still
be needed even when the model brain is local. No remote fallback was added here.

Suite acceptance must still wire startup/rescan/serial hooks, presentation,
approved font callbacks and stage checkpoints; then run ordinary Storylens
requests with the actual configured local models. Preserve full creator
guidance. Record provider/model/version, redacted prompt/tool requests, execution
receipts, retries/outcomes, cache lineage and human/development intervention
flags. Do not insert handcrafted successful plans to pass acceptance.

Planned serialized benchmarks (not run): one new reference with a short script
and exact licensed font, followed by several stable/duplicate/replaced references
and a long English/Hinglish script. Measure queue wait separately from Vision,
planning, rendering and native transfer; record tokens, peak CPU/RAM/VRAM,
wall times, word preservation and saved-state continuation. Check each native
host separately under suite scheduling. No new model download, concurrent GPU
work, Adobe launch, publication or security change is part of this handoff.

## Suite startup, state and cancellation addendum

This is an integration contract for the suite owner, **not installed startup
code**. Source and tests remain frozen at the hashes in
`output/caption-intake-evidence/component-validation.json`. Do not import fixture
`*.golden.json` envelopes as production state or use their fake READY receipts.

Exact entrypoints:

```python
from hinglish_captions.reference_intake import ReferenceIntake
from hinglish_captions.font_intake import FontIntake

# Supplied by the suite's existing lifecycle/queue; no independent watcher.
references = ReferenceIntake(root, serial=run_on_existing_serial_worker)
references.startup()     # scan only; first sighting begins stable-write debounce

# On a subsequent existing lifecycle tick, after the debounce interval:
references.scan()        # commits new stable content, without model inference
# Only the suite's authorized worker invokes this, when resource scheduling allows:
# result = references.run_next()

fonts = FontIntake(
    root,
    allowed_roots=approved_supplied_and_bundled_font_directories,
    install_roots=approved_per_user_font_directories,
    resolver=approved_official_source_resolver,
    downloader=bounded_trusted_downloader,
    installer=approved_user_font_installer,
    preflight=actual_target_font_recognition,
)
fonts.startup()          # state recovery only; no resolve/install/preflight calls
```

All callback/directory variables above are suite-owned dependencies, not defined
or auto-discovered by the new components. In particular, `run_on_existing_serial_worker`
must run exactly the supplied callable and return its completed receipt. It must
not invent a plan, return an asynchronous queue ticket or acquire the GPU lock
outside `prepare`. Calling `run_next` without that adapter raises a setup error.

Runtime state is raw JSON with `version:1`, not the evidence envelope:

| State file | Top-level fields and identities |
| --- | --- |
| Reference | `kind:'caption-references'`, `observations:{casefold_absolute_source:observation}`, `assets:{sha256:asset}`. Observation fields: `source`, `signature:[bytes,mtime_ns]`, `stable_since`, `present`, optional `sha256`. Asset fields: `sha256`, `status`, `attempts`, `sources`, `reference`, `checkpoint`; optional `result`, `retry_at`, `message`, `technical_details`, and active `token`/`lease_until`. |
| Font | `kind:'caption-fonts'`, `requests:{request_id:request}`, `assets:{sha256:asset}`. Request ID is SHA256 of case-folded family, style and PostScript joined by NUL. Requests retain identity, `origin`, `status`, `attempts`, `ready_for`, and optional `resolution`, `asset_sha256`, `installation`, per-target `preflight`, `review_count`, retry/claim fields and messages. Assets retain verified identity, source `path`, SHA256, provenance, licence proof and source `aliases`. |

Reference statuses are `queued`, `running`, `retry`, `prepared`, `unsupported`.
Font statuses are `pending_source`, `resolving`, `retry`, `needs_review`,
`verified`, `installing`, `installed_pending_preflight`, `ready`.
All timestamps use the injected clock (wall-clock seconds by default). State
transactions use short per-file cross-process locks; writes flush/fsync a unique
temporary file and atomically replace the previous JSON. Malformed state is
preserved and raises; the suite must present a recovery error rather than erase
it. These schema details are not permission to edit state manually or falsify
receipts.

**Cancellation is a current API limitation:** neither component exposes a
`cancel()` method, a cancelled status, an abort token for model/network adapters,
or a native undo operation. Do not display a successful Cancel receipt based on
stopping the caller's wait.

- Before dispatch, the suite may stop scheduling new `run_next`/font actions.
  Keep persisted queued work and its receipts intact. Application pause/cancel
  intent must be persisted by the suite's existing job system; it is not stored
  in these component files.
- An in-flight `run_next()` is synchronous. A cooperative suite adapter can
  raise on its own cancellation signal, but the component currently treats that
  exception as a retriable preparation failure, not terminal cancellation.
  Keep cancelled jobs out of automatic redispatch at the suite boundary.
- Do not kill another GPU job, bypass its lock, assume aborting a request stopped
  the model, or remove a claim while its worker may still execute. Verify worker
  termination/ownership through existing suite scheduling. Late stale-token
  results cannot overwrite a reclaimed reference claim; that is not proof the
  old computation stopped.
- After a crashed reference worker, lease expiry permits later recovery with
  checkpoints (default one hour). Progress from the preparation callback renews
  the lease. There is no public out-of-band renewal API while a callback is
  merely waiting in an external queue. The suite must account for queue wait in
  its lease/scheduling policy before enabling unattended dispatch.
- Font source claims default to five minutes and have no progress-renewal
  callback. Bound callback time below the lease or supply an appropriate lease.
  Expired source work can retry from the persisted resolution; an expired
  installation instead becomes `needs_review`, because installation may have
  happened without a receipt. Never automatically undo or repeat that uncertain
  operation.

### Queued minimal repair cycle — not authorized or executed here

The two exact expected-failure reproductions remain unchanged. The applicable
rule in `AGENTS.md` is: “Do NOT fix failures found during this final adversarial
review unless the owner subsequently asks.” Parent coordination is clarifying
that separate repair cycle; this handoff does not infer approval.

1. When explicitly authorized, start from the existing stale-receipt test with
   its expected-failure marker removed and observe the genuine failure. Invalidate
   confirmations for a failed attempted preflight, including stored per-target
   receipts; never let a partial check resurrect invalidated confirmations.
   Coordinate a host/session freshness contract with the suite, then verify
   partial checks, full exceptions, host restart/reload, font version replacement
   and repeated saved-state recovery. Actual native recognition remains a
   separate one-host-at-a-time acceptance check.
2. Start from the existing removed-first-alias test as a genuine failing test.
   Select a remaining allowed source only after independently checking its
   expected bytes, exact parsed face and applicable licence proof. Persist the
   selected canonical source atomically; do not reinstall when an already valid
   installed receipt exists. Cover removed first alias, changed alias bytes,
   outside-folder aliases, no remaining source and restart/dedup behavior. Do
   not move, rewrite or delete owner font files.

After those repairs, run the two dedicated modules plus affected reference-library
checks; repeat a safe final review and record any new findings separately. Do not
rewrite the current 38-pass/two-known-failure evidence as historical clean success.

Current blockers for startup/host-ready acceptance are: the protected two findings;
suite lifecycle/serialized-dispatch/cancellation integration; actual trusted font
source/install/preflight adapters; existing prepare's unconsumed stage checkpoint;
and real configured local-model plus session-fresh native recognition evidence.
The suite may wire discovery/bookkeeping using this API while keeping font readiness
non-authoritative. No independent watcher, inference, shared/native change or GPU
action was started for this addendum.
