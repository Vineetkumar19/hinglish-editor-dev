# Reference Reel

Builds a draft using your footage against the timing of a reference video. Choose the reference and your footage folder, click Build reel, then compare the original and your draft before export. Reel Recreate instead prepares caption, beat and footage slots.

## Where to start

- [Visible screen](../../components/storylens/hinglish_app/static/reference-reel.html)
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

- [hinglish_app/reference_reel.py](../../components/storylens/hinglish_app/reference_reel.py)
- [hinglish_app/reference_reel_ae.jsx](../../components/storylens/hinglish_app/reference_reel_ae.jsx)
- [hinglish_app/reference_reel_media.py](../../components/storylens/hinglish_app/reference_reel_media.py)
- [hinglish_app/reference_reel_research.py](../../components/storylens/hinglish_app/reference_reel_research.py)

## Buttons and their purposes

| Control | Purpose |
| --- | --- |
| Build reel | Starts reconstruction using the selected reference and input footage. |

Common and dynamic button families are also documented in the source voice catalogue. Dropdown options are defined in the actual HTML and JavaScript.

## Checks and limits

Use the component tests and a representative task in the receiving application.

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
- [/api/reference-reel/upload](../../components/storylens/hinglish_app/reference_reel.py#L1360)
- [/api/reference-reel/analyze](../../components/storylens/hinglish_app/reference_reel.py#L1364)
- [/api/reference-reel/reuse](../../components/storylens/hinglish_app/reference_reel.py#L1364)
- [/api/reference-reel/recut](../../components/storylens/hinglish_app/reference_reel.py#L1365)
- [/api/reference-reel/export](../../components/storylens/hinglish_app/reference_reel.py#L1365)

[All source-declared screen controls and dropdown choices](../control-screens.json)
