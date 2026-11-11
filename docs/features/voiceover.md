# Voice Clone

Turns a written script into speech using a saved voice. Save a clear authorized 3–20 second sample of one speaker without music, choose the voice and enter the script, then Generate voice clone and listen to the result.

## Where to start

- [Visible screen](../../components/storylens/hinglish_app/static/voiceover.html)
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

- [hinglish_app/voiceover_http.py](../../components/storylens/hinglish_app/voiceover_http.py)
- [hinglish_voice/audio.py](../../components/storylens/hinglish_voice/audio.py)
- [hinglish_voice/pronunciation.py](../../components/storylens/hinglish_voice/pronunciation.py)
- [hinglish_voice/runtime.py](../../components/storylens/hinglish_voice/runtime.py)
- [hinglish_voice/service.py](../../components/storylens/hinglish_voice/service.py)
- [hinglish_voice/worker.py](../../components/storylens/hinglish_voice/worker.py)
- [hinglish_voice/__init__.py](../../components/storylens/hinglish_voice/__init__.py)

## Buttons and their purposes

| Control | Purpose |
| --- | --- |
| Generate voice clone | Synthesizes the current script using the selected saved voice and speed. |
| Download MP3 | Downloads the current finished voiceover as MP3. |
| Download WAV | Downloads the current finished voiceover as WAV. |
| Save voice | Saves the uploaded sample and its name as a selectable voice. |
| Refresh | Reloads local voice readiness, saved voices and the current job. |
| Listen / download | Reopens the completed voiceover with its audio player and downloads. |
| Check progress | Rechecks the saved voice generation job. |
| Use script | Restores the saved text to the editor. |
| Restore script | Restores the saved text to the editor. |

Common and dynamic button families are also documented in the source voice catalogue. Dropdown options are defined in the actual HTML and JavaScript.

## Checks and limits

- [tests/test_support_call_feature_voice.py](../../components/storylens/tests/test_support_call_feature_voice.py)
- [tests/test_voiceover.py](../../components/storylens/tests/test_voiceover.py)
- [tests/test_voiceover_gpu.py](../../components/storylens/tests/test_voiceover_gpu.py)
- [tests/test_voiceover_http.py](../../components/storylens/tests/test_voiceover_http.py)
- [tests/test_voiceover_pronunciation.py](../../components/storylens/tests/test_voiceover_pronunciation.py)
- [tests/test_voiceover_runtime.py](../../components/storylens/tests/test_voiceover_runtime.py)
- [tests/test_voice_latency.py](../../components/storylens/tests/test_voice_latency.py)

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
- [/api/voiceover/file](../../components/storylens/hinglish_app/voiceover_http.py#L20)
- [/api/voiceover/status](../../components/storylens/hinglish_app/voiceover_http.py#L24)
- [/api/voiceover/job](../../components/storylens/hinglish_app/voiceover_http.py#L25)
- [/api/voiceover/voices](../../components/storylens/hinglish_app/voiceover_http.py#L44)
- [/api/voiceover/start](../../components/storylens/hinglish_app/voiceover_http.py#L45)
- [/api/voiceover/upload?name=mine.wav](../../components/storylens/tests/test_voiceover_http.py#L31)
- [/api/voiceover/job?id=](../../components/storylens/tests/test_voiceover_http.py#L37)
- [/api/voiceover/file?id=](../../components/storylens/tests/test_voiceover_http.py#L39)
- [/api/voiceover/job?id=..](../../components/storylens/tests/test_voiceover_http.py#L40)
- [/api/support-call/local-result](../../components/storylens/tests/test_voice_latency.py#L49)

[All source-declared screen controls and dropdown choices](../control-screens.json)
