# Prepare and Post

Prepares YouTube and Instagram drafts and schedules for the selected profile. Open Prepare and Post, verify Connections and the profile, choose Long or Shorts, select media, run preparation, then review copy, account, visibility and time before posting or scheduling. Instagram needs connected Chrome for its local publisher.

## Where to start

- [Visible screen](../../components/storylens/hinglish_app/static/prepare-post.html)
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

- [hinglish_app/prepare_post_http.py](../../components/storylens/hinglish_app/prepare_post_http.py)

## Buttons and their purposes

| Control | Purpose |
| --- | --- |
| Cricket | Sets the publishing workspace to the Cricket creator profile. |
| Gaming | Sets the publishing workspace to the Gaming creator profile. |
| Long | Opens the long-video preparation workflow. |
| Shorts | Opens the Shorts preparation workflow. |
| Highlights | Opens the gaming highlight preparation workflow. |
| Choose video | Opens the source video picker. |
| Choose thumbnail | Opens the picker for a thumbnail image. |
| Save thumbnail selection | Stores the reviewed thumbnail selection with this draft. |
| Run | Prepares the selected source and its review material for the chosen format. |
| Cancel Long video | Requests cancellation of the active long-video preparation. |
| Cancel preparation | Requests cancellation of the active clip preparation. |
| Start | Starts preparing clips from the selected saved video or highlight. |
| Clear | Clears the current workspace or review fields while preserving saved uploads and schedules. |
| Refresh review | Rechecks publishing discovery suggestions for the current item. |
| Use title | Copies the selected suggested title into the review fields. |
| Use description & tags | Copies the selected suggested description and tags into the review fields. |
| Save reviewed text | Saves the reviewed copy for this item. |
| Generate weekly packages · V8 | Generates the requested metadata packages for review. |
| Pause future weekly changes | Pauses the future steps of the selected weekly plan. |
| Resume preparation | Continues the selected interrupted preparation from its saved progress. |
| Review generated clip | Opens the corresponding generated clip for review. |
| Save as draft | Saves the current prepared copy for later review. |
| Cancel unstarted post | Cancels the selected post that has not started uploading. |
| SEO & thumbnail review | Includes the SEO and thumbnail review in a new preparation. |
| Live YouTube search suggestions | Includes live YouTube search suggestions in a new preparation. |
| Audience | Records whether the reviewed video is made for kids. |
| Altered / synthetic content | Records the declaration for the reviewed video's altered or synthetic content. |
| Visibility | Chooses the publishing visibility for the reviewed item. |

Common and dynamic button families are also documented in the source voice catalogue. Dropdown options are defined in the actual HTML and JavaScript.

## Checks and limits

- [tests/prepare_post_progress.test.cjs](../../components/storylens/tests/prepare_post_progress.test.cjs)
- [tests/prepare_post_simple_ui.test.cjs](../../components/storylens/tests/prepare_post_simple_ui.test.cjs)
- [tests/test_assistant_prepare_post.py](../../components/storylens/tests/test_assistant_prepare_post.py)
- [tests/test_prepare_post.py](../../components/storylens/tests/test_prepare_post.py)
- [tests/test_prepare_post_auto_recovery.py](../../components/storylens/tests/test_prepare_post_auto_recovery.py)
- [tests/test_prepare_post_budget.py](../../components/storylens/tests/test_prepare_post_budget.py)
- [tests/test_prepare_post_caption_checks.py](../../components/storylens/tests/test_prepare_post_caption_checks.py)
- [tests/test_prepare_post_delivery.py](../../components/storylens/tests/test_prepare_post_delivery.py)
- [tests/test_prepare_post_rejected_copy.py](../../components/storylens/tests/test_prepare_post_rejected_copy.py)
- [tests/test_prepare_post_release.py](../../components/storylens/tests/test_prepare_post_release.py)
- [tests/test_prepare_post_runtime_connection.py](../../components/storylens/tests/test_prepare_post_runtime_connection.py)
- [tests/test_prepare_post_schedule_recovery.py](../../components/storylens/tests/test_prepare_post_schedule_recovery.py)
- [tests/test_prepare_post_simple_flow.py](../../components/storylens/tests/test_prepare_post_simple_flow.py)
- [tests/test_prepare_post_source_quotes.py](../../components/storylens/tests/test_prepare_post_source_quotes.py)
- [tests/test_prepare_post_video_picker.py](../../components/storylens/tests/test_prepare_post_video_picker.py)
- [tests/test_prepare_post_worker_gpu.py](../../components/storylens/tests/test_prepare_post_worker_gpu.py)
Requires authorized accounts or a dedicated review account. Credentials and live queues are outside this package.

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
- [/api/tags](../../components/storylens/tests/test_prepare_post_runtime_connection.py#L38)

[All source-declared screen controls and dropdown choices](../control-screens.json)
