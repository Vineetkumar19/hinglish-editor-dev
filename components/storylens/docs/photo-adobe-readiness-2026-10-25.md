# Photo Collector: Adobe readiness — 25 October 2026

This is a file-based handoff and plan, not a new native acceptance run. The suite
owner, **Uploading Ai editor** (`01a147ee-67b7-7310-bcfc-76a5fc16139d`), currently
owns shared panel/bridge/server integration, host adapters, packaging, installation
and Adobe UI. Premiere is reserved by that owner. This readiness assignment made
no Adobe captures or inputs, started no media/model jobs, changed no feature code
or adapter mirrors, installed nothing and changed no security preferences.

## Required workflow and preserved behavior

Paste or choose a screenshot; submit it; display its detected photos in the
accepted square grid with individual overlaid Download controls. The agent finds
available matching original source images without requiring manually copied URLs.
Import into the chosen open editor's root **Images** bin, then a separate numbered
**Screenshot 1**, **Screenshot 2**, etc. bin for each collection. The owner places
the photos manually. Photo import does not add timeline clips or AE layers, change
an existing composition, export, or save the owner's project automatically.

Preserve collection and photo identity on retries; originals should replace the
same preview media items. Preserve source metadata and existing native receipts.
Trash is metadata-only: native-linked media stay at their current disk paths.
Keep the earlier results and findings available.

## Source and ownership map

Paths below are relative to `A:/Full Drive/remove silence`.

| File | Current contract / role |
| --- | --- |
| `hinglish_photos/native_host.jsx` | Canonical shared photo host source. Exports `storylensPhotoImportAE(m)` and `storylensPhotoImportPremiere(m)`, returning receipt objects; `storylensPhotoJSON(v)` serializes host results. |
| `editor_plugins/shared/photo-import.jsx` | Exact source mirror used by suite packaging. Suite owner controls further mirror/deployment changes while integration tests run. |
| `editor_plugins/{after-effects-cep,premiere-cep}/jsx/photo-import.jsx` | Prepared host copies included by each `jsx/host.jsx`. File presence is not evidence of runtime loading. |
| `hinglish_photos/editor_plugin.py` | `prepare(service,id,host,context=None)` creates the typed manifest; `accept_receipt(service,id,host,receipt)` validates and persists native confirmation. |
| `hinglish_photos/aftereffects.py` | Standalone AE launcher/receipt wrapper and shared `prepare_files(folder,paths,photos=None)` media preparation. The plugin path calls the media preparation function without launching AE. |
| `hinglish_photos/service.py`, `quality.py`, `previews.py`, `core.py` | Durable collections, matching/quality policy, exact-pixel labelled previews and source identity checks. |
| `hinglish_app/photo_collector_http.py` | Screenshot collection/history/save/retry/archive/restore and standalone AE routes. No client-selected arbitrary filesystem import paths. |
| `hinglish_app/editor_panel_http.py` | Authenticated suite routes; maps saved context to the photo manifest, preserving native project identity separately from its file path. Suite-owned. |
| `hinglish_app/static/photos.js`, `photos-model.js` | Collector UI and per-host native receipt display. Browser globals remain available when Adobe also exposes CommonJS `module`. |
| `hinglish_app/static/editor-panel.js` | Suite-owned `importPhotos(id)` captures project context, prepares the manifest, requests native import, saves the receipt and watches active searches. |
| `editor_plugins/shared/{cep-shell.js,aftereffects-panel.jsx,premiere-panel.jsx}` | Suite-owned typed bridge and host project guards. Photo transfers use the existing `import` action and `manifest.type === 'photos'`. |

### Adapter consistency checkpoint

A read-only filesystem check during this handoff found **all six copies** below
at **7,183 bytes**, SHA256:

`CE236A8F2309E516B2A0891248526C9D6CD51D5546E21B896F503E85AE825806`

- Canonical source and shared mirror.
- Both prepared CEP host copies.
- Installed `C:/Users/Vineet Kumar/AppData/Roaming/Adobe/CEP/extensions/Storylens-after-effects-cep/jsx/photo-import.jsx`.
- Installed `C:/Users/Vineet Kumar/AppData/Roaming/Adobe/CEP/extensions/Storylens-premiere-cep/jsx/photo-import.jsx`.

The coordinator's earlier installed-AE observation was 7,016 bytes/hash beginning
`A3A66507`; it is historical drift, not the current disk comparison. No copy or
installation was performed by this readiness assignment. The suite owner must
still distinguish disk parity from the actual code loaded in each editor.

## Typed manifest and receipt contract

Requests use the local application's existing authentication (`X-Hinglish-Token`)
and licensing checks. Do not include a token in documentation or evidence.

1. Suite native action `projectContext` obtains the current host/project, without
   requiring an active AE composition for photo import. The suite saves that
   context through `/api/panel/context`.
2. `POST /api/panel/photos` body: `{id, host, context_id?}`. `id` is a saved photo
   collection ID; host is `aftereffects` or `premiere`. A supplied saved context
   determines the host. This route returns the manifest directly, not a wrapper.
3. The suite sends native action `import` with that manifest.
4. `POST /api/panel/photo-receipt` body: `{id, host, receipt}`. Success returns the
   collection snapshot only after validating the host confirmation.

Manifest shape:

```text
type: "photos"
id: saved collection ID
name: saved collection title (not the numbered native bin name)
host: "aftereffects" | "premiere"
photos: [{id: stable photo ID, path: prepared local media path,
          origin: "original" | "screenshot-preview"}]
paths: the prepared local paths represented by photos
expected: previous receipt.project, or null on first transfer
folder_id: previous receipt.folder.id, or null
project_id: current project file path used for receipt binding, possibly empty
panel_project_id: suite's native project identity, added when context is supplied
```

The HTTP wrapper maps `context.project_path` to the photo adapter's `project_id`
when available, while retaining `context.project_id` as `panel_project_id` for
the native guard. An unsaved project's identity must not be confused with its
empty file path. Existing expected-project checks remain in place.

Native success receipt:

```text
status: "done"                 // "failed" plus error on host failure
host: "aftereffects" | "premiere"
collection_id: manifest.id
project: {path, root, name}      // AE root is numeric; Premiere IDs are strings
folder: {name: "Screenshot N", id, parent: "Images", parent_id}
imported: [photo receipt rows]
upgraded: [photo receipt rows]
already_present: [photo receipt rows]
preview_count: number
original_count: number

photo receipt row: {photo_id, id: native media item ID, path, origin}
AE rows additionally report width and height.
```

`accept_receipt` requires the pending manifest, correct host/collection/status,
matching project path when supplied, an identified Images/Screenshot folder, and
coverage of every requested photo with a native ID and matching resolved path.
An original request cannot be confirmed as a preview. It writes a separate JSON
under the collection's `native-receipts/` and updates `native_receipts[host]`.
AE receipts also populate the existing AE status/project fields. A successful
launcher exit, local queue entry or file existence alone is not acceptance.

The CEP shell validates message source, configured local origin, nonce and named
action before invoking the host. Preserve this boundary and the suite's native
project-switch guard; no arbitrary script execution action is part of this flow.

## Native identity, upgrade and file rules

AE bins carry comment `storylens-photos:<collection-id>`. Photo item comments
carry `storylens-photo:<collection-id>:<photo-id>:<origin>`, with a same-path
fallback. `FootageItem.replace` upgrades an existing preview; it does not add a
layer. Already-original items must not downgrade to screenshot previews.

Premiere names photos `Storylens <collection-id> - <photo-id> PREVIEW` or
`... Original`. It uses the saved native folder ID, with identity-based bin
recovery when the first receipt is missing. `changeMediaPath` must return zero
and the actual resulting path must match after Windows path normalization.
The renamed-item limitation below remains recorded; do not assume renaming is
covered by ordinary retry success.

JPEG/PNG and supported native image formats retain their files. WebP/GIF/AVIF
handoffs use a full-dimension PNG conversion, preserving decoded pixels and ICC
profile. Identical conversions are reused to avoid overwriting Adobe-locked
media. Changed source content gets a different file path. The compatibility
directory is currently named `after-effects/` even when used by Premiere; this
directory name does not mean AE was launched.

## Original quality and provenance

Default `min_edge=0` means an original must preserve **both dimensions of its
photo tile in the screenshot**, plus corresponding matching detail. It does not
mean a small thumbnail can be labelled HD. Optional 1280/1920/3840 filters add a
stricter long-edge requirement. The geometry check allows two pixels of rounding
on measured detail; actual source width and height must meet the tile dimensions.
Largest clean verified detail wins within the bounded search. Added banners,
partial-image/collage matches and padded/blurred canvases are not sufficient
resolution evidence. No invented upscaling, generated replacement or fake detail.

Approved previews are exact screenshot tile pixels, separate from originals and
labelled `screenshot-preview` / `PREVIEW`. They are not original downloads or HD.
Raw original downloads and source/page URLs are retained. Provenance fields
include `source_url`, `source_page`, `source_title`, `license` and match evidence;
the collection also saves `sources.csv`, `collection.json` and source hash.
Existing sources have unverified usage rights; retrieval is not a licence claim.

Actual collection `473fda36039c` recovered **10 matching originals and 7 unresolved
previews**. Original sizes span 640×400 through 1213×681 (maximum long edge 1213),
so this batch is **not complete HD recovery**. Unresolved photo IDs:
**3, 5, 11, 12, 15, 16, 17**. Publisher/source metadata is preserved, including MI,
Hindustan Times, Zee, BBC, The Quint, India Today, Doolnews and CricTracker.
Do not infer all photos were from the searched season solely from that query;
the screenshot contains varied source cards, and identity matching is per tile.

## Existing evidence and exact coverage

All evidence below is under `output/photo-collector-evidence/`.

| Evidence | What it establishes |
| --- | --- |
| `production-first-preview-receipt.json`, `production-upgrade-receipt.json`, `production-native-pixel-audit.json` | Actual AE Screenshot 3 held the same 17 IDs; eight previews upgraded in place, finishing at 10 originals/7 previews. Source/handoff pixels and dimensions were checked. |
| `production-trash-check.json` | Running-app Trash/Restore kept all 17 native-linked paths and file hashes. |
| `production-ae-upgraded-photo.png` | Actual AE Source/Footage viewer inspection of an original. |
| `premiere-first-native-receipt.json`, `premiere-repeat-native-receipt.json`, `premiere-native-audit.json` | Actual installed Premiere panel imported 17 photos into Images/Screenshot 1; ordinary repeat returned 0 new/17 existing items, same IDs, folder and paths. |
| `premiere-native-screenshot-1.png`, `premiere-native-original-viewer.png`, `premiere-final-panel-proof.png` | Actual native 17-item bin, original Source viewer and correct Premiere receipt with clean final UI. |
| `premiere-final-review.json` | Confirmed mock-host renamed-item duplicate limitation. No owner project was used for that probe. |
| `production-core-review.json` | Earlier mock-host findings. Missing-first-receipt duplication was subsequently repaired for the new Premiere request; the standalone AE unsaved-project finding remains. |

Previous execution passed **53 Python unit/component/HTTP checks**, **11 Node
tests**, and Photo UI contracts. These were not rerun during this read/plan
assignment. Component fixtures cover Windows paths, missing-folder-receipt retry
recovery and native same-item replacement logic; they do not substitute for
unperformed live scenarios. The AE docked-panel test was interrupted, then the
owner explicitly moved to Premiere. Other tools' native suite checks belong to
the suite owner and are not established by this photo result.

## Remaining checks after coordinated release

1. Suite owner verifies the loaded host adapter version and installation parity;
   do not independently reinstall or open AE while Premiere is in use.
2. Exercise a genuine **Premiere** preview-to-original upgrade through normal
   screenshot submission/recovery, comparing native item identity before/after.
   That path currently has component coverage, not a live upgrade receipt.
3. Verify another collection creates Premiere Screenshot 2 while retrying the
   first reuses Screenshot 1. AE Screenshot 2/3 were verified separately; that is
   not native Premiere numbering acceptance beyond Screenshot 1.
4. Save/reopen a designated test project and verify imported media, folder
   association and future retries. Neither Adobe save/reopen path was completed
   by this photo check. The owner review project was left unsaved with added bins;
   current host state is exclusively controlled by the suite owner.
5. Complete AE installed-panel checks in a separately released, one-host window;
   standalone AE imports and source inspection do not prove that panel round trip.
6. Continue bounded original recovery for the seven unresolved photos only when
   requested/released. Preserve honest previews if no larger exact original is
   available; do not bypass publisher/browser challenges.
7. Cover missing media, changed-project and uncertain-receipt failures in safe
   designated test data. Keep native confirmation uncertainty explicit and
   preserve retry/media paths. No native failure injection was performed earlier.

Existing final-review findings remain unchanged pending an owner repair request:

- **P2, Premiere rename/reimport:** rename an imported item, then import the same
  collection again. Expected: reuse its media item. Mock-host actual: duplicate
  item in the same bin because identity is encoded in its name. Existing timeline
  references remain. This is different from the repaired missing-receipt case.
- **P1, standalone AE unsaved-project switch:** switching between two new unsaved
  projects can pass the existing empty-path/root-ID guard. The actual saved
  `1.aep` imports did not exercise this. The suite has an additional project guard;
  that does not erase the standalone finding.

## Caption ownership metadata

The app's returned title for this chat is **ai video/ photo collection**, ID
`01a16924-2717-7e72-876e-76ff825043f9`. Its retrieval summary references Serif Circle.
The available current project chat metadata also lists **Uploading Ai editor**
with a historical Caption 2 summary; it is the shared-suite owner, not established
as a dedicated Serif Circle owner by that summary alone.

No separate current Serif Circle/caption owner could be established from the
50-recent-plus-pinned listing inspected here. This is a visibility limit, not a
claim that no older caption chat exists. Preserve Serif Circle as approved under
`docs/CAPTION_STYLE_REFERENCES.md` (owner approval, 23 October 2026): compact mixed
sans/italic-serif typography, measured row entrances and traced annotations. The
recorded 15-second native check is limited evidence, not exhaustive source-frame
parity. No caption edits, renders or host operation were resumed.

## Later bounded component-validation checkpoint

The coordinator subsequently released only photo component files/tests/docs.
Ten missing offline cases were added after inspecting existing coverage. A new
normal-flow failure was observed first: a missing declared preview was silently
omitted from the native manifest. `editor_plugin.py` now rejects missing/invalid
declared previews, preserving originals. No shared/native files, Adobe apps,
services, installations or caption code were changed. All 36 affected component
tests pass; these fake-receipt tests do not establish native save/reopen, second
batch numbering or live upgrade acceptance. Exact commands, counts, fixture
boundaries and suite handoff are in
`docs/photo-component-validation-2026-10-25.md`. Full test log:
`output/photo-collector-evidence/component-batch-validation-2026-10-25.log`.
The protected prior final-review findings remain unchanged.
