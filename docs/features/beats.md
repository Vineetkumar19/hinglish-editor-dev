# Beat Studio

Finds music beat positions and prepares optional beat-timed effects. Add the music, run Detect beats, then download marker JSON/CSV or prepare and review an effect plan.

## Where to start

- [Visible screen](../../components/storylens/hinglish_app/static/beats.html)
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

- [hinglish_beats/detect.py](../../components/storylens/hinglish_beats/detect.py)
- [hinglish_beats/service.py](../../components/storylens/hinglish_beats/service.py)
- [hinglish_beats/__init__.py](../../components/storylens/hinglish_beats/__init__.py)

## Buttons and their purposes

| Control | Purpose |
| --- | --- |
| Timing and trimmed music | Expands timing and music trim settings for beat detection. |
| Detect beats | Analyzes the selected music and creates a timed beat marker plan. |
| Download marker JSON | Downloads the beat plan as structured JSON. |
| Download marker CSV | Downloads marker names, times, frames and strengths in CSV. |
| Prepare effect plan | Uses detected beats and the chosen style to create an effects cue plan. |
| Add beat markers to After Effects | Imports the current beat plan into the After Effects timeline as markers. |
| Add beat markers to Premiere Pro | Imports the current beat plan into the Premiere Pro timeline as markers. |

Common and dynamic button families are also documented in the source voice catalogue. Dropdown options are defined in the actual HTML and JavaScript.

## Checks and limits

- [tests/test_beats.py](../../components/storylens/tests/test_beats.py)

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
- [/api/beats/analyze](../../components/storylens/tests/test_beats.py#L174)
- [/api/beats/jobs/](../../components/storylens/tests/test_beats.py#L177)
- [/api/beats/effects](../../components/storylens/tests/test_beats.py#L180)
- [/api/beats/jobs/missing](../../components/storylens/tests/test_beats.py#L184)
- [/api/beats/upload?name=music.wav](../../components/storylens/tests/test_beats.py#L184)

[All source-declared screen controls and dropdown choices](../control-screens.json)
