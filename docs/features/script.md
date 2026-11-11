# Smart Edit

Builds an editable cut by matching recorded takes to a supplied script and arranging them by meaning. Add footage and the exact script, choose pacing, run Build my timeline, and check omitted lines and selected takes before exporting.

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

- [hinglish_semantic/analysis.py](../../components/storylens/hinglish_semantic/analysis.py)
- [hinglish_semantic/assembly.py](../../components/storylens/hinglish_semantic/assembly.py)
- [hinglish_semantic/cleanup.py](../../components/storylens/hinglish_semantic/cleanup.py)
- [hinglish_semantic/core.py](../../components/storylens/hinglish_semantic/core.py)
- [hinglish_semantic/coverage.py](../../components/storylens/hinglish_semantic/coverage.py)
- [hinglish_semantic/learning.py](../../components/storylens/hinglish_semantic/learning.py)
- [hinglish_semantic/local_judge.py](../../components/storylens/hinglish_semantic/local_judge.py)
- [hinglish_semantic/meaning.py](../../components/storylens/hinglish_semantic/meaning.py)
- [hinglish_semantic/models.py](../../components/storylens/hinglish_semantic/models.py)
- [hinglish_semantic/pacing.py](../../components/storylens/hinglish_semantic/pacing.py)
- [hinglish_semantic/paragraph_export.py](../../components/storylens/hinglish_semantic/paragraph_export.py)
- [hinglish_semantic/pipeline.py](../../components/storylens/hinglish_semantic/pipeline.py)
- [hinglish_semantic/preview.py](../../components/storylens/hinglish_semantic/preview.py)
- [hinglish_semantic/report.py](../../components/storylens/hinglish_semantic/report.py)
- [hinglish_semantic/script_reference.py](../../components/storylens/hinglish_semantic/script_reference.py)
- [hinglish_semantic/setup_meaning.py](../../components/storylens/hinglish_semantic/setup_meaning.py)
- [hinglish_semantic/shared_passages.py](../../components/storylens/hinglish_semantic/shared_passages.py)
- [hinglish_semantic/speech.py](../../components/storylens/hinglish_semantic/speech.py)
- [hinglish_semantic/__init__.py](../../components/storylens/hinglish_semantic/__init__.py)
- [hinglish_semantic/__main__.py](../../components/storylens/hinglish_semantic/__main__.py)

## Buttons and their purposes

| Control | Purpose |
| --- | --- |
| Edit by script | Matches the script to the footage and prepares a cut in script order. |
| Build my timeline | Matches the written script to source clips and assembles the editable timeline in script order. |

Common and dynamic button families are also documented in the source voice catalogue. Dropdown options are defined in the actual HTML and JavaScript.

## Checks and limits

- [tests/test_caption_script_preview.py](../../components/storylens/tests/test_caption_script_preview.py)
- [tests/test_cinematic_semantic_windows.py](../../components/storylens/tests/test_cinematic_semantic_windows.py)
- [tests/test_description_policy.py](../../components/storylens/tests/test_description_policy.py)
- [tests/test_gaming_transcription.py](../../components/storylens/tests/test_gaming_transcription.py)
- [tests/test_publisher_transcript_reuse.py](../../components/storylens/tests/test_publisher_transcript_reuse.py)
- [tests/test_script_quality.py](../../components/storylens/tests/test_script_quality.py)
- [tests/test_script_reference.py](../../components/storylens/tests/test_script_reference.py)
- [tests/test_semantic.py](../../components/storylens/tests/test_semantic.py)
- [tests/test_semantic_recognition_retry.py](../../components/storylens/tests/test_semantic_recognition_retry.py)

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
- [/api/chat](../../components/storylens/hinglish_semantic/local_judge.py#L161)
- [/api/tags](../../components/storylens/tests/test_cinematic_semantic_windows.py#L207)

[All source-declared screen controls and dropdown choices](../control-screens.json)
