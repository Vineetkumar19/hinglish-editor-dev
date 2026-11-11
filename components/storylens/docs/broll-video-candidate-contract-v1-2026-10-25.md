# Manual video-only B-roll candidate contract v1

## Delivered scope

New feature-owned helpers only:

- `hinglish_broll/candidate_manifest.py`: typed video records, fresh-window
  evidence binding, read-only saved-bank conversion and per-candidate rejection.
- `hinglish_broll/candidate_selection.py`: explicit owner choices, retry-safe
  sidecars and validation of the selected handoff records.
- `tests/test_broll_candidate_manifest.py` and three new synthetic golden files.

No existing B-roll generator/renderer was changed for this release. No shared
panel, bridge, server, host adapter, packaging or installation file was edited.
No host was opened or controlled. No web/stock/model call, GPU job, media render,
encoder job or old-job restart was performed. The test default-reader error case
opens invalid synthetic bytes to reject them; it does not render video.

**Component-ready; integration and native acceptance are pending.** This contract
does not insert media, start a queue, choose an option automatically or issue a
native success receipt. The suite owner retains exclusive shared/Adobe work.
Premiere and AE must never be open together. Unrelated tools are outside scope.

## Version and records

The returned root has `schema=storylens.broll.video-candidates`, integer
`version=1`, stable `bank_id`, source `project_path`, `content_format`,
`per_keyword_cap`, `collection_state`, `timeline`, `slots` and
`orphaned_choices`. TypedDict definitions describe the candidate, media identity,
source mapping, source credits, checked window, owner choice, anchor and slot.

| Record | Required meaning |
|---|---|
| Keyword/slot IDs | Distinct namespaced `keyword_id` and slot `id`, plus original integer `slot_index`. A candidate carries both IDs and its original `candidate_id`; its public `id` includes the slot namespace. IDs never depend on displayed option order. |
| Anchor | Exact spoken quote and unrounded source seconds; sequence start/end frames and frame-quantized seconds; explicit rational fps, `sequence_frames` timebase, `nearest_even` boundary rounding and canvas. No playhead/filename placement inference. |
| Original | Actual local source-video path, streamed SHA256, byte count, video duration, rational fps/timebase, upright dimensions and rotation. A hash is an immutable identity of those bytes, not a filesystem lock. |
| Prepared | Separate prepared-video path and the same inspected identity/metadata fields. This file is for preview; it is not silently treated as the complete original. |
| Mapping | Explicit prepared origin within the original, active original/prepared in/out intervals, source ticks and available original range represented by the prepared clip. Linear time mapping only. |
| Handles | Original and prepared before/after availability. `availability_only=true`: quality outside the checked active interval has not been established. Extension cannot invent missing footage. |
| Check | Exact active interval/crop, three frame checks, checker name and JSON-pointer/SHA references to the actual saved verdict and window receipt. This is recorded evidence, not a new vision judgement. |
| Source/credit | Provider, author/title, source/license links and license text. Authentication query values and URL user-info are removed. A downloaded web excerpt is labelled `downloaded_excerpt`; its duration is not the full online video's duration. |
| Owner choice | `unselected`, `selected` or `no_broll`, owner/none origin, revision, exact selected identity/fingerprint, slot fingerprint and ready/blocked state. Existing machine-suggested `chosen/clip` fields are never copied into an owner decision. |

The bank reader accepts saved project versions 1–3 only when their required
fields/evidence validate. Unsupported versions and invalid anchors fail clearly.
Non-video, absent, unreadable, changing, out-of-bounds, wrongly cropped or rejected
candidates appear under `rejected_candidates` with a useful issue. They never
become images, captions or automatic replacements.

### Honest collection and caps

- Long form has **at most 2** displayed video candidates per keyword; short form
  has **at most 5**. This is an explicit format choice, not duration inference.
  A maximum does not promise that many matching videos exist.
- The contract records total valid-media and selectable counts separately from
  `omitted_by_cap`. Bound ready choices are displayed before unbound legacy
  previews. A previously selected option remains pinned within the cap even if
  it was later in the original list; an unrelated option is displaced instead.
- Slot collection states distinguish `pending`, `collecting`, `no_match`,
  `blocked` and `complete`. A saved recovery plan supplies unstarted slots that
  are not yet in the partial project. No worker is resumed by reading it.
- Bank `complete` refers only to terminal saved collection, not owner approval,
  visual fidelity, full playback or native insertion. Incomplete work stays
  `saved_incomplete`, including a stale persisted “running” job.

## Exact hooks for the suite owner

### 1. Producer: save a fresh checked-window receipt

`checked_window_receipt(original_file, prepared_file, *,
prepared_origin_in_original, prepared_source_in, active_duration, crop, verdict,
media_reader=None)` returns a `storylens.broll.checked-window` v1 record.

It is a **producer hook after an actual passing local check and preparation of
that exact shot**. It validates the supplied latest verdict, bounds and source
crop and records the original/prepared hashes, candidate ID, verdict hash and
checked source interval. It does not search, inspect pixels with a model, render
or write files. The generator must save the returned object as
`option['checked_window']` alongside the same saved verdict containing its `id`.

The producer already calculates `source_path`, `original_offset`, prepared
`source_in` and duration in `render_choice`. A later authorized integration must
carry that mapping into each option; currently the legacy option packing drops
some of these temporary fields. Preserve the exact crop used by the actual
checker and conformation, in upright source pixels, including orientation.

**Do not backfill this receipt on an old/interrupted bank from a prior verdict
alone.** Both file hashes, crop/window and the current verdict must actually
refer to the shot that was checked. Arbitrary re-timing, unknown orientation and
an invented source mapping are not supported. The helper cannot independently
prove caller-supplied pixel evidence or analyze arbitrary speed ramps.

### 2. Reader: build a read-only candidate manifest

```python
from hinglish_broll.candidate_manifest import build_manifest
from hinglish_broll.candidate_selection import load_selections

previous = load_selections(owner_sidecar) if owner_sidecar.exists() else None
manifest = build_manifest(
    project_file,
    content_format=explicit_format,  # "long" or "short"
    bank_id=stable_result_id,
    previous=previous,
)
```

Prefer an explicit stable result ID. The fallback bank ID is path-derived;
copying/moving a bank does not silently authorize choices for another bank.
`planned_slots=` can supply an explicit saved plan; otherwise the reader checks
the matching sibling recovery journal. This read never starts recovery.

`media_reader=` is a trusted inspection seam for bounded CPU metadata readers
and tests. A reader returns `duration`, rational `fps`/`time_base`, upright
`width/height` and optional `rotation_degrees`. The default reads local container
metadata and one decoded frame on CPU; it rejects unknown display-matrix
orientation rather than guessing. It is not full-file or full-playback QA.
Never inject permissive synthetic metadata into production to make bad files pass.

Legacy files/checks remain visible when their metadata can be mapped, but a
candidate without the versioned hash/window/verdict binding is `unbound` and
`selectable=false`. Missing quality evidence is not inferred from a filename or
thumbnail. A malformed or failed candidate is rejected independently so other
usable choices and owner decisions remain available.

### 3. Owner UI: apply only an explicit decision

```python
from hinglish_broll.candidate_selection import choose, save_selections

# IDs come from the actual clicked card, never an automatic first-option pick.
manifest = choose(manifest, clicked_slot_id, "selected", clicked_candidate_id)
# Or: choose(manifest, clicked_slot_id, "no_broll")
# Or: choose(manifest, clicked_slot_id, "unselected")
save_selections(owner_sidecar, manifest)
```

The choice call returns a copy. Duplicate identical choices are idempotent.
Sidecar schema is `storylens.broll.owner-selections`, integer version 1. Atomic
sidecar writes refuse to overwrite arbitrary project JSON or another bank's
choices. A failed save preserves the old file and provides an actionable error.

On retry, load this sidecar and pass it as `previous`. Order changes and format
caps do not replace the selected identity. Changed/missing media, changed
anchors or unbound evidence retain the exact decision with `status=blocked`.
Removed slots retain `orphaned_choices`. Restoring the identical approved bytes
can restore the same decision; no fallback clip is chosen. Owner confirmation
is required to change the selection or clear it.

### 4. Handoff boundary: request only explicitly selected records

```python
from hinglish_broll.candidate_selection import selected_candidates
from hinglish_broll.candidate_manifest import CandidateContractError

try:
    selected = selected_candidates(manifest)
except CandidateContractError as error:
    issue = error.as_issue()  # shared plain-language message + Technical details
    # Preserve decisions and display the issue; do not insert a substitute.
```

This validates the current saved receipt references/latest verdict and rehashes
both selected files. It rejects swapped candidate/window references, later
rejections, changed saved anchors, non-video records and changed/disappeared
files. It returns only owner-selected typed records, including their anchors;
`unselected` and `no_broll` return nothing for that slot. It does not prepare a
generic `paths[]` import, invoke a host, mark insertion done or prevent a later
external file edit.

The **suite-owned** host adapter must consume the original media and agreed
crop/orientation/source mapping, validate the expected active project/sequence
and current file identity, place the chosen video at its sequence-frame anchor,
retain editability and return the actual native insertion receipt. The prepared
preview must not silently replace the original or expand trimming beyond its
handles. Protect duplicate native insertions at the host boundary. Existing
planned-time/receipt gaps remain pending shared integration.

`CandidateContractError.as_issue()` reuses shared presentation and diagnostics
redaction, with stable feature `broll_*` codes. No shared catalog was edited.
The receiving UI must keep `details` in its existing Technical details control.
Source strings and links are data, never instructions to execute.

## TDD and bounded evidence

Observed RED checks included the initially missing module/API, absent explicit
keyword IDs, and a selected manifest incorrectly accepting another candidate's
window-reference swap. Each was demonstrated before its correction. The swap
test is retained; receipt identity is checked at the handoff boundary.

The final dedicated command was:

```text
.venv/Scripts/python.exe -X utf8 -m unittest tests.test_broll_candidate_manifest
```

**35 component tests passed, 0 failures, 0 errors.** The recorded run took 1.777
seconds. Evidence is in
`docs/broll-candidate-contract-evidence-2026-10-25/validation.json` and
`unit-tests.txt`. It covers timing/rates, hashes/mappings/crops, quality and
watermark vetoes, format caps, incomplete/recovery-plan/no-match states, owner
decision preservation/pinning, changed/missing media, exact receipt references,
sidecar safety, useful errors and no implicit selection/insertion. A guard test
forbids network/process launch while using injected metadata. No production
model or media render test was run.

The three golden files under `tests/fixtures/broll-candidates-v1/` are:

- `short-unselected.json`: five choices; all owner decisions unselected.
- `long-selected-pinned.json`: two choices, preserving the owner's originally
  fifth option rather than replacing it with the first option.
- `incomplete-and-no-match.json`: a collecting slot, an explicit no-match slot
  and an unstarted planned slot.

Each wrapper prominently labels synthetic bytes/injected metadata, uses
`<FIXTURE_ROOT>` paths and is **not playable media or a live/native receipt**.
The inner `manifest` is the contract example. Golden equality is checked by the
dedicated suite; fixture creation is not invoked automatically by the tests.

## Existing real result remains unverified

The old `c1145994598a` job and its checkpoint, recovery journal and partial
project were hashed before and after the component run; all four were unchanged.
No status was rewritten and no earlier failed/adversarial finding was edited.
The source inspection remains as recorded in
`docs/broll-adobe-readiness-2026-10-25.md`: only two apartment clips were saved,
the persisted running status was stale, and there was no final preview/export
or native insertion receipt. This release does not upgrade that result.

Remaining gates are producer receipt integration, shared panel choice/timing
wiring, an authorized real local result and suite-owned native insertion.
Do not claim end-to-end acceptance from these component tests or golden files.

## Local-runtime dependency audit and acceptance gap

Read-only source/config evidence is saved as
`docs/broll-candidate-contract-evidence-2026-10-25/runtime-route-audit.json`.
No provider endpoint was queried and no model was loaded for this audit.

- The **new contract/choice route** imports ordinary local Python/file helpers,
  shared message/redaction functions and the explicit atomic sidecar writer.
  Its default metadata reader lazily uses local PyAV on CPU. It has no Codex,
  ChatGPT/OpenAI session, cloud LLM, browser agent or remote fallback dependency.
  It performs validation/bookkeeping, not semantic keyword or footage selection.
- The inspected **upstream semantic route** uses `LocalLLM` with the configured
  local Ollama meaning model, or the bundled loopback llama.cpp path. Ollama is
  fixed to `http://127.0.0.1:11434` on the normal B-roll route; the meaning start
  and configured-model resolver reject cloud-model tags. The local vision
  checker is instantiated with the normal loopback default. No remote LLM
  fallback was found in this inspected route. This is not an audit of every
  unrelated feature or arbitrary custom constructor caller.
- Current **configured identities, not newly loaded-model proof**: meaning is
  `storylens-meaning:14b` / Qwen3-14B Q4_K_M; the active vision configuration is
  `storylens-planner:9b-q6` / Qwen3.5-9B Q6_K; B-roll matching uses local
  Qwen3-VL-Embedding-2B; ASR storage selects Whisper-Hindi2Hinglish-Prime.
  Their configured repository revisions and local-directory presence are in
  the audit JSON. The meaning manifest records llama runtime `b11011` and
  Ollama `0.40.5`; installed/running versions were **not queried** today.
- `openai/clip-vit-base-patch32` is a local-weight compatibility/default name,
  not a call to ChatGPT. The legacy model-folder path can fetch missing weights
  from Hugging Face. That is a setup/network dependency, not a cloud brain; a
  cold offline laptop with missing weights is not established to work.
- Stock/search/download APIs and their credentials/network, local binaries and
  GPU resources, and applicable Storylens/Adobe product licensing remain real
  dependencies. They are separate from a ChatGPT subscription. The earlier
  Pexels rejection and interrupted E2 run are not erased by this source audit.

Existing cache keys/receipts provide useful data but do not yet establish all
required acceptance lineage. Meaning-cache keys include model/revision/runtime
and request inputs; Vision caches include model tag, prompts, image bytes and
schema but not a verified active weight digest. The old model-check receipts
record attempts/check outcomes and the saved frame verdicts record a judge tag;
they are not a complete per-run provider/version/tool-execution trace. The new
manifest references the exact persisted verdict; it does not invent missing
upstream provenance. Logging/integration changes stay with the suite owner or a
later explicitly released producer change.

### Representative laptop benchmarks — planned only

1. After shared wiring and scheduling release, use the approved real **35.7-second
   E2 short-form source** through the normal Storylens request, maximum five
   videos per keyword, low preview resolution and one job. The local configured
   LLM must derive keywords/queries and local Vision must check the actual chosen
   source windows. No manually supplied model JSON, cloud answers, handpicked
   successful clips or synthetic golden files. The suite owner must first decide
   how to handle the preserved interrupted job; do not duplicate or rewrite it.
2. Then use **one approved genuine long-form talking-head source/timeline**,
   initially a bounded 3–5 minute representative sample if the suite owner
   approves it, explicit long-form setting and maximum two options per keyword.
   That source has not yet been designated here. Don't manufacture a long-form
   success from a looped short or a prefilled plan. Follow with any larger
   workload only if the measured laptop resources justify it.
3. Record actual queue wait, ASR, model load/planning, retrieval, pixel-check,
   preparation and finalization times separately, plus available/peak RAM/VRAM,
   candidate counts/gaps, retries and final native receipts where authorized.
   No processing-time or zero-failure SLA is invented by this document. Keep
   heavy jobs serialized and exactly one Adobe host under suite reservation.
4. Each actual run needs configured **and active** model/provider/runtime/weight
   identities, redacted prompt/tool requests and actual executions, outputs,
   retries/outcomes, source hashes, cache keys/hit lineage and intervention flags.
   A wholly cached result must not be described as fresh model reasoning. Use
   approved fresh source material or supported explicit revalidation rather than
   deleting caches or fabricating a receipt to claim an uncached pass.
5. Controller failure checks should cover absent model/runtime, invalid/unavailable
   stock credentials, unknown speech, no matching footage, missing/changed media,
   interrupted collection and a wrong active target. Preserve progress, report
   the actual failure, avoid image/text substitution and bound retries. If the
   real local agent fails, preserve/reproduce that outcome, repair within released
   ownership, then repeat the same normal local-agent flow. The deterministic
   controller owns timing arithmetic, state and checkpointing.

The desired runtime must finish without a Codex/ChatGPT session after the normal
user request. That requirement is **not yet accepted end-to-end**: producer and
panel wiring, the genuine short/long local-model runs and native host receipts
remain pending. These component tests intentionally use labelled synthetic
fixtures; they cannot answer whether the actual local brain passes those tasks.
