# Native editor suite validation — 25 October 2026

Premiere Pro is the only open Adobe host. This task owns its UI reservation.
Owner-approved separate recovery copies of both open projects were saved before
the Premiere-only restart; original file hashes were preserved. Both reopened.
Testing uses Storylens Plugin Check Recovery f3475c, never the owner original.
Do not open After Effects concurrently or infer its acceptance from Premiere.

The shared panels are installed with eleven tool entries. Several workflows
still need integration or native acceptance; installed controls do not prove a
finished feature. The table separates native editability, visible appearance,
and remaining acceptance work. Tests and prepared handoffs are supplementary.

Latest owner scope narrows the active acceptance work to the camera/shared-script
workflow, Smart Clean, Script Edit, captions/selective long typography, Sound
Design, video-only B-roll, AE templates/photos and paired Beat/Cinematic.
Unrelated tools remain available but their checks below are deferred; this is
not a request to finish every one of the eleven tools now. Publishing is
preparation/queue work only, with no real upload.

| Tool | Premiere native result | Premiere appearance/playback | After Effects native result / appearance | Remaining limits |
| --- | --- | --- | --- | --- |
| Smart Clean | PASS: separate editable 30 fps timeline with three cuts and stereo audio; source trims and 300-frame duration unchanged | PASS: uninterrupted playback reached 00:00:07:11 from the ten-second input | Pending installed-panel check | AE accepts supported straight footage only; original composition is preserved |
| Script Edit | Technical transfer PASS for short two-clause case: editable 30 fps timeline, two cuts, stereo | Actual playback reached 00:00:07:09 | Pending | Engine report is REVIEW_REQUIRED; panel review handling remains unaccepted. Technical score does not confer semantic approval |
| Auto Captions | PASS for fresh short Caption 2: native 30fps/timecode, individual Source Text, exact installed face, transform/opacity/blur keys; Before edited to Earlier and restored | PASS for this ten-second sample: compact white/lime text, sampled motion and uninterrupted playback to 10:00 | Pending | Not every-frame reference comparison, other styles or AE acceptance. Full-canvas word hit boxes can require timeline selection/temporary track isolation |
| Add B-roll | PARTIAL: actual washing-machine selection inserted with exact trims; native repeat reused its timeline. Fresh apartment prepared clip also imported; separate AV1 original import FAILED | Washing-machine playback from zero reached35:21; apartment active pixels inspected and playback02:10 to35:21.30fps/stereo retained | Pending | Fresh ordinary local chat found7options/4of10moments; quality89 failed coverage/duration. Apartment original codec rejected; whole bank/handoff unaccepted |
| Smart Visuals | No native image import warranted: latest real result has zero assets | Actual ordinary chat corrected housing/PG context; no qualified images | Pending | Normal local plan preserves black/manual5/no-popups. PG paying-guest meaning kept without Gutenberg or a redundant question. No-match remains partial; quality95 is not semantic acceptance |
| Smart Zoom | Deferred under latest scope | Deferred | Deferred | AE unsampled XML effect keyframes are explicitly unsupported |
| Sound Design | Manual analysis/routes/ranked review wired and component-tested; actual run and native originals still pending | Pending real auditions/listening | Pending | Automatic placement remains a separate gate. New source-item dedup is source-only until package installation. Protected Sound findings remain unfixed |
| Beat Studio | Pending markers and supported effects | Pending | Pending | Native AE beat effects are unsupported; do not claim parity |
| Cinematic Reels | Pending selected shots, music, beat-aligned native cuts | Pending | Pending | Verify footage trims and original music, not just an MP4 preview |
| Downloader | Deferred under latest scope | Deferred | Deferred | Existing service checks do not establish native playhead placement |
| Photo Collector | PASS:17items,ten originals/seven labelled previews; repeat import zero new items;17confirmed after save/reopen | PASS: native bin and original Photo4 inspected | Standalone native checks passed; installed-panel bridge remains pending | Live preview upgrade untested; seven originals unresolved; rename/reimport duplicate finding remains unfixed |

## Evidence

- `output/plugin-validation/premiere-clean-engine.json`: actual Smart Clean job.
- `output/plugin-validation/premiere-clean-30fps-import.png`: native cut timeline.
- `output/plugin-validation/premiere-clean-30fps-playback.png`: actual playback end.
- `output/plugin-validation/premiere-original-preserved.json`: before/after native
  captures have the same source clips, trims, paths, frame rate and duration.
- `output/plugin-validation/premiere-script-engine.json`: actual shared-script
  engine job 0cb8a534e45a, complete with a saved two-section edit decision list.
- `output/plugin-validation/premiere-script-import.png`: actual native two-cut
  timeline, linked original audio and the panel's shared script.
- `output/plugin-validation/premiere-script-playback-end.png`: actual 00:00:07:09
  playback end. Accessibility time text was stale during playback; the native
  timeline and Program monitor screenshot show the final time consistently.
- `output/plugin-validation/premiere-caption-engine.json`: current caption job
  receipt, with a failed timing-overlap quality check.
- `output/plugin-validation/premiere-caption-playback-end.png`: native 10:00 end.
- `output/plugin-validation/premiere-caption-native-font.png`: independent word
  and bracketed font field.
- `output/plugin-validation/premiere-caption-font-warning.png`: actual Resolve
  Fonts warning naming StorylensCaptionOne-Bold.
- `output/plugin-validation/font-diagnosis.json`: exact source/installed names,
  matching hashes, unresolved Adobe recognition and preservation limits.
- `output/photo-collector-evidence/premiere-native-audit.json`: actual photo IDs.
- `output/photo-collector-evidence/premiere-native-original-viewer.png`: original.
- `output/photo-collector-evidence/premiere-final-review.json`: unfixed rename case.

## Component checks at this checkpoint

39 focused Python tests passed (panel, native integration contracts, visual
choice counts, photo suite integration, timeline cuts, and four HTTP endpoint
tests). Fourteen Node tests
passed (native adapters, CEP mixed-context models, panel request contracts).
These results do not replace the native checks above.

## Installation reconciliation

The stale installed AE `jsx/photo-import.jsx` was reconciled while AE was closed.
The old helper is backed up outside Adobe's extension-discovery folder; source,
rebuilt package and installed helper now hash to CE236A8F…. Receipt:
`output/plugin-validation/ae-photo-helper-reconciliation.json`. This is a file
reconciliation, not native AE acceptance. The CEP suite is the primary path;
optional UXP coverage is
narrower and has not been natively validated.

## Current caption repair gate

The 80 ms readability hold overlapped the next caption by 20 ms in the actual
sample. Two new regression tests failed before the change. Three new boundary
tests now pass: balanced slides, punctuation/SRT export and preserved silence
holds. Only extra hold is clipped at the next cue; measured words and typography
are unchanged. The 31 existing general-caption checks have five identical
failures before/after this repair (old UI/template and typography assertions).
Do not report the whole caption suite green. Full results:
`output/plugin-validation/caption-boundary-regression-results.json`.
Fresh actual panel job67d74232d76b has quality100/100 and zero cue overlaps.
The owner-approved recovery/restart resolved actual Adobe font recognition:
Before Properties reads Storylens Caption One/Bold without brackets. No face
substitution or font/profile change was used. Both recovery copies reopened;
17 photo items were still present. Receipt: premiere-restart-recovery.json.

Native transfer audit then found a separate source30/sequence60fps defect.
One new regression with four rate cases failed first; the exporter now updates
the canonical nested video/data TrackGroup timebase plus Adobe display enum.
Eleven focused codec/cue tests pass. Normal Add result re-exported the actual
saved local-caption result to editor-handoffs/e8d0d757547df5/CAPTIONS-001.prproj.
Premiere Sequence Settings AND its saved native recovery now confirm30fps,
8467200000ticks/frame and30fpsTimecode. Before->Earlier->Before was repeated
on this import; all original words were checked restored in the saved text
blobs, and all temporary track visibility changes were restored. Full native
playback was repeated after text restoration and reached10:00.
Evidence: output/plugin-validation/premiere-caption-30fps-acceptance.json and
premiere-caption-30fps-{settings,font,word-edit,restored-resting,final-motion,
final-playback-end}.png. These checks cover this sample only.

## Final review

The suite's final adversarial review has not started. Do not call preliminary
implementation repairs final-review findings. Preserve the confirmed Photo
Collector rename/reimport issue without fixing it unless the owner requests it.
CapCut is a separate companion workflow and remains natively unverified.

## Subsequent real local-model and native checkpoints

Fresh normal B-roll chat03148823cc9a41fe / enginea87c39c6a791 completed with
seven options over four of ten moments. The actual quality report is89/100,
passed=false: coverage and spoken-line duration remain open. The earlier
keyword-rule failure is absent. Actual events took955.362seconds; these are
application boundaries, not pure GPU/model times. Full result and session:
`output/plugin-validation/broll-normal-chat-terminal.json`.

An explicit test-operator choice of the genuinely offered apartment video
web:6fae583c1519ba0d was made after inspecting original and prepared frames.
Premiere rejected its AV1 original with unsupported compression type. The
separate prepared H264 clip did import: native30fps, V2frames64..93, source
0..29/30s, original35.7s black video/stereo preserved. Program pixels and playback
02:10..35:21 were observed. This is partial transfer, not full handoff acceptance.
Receipt: `output/plugin-validation/premiere-broll-apartment-native-partial.json`.
The original codec failure is recorded without a transcode/source overwrite.

The third identical ordinary Smart Visuals request in chat542f7a0a2f764b90
used the configured local14B planner and engine8f1392b1d630. It retained housing
context and the saved “PG (paying guest) accommodation” meaning, rejected the former Gutenberg
identity, and did not ask an unnecessary question. Two subjects/zero verified
images remained. No native image insertion was warranted. Receipt:
`output/plugin-validation/visuals-context-third-terminal.json`.

New shared clarification handling reads the typed job-local receipt, verifies
its output-resolution binding and asks the actual question before recovery or
asset collection. Original sources/profile/outcomes are retained. Four new
controller tests failed first, then passed. The live E2 run did not need a
question, so its clarification path is CPU-tested, not live-triggered evidence.
Focused runs passed28Python component checks and29authenticated HTTP/component
checks (overlapping suites), plus18Node adapter/frontend checks. These do not
replace pending real Sound/Beat/Cinematic/AE acceptance. Twelve previously
protected final findings remain unfixed; the initial native AV1 interoperability
failure above is recorded separately.


25 October follow-up: Premiere-only installed-panel Sound manual transport verified for actual normal-chat job9ade0cafcfa6:10s auditionUIplayback,full176.7735sCylinderFouroriginalbinimport,repeatno-duplicate; semanticcoverageFAILED/pending,subjectivelisteningBLOCKED(audioinputunsupported),notfullmix/AEapproval. Protected findings now16,allunfixed. ActualB-rollAV1compatibilityNEW259e262d6ca94b59eebda6c8created/playedback00:00to35:21,actualapartment02:10/native30fps/in-out/sourceaudioverified;fulloriginaltrimmingunavailabledisclosed. Prepared270x480only,originalbytes/oldfailed038areceiptkept. Deferredpreviewsharedcontract33focusedPython+18Nodepassed;realunselectednegativebankCOPY sourceplays/range206,oldpreviewhidden; actualSave&rebuildreadyH264/AAC29.1andplayverified. Thisdoesnotapproveemptybanksemanticsorallfeatures. Evidence:output/plugin-validation/sound-native-original-import-receipt.json,premiere-broll-codec-repaired-native.json,broll-deferred-preview-live.json.
