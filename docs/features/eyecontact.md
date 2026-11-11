# Eye Contact

Adjusts the apparent gaze of camera footage toward the lens while preserving blinks, audio and timing. Choose camera clips or a timeline XML, select where the script was relative to the lens, run Fix eye contact, and review the result. B-roll is skipped.

## Where to start

- [Visible screen](../../components/storylens/hinglish_app/static/index.html)
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

- [hinglish_eyecontact/engine.py](../../components/storylens/hinglish_eyecontact/engine.py)
- [hinglish_eyecontact/maxine.py](../../components/storylens/hinglish_eyecontact/maxine.py)
- [hinglish_eyecontact/media.py](../../components/storylens/hinglish_eyecontact/media.py)
- [hinglish_eyecontact/open_gaze.py](../../components/storylens/hinglish_eyecontact/open_gaze.py)
- [hinglish_eyecontact/pipeline.py](../../components/storylens/hinglish_eyecontact/pipeline.py)
- [hinglish_eyecontact/report.py](../../components/storylens/hinglish_eyecontact/report.py)
- [hinglish_eyecontact/settings.py](../../components/storylens/hinglish_eyecontact/settings.py)
- [hinglish_eyecontact/timeline.py](../../components/storylens/hinglish_eyecontact/timeline.py)
- [hinglish_eyecontact/__init__.py](../../components/storylens/hinglish_eyecontact/__init__.py)
- [hinglish_eyecontact/__main__.py](../../components/storylens/hinglish_eyecontact/__main__.py)

## Buttons and their purposes

| Control | Purpose |
| --- | --- |
| Fix eye contact | Processes the eligible camera clips to adjust their gaze. |

Common and dynamic button families are also documented in the source voice catalogue. Dropdown options are defined in the actual HTML and JavaScript.

## Checks and limits

- [tests/test_open_eyecontact.py](../../components/storylens/tests/test_open_eyecontact.py)

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

[All source-declared screen controls and dropdown choices](../control-screens.json)
