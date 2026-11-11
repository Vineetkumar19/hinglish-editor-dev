# Ask the editor

Accepts editing requests through the editor chat. Open Ask the editor, attach the relevant video, image, timeline or script, describe what you want, and review the plan and results. Cortana AI can explain and operate supported Storylens controls during the call.

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

- [hinglish_app/assistant.py](../../components/storylens/hinglish_app/assistant.py)
- [hinglish_app/assistant_artifacts.py](../../components/storylens/hinglish_app/assistant_artifacts.py)
- [hinglish_app/assistant_campaign.py](../../components/storylens/hinglish_app/assistant_campaign.py)
- [hinglish_app/assistant_caption_repair.py](../../components/storylens/hinglish_app/assistant_caption_repair.py)
- [hinglish_app/assistant_clean_plan.py](../../components/storylens/hinglish_app/assistant_clean_plan.py)
- [hinglish_app/assistant_contracts.py](../../components/storylens/hinglish_app/assistant_contracts.py)
- [hinglish_app/assistant_copy_review.py](../../components/storylens/hinglish_app/assistant_copy_review.py)
- [hinglish_app/assistant_creative_tools.py](../../components/storylens/hinglish_app/assistant_creative_tools.py)
- [hinglish_app/assistant_distribution.py](../../components/storylens/hinglish_app/assistant_distribution.py)
- [hinglish_app/assistant_edit_workflow.py](../../components/storylens/hinglish_app/assistant_edit_workflow.py)
- [hinglish_app/assistant_finished_upload.py](../../components/storylens/hinglish_app/assistant_finished_upload.py)
- [hinglish_app/assistant_handoff.py](../../components/storylens/hinglish_app/assistant_handoff.py)
- [hinglish_app/assistant_image_plan.py](../../components/storylens/hinglish_app/assistant_image_plan.py)
- [hinglish_app/assistant_instagram_verification.py](../../components/storylens/hinglish_app/assistant_instagram_verification.py)
- [hinglish_app/assistant_media.py](../../components/storylens/hinglish_app/assistant_media.py)
- [hinglish_app/assistant_metadata_repair.py](../../components/storylens/hinglish_app/assistant_metadata_repair.py)
- [hinglish_app/assistant_motion_compare.py](../../components/storylens/hinglish_app/assistant_motion_compare.py)
- [hinglish_app/assistant_motion_plan.py](../../components/storylens/hinglish_app/assistant_motion_plan.py)
- [hinglish_app/assistant_motion_reference.py](../../components/storylens/hinglish_app/assistant_motion_reference.py)
- [hinglish_app/assistant_pipeline.py](../../components/storylens/hinglish_app/assistant_pipeline.py)
- [hinglish_app/assistant_plan.py](../../components/storylens/hinglish_app/assistant_plan.py)
- [hinglish_app/assistant_planner_check.py](../../components/storylens/hinglish_app/assistant_planner_check.py)
- [hinglish_app/assistant_plan_context.py](../../components/storylens/hinglish_app/assistant_plan_context.py)
- [hinglish_app/assistant_post_now.py](../../components/storylens/hinglish_app/assistant_post_now.py)
- [hinglish_app/assistant_preferences.py](../../components/storylens/hinglish_app/assistant_preferences.py)
- [hinglish_app/assistant_prepare_post.py](../../components/storylens/hinglish_app/assistant_prepare_post.py)
- [hinglish_app/assistant_progress.py](../../components/storylens/hinglish_app/assistant_progress.py)
- [hinglish_app/assistant_publish.py](../../components/storylens/hinglish_app/assistant_publish.py)
- [hinglish_app/assistant_publishing_context.py](../../components/storylens/hinglish_app/assistant_publishing_context.py)
- [hinglish_app/assistant_publish_intent.py](../../components/storylens/hinglish_app/assistant_publish_intent.py)
- [hinglish_app/assistant_request_status.py](../../components/storylens/hinglish_app/assistant_request_status.py)
- [hinglish_app/assistant_saved_reels.py](../../components/storylens/hinglish_app/assistant_saved_reels.py)
- [hinglish_app/assistant_schedule.py](../../components/storylens/hinglish_app/assistant_schedule.py)
- [hinglish_app/assistant_schedule_status.py](../../components/storylens/hinglish_app/assistant_schedule_status.py)
- [hinglish_app/assistant_social.py](../../components/storylens/hinglish_app/assistant_social.py)
- [hinglish_app/assistant_sources.py](../../components/storylens/hinglish_app/assistant_sources.py)
- [hinglish_app/assistant_stream.py](../../components/storylens/hinglish_app/assistant_stream.py)
- [hinglish_app/assistant_take_plan.py](../../components/storylens/hinglish_app/assistant_take_plan.py)
- [hinglish_app/assistant_upload_recovery.py](../../components/storylens/hinglish_app/assistant_upload_recovery.py)
- [hinglish_app/assistant_upload_workflow.py](../../components/storylens/hinglish_app/assistant_upload_workflow.py)
- [hinglish_app/assistant_visuals_source.py](../../components/storylens/hinglish_app/assistant_visuals_source.py)
- [hinglish_app/assistant_youtube_check.py](../../components/storylens/hinglish_app/assistant_youtube_check.py)
- [hinglish_app/assistant_zoom_plan.py](../../components/storylens/hinglish_app/assistant_zoom_plan.py)

## Buttons and their purposes

| Control | Purpose |
| --- | --- |
| Ask the editor | Opens or closes the editor conversation panel. |
| Attach | Opens the editor's attachment file picker. |
| Speak your editing request | Records speech for the editor prompt. |
| Send | Submits the current prompt and attachments to the editor workflow. |
| Start a new chat | Opens a separate editor conversation. |
| Close editing assistant | Closes the editor conversation panel. |
| Stop after this step | Requests the editor stop at the next safe step boundary. |
| Close assistant | Closes the editor conversation panel. |
| Close assistant | Closes the editor conversation panel. |
| Tell the assistant what to edit | Sets the draft editing request to review before using Send. |

Common and dynamic button families are also documented in the source voice catalogue. Dropdown options are defined in the actual HTML and JavaScript.

## Checks and limits

- [tests/assistant_progress.test.cjs](../../components/storylens/tests/assistant_progress.test.cjs)
- [tests/test_assistant.py](../../components/storylens/tests/test_assistant.py)
- [tests/test_assistant_artifacts.py](../../components/storylens/tests/test_assistant_artifacts.py)
- [tests/test_assistant_caption_repair.py](../../components/storylens/tests/test_assistant_caption_repair.py)
- [tests/test_assistant_contracts.py](../../components/storylens/tests/test_assistant_contracts.py)
- [tests/test_assistant_copy_review.py](../../components/storylens/tests/test_assistant_copy_review.py)
- [tests/test_assistant_creative_tools.py](../../components/storylens/tests/test_assistant_creative_tools.py)
- [tests/test_assistant_http.py](../../components/storylens/tests/test_assistant_http.py)
- [tests/test_assistant_live_progress.py](../../components/storylens/tests/test_assistant_live_progress.py)
- [tests/test_assistant_prepare_post.py](../../components/storylens/tests/test_assistant_prepare_post.py)
- [tests/test_assistant_publishing_chat.py](../../components/storylens/tests/test_assistant_publishing_chat.py)
- [tests/test_assistant_sound_manual.py](../../components/storylens/tests/test_assistant_sound_manual.py)

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
- [/api/assistant/session](../../components/storylens/tests/test_assistant_http.py#L37)
- [/api/assistant/session?id=](../../components/storylens/tests/test_assistant_http.py#L40)
- [/api/scheduled](../../components/storylens/tests/test_assistant_http.py#L45)
- [/api/scheduled/action](../../components/storylens/tests/test_assistant_http.py#L46)
- [/api/assistant/history](../../components/storylens/tests/test_assistant_http.py#L54)
- [/api/assistant/messages?id=](../../components/storylens/tests/test_assistant_http.py#L55)
- [/api/assistant/history?q=SEO](../../components/storylens/tests/test_assistant_http.py#L56)
- [/api/distribution](../../components/storylens/tests/test_assistant_http.py#L71)
- [/api/assistant/publish](../../components/storylens/tests/test_assistant_http.py#L84)
- [/api/assistant/upload?session=](../../components/storylens/tests/test_assistant_http.py#L93)
- [/api/assistant/message](../../components/storylens/tests/test_assistant_http.py#L99)
- [/api/niche](../../components/storylens/tests/test_assistant_http.py#L109)
- [/api/publisher/settings](../../components/storylens/tests/test_assistant_http.py#L113)
- [/api/publisher?profile=gaming](../../components/storylens/tests/test_assistant_http.py#L114)
- [/api/publisher?profile=general](../../components/storylens/tests/test_assistant_http.py#L115)
- [/api/assistant/media?session={s](../../components/storylens/tests/test_assistant_http.py#L130)

[All source-declared screen controls and dropdown choices](../control-screens.json)
