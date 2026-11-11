# Photo Collector — screenshot-only build

The owner requests one large screenshot as the only required input. They explicitly
rejected manually copying image/page URLs. The application must identify the main
photo results, search for originals itself, verify matches, and keep files together.
No required URL field or per-photo URL copying belongs in this feature.

The new panel inherits Storylens' existing dark shell, type and controls. This is
one feature panel, not a redesign; the frontend skill's existing-component exception
applies. Its signature is the screenshot tile beside its matched original, with
honest saved / duplicate / needs-review / not-found states. No fabricated counts.

Implementation acceptance: real screenshot upload/paste; local Vision reads visible
captions and publishers; local code verifies actual downloaded pixels; originals go
to a dated collection with source metadata, duplicates avoided, resumable progress
and a portable photo ZIP. Missing matches stay unresolved, never screenshot crops
presented as original downloads. Cleanup is scoped, recoverable collection Trash;
owner originals, previous projects and saved creator guidance remain intact.

Local inference waits in the existing shared GPU queue. Source retrieval releases
that reservation and uses bounded public-network downloads. The new transport must
bind public-address validation to actual connections and check every redirect;
the older Downloader's documented D1/D2/D3 findings remain untouched.

TDD: initial core/transport contract tests were written before the new package.
Real application validation and a final safe adversarial review are required.
Final-review findings must be reported without fixes unless the owner asks.

Latest owner scope: photo-only square grid, eight across on wide screens, Download
overlaid inside each photo. Paste a screenshot, submit, then press After Effects.
Use the open project's root Images folder and create Screenshot 1, Screenshot 2,
etc. Each collection reuses its own bin on retry. Only After Effects is in scope;
Premiere/CapCut photo imports are not implemented. Do not alter the accepted grid
and folder flow while repairing image quality.

Native import has actually succeeded through the visible Storylens After Effects
button. Receipt: output/photo-collector/20261025-010508-9c34ab110077/after-effects/
f0a691419c8d-receipt.json, project A:/AE mere edited files/1.aep, Images / Screenshot 1,
six FootageItems. Native screenshot: output/photo-collector-evidence/ae-screenshot-1.png.
These were a connection check with earlier, undersized sources (624–1200 pixels),
not high-resolution acceptance. The owner explicitly rejected that softness.
Do not delete/move already-imported source files or claim quality was accepted.

Initial live repairs (before final review): visible numeric tile IDs corrected
cross-card model associations; full reference coverage and aligned-pixel agreement
reject cropped fragments and added banners; matching-content resolution prevents
blurred/padded canvases from counting as high resolution. New source selection
compares all bounded matches, chooses the largest clean matching content, reads
the largest responsive rendition and tries known public CDN originals without
constructing enlarged renditions. Files copy unchanged; AE-only WebP/GIF conversion
uses lossless PNG at original dimensions. Default requested size remains 1920px
on the longest side, with a separately enforced matching-detail size.

Current supplementary checks: 41 Python checks including real HTTP handlers with
explicit fixture model/search adapters, native-host folder/numbering mock checks,
and Node UI contracts pass. Browser checks verified paste, actual local Vision,
17 detected main image regions, source downloads, single/all direct saving,
eight columns on desktop, two on a 390px viewport, no overflow and image-overlay
button bounds. The first strict 1920px live run yielded zero eligible originals;
it is a documented limitation, not success. Revised original-source quality lookup
was tried through the actual visible application. It still found zero clean
1920px-eligible originals. A bounded Google public-index fallback encountered
16 real JavaScript/browser-check pages, which are now recognized as unavailable;
no challenge was bypassed. The tested legacy Hindustan Times original-path
attempt returned 404. Neither provider attempt is a successful HD recovery.

Latest owner quality correction is implemented: do not stop at the first matching
thumbnail/source; compare the bounded per-photo results and use the largest clean
matching detail area. Each photo has its own search budget. Cropped search
thumbnails may nominate an original, but that actual original must pass strict
full-photo/pixel checks. Original downloads without separate thumbnails receive
the original-file byte allowance. The selected quality limit is passed by
Download, Download all, retry and After Effects, including older collections;
the old any-size setting cannot silently override the current selection. No
application upscale or lower-resolution fallback is used to meet a size label.

Actual quality-guard validation: the visible After Effects button on collection
9c34ab110077 at 1920px was blocked, reported photo_quality_unavailable and did not
create a second host receipt. All six existing native footage paths remain
present. Their earlier source-to-handoff audit showed identical decoded RGB
pixels, source dimensions and host-reported dimensions. This proves the handoff
did not shrink those files; those original sources themselves were undersized.
Evidence: output/photo-collector-evidence/handoff-pixel-audit.json.

Final safe adversarial review is complete, with two failures deliberately left
UNFIXED per owner instruction. Reproductions and evidence are in
output/photo-collector-evidence/final-adversarial-review.json:

- P1: Move an AE-imported collection to Trash. The physical move invalidates
  its existing AE footage paths until Restore. Probe used fixture files only;
  no owner collection or AE project was moved. Avoid Trash for linked media.
- P2: Name a collection exactly RECEIPT (uppercase). Script-template substitution
  also replaces that word inside the manifest's name, producing invalid host
  JavaScript. Node syntax check reproduced it; no script was run in AE.

No pixel-exact source matching, universal screenshot detection, all-photo HD
recovery, native Screenshot 2+ validation, native project save/reopen persistence,
Premiere/CapCut import or full editing workflow acceptance is claimed. The owner
approved the folder/grid flow but rejected the initial small-source quality.
The high-resolution recovery requirement remains incomplete for this batch.
Working isolated app: http://127.0.0.1:8918/photos.html. Other services/jobs and
the owner's native edits were left running; main 8765 was not restarted.

## Owner-requested production repairs and Premiere validation

This later request supersedes the old 1920px default and the ban on screenshot
previews above. Default originals must preserve both screenshot-tile dimensions
and real matching detail; larger sources are preferred. HD/4K filters remain.
The owner explicitly approved exact-pixel labelled previews followed by native
same-item upgrades. No artificial enlargement or claim that previews are HD.

The earlier Trash/path and RECEIPT/template failures are repaired. Trash/Restore
was exercised through the running app on collection 473fda36039c; all 17 actual
native media paths and byte hashes remained unchanged. Source input named RECEIPT
was pasted/submitted normally and imported successfully. AE Images/Screenshot 2
and Screenshot 3 were verified live. Screenshot 3 initially held two originals
and 15 previews, then automatically replaced eight preview items: same 17 native
IDs, same folder ID, ten originals and seven previews. Native original Photo 4
was opened and inspected. Decoded source/native file pixels and dimensions match.
Evidence: production-native-pixel-audit.json and production-trash-check.json.

The installed Premiere panel was opened through Window > Extensions > Storylens.
Its first startup exposed a real Adobe mixed Node/browser global export bug;
meaningful failing VM tests preceded repairs to panel-model.js and photos-model.js.
The reopened panel connected to source-timeline_SOUND and displayed all 11 tools.
It was docked in the current workspace; no timeline edits were made.

Premiere's actual Photo Collector button imported collection 473fda36039c into
Images/Screenshot 1: 17 media items, ten matching originals and seven labelled
previews. Native bin count and Source viewer Photo 4 were visually inspected.
The first repeat exposed Windows file locking of already-linked converted PNGs.
A failing regression preceded the repair: identical conversions are now reused;
changed source content gets a different file rather than overwriting linked media.
The main service's owning chat reloaded verified idle 8765 without editor restart.
The real repeat then confirmed 17 already-present native items, zero new items,
the same folder ID and unchanged source paths. Host-specific UI receipts now
show Premiere rather than reusing an earlier AE confirmation.

The missing-first-receipt duplicate-bin issue was separately repaired for this
new Premiere request. The native adapter recovers a collection bin from its media
identity even without a saved folder ID. Mixed Windows paths, same-item upgrades
and uncertain retry recovery pass the mock-host fixture. Loss of a live platform
receipt was not deliberately injected. Actual live Premiere preview-to-original
replacement, project save/reopen and export remain untested. The owner project
was left open with its new bins unsaved; AE stayed closed throughout this check.

53 targeted Python unit/component/HTTP tests pass, plus the Node UI/native/CEP
checks. Tests are supplementary to the actual panel/native receipts. Evidence:
premiere-first-native-receipt.json, premiere-repeat-native-receipt.json,
premiere-native-audit.json and premiere-native-original-viewer.png under
output/photo-collector-evidence. Ten originals remain below 1280px long edge;
seven exact sources unresolved. This is not universal HD recovery or native
verification of the other ten tools in the unified suite.

Final Premiere panel reload/retry shows the correct host-specific receipt without
the earlier stale error. The native UI was released to “Uploading Ai editor” for
its separate suite checks. Final panel proof: premiere-final-panel-proof.png.
The shared suite package was rebuilt after the compatibility and adapter repairs.

Final adversarial review used mock host objects only. A NEW confirmed P2 remains
unfixed: rename an imported photo inside Premiere, then import the same collection
again; the adapter creates another media item in that same bin rather than finding
the renamed item, because photo identity is encoded in its name. Existing media
and timeline layers are retained. Reproduction and scope are recorded in
premiere-final-review.json. The earlier missing-first-receipt problem is repaired;
do not conflate these cases. The prior standalone AE unsaved-project switch finding
also remains outside this Premiere follow-up. No further repairs were made after
this final review, following the repository's owner instruction.
