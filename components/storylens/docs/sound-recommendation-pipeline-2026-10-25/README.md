# Fresh local analysis adapter — bounded component delivery

Implemented `hinglish_sound/recommendation_pipeline.py` and 21 dedicated checks.
The suite can now pass media plus the exact shared script and complete creator
context to one callable. The production adapter invokes existing local ASR,
temporal Vision, prosody, sound-story/palette/composition, library indexing and
ranking tools, then the existing candidate manifest. It never invokes the full
automatic mix/render first. No actual inference or creative acceptance is claimed.

The shared app route, panel, server, bridges, Adobe packaging and automatic Sound
Design path were not changed. This is callable integration infrastructure, **not
a deployed or verified repair of the owner's existing automatic result**. The
suite owner must connect the normal recommendation route to this entry point.

## Public call for the suite worker

Run only after the coordinator releases inference and the suite holds its single
serialized resource lease. Do not acquire a nested GPU lock in this function.
`resource_lease` records the suite's lease ID; it is not permission or a security
credential. Do not create a Codex-generated semantic/timestamp plan as its input.

```python
from hinglish_sound.recommendation_pipeline import run

result = run(
    root,                    # installed Storylens project root
    input_path,              # actual captured timeline XML or supported CFR video
    shared_script,           # exact owner text; never rewritten by Codex
    creator_context,         # complete existing per-request creator JSON
    execute_local=True,
    resource_lease=suite_lease_id,
    expected_models={
        "planning": selected_planning_model,
        "vision": selected_vision_model,
        "embedding": selected_embedding_model,
    },
    script_role="spoken_reference",  # context_only for genuinely silent footage
    token=cancellation_token,
    progress=normal_app_progress,
)
```

CLI equivalent (arguments must refer to the same normal request, not invented
model replies). This command is a handoff, **not executed here**:

```powershell
& 'A:\Full Drive\remove silence\.venv\Scripts\python.exe' -m hinglish_sound.recommendation_pipeline --root 'A:\Full Drive\remove silence' --input $capturedMediaOrXml --script-file $sharedScriptFile --creator-context $fullCreatorContextFile --execute-local --resource-lease $suiteLeaseId
```

`--help` was exercised without model construction. A normal Python/app call can
enforce `expected_models`; CLI resolves the explicit configured roles. No cloud
or smaller-model substitution, pull/download, local runtime startup, background
recovery or retry of the whole feature is added. Existing production per-call
guards remain bounded at their existing limits; this is not a latency guarantee.

## Actual adapter stages and limits

1. `prepare`: parse existing XML, or strict `probe` + one-clip XML metadata. Does
   not conform/render an incompatible video behind the user's back.
2. `transcribe`: existing offline Swift/installed ASR and timeline mapping. Keep
   original ASR and script-spelling corrections separately. Missing timing for a
   spoken-reference script stops; no invented word positions. The script itself
   remains exact. Context-only mode may use explicitly labelled visual lines.
3. `observe`: existing temporal contact sheets/action evidence. The only existing
   adapter edit is optional injected Judge, digest-specific cache namespace and
   exact creator-context JSON in `scenes.inspect`; defaults stay unchanged.
4. `prosody`: existing line delivery analysis on in-memory audio; no original-
   audio WAV, full score, preview MP4 or stem rendering is required.
5. `inventory`: real configured libraries, installed offline CLAP and existing
   SoundIndex. This can be expensive on first indexing; it was not run here.
6. `plan`: actual configured Brain calls for story/music, rhetorical delivery and
   observed action/speech layer composition. Existing evidence IDs determine
   times. Scene-first source requirements are retained. Sparse Vision stays
   `visual_interval`/`sampled`, not precise impacts. Natural authored durations
   survive rather than being replaced by a universal .1-second clip.
7. `prepare-rankings`: existing CLAP/text ranking and source relevance gates;
   snapshot alternatives, do not call the old automatic winner picker. Missing
   matches remain missing; no unrelated click fallback or automatic download.
8. `recommendations`: protected existing manifest API with prepared snapshots,
   measured energy passage/peak windows, `checkpoint=None`. Alternatives require
   review. Acoustic peak position is not proof of a semantic action contact.

Results are fresh directories under `output/sound-recommendations`. Preserve
`input.json`, each stage, local analysis, inventory/ranking snapshots, request,
manifest and `result.json`. `ready` means alternatives exist for review; it does
not mean a host import, sound-design quality approval or complete event coverage.
Source, timing/credit validation remains in the frozen candidate component.

## Provenance and model receipts

The execution gate is off by default. An injected factory is **always** labelled
`test_factory_used=true`, including manifest provenance, and never local-agent
acceptance. Actual mode requires exact installed loopback Ollama roles with
provider version/digests, rejects cloud names/remote tags and fails rather than
using an undocumented fallback. Model-weight changes separate planning/Vision
cache namespaces. Complete creator JSON is kept as an exact JSON value in local
model input even when the shared general-profile injection would skip it.

Own redacted JSON receipts capture tool inputs/replies, instance-local model
HTTP bodies/responses, image bytes via hashed local blob references, actual Brain
cache reads/writes and stage monotonic durations. No raw request headers are
captured. The protected Telemetry implementation is unchanged. The existing
embedding encoder may own a separate session: its adapter input/model/shape are
recorded, but its transport/cache state is explicitly unobserved. ASR per-source
cache lineage likewise remains unobserved by this adapter. Do not represent
these unknowns as cache hits or measured GPU/RAM statistics. Input/profile files
are private job inputs, not public audition URLs.

No semantic checkpoint resume is enabled. Existing final-review findings remain
in their separate repair queue. This stage does not repair shared model policy,
old telemetry, checkpoint authentication, old picker duplicate IDs or the known
uneven automatic creative result.

## Validation performed

58 CPU/temp component checks passed in 7.152s: 21 new and 37 frozen/existing
focused regressions. New core tests failed first with the missing module; added
contracts then failed for redaction, provenance and exact-profile/transport/cache
behavior before their implementation. Initial optional Judge/cache hooks were
covered subsequently; do not describe every adapter line as test-first.

The combined checks used injected analysis/model replies and tiny sine WAVs.
They exercise controller-to-production timing helpers, optional scene adapter
cache isolation, actual candidate hashing/demux/windows, cancellation, plain
errors, exact models, full profile/script preservation and credential fixtures.
They are **not** actual water sounds, actual model inference or a live app demo.
All three frozen delivery hashes remain unchanged. The first standalone final
probe failed due to restricted system TEMP; rerunning the unchanged probe using
workspace `tmp` succeeded. No permission/system changes were made.

No browser, model/GPU work, library scan/download, media rendering, Adobe/native
actions or publishing occurred. Live acceptance is blocked by the current
coordinated resource release and suite-owned route/native boundaries. After
release, dispatch ONE short normal local-agent request through the app, verify
its source-relevant sustained choices and receipts, then separately check suite
selection/import/playback. No speed, creative quality or long-form acceptance
claim is supported by these component tests.

## Final review — findings left unchanged

- **Physical action interval overrun (confirmed component reproduction):** an
  injected model proposes 1–6s of Foley for an action observed only at 1–4s.
  The controller accepts the extended interval. Expected: bound the physical
  coverage or explicitly distinguish a motivated tail. Impact: recommendations
  can continue beyond observed motion. Not a real inference/listening result.
- **Intentional silence status (confirmed component limitation):** a valid
  voice-only analysis creates no groups and is reported as `insufficient_analysis`.
  Expected: distinguish deliberate silence from failed planning. No unwanted
  audio is generated, but the status is misleading.

Reproduction/evidence is in `final-review.json`. Per AGENTS.md's final-review
boundary, neither issue was fixed after discovery. They must be considered before
claiming normal-app acceptance. No repeated approval question or owner wake-up
was issued in this bounded stage.
