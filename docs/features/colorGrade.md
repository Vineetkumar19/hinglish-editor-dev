# Color Grade

Prepares editable grading for DaVinci Resolve on a duplicate timeline. Select Color Grade 1 for RealFilm V2 on Rec.709 or Color Grade 2 for the original node structure, set the matching input profile and review settings, then apply to a duplicate or download the DRX. Presets & LUTs provides available LUT downloads.

## Where to start

- [Visible screen](../../components/storylens/hinglish_app/static/color-grade.html)
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

Follow this screen’s button handler through the main server or native editor dispatch.

## Buttons and their purposes

| Control | Purpose |
| --- | --- |
| Color Grade 1 | Selects the RealFilm V2 Rec.709 grade workflow. |
| Color Grade 2 | Selects the original editable 19-node Resolve workflow. |
| Apply to duplicate timeline | Applies the selected grade to a duplicate timeline in the connected Resolve project. |
| Download DRX | Downloads the native grade file for Resolve. |
| Download LUT | Downloads the selected Sony LUT from the local catalogue. |
| Restore previous grade | Restores the grade saved before the current Resolve LUT preview. |
| Project setup | Expands instructions for the Resolve project and connection. |

Common and dynamic button families are also documented in the source voice catalogue. Dropdown options are defined in the actual HTML and JavaScript.

## Checks and limits

Use the component tests and a representative task in the receiving application.
Requires the named native editor and integration. Cross-editor editability and Mac compatibility require route-specific validation.

## API references in this feature’s source

- [/api/workbench/grade-template](../../components/storylens/hinglish_app/static/color-grade.html#L138)
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

[All source-declared screen controls and dropdown choices](../control-screens.json)
