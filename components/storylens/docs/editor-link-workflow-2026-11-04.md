# Storylens editor handoffs

## Verified in the editors

- Premiere → After Effects created a native linked composition from real Reel2 footage. After Effects → Premiere showed the same composition at 80% scale and again at 100% on frame 29 after saving each AE change. The test used one clip. The exact cause of the earlier blank preview remains undetermined.
- Premiere → Resolve used original media and XML for Reel2. All 80 audio channel entries (40 stereo placements) and two crossfades matched the source timing. Resolve’s complete compound contains all 83 native items, including the transitions. The original editable import remains available.
- Premiere → Resolve also worked with a rendered appearance cache on the Reel1 graphics test. Resolve matched three sampled cache frames, including the text and blur at 00:00:12:16. Graphics and effects are baked into this cache. Premiere used a substitute for the missing test font.
- CapCut-format draft → Resolve imported the prepared editable draft with one video item and 80 audio channel entries. This used a generated local draft. Native CapCut playback and a CapCut-saved round trip still need verification. The editable draft does not carry the two crossfades.

## Route status

| Source | Premiere | After Effects | Resolve | CapCut |
| --- | --- | --- | --- | --- |
| Premiere | — | Live one-clip test passed | Editable and compound passed. Rendered graphics tested separately. | Draft registered. Native open pending. |
| After Effects | Live one-clip test passed | — | Pending | Pending |
| Resolve | Native XML and appearance media prepared. Premiere import pending. | Native import script prepared from the appearance media. AE run pending. | — | Corrected draft registered. Native open pending. |
| CapCut | Editable XML prepared. Premiere import pending. | Native import script prepared. AE run pending. | Prepared draft imported. CapCut-saved source pending. | — |

Premiere opened to Home during the return check. The desktop Open Project, File menu and keyboard controls left it on Home, and the Storylens bridge reported zero connected Premiere panels. No Resolve-to-Premiere import was confirmed. The CapCut Home entries are isolated draft registrations. Use the Resolve draft named **Storylens Resolve to CapCut timing test v2**. The earlier diagnostic entry duplicates the stereo channels.

## Saved results

- Resolve project **Storylens Reel2 Direct Bridge 20261104**. Use the timeline ending in **complete compound with fades**. Native backup under `output/editor-link-20261104/one-command-validation/Reel2-complete-compound-with-fades.drp`.
- Adobe test projects in `output/editor-link-20261104/projects`, named `Reel2-adobe-two-way-test.prproj` and `Reel2-native-linked-test.aep`.
- Native Resolve editable export in `output/editor-link-20261104/resolve-native-export/original-edit.xml`. The 644-frame SDR compatibility clip and its XML are in `resolve-appearance-cache` under the same run.
- Reel1 graphics backup under `output/editor-link-20261104/layered-effects/Native-Effects-Handoff.drp`.
- See `adobe-live-update-verification.json`, `audio-timing-audit.json`, and `full-compound-nested-verification.json` in the run folder. The comparison of the Resolve compound render to a historical Premiere mix found zero sample lag at 48 kHz and a level difference. Full audio mix parity remains unverified.

## Repeat the original-media Premiere handoff

Open the intended sequence with the Storylens panel connected and have an activated Resolve session available. From the Storylens workspace run:

```powershell
& '.venv/Scripts/python.exe' 'tools/editor_link/send_to_resolve.py' --folder 'output/editor-handoff-new-revision' --project 'My Resolve Handoff' --compound
```

Use a fresh folder and destination project for each new source revision. Use `--resume` with the same arguments for the same frozen XML revision. The command checks the supported properties and reports unsupported appearance. It leaves the original ungrouped import beside the compound. Its explicit `--preserve-appearance` option requests a native Premiere render. The manual Premiere render route was verified with Reel1. The new SDK-triggered render remains unverified.

For native Dynamic Link use **Replace With After Effects Composition** from Premiere, or **File → Adobe Dynamic Link → Import After Effects Composition** for an existing comp. The Reel2 recovery followed a clean reopen, waiting for the linked media to load, and dismissing the cache and missing-font notices. It needed no intermediate render.

[Adobe Dynamic Link documentation](https://helpx.adobe.com/after-effects/desktop/work-with-other-applications/work-with-dynamic-link/dynamic-link-effects.html)

[Adobe Final Cut Pro XML limitations](https://helpx.adobe.com/premiere/desktop/render-and-export/export-files/export-a-project-as-a-final-cut-pro-xml-file.html)

[CapCut project interchange documentation](https://www.capcut.com/help/how-to-export-pro-project)

## Visible handoff feature

See [Editor Handoff in Storylens](editor-handoff-feature.md) for the live entry point, all 12 package checks, and the current native verification scope.
