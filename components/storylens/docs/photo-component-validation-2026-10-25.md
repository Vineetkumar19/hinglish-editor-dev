# Photo component validation — 25 October 2026

Status: **36 affected component tests passed**. Ten are new focused coverage
cases. This is bounded offline validation, not a new native acceptance run.

The coordinator released only Photo Collector component files/tests/docs while
the suite owner retains Adobe and shared integration ownership. No Adobe state
capture/input, service restart, model/GPU job, online retrieval, download, media
render, packaging or installation was performed in this stage. The latest scope
correction was respected: no unrelated eleven-tool validation or caption work.

## Existing coverage inspected before additions

- `tests/test_photo_collection_service.py`: scoped saves/reopen, same-collection
  retry, quality limits, original dimensions/provenance, duplicates and source
  verification. It already supplied an offline analyser/search/fetch fixture.
- `tests/test_photo_production.py`: metadata Trash preserves a linked original
  across service reopen, exact script-name serialization, quality axes and
  mocked AE same-item upgrade/final-confirmation timing.
- `tests/test_photo_previews.py`: immediate labelled previews before analysis.
- `tests/test_photo_editor_plugin.py`: complete receipt/project binding, native
  fixture behavior, lossless WebP preparation and reuse of Adobe-locked files.
- Existing AE/Premiere JS fixtures already covered numbered AE bins and ordinary
  same-item upgrades/Windows paths. No duplicate JS fixture was added.

The missing coverage was the Python collection/manifest/receipt association
across two batches and a new service instance, byte-exact original versus
preview evidence, and specific missing/cross-project/cross-batch rejection paths.

## New fixture and tests

Dedicated file: `tests/test_photo_batch_contracts.py`.

It reuses `CollectionServiceTests.make_service` rather than duplicating that
source provider. Data stays in a `TemporaryDirectory` under workspace
`tmp/photo-batch-contract-*`. The source is the existing deterministic synthetic
640×420 PNG fixture; screenshot photo tiles are 280×184. The three fixture rows
include two matching placements of that original and an unresolved photo with
an exact screenshot preview. A second screenshot changes a background pixel,
giving it an independent upload/source hash while retaining repeated photo
content, a normal multi-screenshot use case.

The analyser, search and byte fetcher are local fakes. Synthetic URLs use
`photos.example` / `publisher.example`; no network request is made. The native
importer is replaced by an assertion that fails if called. Reopened service
instances likewise forbid analysis/fetch/native calls for the tested operations.
Fake receipt helpers explicitly supply `Screenshot 1`/`Screenshot 2` and host IDs.
Thus the tests prove association/persistence, **not native bin numbering**.

| New test | Assertion |
| --- | --- |
| `test_two_independent_batches_keep_separate_receipts_and_retry_associations` | Different collection IDs/source hashes/output directories and disjoint media paths; each keeps its own mock native folder/project receipt after retry. First source bytes stay unchanged. |
| `test_original_bytes_dimensions_and_provenance_are_distinct_from_labelled_preview` | Saved PNG is byte-identical to the supplied original at 640×420; unresolved preview is 280×184, exactly equals screenshot crop pixels and remains `screenshot-preview`. Source/page/rights metadata is retained. |
| `test_both_hosts_receipts_survive_a_new_service_instance` | AE and Premiere receipt files and per-host folder/project association persist after recreating `PhotoService`; later manifests reuse the correct stored identity. |
| `test_missing_original_is_rejected_before_any_receipt_is_saved` | Removing only temporary original/download copies stops manifest preparation and records no false native success. |
| `test_missing_labelled_preview_is_rejected_instead_of_silently_dropping_a_photo` | A deleted temporary preview stops preparation rather than quietly reducing the requested batch. |
| `test_wrong_project_receipt_is_rejected_without_overwriting_pending_manifest` | Wrong-project confirmation is rejected; the pending manifest remains and no success receipt is written. |
| `test_one_batch_receipt_cannot_be_attached_to_another_batch` | A receipt for batch one cannot satisfy batch two or overwrite its pending association. |
| `test_original_and_preview_links_survive_metadata_trash_restore_and_service_reopen` | Both original and preview paths/hashes and the mock native folder ID remain stable through archive, new service instance, restore and new manifest preparation. |
| `test_preview_path_cannot_escape_its_collection_preview_directory` | A temporary `../outside.png` reference is rejected; its bytes remain unchanged and no pending native transfer is persisted. |
| `test_preview_cannot_be_reported_as_fulfilling_a_requested_original` | A native receipt labelling a requested original as a preview is rejected, with no success receipt saved. |

## Observed failure and narrowly scoped repair

Initial command:

```powershell
.venv\Scripts\python.exe -m unittest tests.test_photo_batch_contracts -v
```

Observed: **8 tests run, 7 passed, 1 failed** in 6.328 seconds.
`test_missing_labelled_preview_is_rejected_instead_of_silently_dropping_a_photo`
failed with `AssertionError: ValueError not raised`.

Cause: `hinglish_photos/editor_plugin.py` used `continue` when a declared preview
path was absent or outside the previews directory. A partially populated manifest
could then be accepted as if it represented the available screenshot batch.

The only production change in this stage is in that existing preview branch:
reject a path outside the collection with `Photo file invalid`, and reject a
missing declared preview with `Photo file missing`, preserving confirmed originals.
The diagnostic directs restoration of the file or resubmission of the saved
screenshot. Native preparation no longer silently drops that declared photo.
No service.py change was needed. No automatic recovery, source replacement or
shared error catalogue change was introduced.

The eight original added cases then passed alongside affected existing checks
(**34 tests**, 33.942 seconds). Two isolated boundary cases were added afterward
for the preview directory escape and original/preview receipt distinction; they
exposed no additional failure. These are supplementary review coverage, not a
claim of another pre-implementation TDD cycle.

## Final execution and evidence

Exact test invocation:

```powershell
.venv\Scripts\python.exe -m unittest tests.test_photo_batch_contracts tests.test_photo_editor_plugin tests.test_photo_collection_service tests.test_photo_production tests.test_photo_previews -v
```

Observed: **36 tests passed**, exit code **0**, **32.318 seconds**. The full
captured stdout/stderr is saved at:

`output/photo-collector-evidence/component-batch-validation-2026-10-25.log`

The PowerShell runner buffered the test output, wrote that log, printed its final
seven lines and returned the Python exit code. No mocks are presented as native
receipts. The earlier 53-test broader execution and actual Adobe results remain
historical evidence in `docs/photo-adobe-readiness-2026-10-25.md`; that entire
broader suite was not rerun or upgraded to a claimed 63-test execution here.

## Handoff and remaining acceptance

Changed files in this stage:

- `hinglish_photos/editor_plugin.py`: missing/invalid declared preview rejection.
- `tests/test_photo_batch_contracts.py`: ten offline cases above.
- This document, its machine-readable evidence receipt, and an appended checkpoint
  in `docs/photo-adobe-readiness-2026-10-25.md`.

Shared/native helpers, mirrors, UI/bridge/server, packaging, installations,
`docs/PROJECT_TASK_MAP.md`, approved Serif Circle and owner media were untouched.
No running Python process was reloaded by this component owner. The suite owner
must decide when to load the current feature module in its reserved application.

Remaining live checks, exclusively after coordinated host release:

1. Verify the missing-preview failure through the actual panel/shared error
   presenter using designated test data. The adapter diagnostic was tested here;
   the shared catalogue's visible message and recovery action were not inspected.
2. Genuine Premiere preview-to-original replacement preserving native references.
3. Native Premiere Screenshot 2 creation and separate retry association for two
   actual batches; the mock receipt numbers are not that acceptance evidence.
4. Adobe project save/reopen with persistent imported media and future retry
   association. Recreating `PhotoService` tests backend persistence only.
5. AE docked-panel transfer in a separately reserved one-host session, not while
   Premiere is open. Previous standalone AE import is separate evidence.
6. Larger exact originals for the seven unresolved photos remain a separate
   permitted recovery task; no online recovery was attempted during this stage.

Protected prior findings were neither altered nor reclassified: Premiere
rename/reimport duplicate items (`premiere-final-review.json`) and standalone AE
unsaved-project switch (`production-core-review.json`). No new unresolved failure
was found in these ten bounded component cases after the missing-preview repair.
This does not establish end-to-end Adobe acceptance or an inability to break.
