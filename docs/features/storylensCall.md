# Voice assistant

Opens Cortana AI, the in-app voice assistant. Click Voice assistant, allow microphone access and ask a question in English, Hindi or Hinglish. Pause or resume when needed, and select End call to release the microphone. Ask what a button does or say “Press” followed by its label. Keep the call running with Minimize.

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

- [hinglish_app/support_call.py](../../components/storylens/hinglish_app/support_call.py)
- [hinglish_app/support_call_actions.py](../../components/storylens/hinglish_app/support_call_actions.py)
- [hinglish_app/support_call_avatar.py](../../components/storylens/hinglish_app/support_call_avatar.py)
- [hinglish_app/support_call_controls.py](../../components/storylens/hinglish_app/support_call_controls.py)
- [hinglish_app/support_call_desktop.py](../../components/storylens/hinglish_app/support_call_desktop.py)
- [hinglish_app/support_call_fast_help.py](../../components/storylens/hinglish_app/support_call_fast_help.py)
- [hinglish_app/support_call_help_audio.py](../../components/storylens/hinglish_app/support_call_help_audio.py)
- [hinglish_app/support_call_knowledge.py](../../components/storylens/hinglish_app/support_call_knowledge.py)
- [hinglish_app/support_call_local.py](../../components/storylens/hinglish_app/support_call_local.py)
- [hinglish_app/support_call_lookup.py](../../components/storylens/hinglish_app/support_call_lookup.py)
- [hinglish_app/support_call_router.py](../../components/storylens/hinglish_app/support_call_router.py)
- [hinglish_app/support_call_speech.py](../../components/storylens/hinglish_app/support_call_speech.py)

## Buttons and their purposes

| Control | Purpose |
| --- | --- |
| Pause | Pauses the voice session until Resume is selected. |
| Resume | Resumes microphone input in the current voice session. |
| Pause call | Pauses the voice session until Resume is selected. |
| Resume call | Resumes microphone input in the current voice session. |
| Expand call to fill screen | Expands the voice assistant panel. |
| Restore call size | Returns the maximized panel to its previous size. |
| Close voice assistant | Ends the call and releases the microphone. |
| Close-up | Shows a closer view of the Cortana avatar. |
| Full body | Returns the avatar to its full-body view. |
| Voice language | Selects Auto, English, or Hindi for speech recognition and voice. |

Common and dynamic button families are also documented in the source voice catalogue. Dropdown options are defined in the actual HTML and JavaScript.

## Checks and limits

- [tests/test_support_call_controls.py](../../components/storylens/tests/test_support_call_controls.py)
- [tests/test_support_call_control_coverage.py](../../components/storylens/tests/test_support_call_control_coverage.py)
- [tests/test_support_call_fast_help.py](../../components/storylens/tests/test_support_call_fast_help.py)
- [tests/test_support_call_feature_coverage.py](../../components/storylens/tests/test_support_call_feature_coverage.py)
- [tests/test_support_call_feature_voice.py](../../components/storylens/tests/test_support_call_feature_voice.py)
- [tests/test_support_call_frontend_latency.cjs](../../components/storylens/tests/test_support_call_frontend_latency.cjs)
- [tests/test_support_call_grounding.py](../../components/storylens/tests/test_support_call_grounding.py)
- [tests/test_support_call_navigation.py](../../components/storylens/tests/test_support_call_navigation.py)
- [tests/test_support_call_options.py](../../components/storylens/tests/test_support_call_options.py)
- [tests/test_support_call_speech_latency.py](../../components/storylens/tests/test_support_call_speech_latency.py)
The integration locates its shared speech and desktop runtime through D:/Cortana. That source is included under components/cortana-runtime. Native app control and speech need platform-specific setup.

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
- [/api/support-call/status](../../components/storylens/hinglish_app/support_call.py#L77)
- [/api/support-call/recent](../../components/storylens/hinglish_app/support_call.py#L80)
- [/api/support-call/catalog](../../components/storylens/hinglish_app/support_call.py#L83)
- [/api/support-call/local-warm](../../components/storylens/hinglish_app/support_call.py#L103)
- [/api/support-call/local-turn](../../components/storylens/hinglish_app/support_call.py#L103)
- [/api/support-call/local-step](../../components/storylens/hinglish_app/support_call.py#L103)
- [/api/support-call/local-end](../../components/storylens/hinglish_app/support_call.py#L103)
- [/api/support-call/local-speech](../../components/storylens/hinglish_app/support_call.py#L103)
- [/api/support-call/local-result](../../components/storylens/hinglish_app/support_call.py#L103)
- [/api/support-call/avatar-warm](../../components/storylens/hinglish_app/support_call.py#L109)
- [/api/support-call/avatar-frames](../../components/storylens/hinglish_app/support_call.py#L109)
- [/api/support-call/connect](../../components/storylens/hinglish_app/support_call.py#L112)
- [/api/version](../../components/storylens/hinglish_app/support_call_local.py#L230)

[All source-declared screen controls and dropdown choices](../control-screens.json)
