# Add B-roll

Finds supporting footage that matches what the video says. Add the video or timeline, open B-roll settings if needed, use Find B-roll, and check suggested footage for relevance and usage rights before using it.

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

- [hinglish_broll/audio_test.py](../../components/storylens/hinglish_broll/audio_test.py)
- [hinglish_broll/candidate_manifest.py](../../components/storylens/hinglish_broll/candidate_manifest.py)
- [hinglish_broll/candidate_selection.py](../../components/storylens/hinglish_broll/candidate_selection.py)
- [hinglish_broll/capcut.py](../../components/storylens/hinglish_broll/capcut.py)
- [hinglish_broll/choice_policy.py](../../components/storylens/hinglish_broll/choice_policy.py)
- [hinglish_broll/clauses.py](../../components/storylens/hinglish_broll/clauses.py)
- [hinglish_broll/conform.py](../../components/storylens/hinglish_broll/conform.py)
- [hinglish_broll/internet.py](../../components/storylens/hinglish_broll/internet.py)
- [hinglish_broll/keywords.py](../../components/storylens/hinglish_broll/keywords.py)
- [hinglish_broll/keyword_windows.py](../../components/storylens/hinglish_broll/keyword_windows.py)
- [hinglish_broll/library.py](../../components/storylens/hinglish_broll/library.py)
- [hinglish_broll/llm.py](../../components/storylens/hinglish_broll/llm.py)
- [hinglish_broll/model_trace.py](../../components/storylens/hinglish_broll/model_trace.py)
- [hinglish_broll/options.py](../../components/storylens/hinglish_broll/options.py)
- [hinglish_broll/phrases.py](../../components/storylens/hinglish_broll/phrases.py)
- [hinglish_broll/pipeline.py](../../components/storylens/hinglish_broll/pipeline.py)
- [hinglish_broll/placement.py](../../components/storylens/hinglish_broll/placement.py)
- [hinglish_broll/places.py](../../components/storylens/hinglish_broll/places.py)
- [hinglish_broll/planner.py](../../components/storylens/hinglish_broll/planner.py)
- [hinglish_broll/premiere.py](../../components/storylens/hinglish_broll/premiere.py)
- [hinglish_broll/producer_contract.py](../../components/storylens/hinglish_broll/producer_contract.py)
- [hinglish_broll/ranker.py](../../components/storylens/hinglish_broll/ranker.py)
- [hinglish_broll/recovery.py](../../components/storylens/hinglish_broll/recovery.py)
- [hinglish_broll/report.py](../../components/storylens/hinglish_broll/report.py)
- [hinglish_broll/settings.py](../../components/storylens/hinglish_broll/settings.py)
- [hinglish_broll/stock.py](../../components/storylens/hinglish_broll/stock.py)
- [hinglish_broll/stock_browser_client.py](../../components/storylens/hinglish_broll/stock_browser_client.py)
- [hinglish_broll/stock_pages.py](../../components/storylens/hinglish_broll/stock_pages.py)
- [hinglish_broll/subjects.py](../../components/storylens/hinglish_broll/subjects.py)
- [hinglish_broll/timeline.py](../../components/storylens/hinglish_broll/timeline.py)
- [hinglish_broll/verify.py](../../components/storylens/hinglish_broll/verify.py)
- [hinglish_broll/vision.py](../../components/storylens/hinglish_broll/vision.py)
- [hinglish_broll/vl_embedding.py](../../components/storylens/hinglish_broll/vl_embedding.py)
- [hinglish_broll/website_catalogs.py](../../components/storylens/hinglish_broll/website_catalogs.py)
- [hinglish_broll/website_review.py](../../components/storylens/hinglish_broll/website_review.py)
- [hinglish_broll/web_download.py](../../components/storylens/hinglish_broll/web_download.py)
- [hinglish_broll/worker_lease.py](../../components/storylens/hinglish_broll/worker_lease.py)
- [hinglish_broll/xml_export.py](../../components/storylens/hinglish_broll/xml_export.py)
- [hinglish_broll/__init__.py](../../components/storylens/hinglish_broll/__init__.py)
- [hinglish_broll/__main__.py](../../components/storylens/hinglish_broll/__main__.py)

## Buttons and their purposes

| Control | Purpose |
| --- | --- |
| B-roll settings | Opens the settings dialog for footage folders and tool options. |
| Add footage folder | Opens the folder picker and adds its selection to the dialog's list. |
| Remove | Removes the corresponding footage folder from the settings list. |
| Save settings | Stores the edited B-roll library settings. |
| No B-roll | Records that the corresponding keyword should have no B-roll choice. |
| Use at keyword | Chooses the candidate at the matching keyword in the editable result. |
| Use in new project | Sends the selected candidate into the supported editor's new project. |
| Find B-roll | Searches for supporting footage using narration and the chosen discovery method. |
| Horizontal | Sets the B-roll handoff orientation to landscape. |
| Vertical | Sets the B-roll handoff orientation to portrait. |
| Refresh results | Reloads saved B-roll results for this project. |
| Open | Opens the selected B-roll result for candidate review. |

Common and dynamic button families are also documented in the source voice catalogue. Dropdown options are defined in the actual HTML and JavaScript.

## Checks and limits

- [tests/broll-editor-choices.test.cjs](../../components/storylens/tests/broll-editor-choices.test.cjs)
- [tests/broll-main-handoff.test.cjs](../../components/storylens/tests/broll-main-handoff.test.cjs)
- [tests/broll-preview-result.test.cjs](../../components/storylens/tests/broll-preview-result.test.cjs)
- [tests/broll_choice_policy.test.cjs](../../components/storylens/tests/broll_choice_policy.test.cjs)
- [tests/panel-broll-choices.test.cjs](../../components/storylens/tests/panel-broll-choices.test.cjs)
- [tests/test_broll.py](../../components/storylens/tests/test_broll.py)
- [tests/test_broll_ae_direct.py](../../components/storylens/tests/test_broll_ae_direct.py)
- [tests/test_broll_candidate_manifest.py](../../components/storylens/tests/test_broll_candidate_manifest.py)
- [tests/test_broll_catalogs.py](../../components/storylens/tests/test_broll_catalogs.py)
- [tests/test_broll_choice_policy.py](../../components/storylens/tests/test_broll_choice_policy.py)
- [tests/test_broll_clauses.py](../../components/storylens/tests/test_broll_clauses.py)
- [tests/test_broll_deferred_preview.py](../../components/storylens/tests/test_broll_deferred_preview.py)
- [tests/test_broll_duration_metadata_regression.py](../../components/storylens/tests/test_broll_duration_metadata_regression.py)
- [tests/test_broll_editable.py](../../components/storylens/tests/test_broll_editable.py)
- [tests/test_broll_empty_report.py](../../components/storylens/tests/test_broll_empty_report.py)
- [tests/test_broll_keywords.py](../../components/storylens/tests/test_broll_keywords.py)

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
- [/api/chat](../../components/storylens/hinglish_broll/llm.py#L95)
- [/api/editors/action](../../components/storylens/hinglish_broll/report.py#L76)
- [/api/panel/broll-native](../../components/storylens/hinglish_broll/report.py#L83)
- [/api/bridge](../../components/storylens/hinglish_broll/report.py#L95)
- [/api/broll/rebuild](../../components/storylens/hinglish_broll/report.py#L96)
- [/api/panel/broll-website](../../components/storylens/hinglish_broll/report.py#L210)
- [/api/videos/](../../components/storylens/hinglish_broll/stock.py#L124)
- [/api/stock-browser](../../components/storylens/hinglish_broll/stock_browser_client.py#L21)

[All source-declared screen controls and dropdown choices](../control-screens.json)
