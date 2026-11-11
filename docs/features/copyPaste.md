# Copy Paste

Places selected source media into template placeholders in a connected After Effects project. Select and copy the source media, then select the target layer and paste. Verify framing and use Undo if the target was wrong.

## Where to start

- [Visible screen](../../components/storylens/hinglish_app/static/editor-panel.html)
- [HTTP routing](../../components/storylens/hinglish_app/server.py)
- [Main editor requests](../../components/storylens/hinglish_app/static/app.js)
- [Assistant intent schema](../../components/storylens/hinglish_app/assistant_plan.py)
- [Assistant execution and recovery](../../components/storylens/hinglish_app/assistant_pipeline.py)

## Execution flow

1. The screen collects the source and feature options. Its frontend defines button handlers and dropdown values.
2. The frontend sends a local API request. The server checks the request and delegates to a feature handler or job service.
3. The implementation validates inputs and calls its processing, model, retrieval, or native editor adapter.
4. The result is saved locally and reported through a response or job status. The screen provides preview, review, and available export controls.
5. Native editor work and account operations require a result check in the receiving application.

This shared sequence is a navigation guide. The linked feature implementation contains the exact route, branches, state changes, and return values.

## Feature implementation

- [hinglish_app/editor_panel.py](../../components/storylens/hinglish_app/editor_panel.py)
- [hinglish_app/editor_panel_http.py](../../components/storylens/hinglish_app/editor_panel_http.py)
- [editor_plugins/animation-presets/host.jsx](../../components/storylens/editor_plugins/animation-presets/host.jsx)
- [editor_plugins/caption-3d/camera-engine.jsx](../../components/storylens/editor_plugins/caption-3d/camera-engine.jsx)
- [editor_plugins/caption-3d/engine.jsx](../../components/storylens/editor_plugins/caption-3d/engine.jsx)
- [editor_plugins/caption-3d/folders.jsx](../../components/storylens/editor_plugins/caption-3d/folders.jsx)
- [editor_plugins/caption-3d/host.jsx](../../components/storylens/editor_plugins/caption-3d/host.jsx)
- [editor_plugins/caption-3d/solid.jsx](../../components/storylens/editor_plugins/caption-3d/solid.jsx)
- [editor_plugins/caption-3d/sound-data.jsx](../../components/storylens/editor_plugins/caption-3d/sound-data.jsx)
- [editor_plugins/caption-3d/sound-edit.jsx](../../components/storylens/editor_plugins/caption-3d/sound-edit.jsx)
- [editor_plugins/caption-3d/sound.jsx](../../components/storylens/editor_plugins/caption-3d/sound.jsx)
- [editor_plugins/caption-patterns/engine.jsx](../../components/storylens/editor_plugins/caption-patterns/engine.jsx)
- [editor_plugins/caption-patterns/geometry.jsx](../../components/storylens/editor_plugins/caption-patterns/geometry.jsx)
- [editor_plugins/caption-six/geometry.jsx](../../components/storylens/editor_plugins/caption-six/geometry.jsx)
- [editor_plugins/caption-six/motion.jsx](../../components/storylens/editor_plugins/caption-six/motion.jsx)
- [editor_plugins/caption-three/geometry.jsx](../../components/storylens/editor_plugins/caption-three/geometry.jsx)
- [editor_plugins/caption-three/motion.jsx](../../components/storylens/editor_plugins/caption-three/motion.jsx)
- [editor_plugins/caption-two/geometry.jsx](../../components/storylens/editor_plugins/caption-two/geometry.jsx)
- [editor_plugins/caption-two/motion.jsx](../../components/storylens/editor_plugins/caption-two/motion.jsx)
- [editor_plugins/cinematic-text/host.jsx](../../components/storylens/editor_plugins/cinematic-text/host.jsx)
- [editor_plugins/cinematic-text/model.js](../../components/storylens/editor_plugins/cinematic-text/model.js)
- [editor_plugins/cinematic-text/selective.jsx](../../components/storylens/editor_plugins/cinematic-text/selective.jsx)
- [editor_plugins/copy-paste/Copy Paste.jsx](../../components/storylens/editor_plugins/copy-paste/Copy Paste.jsx)
- [editor_plugins/copy-paste/framing-model.js](../../components/storylens/editor_plugins/copy-paste/framing-model.js)
- [editor_plugins/copy-paste/framing.jsx](../../components/storylens/editor_plugins/copy-paste/framing.jsx)
- [editor_plugins/copy-paste/host.jsx](../../components/storylens/editor_plugins/copy-paste/host.jsx)
- [editor_plugins/copy-paste/menu-command.jsx](../../components/storylens/editor_plugins/copy-paste/menu-command.jsx)
- [editor_plugins/copy-paste/model.js](../../components/storylens/editor_plugins/copy-paste/model.js)
- [editor_plugins/copy-paste/ui.js](../../components/storylens/editor_plugins/copy-paste/ui.js)
- [editor_plugins/davinci-resolve-studio/Hinglish Editor.py](../../components/storylens/editor_plugins/davinci-resolve-studio/Hinglish Editor.py)
- [editor_plugins/effects-library/host.jsx](../../components/storylens/editor_plugins/effects-library/host.jsx)
- [editor_plugins/effects-library/model.js](../../components/storylens/editor_plugins/effects-library/model.js)
- [editor_plugins/effects-toolkit/builders-model.js](../../components/storylens/editor_plugins/effects-toolkit/builders-model.js)
- [editor_plugins/effects-toolkit/builders.jsx](../../components/storylens/editor_plugins/effects-toolkit/builders.jsx)
- [editor_plugins/effects-toolkit/camera-model.js](../../components/storylens/editor_plugins/effects-toolkit/camera-model.js)
- [editor_plugins/effects-toolkit/camera.jsx](../../components/storylens/editor_plugins/effects-toolkit/camera.jsx)
- [editor_plugins/effects-toolkit/controls.jsx](../../components/storylens/editor_plugins/effects-toolkit/controls.jsx)
- [editor_plugins/effects-toolkit/delivery-model.js](../../components/storylens/editor_plugins/effects-toolkit/delivery-model.js)
- [editor_plugins/effects-toolkit/delivery.jsx](../../components/storylens/editor_plugins/effects-toolkit/delivery.jsx)
- [editor_plugins/effects-toolkit/host.jsx](../../components/storylens/editor_plugins/effects-toolkit/host.jsx)
- [editor_plugins/effects-toolkit/layer-styles.jsx](../../components/storylens/editor_plugins/effects-toolkit/layer-styles.jsx)
- [editor_plugins/effects-toolkit/layers-model.js](../../components/storylens/editor_plugins/effects-toolkit/layers-model.js)
- [editor_plugins/effects-toolkit/layers.jsx](../../components/storylens/editor_plugins/effects-toolkit/layers.jsx)
- [editor_plugins/effects-toolkit/library-model.js](../../components/storylens/editor_plugins/effects-toolkit/library-model.js)
- [editor_plugins/effects-toolkit/library.jsx](../../components/storylens/editor_plugins/effects-toolkit/library.jsx)
- [editor_plugins/effects-toolkit/masks-model.js](../../components/storylens/editor_plugins/effects-toolkit/masks-model.js)
- [editor_plugins/effects-toolkit/masks.jsx](../../components/storylens/editor_plugins/effects-toolkit/masks.jsx)
- [editor_plugins/effects-toolkit/model.js](../../components/storylens/editor_plugins/effects-toolkit/model.js)
- [editor_plugins/effects-toolkit/motion.jsx](../../components/storylens/editor_plugins/effects-toolkit/motion.jsx)
- [editor_plugins/effects-toolkit/styling-model.js](../../components/storylens/editor_plugins/effects-toolkit/styling-model.js)
- [editor_plugins/effects-toolkit/styling.jsx](../../components/storylens/editor_plugins/effects-toolkit/styling.jsx)
- [editor_plugins/effects-toolkit/text-model.js](../../components/storylens/editor_plugins/effects-toolkit/text-model.js)
- [editor_plugins/effects-toolkit/text.jsx](../../components/storylens/editor_plugins/effects-toolkit/text.jsx)
- [editor_plugins/effects-toolkit/timing-model.js](../../components/storylens/editor_plugins/effects-toolkit/timing-model.js)
- [editor_plugins/effects-toolkit/timing.jsx](../../components/storylens/editor_plugins/effects-toolkit/timing.jsx)
- [editor_plugins/effects-toolkit/transitions-model.js](../../components/storylens/editor_plugins/effects-toolkit/transitions-model.js)
- [editor_plugins/effects-toolkit/transitions.jsx](../../components/storylens/editor_plugins/effects-toolkit/transitions.jsx)
- [editor_plugins/effects-toolkit/typography-model.js](../../components/storylens/editor_plugins/effects-toolkit/typography-model.js)
- [editor_plugins/effects-toolkit/typography.jsx](../../components/storylens/editor_plugins/effects-toolkit/typography.jsx)
- [editor_plugins/premiere-reel-recreate/prepare.py](../../components/storylens/editor_plugins/premiere-reel-recreate/prepare.py)
- [editor_plugins/premiere-reel-recreate/reel-recreate.jsx](../../components/storylens/editor_plugins/premiere-reel-recreate/reel-recreate.jsx)
- [editor_plugins/premiere-uxp/beats.js](../../components/storylens/editor_plugins/premiere-uxp/beats.js)
- [editor_plugins/premiere-uxp/main.js](../../components/storylens/editor_plugins/premiere-uxp/main.js)
- [editor_plugins/preset-library/host.jsx](../../components/storylens/editor_plugins/preset-library/host.jsx)
- [editor_plugins/preset-library/model.js](../../components/storylens/editor_plugins/preset-library/model.js)

## Buttons and their purposes

| Control | Purpose |
| --- | --- |
| Copy | Captures the selected editor item as the current copy source. |
| Paste | Pastes the captured item into the selected template target. |
| Undo | Reverts the last tracked paste. |
| Reset | Clears the current Copy Paste source and progress state. |

Common and dynamic button families are also documented in the source voice catalogue. Dropdown options are defined in the actual HTML and JavaScript.

## Checks and limits

Use the component tests and a representative task in the receiving application.
Requires the named native editor and integration. Cross-editor editability and Mac compatibility require route-specific validation.

## API references in this feature’s source

- [/api/native-tools/connections](../../components/storylens/hinglish_app/static/app.js#L45)
- [/api/upload?batch=](../../components/storylens/hinglish_app/static/app.js#L130)
- [/api/broll/settings](../../components/storylens/hinglish_app/static/app.js#L215)
- [/api/pick?kind=folder](../../components/storylens/hinglish_app/static/app.js#L217)
- [/api/eyecontact/status](../../components/storylens/hinglish_app/static/app.js#L287)
- [/api/sound/settings](../../components/storylens/hinglish_app/static/app.js#L293)
- [/api/aigen/status](../../components/storylens/hinglish_app/static/app.js#L320)
- [/api/aigen/styles](../../components/storylens/hinglish_app/static/app.js#L332)
- [/api/motion/styles](../../components/storylens/hinglish_app/static/app.js#L354)
- [/api/pick?kind=](../../components/storylens/hinglish_app/static/app.js#L363)
- [/api/health](../../components/storylens/hinglish_app/static/app.js#L393)
- [/api/jobs](../../components/storylens/hinglish_app/static/app.js#L424)
- [/api/jobs/](../../components/storylens/hinglish_app/static/app.js#L451)
- [/api/open](../../components/storylens/hinglish_app/static/app.js#L473)
- [/api/panel/media](../../components/storylens/hinglish_app/editor_panel_http.py#L11)
- [/api/panel/visual-source-media](../../components/storylens/hinglish_app/editor_panel_http.py#L11)
- [/api/panel/sound-audition-media](../../components/storylens/hinglish_app/editor_panel_http.py#L11)
- [/api/panel/image-file](../../components/storylens/hinglish_app/editor_panel_http.py#L11)
- [/api/panel/template-text-job](../../components/storylens/hinglish_app/editor_panel_http.py#L14)
- [/api/panel/template-text-plan](../../components/storylens/hinglish_app/editor_panel_http.py#L14)
- [/api/panel/image-download](../../components/storylens/hinglish_app/editor_panel_http.py#L18)
- [/api/panel/config](../../components/storylens/hinglish_app/editor_panel_http.py#L27)
- [/api/panel/context](../../components/storylens/hinglish_app/editor_panel_http.py#L31)
- [/api/panel/job](../../components/storylens/hinglish_app/editor_panel_http.py#L32)
- [/api/panel/broll-results](../../components/storylens/hinglish_app/editor_panel_http.py#L33)
- [/api/panel/broll-candidates](../../components/storylens/hinglish_app/editor_panel_http.py#L36)
- [/api/panel/visual-sources](../../components/storylens/hinglish_app/editor_panel_http.py#L40)
- [/api/panel/visual-results](../../components/storylens/hinglish_app/editor_panel_http.py#L43)
- [/api/panel/sound-review](../../components/storylens/hinglish_app/editor_panel_http.py#L47)
- [/api/panel/sound-results](../../components/storylens/hinglish_app/editor_panel_http.py#L50)

[All source-declared screen controls and dropdown choices](../control-screens.json)
