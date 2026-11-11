# Documentary Intro

Reviews source spans and reference style, then prepares a documentary intro preview.

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

- [hinglish_app/documentary_service.py](../../components/storylens/hinglish_app/documentary_service.py)

## Buttons and their purposes

| Control | Purpose |
| --- | --- |
| Inspect and import | Inspects and saves the selected media for this documentary project. |
| Restore documentary preview | Restores the most recent saved documentary preview. |
| Resume saved render | Resumes the saved unfinished preview render. |
| Reference style review | Expands the documentary reference inspection and notes. |
| Inspect reference video | Analyzes the chosen reference video for style review. |
| Save reference observations | Saves the reviewed notes about the reference. |
| Script and timed words | Expands narration text and word timing for review. |
| Add source span | Adds a source range to the story review. |
| Protect scoreboard and other revealing visuals | Expands exclusions for source visuals that reveal results too early. |
| Save story review | Saves the reviewed story spans and reviewer details. |
| Render 40-second preview | Renders a forty-second draft using the saved story review. |

Common and dynamic button families are also documented in the source voice catalogue. Dropdown options are defined in the actual HTML and JavaScript.

## Checks and limits

- [tests/preset-documentary-cover-review.test.cjs](../../components/storylens/tests/preset-documentary-cover-review.test.cjs)
- [tests/preset-documentary-covers-native.test.cjs](../../components/storylens/tests/preset-documentary-covers-native.test.cjs)
- [tests/preset-documentary-covers.test.cjs](../../components/storylens/tests/preset-documentary-covers.test.cjs)
- [tests/preset-documentary-review.test.cjs](../../components/storylens/tests/preset-documentary-review.test.cjs)
- [tests/preset-documentary.test.cjs](../../components/storylens/tests/preset-documentary.test.cjs)
- [tests/test_continuous_documentary_memory.py](../../components/storylens/tests/test_continuous_documentary_memory.py)
- [tests/test_documentary.py](../../components/storylens/tests/test_documentary.py)
- [tests/test_documentary_consolidation.py](../../components/storylens/tests/test_documentary_consolidation.py)
- [tests/test_documentary_sets.py](../../components/storylens/tests/test_documentary_sets.py)
- [tests/test_independent_documentary_sample.py](../../components/storylens/tests/test_independent_documentary_sample.py)

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
