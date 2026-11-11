# Smart Visuals

Finds visual evidence and relevant assets such as real people, logos, and factual imagery for narration. Choose a video or timeline XML, add a script when available, run Add smart visuals and check exact identity, context, and usage rights before accepting selections.

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

- [hinglish_visuals/behind.py](../../components/storylens/hinglish_visuals/behind.py)
- [hinglish_visuals/brain.py](../../components/storylens/hinglish_visuals/brain.py)
- [hinglish_visuals/diagnostic.py](../../components/storylens/hinglish_visuals/diagnostic.py)
- [hinglish_visuals/evaluator.py](../../components/storylens/hinglish_visuals/evaluator.py)
- [hinglish_visuals/gather.py](../../components/storylens/hinglish_visuals/gather.py)
- [hinglish_visuals/gpu_render.py](../../components/storylens/hinglish_visuals/gpu_render.py)
- [hinglish_visuals/layout.py](../../components/storylens/hinglish_visuals/layout.py)
- [hinglish_visuals/manual_web.py](../../components/storylens/hinglish_visuals/manual_web.py)
- [hinglish_visuals/pipeline.py](../../components/storylens/hinglish_visuals/pipeline.py)
- [hinglish_visuals/planner.py](../../components/storylens/hinglish_visuals/planner.py)
- [hinglish_visuals/presentation.py](../../components/storylens/hinglish_visuals/presentation.py)
- [hinglish_visuals/reach.py](../../components/storylens/hinglish_visuals/reach.py)
- [hinglish_visuals/recovery.py](../../components/storylens/hinglish_visuals/recovery.py)
- [hinglish_visuals/references.py](../../components/storylens/hinglish_visuals/references.py)
- [hinglish_visuals/render.py](../../components/storylens/hinglish_visuals/render.py)
- [hinglish_visuals/report.py](../../components/storylens/hinglish_visuals/report.py)
- [hinglish_visuals/review_ui.py](../../components/storylens/hinglish_visuals/review_ui.py)
- [hinglish_visuals/script.py](../../components/storylens/hinglish_visuals/script.py)
- [hinglish_visuals/settings.py](../../components/storylens/hinglish_visuals/settings.py)
- [hinglish_visuals/source_bank.py](../../components/storylens/hinglish_visuals/source_bank.py)
- [hinglish_visuals/source_result.py](../../components/storylens/hinglish_visuals/source_result.py)
- [hinglish_visuals/timing.py](../../components/storylens/hinglish_visuals/timing.py)
- [hinglish_visuals/web.py](../../components/storylens/hinglish_visuals/web.py)
- [hinglish_visuals/websearch.py](../../components/storylens/hinglish_visuals/websearch.py)
- [hinglish_visuals/__init__.py](../../components/storylens/hinglish_visuals/__init__.py)
- [hinglish_visuals/__main__.py](../../components/storylens/hinglish_visuals/__main__.py)

## Buttons and their purposes

| Control | Purpose |
| --- | --- |
| No visual | Records that the corresponding moment should have no visual. |
| Import source image | Imports the chosen visual candidate into the connected editor. |
| Add smart visuals | Finds relevant people, logos and other assets for the selected footage or timeline. |
| Refresh reviews | Reloads saved visual review results for this project. |
| Open | Opens the selected visual review. |

Common and dynamic button families are also documented in the source voice catalogue. Dropdown options are defined in the actual HTML and JavaScript.

## Checks and limits

- [tests/test_visuals.py](../../components/storylens/tests/test_visuals.py)
- [tests/test_visuals_class_source_evidence.py](../../components/storylens/tests/test_visuals_class_source_evidence.py)
- [tests/test_visuals_context_resolution.py](../../components/storylens/tests/test_visuals_context_resolution.py)
- [tests/test_visuals_generic_retrieval.py](../../components/storylens/tests/test_visuals_generic_retrieval.py)
- [tests/test_visuals_gpu_policy.py](../../components/storylens/tests/test_visuals_gpu_policy.py)
- [tests/test_visuals_manual_web.py](../../components/storylens/tests/test_visuals_manual_web.py)
- [tests/test_visuals_plan_grounding.py](../../components/storylens/tests/test_visuals_plan_grounding.py)
- [tests/test_visuals_presentation.py](../../components/storylens/tests/test_visuals_presentation.py)
- [tests/test_visuals_recovery.py](../../components/storylens/tests/test_visuals_recovery.py)
- [tests/test_visuals_references.py](../../components/storylens/tests/test_visuals_references.py)
- [tests/test_visuals_source.py](../../components/storylens/tests/test_visuals_source.py)
- [tests/test_visuals_source_bank.py](../../components/storylens/tests/test_visuals_source_bank.py)
- [tests/test_visuals_source_result.py](../../components/storylens/tests/test_visuals_source_result.py)
- [tests/test_visuals_website_dispatch.py](../../components/storylens/tests/test_visuals_website_dispatch.py)

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
- [/api/tags](../../components/storylens/hinglish_visuals/brain.py#L33)
- [/api/generate](../../components/storylens/hinglish_visuals/brain.py#L124)
- [/api/chat](../../components/storylens/hinglish_visuals/brain.py#L124)
- [/api/bridge](../../components/storylens/hinglish_visuals/report.py#L49)
- [/api/visuals/rebuild](../../components/storylens/hinglish_visuals/report.py#L50)
- [/api/visuals/recheck](../../components/storylens/hinglish_visuals/report.py#L71)

[All source-declared screen controls and dropdown choices](../control-screens.json)
