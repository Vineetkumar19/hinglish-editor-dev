# Editor Handoff in Storylens

Open **Editor Handoff** in the Storylens feature menu. It lists **Premiere Pro**, **After Effects**, **DaVinci Resolve**, and **CapCut** in the From and To selectors. The standalone launcher `Start Editor Handoff.cmd` opens the same screen on the local computer. It starts only the handoff service.

1. Choose the source and destination editors.
2. Select the source. Use an existing video for a finished picture and mix, the active Premiere or Resolve timeline for supported editable transfers, Final Cut Pro 7 XML, or a saved CapCut draft. To render an AE composition, select the .aep and enter its exact composition name.
3. Choose **Prepare transfer**. The screen shows the prepared artifact and what to do in the receiving editor. When it shows a video path, you can also import that file directly in the receiving editor.
4. Use the receiving action shown on screen. Premiere requires an open Storylens panel in the intended project for automatic XML import. Resolve needs to be open and activated for its scripting import. After Effects can run the generated script from an empty project. CapCut drafts appear in Home after adding the draft and reopening CapCut.

Rendered media keeps the source editor’s rendered effects and audio as a clip. Editable handoffs preserve supported timeline items, with effects that need rendering reported separately. CapCut’s nested drafts, captions, keyframes, effects, and other advanced processing may require its video export. The editor guard keeps heavy applications from launching on top of one another.

## Verification

- The running Storylens feature menu opened the new screen. The browser prepared Premiere → CapCut and registered the draft. The CapCut saved-project picker then prepared a CapCut → Premiere XML in the same screen.
- All 12 routes produced packages using real local media or draft fixtures. The latest record is `output/editor-link-20261104/editor-handoff-feature-verification.json`.
- Adobe’s native renderer rendered the actual Reel2 linked composition to a silent 720×1280 video with 644 decoded frames at 30 fps. The three After Effects outgoing packages used that file. Silent video now transfers without adding audio.
- CapCut opened and played all three incoming drafts. Rendered movies now keep their embedded soundtrack with the video, which fixed the Resolve draft’s Link Media prompt. CapCut exported the corrected Resolve draft locally as 644 frames at 30 fps with stereo audio. Five sampled frames matched and the waveform comparison measured zero lag.
- Previously verified in the receiving editor: the one-clip Premiere ↔ After Effects Dynamic Link, Premiere → Resolve original-media and complete compound, and a generated CapCut-format draft → Resolve. See the original [native verification record](editor-link-workflow-2026-11-04.md) for the exact clip and effect coverage.
- After Effects saved native compositions for the Resolve and CapCut returns through **File → Scripts → Run Script File**. Both projects showed changing footage after reopening. Adobe rendered 120 frames from each project, with matching sampled picture and stereo audio. The CapCut composition rendered as ProRes with PCM audio had zero measured lag in three waveform windows. The H.264 output had a 21 ms offset, including with a separate PCM source layer. On retest, automatic script launch still returned no native receipt after the empty editing workspace was ready. The manual script command remains the verified route.

## Native Resolve receiver retest

The receiving Resolve application saved test projects for **Premiere → Resolve**, **After Effects → Resolve**, and **CapCut draft → Resolve**. All three matched the expected source paths, track positions, and timeline lengths. The verification exported a Resolve still from each project and compared it with the corresponding source frame. A separate return from CapCut’s native export also passed the exact 644-frame timing audit and two source-frame comparisons. The saved project backup is in `output/editor-link-20261104/receiver-resolve/CapCut-native-return.drp`.

Active Resolve timeline → Editor Handoff also exported a genuine Final Cut Pro XML from the running application. The Resolve adapter now loads the actual installed scripting extension when Python resolves the module name to an empty namespace. Native projects, timing receipts, and picture comparisons are under `output/editor-link-20261104/receiver-resolve`.

## Premiere receiver status

The Resolve and CapCut return files are prepared. Premiere 26.5.2 froze while loading the editing workspace in both a copied project and a new empty project. The empty project also stalled with a fresh workspace layout and temporary default preferences. A separate project started in Import mode reached the Import screen, but Windows marked Premiere unresponsive before the media picker loaded. The two original movies were staged for this test and their hashes match the originals. Premiere must reach a responsive editing workspace before the two return imports can be verified.

The owner’s original workspace layout, preference file, and **Skip import mode** choice were restored after their respective tests.
