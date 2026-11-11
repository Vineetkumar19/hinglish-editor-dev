# Explicit candidate audition — component handoff

New module: `hinglish_sound/audition.py`; new tests: `tests/test_sound_audition.py`.
No edits to protected recommendations/runtime/analysis code, shared model policy,
routes, panels, native adapters, automatic mix, packaging or running services.

## Callable contract

```python
from hinglish_sound.audition import prepare

result = prepare(
    root, saved_verified_manifest_path, saved_verified_manifest_sha256,
    explicitly_selected_candidate_id,
    allowed_roots=configured_library_roots,
    banned_paths=current_banned_paths,
    token=owned_job_cancellation_token,
)
```

The suite owns authentication/job authorization and obtains the exact path/hash
from its verified saved receipt. A browser-supplied hash is not permission. This
call accepts no candidate object, arbitrary client source path, implicit first
row or automatic winner. The manifest must be in an existing Storylens output
job. Its `auditions/` folder receives the checked audio and JSON receipt. Serve
`preview.path` only through the suite's authorized output-only/job-bound media
route; do not expose raw library paths or widen the existing endpoint.

Ready response: `schema=storylens.sound-audition`, version 1, stable `id`, exact
manifest SHA/candidate ID, `binding`, source/credits, preview path/SHA256/bytes/
frames/rate/channels/duration, proposed timeline/level/processing and `cache_hit`.
Failures/cancellation have plain `notice`; failures use shared `error_code` plus
separate `technical_details`. Failed/cancelled preparations are not ready files.

The preview is the **raw selected source window**, not a final mix simulation.
`applied_gain_db=0`, `applied_processing={}`; proposed mix settings remain
metadata. Default: 48kHz PCM16 WAV, native mono/stereo channel count retained.
No other layers, voice, background music, ducking or mastering are applied. The
known physical-action interval issue is not repaired or retimed here: audition
the exact source window already validated in the supplied manifest.

## Bounds and identity

- Reuse existing source verification, candidate ID, credit and atomic JSON
  helpers without modifying protected implementations. Check exact manifest
  bytes, completed schema, unique explicit candidate/group identity, timeline
  and source bounds, original SHA256, bans, configured roots and complete current
  licence-credit metadata. Existing full-file decode and the 16kHz-only analysis
  reader were unsuitable for bounded general audio seek/window extraction.
- Encode from a temporary hash-verified private source snapshot. Recheck source
  and manifest before commit. Source/library/plan/manifest remain untouched.
- Exact positive window, maximum 30 seconds; snapshot cap 256MiB. No implicit
  truncation, stretching, padding or loop. Default encoder checks timestamped
  sample coverage and bounded seek preroll. Source endpoints quantize to nearest
  48kHz sample. No external FFmpeg process, full mix or video render starts.
- Idempotent key binds manifest, candidate, source/window/credits, proposed
  controls and encoder version. Exclusive owned lock prevents concurrent
  commits. Reuse checks actual PCM format/duration/byte count/hash and receipt
  binding. Altered, truncated or incomplete prepared output is rejected without
  silently replacing a saved preview.
- Audio commits before atomic receipt. A crash between those commits remains
  incomplete, never ready. Stale locks require review, not automatic removal.
  Cancellation is cooperative between chunks/frames/stages. Only this call's
  temporary directory is cleaned after verifying its resolved absolute location
  remains inside this job. No library deletion or input rewriting.

Injected seam: `encoder(snapshot_path, temporary_wav_path, source_in, source_out,
token)` plus a required `encoder_revision`. Always labelled
`test_encoder_used=true`, separate from the actual encoder's cache key. It
receives the private snapshot, not the original path. No listener, model,
provider, network access, library scan or import autostarts from this module.

## Evidence

TDD began with the missing module failure. Later contracts exposed acceptance
of altered cached descriptor metadata and unwanted mono-to-stereo level
conversion; both were handled during implementation, before final review. One
Windows fixture assertion was corrected to compare original bytes/newlines.

79 combined CPU/component checks passed in 5.833 seconds: 21 new audition checks,
21 prior analysis-adapter checks and 37 existing/frozen focused checks. Tiny
synthetic WAVs/injected stdlib encoders cover exact window/sample bytes,
idempotence, stale manifest, changed source/credits, unknown/duplicate choice,
malformed times/identity, outside-job paths, invalid/truncated/altered output,
encoder failure, mutation during encoding and cancellation. One default PyAV
test extracts a two-second synthetic source with different values each second,
checking actual offset handling and native mono level preservation. No external
FFmpeg job or full soundtrack is required. Frozen hashes are unchanged.

No real owner audio, model, GPU, network, library scan/download, browser, Adobe,
service change or normal-app audition occurred. The suite retains auth, routes,
UI and native integration. App playback/seek, owner listening and native/package
acceptance remain pending. Synthetic PCM evidence is not creative acceptance.

## Final review: one new finding, left unchanged

- **Whole-source verification precedes the snapshot size cap.** A tiny fixture
  with the cap reduced to one byte is still passed to the source verifier first.
  Expected: size rejection before expensive whole-source hashing. Actual: copy
  and encoder are blocked, but a huge source could consume disk I/O before
  rejection. No large file was created/read. This limits bounded-I/O claims and
  remains unfixed under the standing final-review rule.

Reproduction, test counts and release hashes: `final-review.json`. No repair was
applied after that probe. Existing checkpoint/telemetry/global override/action
interval/silence status/creative/native findings remain separate and unchanged.
No approval question, owner wake-up, cross-task reply or inference job was issued.
