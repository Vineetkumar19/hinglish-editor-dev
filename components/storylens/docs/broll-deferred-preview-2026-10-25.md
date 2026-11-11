# Deferred unselected B-roll preview: feature handoff

Scope: initial performance repair, **`hinglish_broll/pipeline.py` and
`hinglish_broll/report.py` only**, plus dedicated tests/evidence/docs. The suite
owns Sound/native and reviews shared server/UI integration before deployment.
No actual model, provider/network, media render, GPU, job/restart or native action
was started by this task. Saved six-empty-moment project and verification code
hashes remain unchanged. All12 protected findings and provider/cache/policy/key
behavior remain untouched.

Pre-edit collision checks confirmed:

- pipeline.py: `759c7314f06e231da5842ea9707afa216afc2ce13e510524c0f9940ba7bb8619`
- report.py: `b89537b23659685d5a55973fedef161cd8addd344b8b57ab10ad4b4a2213a5bf`

Post-edit hashes are in
`docs/broll-producer-integration-evidence-2026-10-25/deferred-preview-validation.json`.

## Behavior and safety boundaries

`run` now requests aggregate-preview deferral when collecting manual review
options. `write_outputs(..., *, defer_review_preview=False, progress=None)`
retains its default real-render behavior for all existing ordinary callers;
`rebuild_project` explicitly keeps that default and forwards its progress callback.
Test doubles replacing this function must accept its optional keyword arguments.

Deferral is limited to a new unselected manual bank with an **existing nonempty
generated audio-over-black file** in the same job root. A saved owner-selection
sidecar, earlier explicit/default preview request, nonreview mode, nonblack source,
missing source audio, or a resolved source escaping that job root retains the
existing render path. A sidecar is never deleted, rewritten, interpreted as a new
unselected choice or bypassed to obtain deferral.

When deferred:

- No full-sequence preview renderer is imported or called by this branch.
- Every candidate still passes the same original/prepared checks, hashes, crop
  and interval binding. Its prepared option remains playable. Exports and typed
  manual choices are built by the existing paths; no option gains approval.
- The report plays the already-generated `../audio-only-source.mp4`, explicitly
  labelled **Original audio over black**, and explains that the combined preview
  waits for Save & rebuild. The existing button is enabled for that explicit
  request even without a changed selection. Its existing authenticated rebuild
  endpoint and selection/timing behavior are unchanged.
- An older `preview.mp4` is preserved byte-for-byte, but the report does not
  display it as current. Old preview-error text is cleared for the new deferred
  state. No fake successful preview or placeholder media is written.

An explicit preview/rebuild renders normally and records ready or failed. Future
output calls keep that explicit opt-in. Failure uses the existing plain-language
notice/details, never ready status or a stale current aggregate. Legacy reports
without a preview-state field retain their previous file-based display behavior.
The familiar layout/style and three editor buttons remain unchanged.

**Limitation:** deferring a nonblack source without removing its audio playback
would require a suite-approved safe source-media URL/contract. This implementation
does not add an arbitrary-file route, copy/render another source or silently make
audio unavailable; it falls back to the existing render in that case.

## Saved project/report contract for suite review

| Field | Meaning |
|---|---|
| `preview_state=deferred` | Aggregate intentionally not rendered; not failed or ready. |
| `preview_requested=false` | New unselected bank has not requested aggregate rendering. |
| `preview_source=../audio-only-source.mp4` | Fixed generated same-job source only; not an arbitrary path/URL. |
| `preview_notice` | Plain source-audio/deferred instructions. |
| `preview_state=ready` | Current render path completed. |
| `preview_state=failed` | Current render failed; saved edit/choices remain. |
| `preview_requested=true` | Explicit/default aggregate path remains opted in. |

The report only embeds the fixed source URL after checking its resolved path and
existence. Its current combined watch player requires ready/legacy state; it does
not trust an arbitrary `preview_source` or an old file when deferred/failed.

Existing generated-output routing in `hinglish_app/server.py` serves MP4s inside
`output/broll`, so this relative same-job source is within its existing boundary.
**No live HTTP/range/audio check has been run.** Root must verify token/range
behavior in the running app and actual Save & rebuild with the final source.

### Shared interface gate — outside this lease, do not deploy blindly

`hinglish_app/server.py:869` collects `preview.mp4` by filesystem presence,
without consulting these fields. On a newly generated bank with no old aggregate,
the list will be empty rather than a render failure. On a resumed bank retaining
an old aggregate, that shared collector can still list the stale file even though
the feature report correctly hides it. The suite must make the shared result/UI
contract state-aware before exposing a retained file as current. `previews=[]`
with deferred state must not be presented as a failed render or completed edit.
If the shared UI needs the source-audio path in its result, the suite owns adding
and validating that field; this task did not expand server access or edit it.

This is an identified integration boundary, not a shared-code fix or live
deployment acceptance. No service was restarted and no normal B-roll run was
launched here. Shared/native manual-selection behavior remains suite-owned.

## TDD, component integration and measured limits

`tests/test_broll_deferred_preview.py` first exposed the missing optional API.
After adding only the signature and correcting synthetic fixture setup, its
behavioral red run recorded7 tests,4 failures,2 missing-state errors,0.634s:
unnecessary aggregate calls, overwritten old preview, absent deferred state and
no explicit request/real boundary handling. No deferral implementation existed
at that behavioral observation.

The completed focused set passes **117 tests, zero failures/errors,4.112s**.
It includes nine new preview tests plus the prior108 focused checks. New tests
exercise actual output/report/typed-manifest file writing with synthetic media
metadata/checks and a mocked renderer, the ordinary `run` output-call boundary,
and the explicit rebuild default. They verify:

- New unselected review makes **zero aggregate-render calls**, retains real
  fixture source-audio and option links, preserves checker records and keeps
  typed owner choices unselected.
- Explicit preview makes **one aggregate-render call**, emits actual path start/
  completion events and records ready. Nonreview and saved owner decisions keep
  their render path. Missing safe source audio falls back honestly.
- Deferred stale aggregate bytes are preserved and hidden; explicit failure
  never reports ready or plays the failed current aggregate.

The zero/one call counts are measured **CPU fixture behavior**, not successful
media playback or a real runtime saving. Inference and renderer boundaries were
mocked. No fresh semantic or native acceptance was produced.

Progress now uses the existing callback for:

- `Combined preview deferred until you choose Save & rebuild`
- `Rendering the combined B-roll preview`
- `Combined B-roll preview ready`, or the plain failure notice.

These boundaries allow later measurement of the real aggregate-preview path;
the span also includes sequence setup, not an isolated encoder/kernel timer.
There is no measured elapsed saving here. The earlier717.985s mixed downstream
phase and28.139s final candidate/preview tail must not be represented as saved
time, pure model duration or a predicted benchmark improvement.

## Bounded final review and freeze

Two separate final safe probes confirmed an untrusted deferred source URL is
not embedded, and an earlier explicit preview remains opted in. A fresh isolated
import loaded neither `hinglish_zoom.preview`, Torch nor Transformers. No new
breaking point was found in those performed probes. The shared file-presence
collector gate above remains unresolved and was not fixed outside the lease.
No product source was changed after these final probes.

Evidence: `deferred-preview-red-tests.txt`, `deferred-preview-green-tests.txt`,
`deferred-preview-integration-tests.txt` and `deferred-preview-validation.json`
in `docs/broll-producer-integration-evidence-2026-10-25/`.

**Feature lease released to root/suite for import-safe server/UI review.** Actual
source-audio playback, explicit rebuild render, normal application recovery,
native/export handoff and elapsed savings remain live gates. Existing real-media
recovery tests that create encoded fixtures were not run under this CPU/mock-only
lease; the new boundary checks are supplementary, not substitutes for that run.
The six empty moments, all raw negatives and full creator guidance are preserved.
