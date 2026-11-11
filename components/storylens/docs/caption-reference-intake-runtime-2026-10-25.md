# Reference intake runtime adapter — 25 October 2026

Added `hinglish_captions/reference_intake_runtime.py` and its dedicated
`tests/test_caption_reference_intake_runtime.py`. An initial scoped search found
existing reference discovery, preparation and UI refresh, but no persisted
lifecycle runtime. Both new paths were absent before this work. The task map
already reserves this additive runtime to this feature owner.

**The adapter has component evidence, not running-app/local-agent acceptance.**
Its 25 temporary-fixture checks pass. The combined run executes 65 checks:
**63 pass and the two original protected font findings remain expected failures**.
The original intake modules and both original test files match the hashes in the
earlier validation receipt. No shared server/UI/native/profile/font files were
edited. No real reference folder state, model, network, GPU, font installation,
Adobe host or service action was performed.

## Exact suite lifecycle connection

The suite owns actual application startup/shutdown, worker scheduling, filesystem
subscription and calls to `tick`. The module imports/constructs without starting
a thread, timer, watcher, scan or model request. Even explicit `start()` performs
discovery while the new instance remains unarmed; `resume()` is a separate action.

```python
from hinglish_captions.reference_intake_runtime import ReferenceIntakeRuntime

runtime = ReferenceIntakeRuntime(
    application_root,
    serial=suite_run_synchronously,
    can_dispatch=suite_reference_work_may_start,
    subscribe=suite_subscribe_reference_folder,  # optional; omitted => polling
)
startup_result = runtime.start()  # discovery and optional subscription; no analysis

# Suite activation must be explicit. This was NOT activated during this task.
# runtime.resume()

# The existing suite scheduler calls one tick at a time:
# result = runtime.tick()

# On lifecycle shutdown:
# stopped = runtime.stop()
```

`application_root` remains the existing Storylens root. The reference source
folder is read through `reference_library.folder(root)` from existing
`auto_caption_references.json`, currently `A:/Full Drive/Styles/Videos`. There is
no second input folder or new automation. Tests supply a temporary configuration.

| Dependency / call | Exact behavior |
| --- | --- |
| `serial(work)` | Must execute the one supplied callable synchronously and return its completed preparation dictionary. Do not return a future or ticket, enqueue-and-forget, fabricate a result, or block waiting on the same worker that must execute it. If already on that worker, the suite adapter must handle its own queue reentrancy safely. |
| `can_dispatch()` | Return literal `True` only when the existing shared scheduler permits reference work. False/other values produce `waiting_for_scheduler`, leaving reference attempts untouched. Exceptions produce a plain `error` with separate diagnostics. This callback is not permission to acquire the GPU lock outside `prepare`. |
| `subscribe(callback)` | Optional suite-owned filesystem event subscription. Return a callable unsubscribe handle. The suite binds it to the already configured folder and forwards `callback(kind,source=None,destination=None)`. A failing subscription falls back to polling and preserves diagnostics. No OS watcher package or independent background loop was added. |
| `tick()` | At most one preparation attempt, synchronous through the existing callback. The suite must call from its authorized worker, not block its visible UI thread. Scans occur only when due/requested. Default polling fallback is five seconds; the suite drives ticks frequently enough to honor earlier debounce deadlines. |
| `on_event(...)` | Accepts created/modified/deleted/moved/overflow hints. Validates paths under the configured source folder; rejects outside paths. Ignores unsupported temporary extensions while allowing an atomic rename into a supported video extension. Coalesces events by trailing 0.25-second debounce. Polling remains active to recover missed events/overflow. |
| `rescan()` | Requests a full scan on the next tick. Does not infer, render or change accepted patterns. |
| `pause(reason)` | Persists a stop on new analysis. Discovery continues on suite ticks; work already in flight may finish. |
| `resume()` | Requires a started instance plus both scheduler callbacks. Explicitly arms this instance and clears persisted pause/cancel intent. Does not reset original reference backoff, unsupported status or stage checkpoints. A restarted instance is always unarmed even if earlier state allowed work. |
| `request_cancel(reason)` | Persists a feature-queue-wide pause/cancel request. Not a per-reference delete and not an abort receipt. Reports `cancel_requested`, `cancellation_observed:false`, `model_abort_verified:false`. |
| `stop()` | Stops this instance's subscription and new dispatch, preserving owner files/state. In-flight work receives cooperative cancellation at the next supported boundary. Returned `stopped` describes this lifecycle adapter; it does not prove a model request was aborted. Late events are ignored. |
| `snapshot()` | Reads durable control/scheduling/last-result metadata. It is not a native font readiness or model-health check. |

## Existing preparation, concurrency and persistent state

The adapter constructs the unchanged `ReferenceIntake` with a wrapper around
existing preparation. Discovery/digest, content SHA identity, stable-write waits,
original reference job state, backoff and claim recovery remain owned by that
component. Accepted profiles and result/source/slot fields are preserved.

The adapter adds a **separate feature dispatch mutex**, held across a synchronous
tick/work call. It uses a nonblocking per-process thread guard plus native OS
file locking. A second Python process was tested against that actual file lock;
it reported `busy` without preparing. A clock/lease expiry alone cannot bypass
this mutex while the original runtime worker is alive. Process death releases
the native lock; the original persisted reference claim still waits for its own
lease/recovery rules. A live prior claim produces `waiting_for_worker` with its
lease deadline, not a completed/idle receipt.

**This mutex is not the GPU lock.** The wrapper never acquires `gpu-work.lock`;
unchanged `reference_library.prepare` owns that acquisition. The suite must route
its reference dispatch through one coordinated controller and avoid a parallel
direct `ReferenceIntake.run_next` caller that does not share this mutex.

New bookkeeping files under the existing cache namespace:

- `cache/captions/reference-library/intake-runtime-state.json`
- its short transaction `.lock` and synchronous-worker `.dispatch.lock`

Runtime JSON is raw `{version:1,kind:'caption-reference-runtime',...}` with:

| Field | Contents |
| --- | --- |
| `control` | `paused`, `cancel_requested`, `reason`, configured `watch_mode`, `event_error`. `watch_mode` describes subscription configuration, not a proof that a stopped watcher/host is alive. |
| `schedule` | `next_poll_at`, optional `event_at`/`stable_at`, `event_sequence`, `scan_requested`, optional `last_scan_at`. Event sequence protects hints arriving during a scan. |
| `last` | Returned status/message, optional asset/cancellation flags/diagnostics and timestamp. |
| `dispatcher` | Active token, PID, start time and descriptive lease deadline while the native dispatch mutex is held; cleared on normal exit. Mutex ownership, not this descriptive deadline, prevents overlap. |

All use the injected clock, default wall-clock seconds. Existing atomic
`DurableState` handles writes; no new job schema replaces the original reference
JSON. Malformed/unwritable state produces a useful error without resetting its
bytes or inventing success. Shared error-catalog/UI mapping remains suite-owned;
show `message` plainly and `technical_details` separately.

Status values include `stopped`, `paused`, `idle`, `busy`,
`waiting_for_scheduler`, `waiting_for_worker`, `cancel_requested`, `cancelled`,
`prepared`, `retry`, `unsupported`, `error`. `idle` means no attempt ran in that
tick; a future-backoff retry may still exist in original reference state. It
does not mean the backlog is complete. Every returned view explicitly carries
`native_preflight:'unverified'`; the runtime never calls global font readiness.

## Cooperative cancellation and known integration limits

Cancellation checks run before queue submission/execution, before preparation,
at callback progress checkpoints and after preparation returns. The last
checkpoint is persisted before reporting cancellation. Because the frozen base
component classifies callback exceptions as retriable, a cancelled reference
stays in its original `retry` state; the runtime's separate persistent cancel
gate prevents automatic redispatch. Only explicit resume clears that gate.

No network/model abort API was added. A blocking callback may finish substantial
work before it reports progress or returns. In particular, existing production
`prepare` has no progress boundary between its Vision and planner operations;
this wrapper cannot prove it stopped between those stages. Returning
`cancellation_observed:true` means a cooperative boundary was reached, always
with `model_abort_verified:false`. Never show a model-stopped promise based on
this controller alone, kill other jobs, clear another active claim or bypass
serialization.

Saved `intake_checkpoint` is passed unchanged to preparation. Existing production
`prepare` does not consume it for actual stage-level inference reuse. Fake
checkpoint continuation checks are component-contract evidence only.

The two protected font failures remain exactly as documented in
`caption-intake-components-2026-10-25.md`: stale per-target receipts can restore
global READY after a failed full check; removing the first source filename can
block an otherwise verified alias. This runtime does not repair or route through
either behavior. The original files/tests remain hash-identical. No global
font-ready claim is permitted pending separate authorized repair and live,
session-fresh native confirmation.

## Tests and safe final review

The missing module first produced `ModuleNotFoundError`. Initial implementation
passed 19 tests. Four more lifecycle/integration cases reproduced two initial
problems: damaged runtime JSON raised before readable reporting, and a persisted
active reference claim appeared idle. Those were repaired in this new module
only; all 23 passed. Two final safe adversarial cases then passed without a
further production change:

- Runtime state write failure retains owner source bytes and original job state,
  and returns error rather than fabricated preparation success.
- An unserializable adapter result never commits a prepared result; its original
  durable claim remains available for normal lease recovery.

No new confirmed defect was found in those two final checks. That is not a
zero-breakage guarantee. Protected earlier findings remain unresolved.

Final command:

```text
.venv/Scripts/python.exe -m unittest tests.test_caption_reference_intake_runtime tests.test_caption_reference_intake tests.test_caption_font_intake tests.test_caption_reference_library -q
```

Result: 65 executed in 9.267 seconds, **63 pass, two protected expected failures**,
zero unexpected failures/errors, exit zero. `OK (expected failures=2)` does not
mean a clean release/host acceptance gate. The new runtime contributes 25 passing
checks, including a second short-lived Python process for native mutex exclusion;
all inputs/preparation/scheduler/event callbacks otherwise use isolated fixtures.

Evidence: `output/caption-intake-runtime-evidence/validation.json`,
`combined-test-summary.log` and clearly labelled state examples for paused startup,
scheduler waiting, fake preparation, cancelled dispatch and stopped lifecycle.
`build_receipts.py` creates those examples with temporary bytes/fake callbacks;
it does not rerun tests or activate the actual service. Earlier test/evidence
files were retained rather than rewritten as successful live acceptance.

## Remaining acceptance work

Suite-owned wiring and normal app requests are still pending. Keep the editor
visible for demonstrations and use actual configured local LLM/Vision choices,
not fixture/Codex plans. Record provider/model/version, redacted prompts/tool
requests, actual executions/retries/cache lineage and intervention flags. The
new runtime contains no Codex/OpenAI session dependency; inspected existing
preparation still uses configured local Ollama adapters. Actual model availability,
short/long laptop performance, restart/queue behavior under real load and
subscription-independent operation have not been executed in this stage.

Trusted real font resolution/install, session-fresh per-target native recognition,
the protected repair cycle, actual stage-checkpoint consumption and honest
long-running cancellation remain separate blockers. Keep exactly one Adobe
host and one authorized resource job at a time under suite scheduling. No actual
watcher or unattended processing was enabled by this implementation task.
