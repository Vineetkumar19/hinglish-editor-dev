# Copy Paste

Native After Effects media-slot replacement for the **existing Storylens panel**, not another extension. No LLM, GPU, rendering, source-file overwrite, project save or application launch.

The compact controls are **AE Project / Explorer · Copy · Paste · Undo**, in one row.
AE Project is the default source. Select imported media in the Project panel,
copy it, select its outer template layer on the main timeline, and paste. Each
paste advances that template's own placeholder pointer; nested compositions do
not need opening. Explorer remains an explicit secondary source.

Media always fills the placeholder canvas, cropping excess edges while retaining
the template's authored transforms/masks. Short videos hold their last frame;
replacement audio is muted. The closed Settings section can restart at the first
placeholder. A full template stops rather than silently wrapping.

The owner-approved custom commands are Ctrl+Alt+Shift+2 Copy, +3 Paste, +4 guarded
Undo. They start automatically with the existing AE Storylens panel, with no
activation click or On/Off control. Copy accepts AE Project or Explorer selection;
Paste/Undo accept AE only. Closing the panel stops the scoped helper. Native
Adobe shortcuts remain untouched. These chords can be mapped to mouse buttons.
No ordinary Ctrl+C/V interception, startup registration or typed-text logging.

Routine success is quiet; optional media/slot confirmation lives in button
hover text. Real errors appear once, with separate closed Technical details.

## Contract for the shared panel

- Include `model.js`, then `host.jsx` in the AE host context.
- Allowlist `copyPaste` → `storylensPanelCopyPaste` in the existing source/origin/nonce bridge.
- Load `ui.js` and mount `window.storylensCopyPaste({root,host,native,isBusy,clearError,onAttention,keyboard})`.
- Calls: `{action:'copy'}`, `{action:'inspect'}`, `{action:'paste',fit:'fill'}`, `{action:'reset',next:zeroBased}`.
- Optional paste precondition: `expected:{layer_id,source_id,next}`. All must match.
- Native result is JSON with `ok,template,layer_id,next,total,slots,complete,clipboard,pasted` or `{error,code,details,rollback_complete}`.
- Shared catalog codes: `copy_paste_media`, `copy_paste_target`, `copy_paste_template`, `copy_paste_stale`, `copy_paste_full`, `copy_paste_host`, `copy_paste_native`.
- `Copy Paste.jsx` is a developer-only ScriptUI fallback; do not install another extension/menu.

## Isolation, scope and limitations

Named Image/Photo/Picture/Footage/Video/Media/Placeholder/Replace holder paths are traversed recursively. Slot order follows scene in-points, natural names, then layer order. Repeated references to the same holder are grouped; distinct holders using one shared footage file remain separate. Text, logo, particle, texture, background, overlay and audio branches are excluded. Unlabelled assets and solid-color placeholders require template-specific mapping; this version does not guess them. **Not every third-party template/plugin is supported.** Ambiguous or unsupported holders stop without advancing the pointer.

The first paste duplicates the complete composition dependency tree and redirects the selected instance. Later edits fork again if the root or a mutable nested branch is reused elsewhere. Source footage is not globally replaced. An inner native media composition retains the old source dimensions so masks, effects, outer transforms and keyframes stay in their existing layers. Original Aliner comments are kept verbatim at the start; an appended Copy Paste line stores cursor and structure identity. This is saved with the AE project and participates in Undo. The clipboard is in-memory and clears on project switching.

Expressions using explicit named `comp(...)` references are not rewritten. They may continue reading controls from the original template. Existing expression errors, unsupported effects, unusual time remapping and plugin-driven replacement controls are not repaired. Visual behavior must be checked with the actual template. More template adapters can be added without replacing the shared panel.

**Premiere:** its scripting interface does not expose nested media layers inside an AE Dynamic Link composition. This initial feature is AE-only and reports that limit rather than opening AE behind Premiere. No Premiere native acceptance has been performed. Never open both hosts together on this machine.

## Validation status, 25 October 2026

21 Node checks cover nested discovery, exclusion, repeated holders, independent instances, shared inner branches, locked native layers, preserved outer animation data, still/video sequencing, project switching, stale/full cursor guards and rollback. These use native object mocks, not actual After Effects.

The native AE controller could observe the current project but could not operate its script chooser reliably: the reported filename element was rejected as unavailable in the native cache, and coordinates/keyboard focus remained on Search. Both supported controllers hit the same underlying issue. The inventory script was **not run**, no media paste was executed, and no owner timeline/project was changed or saved by this feature. Native visual, Undo, save/reopen and full panel-click acceptance remain unverified.


## Automatic subject framing — 26 October 2026

New copies use the existing local OpenCV YuNet detector on CPU (no LLM, GPU,
network or model downloads). Bounds include forehead/hair and chin clearance;
all detected faces are considered. Face data is cached by source path/size/time.
No-face media keeps the entire image rather than guessing where a person is.
Video analysis samples five source frames; it is not a full-motion face track.

At Paste, a temporary disabled native text probe measures projected comp crops,
2D/3D camera transforms, additive/intersecting masks and track-matte bounds at
sampled visible times. It is removed inside the same native Undo group. The
sharp image is repositioned/scaled within the measured safe region. If subject
safety requires zooming out, a blurred full-canvas duplicate fills excess edges.
Authored outer transforms, masks, expressions, movement and originals are kept.
No rotation or face reconstruction is invented. Copies that existed before the
update can still paste using whole-image safety; copy again to get face bounds.
Previously placed pictures are not silently rewritten by this update.

Irregular masks, matte effects, collapsed-renderer behavior and camera travel
without a common safe viewport can require visual review. Diagnostics are kept
under closed Technical details. Nine sampled viewport times are not an every-
frame safety guarantee. Source cropping that already removed a head cannot be
recovered. The exact runtime evidence/remaining checks belong in
output/copy-paste-evidence/subject-framing-handoff.json when validation finishes.
