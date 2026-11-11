# Effects Editing Tools — owner guide

Installed 30 October 2026. Source and panel integration are complete for the 96 listed entries. Actual native AE results are awaiting your testing. No Adobe window was operated and no owner project was saved for this build.

## Open and apply

1. Close and reopen the Storylens panel (the panel only).
2. Open **Effects → Editing Tools**. Choose one of the 16 categories, or search across all categories.
3. Select the required layers/keyframes in your active composition. Set the card’s **Adjustments**, then click its name.
4. For animations, refine SLT controls in Effect Controls or the actual keys in the timeline. Generated graphics contain editable native text/shapes inside their precomp.
5. Star tools for Favourites. Recent records successful changes. Settings persist in panel storage.

## Known limits and inputs

- Native card-to-AE-timeline drag/drop is NOT implemented or verified. Dragging into the panel’s apply area and select-and-click use the same implemented dispatch. Native .ffx files saved through AE can be managed through AE’s own preset workflow.
- No claim that all 96 tools are visually correct in AE: you chose to perform native testing yourself. Automated fixtures check code paths, preservation and integration, not Adobe rendering.
- Camera/3D, effect-property identifiers, native dialogs and renderer output still require your native checks. Language-dependent Save Animation Preset commands may require AE’s Animation menu.
- Roto is preparation, not automatic finished segmentation. Paint, review propagation and Freeze in AE. Tracked blur and screen replacement require reviewed tracking/nulls. Beat-linked motion requires supplied beat markers or an Audio Amplitude layer; it does not detect beats.
- Transitions require two overlapping visual layers, upper incoming and lower outgoing. Place the playhead inside the overlap.
- Capture Motion Preview samples eight real native PNG frames at reduced resolution. Select a precomp (or use the open comp), set its playhead, choose the card to attach it to, and capture. Hover its resulting image to play that short cached sample. The 96 cards do not ship with pre-rendered native sample clips. File access must be enabled in AE for capture/collection.
- Save My Preset uses AE’s actual .ffx save/apply dialogs. Select properties to save or layers to apply. A cancelled dialog is not a saved preset.
- Reset disables owned toolkit expressions/text animators/styling and retains settings. Layout, keyframe operations and native precomposing use AE Undo. Replace swaps a layer source; it does not regenerate a graphic from changed card fields.
- Reapplying expression/styling recipes updates their named controls when safe. Generated graphic builders create a new editable comp; edit an existing graphic inside its precomp.
- Batch Variations deep-copies nested comps, replaces a named static text layer and inserts the versions in sequence. Maximum 20 variants and 100 nested comps; cross-comp expression references are refused rather than silently broken.
- Collect Asset Copies copies media and proxies plus a manifest. It does not save unsaved project edits or create a portable collected AEP. Save a project copy separately.
- Relink uses unique exact filename matches. Multiple matches remain unresolved. Dependency reports show media/effects and first-character font names only when requested; there are no automatic missing-font banners.
- Render Profiles first lists installed native templates. Queue adds an item without starting rendering. Export Short Proof renders up to 10 seconds from work-area start; it temporarily excludes other enabled queue items and restores them. Output format follows the chosen native template, so choose an appropriate filename/extension.

## Category catalogue

| # | Category | Tool | Input / behavior |
|---:|---|---|---|
| 1 | Keyframes & Easing | Easing | Select timeline keyframes. Changes easing without moving keys or changing values. |
| 2 | Keyframes & Easing | Copy / Paste Easing | Copy one selected keyframe, then select destination keys and paste. Values stay unchanged. |
| 3 | Keyframes & Easing | Retime Keyframes | Select at least two keyframes. Keeps their relative spacing and the first key time. |
| 4 | Keyframes & Easing | Reverse Animation | Reverse selected keyframes within their time range, including easing and motion paths. |
| 5 | Keyframes & Easing | Bounce / Overshoot | Select keyed numeric properties. Adds a decaying overshoot after each key. |
| 6 | Keyframes & Easing | Stagger Layers | Select layers. Offset them in timeline order while preserving trims and animation. |
| 7 | Element Motion | Impact Shake | Selected visual layers shake from the playhead and settle in place. |
| 8 | Element Motion | Handheld Drift | Gentle continuous irregular movement; underlying position keys remain editable. |
| 9 | Element Motion | Float | Continuous vertical floating around the original position. |
| 10 | Element Motion | Arc Entrance | A curved entrance into the layer’s existing position with an opacity fade. |
| 11 | Element Motion | Follow Mask Path | Select one mask path on the moving 2D layer. The first path point is the motion origin. |
| 12 | Element Motion | Pulse | Continuous scale pulse around existing scale keyframes. |
| 13 | Text Animation | Masked Reveal | Reveal text through a moving rectangular mask. Use a text layer without existing masks. |
| 14 | Text Animation | Tracking Expansion | Letters settle from expanded spacing into the original text. Original wording and font stay editable. |
| 15 | Text Animation | Word Emphasis | Scale one chosen word. Word is counted from the start of this text layer. |
| 16 | Text Animation | Text Flip | A flat vertical character flip with a fade. No camera or 3D-layer changes. |
| 17 | Text Animation | Text Scramble | Random letters resolve into the editable source text. Intended for text with one uniform style. |
| 18 | Text Animation | Line Reveal | Reveal complete authored lines in reading order with upward motion and soft blur. |
| 19 | Typography & Layout | Responsive Text Box | Create a shape behind each selected 2D text layer. The box follows text edits and transforms. |
| 20 | Typography & Layout | Auto-fit Text | Fit static unparented 2D text within a width and height, preserving its words and font. |
| 21 | Typography & Layout | Balance Lines | Balance complete words across lines. Changes line breaks; retains word order. |
| 22 | Typography & Layout | Split Text Layers | Split a static single-line point-text layer into editable words. Keep the original disabled for recovery. |
| 23 | Typography & Layout | Copy / Paste Text Style | Copy the first character’s style, then apply it uniformly to selected text. Destination words stay unchanged. |
| 24 | Typography & Layout | Lower-third Builder | Create an editable name and subtitle graphic in the active timeline. |
| 25 | Layer Styling | Drop Shadow | Add or update an editable native shadow on selected visual layers. |
| 26 | Layer Styling | Outline | Create a coloured alpha expansion behind selected transparent artwork. Original layers stay intact. |
| 27 | Layer Styling | Light Sweep | Animate native CC Light Sweep across selected layers. Requires that bundled effect to be available. |
| 28 | Layer Styling | Glow | Add or update native Glow radius and intensity. All other Glow controls remain available in AE. |
| 29 | Layer Styling | RGB Split | Create separate red, green and blue layers with a horizontal offset. Keep the original disabled for recovery. |
| 30 | Layer Styling | Copy / Paste Effect Stack | Copy supported effect properties and keys, then paste onto selected layers in this composition. |
| 31 | Transitions | Whip Transition | Select two overlapping 2D clips. The upper layer enters; the lower layer leaves around the playhead. |
| 32 | Transitions | Zoom Transition | Select two overlapping clips. Zoom and dissolve into the upper layer. |
| 33 | Transitions | Flash Transition | Select two overlapping clips. A white flash covers their transition at the playhead. |
| 34 | Transitions | Directional Blur Transition | Select two overlapping clips. Crossfade through native directional blur. |
| 35 | Transitions | Glitch Transition | Select two overlapping clips. Add short horizontal jolts, blur and a flickering dissolve. |
| 36 | Transitions | Shape Reveal Transition | Select two overlapping clips. Reveal the upper clip through a rectangular mask; use an unmasked incoming layer. |
| 37 | Shapes & Annotations | Animated Arrow | Editable arrow path with draw-on animation. Move the precomp or edit the path points. |
| 38 | Shapes & Annotations | Callout | A label, leader line and target dot. Edit the label or move the target in its precomp. |
| 39 | Shapes & Annotations | Highlight | A translucent highlighter bar over your footage. Adjust its position, size and colour. |
| 40 | Shapes & Annotations | Progress Bar | An editable progress bar animates to the chosen percentage. |
| 41 | Shapes & Annotations | Timer | Native editable counter with start value and count direction. |
| 42 | Shapes & Annotations | Bar Chart | One label: value per line. Values must be nonnegative; up to 12 bars. |
| 43 | Documentary Tools | Document Highlighter | A marker strip and optional annotation for a document already on your timeline. |
| 44 | Documentary Tools | Focus Zoom | Zoom the selected layer around a chosen point. Tweak its framing after applying. |
| 45 | Documentary Tools | Photo Pan & Zoom | Slow movement and scale on selected photos. Check that the photo covers the frame. |
| 46 | Documentary Tools | Archival Look | Editable monochrome/sepia treatment, contrast and grain. |
| 47 | Documentary Tools | Historical Timeline | One year: event per line. Creates editable dates, labels and timeline markers. |
| 48 | Documentary Tools | Map Route | A route overlay for your existing map. Edit the native path endpoints; no map download is performed. |
| 49 | Cricket & Sports | Player Stats | Enter your player name and stats. All labels and values stay editable. |
| 50 | Cricket & Sports | Scorecard | Use your own team names, score and overs. No live statistics are fetched. |
| 51 | Cricket & Sports | Player Comparison | Two player names with parallel stats. Enter one label: left value / right value per line. |
| 52 | Cricket & Sports | Team Lineup | Enter one player per line, up to 11. Text and positions remain editable. |
| 53 | Cricket & Sports | Points Table | Comma-separated columns, one row per line. Include a header row; 2–6 columns and up to 12 rows. |
| 54 | Cricket & Sports | Four / Six / Wicket | Editable impact lettering with a short overshoot and fade. |
| 55 | Colour | Exposure & Contrast | Editable native exposure and contrast effects; tune by eye for your footage. |
| 56 | Colour | White Balance | Adjust midtone red/blue balance and green tint. Review skin tones after applying. |
| 57 | Colour | Saturation | Adjust native Master Saturation without replacing other colour effects. |
| 58 | Colour | Duotone | Map shadows and highlights to two editable colours. |
| 59 | Colour | Black & White + Spot Colour | Use native Leave Color. Choose the colour to keep, then refine tolerance on the actual footage. |
| 60 | Colour | Colour Looks | Editable warm, cool, soft or monochrome starting looks. Review and tune for each shot. |
| 61 | Masks & Tracking | Track Matte Helper | Select two layers. Use the upper selected layer as the matte for the lower one. |
| 62 | Masks & Tracking | Rounded Crop | Add an editable rounded mask, intersecting existing masks when present. |
| 63 | Masks & Tracking | Green Screen | Apply installed Keylight. Sample the actual screen colour and refine the matte in Effect Controls. |
| 64 | Masks & Tracking | Roto Assistant | Prepare a separate source copy in Layer view. You must paint the Roto Brush selection, review propagation and Freeze it. |
| 65 | Masks & Tracking | Tracked Blur | Select a visual layer and an already tracked null. Blur follows that null; review drift through the shot. |
| 66 | Masks & Tracking | Screen Replacement | Select a replacement layer, optionally with four tracked nulls named TL, TR, BL, BR. Otherwise adjust Corner Pin points manually. |
| 67 | Camera & 3D | Camera + Null Rig | Rig a selected static camera, or create a new camera if the composition has none. |
| 68 | Camera & 3D | Camera Orbit | Rig a selected static camera and animate an orbit around the composition centre. |
| 69 | Camera & 3D | Parallax | Select two or more unparented 2D planes. Creates a separate scene with depth compensation and camera movement. |
| 70 | Camera & 3D | Extruded 3D Title | Create a separate native Cinema 4D text scene. Existing caption designs and the current renderer stay unchanged. |
| 71 | Camera & 3D | Ground & Shadow | Create a separate 3D scene from selected unparented 2D layers, with a floor and shadow-casting light. |
| 72 | Camera & 3D | Focus Pull | Animate focus distance on one selected camera. Depth of field and aperture become editable. |
| 73 | Layer Utilities | Anchor Grid | Move a 2D layer’s anchor without moving its visible content. Scale and rotation must be static. |
| 74 | Layer Utilities | Align & Distribute | Align visible 2D bounds at the playhead. Distribution spaces centres evenly. |
| 75 | Layer Utilities | Fit / Fill | Fit static unparented 2D content to the frame, preserving aspect ratio and centering its visible bounds. |
| 76 | Layer Utilities | Smart Precompose | Move selected layers into an editable precomp. Full duration preserves composition timing; trimmed duration shifts its internal start. |
| 77 | Layer Utilities | Parent to Null | Create one control null for selected layers that share a parent and dimensionality. |
| 78 | Layer Utilities | Resize to Content | Resize this 2D composition to selected visible bounds at the current frame. Check the rest of the animation afterward. |
| 79 | Timing & Audio | Sequence Layers | Arrange selected trimmed clips from the playhead in timeline order. Overlap is optional. |
| 80 | Timing & Audio | Trim Layers | Trim selected layers at the playhead or intersect them with the work area. |
| 81 | Timing & Audio | Freeze Frame | Hold the source frame at the playhead across the selected clip. Existing time remapping is protected. |
| 82 | Timing & Audio | Footage Speed Ramp | Create an editable normal → fast/slow → normal speed ramp from the playhead. Needs unused source handles and no existing remap. |
| 83 | Timing & Audio | Beat-linked Motion | Select a visual layer and a layer containing beat markers or an Audio Amplitude slider. Links scale to that supplied timing; it does not detect beats. |
| 84 | Timing & Audio | Audio Fades / Ducking | Add editable dB fades, or duck a lower music layer across an upper voice layer’s entire interval. |
| 85 | Library & Templates | Favourites & Recent | Star any tool to keep it here. Recent lists tools successfully applied from this panel. |
| 86 | Library & Templates | Search & Tags | Search names, descriptions and categories across the whole toolkit. |
| 87 | Library & Templates | Capture Motion Preview | Capture eight actual frames from the selected precomp (or open comp) starting at its playhead. Attach the cached preview to a tool ID shown on its card. |
| 88 | Library & Templates | Save / Apply My Preset | Save selected properties with AE’s native .ffx dialog, or choose an existing .ffx to apply to selected layers. |
| 89 | Library & Templates | Reset / Replace | Disable toolkit expressions and owned text animators/effects while retaining their settings. Replace swaps one selected layer’s source with one selected Project item. |
| 90 | Library & Templates | Batch Variations | Deep-copy one selected precomp and replace the named static text layer in each copy. One line per version: Name / New text. Original stays intact. |
| 91 | Project & Delivery | Organize Selected Assets | Move selected Project-panel items into type folders under Storylens Assets. Original files and unselected items stay where they are. |
| 92 | Project & Delivery | Relink Missing Footage | Choose a search folder. Relink only unique exact filename matches; ambiguous names remain for manual review. |
| 93 | Project & Delivery | Dependency Report | Inspect missing media, used effects and text font names on request. The report does not change the project. |
| 94 | Project & Delivery | Collect Asset Copies | Copy file-based footage and proxies into a new folder, with a source manifest. Originals stay intact. This collects media, not unsaved project edits; save an AEP copy separately. |
| 95 | Project & Delivery | Render Profiles | List installed AE render/output templates, then enter their exact names to queue the open comp. Queuing does not start rendering. |
| 96 | Project & Delivery | Export Short Proof | Render up to 10 seconds from the work-area start. Other queued jobs are temporarily excluded and restored. Choose the output file in the native dialog. |

## Validation evidence

- 676 affected Node checks passed, including five final safe review tests; 2 installer checks passed. These are executed test cases and include shared fixture suites.
- Final safe review found no new confirmed failure within its tested scope: input bounds, unknown IDs/settings, quoted text, project-save exclusions and repeated module loading.
- Source: `editor_plugins/effects-toolkit/`; UI: `hinglish_app/static/effects-toolkit.js` and `.css`.
- Receipts: `output/effects-toolkit-evidence/installation.json`, `delivery.json`, `status.json` and the test logs.
- No services were restarted, no model/GPU jobs started and no publishing actions performed.

## API references consulted

[AE keyframes](https://ae-scripting.docsforadobe.dev/property/property/), [render queue items](https://ae-scripting.docsforadobe.dev/renderqueue/renderqueueitem/), [output modules](https://ae-scripting.docsforadobe.dev/renderqueue/outputmodule/), [effect names](https://ae-scripting.docsforadobe.dev/matchnames/effects/firstparty/), [CEP native-drag issue](https://github.com/adobe-cep/cep-resources/issues/389).
