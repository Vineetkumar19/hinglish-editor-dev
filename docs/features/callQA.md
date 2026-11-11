# Call QA

Reviews consented test-call recordings with a timed transcript, playable evidence and a QA checklist. Use Import test recording, open the call, play evidence at the relevant times, and save your review or export the anonymized report. The live Storylens Call button is separate.

## Where to start

- [Visible screen](../../components/storylens/hinglish_app/static/call-qa.html)
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

- [hinglish_app/call_qa.py](../../components/storylens/hinglish_app/call_qa.py)
- [hinglish_app/call_qa_http.py](../../components/storylens/hinglish_app/call_qa_http.py)
- [hinglish_app/call_qa_report.py](../../components/storylens/hinglish_app/call_qa_report.py)
- [hinglish_app/call_qa_stream.py](../../components/storylens/hinglish_app/call_qa_stream.py)
- [hinglish_app/call_qa_twilio.py](../../components/storylens/hinglish_app/call_qa_twilio.py)

## Buttons and their purposes

| Control | Purpose |
| --- | --- |
| Start a call | Opens the separate Cortana AI voice panel. |
| Import test recording | Opens the importer for a consented test call. |
| Refresh | Reloads the saved test calls. |
| Load older calls | Fetches the next page of older calls. |
| Test calls | Returns to the saved-call list. |
| Gateway timing | Expands the inbound test call timing record when available. |
| Export anonymized | Starts anonymized report export for the selected call. |
| Save anonymized JSON locally | Saves the anonymized report as a local JSON file. |
| Download anonymized JSON | Downloads the anonymized report. |
| Save review | Saves the current evaluator notes and cited evidence for this call. |
| Reload saved review | Restores the last saved review for the selected call. |
| Recording retention | Shows the recording and report retention controls. |
| Remove recording and review | Removes the selected recording and associated review through the retention flow. |
| Close import | Closes the recording importer. |
| Transcript format | Expands the instructions for the imported transcript. |
| Add to test calls | Submits the recording, transcript and consent details for local review. |
| Mark start | Sets the evidence start to the current playback position. |
| Mark end | Sets the evidence end to the current playback position. |
| Use transcript selection | Copies the selected transcript text into the evidence entry. |
| Play evidence | Plays the selected evidence range in the recording. |

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
- [/api/call-qa/](../../components/storylens/hinglish_app/call_qa_http.py#L18)

[All source-declared screen controls and dropdown choices](../control-screens.json)
