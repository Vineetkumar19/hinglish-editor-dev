# Downloader

Saves permitted source videos or extracts audio from supported links. Paste a link, pick the format and destination, choose Add to queue, then check the result. Check permissions before downloading or reusing content.

## Where to start

- [Visible screen](../../components/storylens/hinglish_app/static/downloader.html)
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

- [hinglish_app/downloader.py](../../components/storylens/hinglish_app/downloader.py)
- [hinglish_app/downloader_http.py](../../components/storylens/hinglish_app/downloader_http.py)

## Buttons and their purposes

| Control | Purpose |
| --- | --- |
| Browse | Opens the download destination folder picker. |
| Add to queue | Submits the current URLs and download options to the local download queue. |
| YouTube clip · optional | Expands the start and end trim controls for a YouTube clip. |
| Remove | Cancels an item still waiting in the queue. |
| Cancel | Requests cancellation for the current download row. |
| Resume | Resumes the corresponding interrupted queue item. |
| Retry | Retries the corresponding failed or cancelled item. |
| Preview video | Plays the video saved for that queue item. |
| Preview audio | Plays the audio saved for that queue item. |
| Import video in After Effects | Imports the selected downloaded video into After Effects. |
| Import audio in After Effects | Imports the selected downloaded audio into After Effects. |
| Import video in Premiere | Imports the selected downloaded video into Premiere. |
| Import audio in Premiere | Imports the selected downloaded audio into Premiere. |

Common and dynamic button families are also documented in the source voice catalogue. Dropdown options are defined in the actual HTML and JavaScript.

## Checks and limits

- [tests/downloader-cep-context.test.cjs](../../components/storylens/tests/downloader-cep-context.test.cjs)
- [tests/downloader_ui.test.cjs](../../components/storylens/tests/downloader_ui.test.cjs)
- [tests/test_downloader.py](../../components/storylens/tests/test_downloader.py)
- [tests/test_downloader_http.py](../../components/storylens/tests/test_downloader_http.py)
- [tests/test_downloader_performance.py](../../components/storylens/tests/test_downloader_performance.py)
- [tests/test_downloader_queue.py](../../components/storylens/tests/test_downloader_queue.py)

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
- [/api/downloader/media](../../components/storylens/hinglish_app/downloader_http.py#L11)
- [/api/downloader/settings](../../components/storylens/hinglish_app/downloader_http.py#L14)
- [/api/downloader/queue](../../components/storylens/hinglish_app/downloader_http.py#L15)
- [/api/downloader/history](../../components/storylens/hinglish_app/downloader_http.py#L16)
- [/api/downloader/job](../../components/storylens/hinglish_app/downloader_http.py#L17)
- [/api/downloader/start](../../components/storylens/tests/test_downloader_http.py#L27)
- [/api/downloader/cancel](../../components/storylens/tests/test_downloader_http.py#L27)
- [/api/downloader/enqueue](../../components/storylens/tests/test_downloader_http.py#L42)
- [/api/downloader/job?id=](../../components/storylens/tests/test_downloader_http.py#L62)
- [/api/downloader/media?id=](../../components/storylens/tests/test_downloader_http.py#L64)
- [/api/editors/prepare](../../components/storylens/tests/test_downloader_http.py#L73)
- [/api/editors/task?id=](../../components/storylens/tests/test_downloader_http.py#L77)

[All source-declared screen controls and dropdown choices](../control-screens.json)
