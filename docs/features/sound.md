# Sound Design

Suggests editable sound layers matched to speech and visible actions. Choose your video, select Short form or Long form and the music/effects you want, run Design the sound, and review the draft and keyword folders. Preserve the existing audio and confirm rights for additions.

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

- [hinglish_sound/acoustic.py](../../components/storylens/hinglish_sound/acoustic.py)
- [hinglish_sound/audition.py](../../components/storylens/hinglish_sound/audition.py)
- [hinglish_sound/brain.py](../../components/storylens/hinglish_sound/brain.py)
- [hinglish_sound/composition.py](../../components/storylens/hinglish_sound/composition.py)
- [hinglish_sound/credits.py](../../components/storylens/hinglish_sound/credits.py)
- [hinglish_sound/cues.py](../../components/storylens/hinglish_sound/cues.py)
- [hinglish_sound/director.py](../../components/storylens/hinglish_sound/director.py)
- [hinglish_sound/editors.py](../../components/storylens/hinglish_sound/editors.py)
- [hinglish_sound/evaluator.py](../../components/storylens/hinglish_sound/evaluator.py)
- [hinglish_sound/events.py](../../components/storylens/hinglish_sound/events.py)
- [hinglish_sound/fetch_pack.py](../../components/storylens/hinglish_sound/fetch_pack.py)
- [hinglish_sound/human_review.py](../../components/storylens/hinglish_sound/human_review.py)
- [hinglish_sound/keyword_folders.py](../../components/storylens/hinglish_sound/keyword_folders.py)
- [hinglish_sound/layers.py](../../components/storylens/hinglish_sound/layers.py)
- [hinglish_sound/learning.py](../../components/storylens/hinglish_sound/learning.py)
- [hinglish_sound/library.py](../../components/storylens/hinglish_sound/library.py)
- [hinglish_sound/listen.py](../../components/storylens/hinglish_sound/listen.py)
- [hinglish_sound/mix.py](../../components/storylens/hinglish_sound/mix.py)
- [hinglish_sound/music.py](../../components/storylens/hinglish_sound/music.py)
- [hinglish_sound/online_sources.py](../../components/storylens/hinglish_sound/online_sources.py)
- [hinglish_sound/pipeline.py](../../components/storylens/hinglish_sound/pipeline.py)
- [hinglish_sound/processing.py](../../components/storylens/hinglish_sound/processing.py)
- [hinglish_sound/prosody.py](../../components/storylens/hinglish_sound/prosody.py)
- [hinglish_sound/providers.py](../../components/storylens/hinglish_sound/providers.py)
- [hinglish_sound/recommendations.py](../../components/storylens/hinglish_sound/recommendations.py)
- [hinglish_sound/recommendation_pipeline.py](../../components/storylens/hinglish_sound/recommendation_pipeline.py)
- [hinglish_sound/recommendation_runtime.py](../../components/storylens/hinglish_sound/recommendation_runtime.py)
- [hinglish_sound/reference_memory.py](../../components/storylens/hinglish_sound/reference_memory.py)
- [hinglish_sound/reference_study.py](../../components/storylens/hinglish_sound/reference_study.py)
- [hinglish_sound/relevance.py](../../components/storylens/hinglish_sound/relevance.py)
- [hinglish_sound/report.py](../../components/storylens/hinglish_sound/report.py)
- [hinglish_sound/retrieval.py](../../components/storylens/hinglish_sound/retrieval.py)
- [hinglish_sound/scenes.py](../../components/storylens/hinglish_sound/scenes.py)
- [hinglish_sound/separation.py](../../components/storylens/hinglish_sound/separation.py)
- [hinglish_sound/settings.py](../../components/storylens/hinglish_sound/settings.py)
- [hinglish_sound/source_audio.py](../../components/storylens/hinglish_sound/source_audio.py)
- [hinglish_sound/spotting.py](../../components/storylens/hinglish_sound/spotting.py)
- [hinglish_sound/teacher_memory.py](../../components/storylens/hinglish_sound/teacher_memory.py)
- [hinglish_sound/tool_bridge.py](../../components/storylens/hinglish_sound/tool_bridge.py)
- [hinglish_sound/tutorial_study.py](../../components/storylens/hinglish_sound/tutorial_study.py)
- [hinglish_sound/vectors.py](../../components/storylens/hinglish_sound/vectors.py)
- [hinglish_sound/xml_export.py](../../components/storylens/hinglish_sound/xml_export.py)
- [hinglish_sound/__init__.py](../../components/storylens/hinglish_sound/__init__.py)
- [hinglish_sound/__main__.py](../../components/storylens/hinglish_sound/__main__.py)

## Buttons and their purposes

| Control | Purpose |
| --- | --- |
| Change music folder | Opens the folder picker for the background music library. |
| Change effects folder | Opens the folder picker for the sound effects library. |
| Review sound alternatives | Opens the saved sound choices for listening and selection. |
| Import folders + draft timeline | Transfers the editable sound draft and source folders. |
| Listen | Auditions the corresponding sound choice. |
| At playhead | Places the selected original sound at the Premiere Pro playhead on a spare audio track. |
| Get sound | Prepares the chosen sound for the CapCut workflow. |
| Design the sound | Analyzes the current source and prepares an editable music and sound effects draft. |
| Refresh reviews | Reloads saved sound review results for this project. |
| Import | Imports the selected original sound into the connected editor. |
| Review sound alternatives | Opens the saved sound review in the panel. |

Common and dynamic button families are also documented in the source voice catalogue. Dropdown options are defined in the actual HTML and JavaScript.

## Checks and limits

- [tests/caption-3d-post-placement-sound.test.cjs](../../components/storylens/tests/caption-3d-post-placement-sound.test.cjs)
- [tests/caption-3d-sound.test.cjs](../../components/storylens/tests/caption-3d-sound.test.cjs)
- [tests/panel-sound-review.test.cjs](../../components/storylens/tests/panel-sound-review.test.cjs)
- [tests/test_assistant_sound_manual.py](../../components/storylens/tests/test_assistant_sound_manual.py)
- [tests/test_completed_sound_jobs.py](../../components/storylens/tests/test_completed_sound_jobs.py)
- [tests/test_editor_panel_sound_review.py](../../components/storylens/tests/test_editor_panel_sound_review.py)
- [tests/test_panel_sound_review.py](../../components/storylens/tests/test_panel_sound_review.py)
- [tests/test_panel_sound_worker.py](../../components/storylens/tests/test_panel_sound_worker.py)
- [tests/test_sound.py](../../components/storylens/tests/test_sound.py)
- [tests/test_sound_adapter_export.py](../../components/storylens/tests/test_sound_adapter_export.py)
- [tests/test_sound_anchor_composition.py](../../components/storylens/tests/test_sound_anchor_composition.py)
- [tests/test_sound_arrangement.py](../../components/storylens/tests/test_sound_arrangement.py)
- [tests/test_sound_audition.py](../../components/storylens/tests/test_sound_audition.py)
- [tests/test_sound_brain_runtime.py](../../components/storylens/tests/test_sound_brain_runtime.py)
- [tests/test_sound_candidate_variety.py](../../components/storylens/tests/test_sound_candidate_variety.py)
- [tests/test_sound_composition.py](../../components/storylens/tests/test_sound_composition.py)

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
- [/api/chat](../../components/storylens/hinglish_sound/brain.py#L120)
- [/api/embed](../../components/storylens/hinglish_sound/brain.py#L168)
- [/api/tags](../../components/storylens/hinglish_sound/recommendation_pipeline.py#L260)
- [/api/version](../../components/storylens/hinglish_sound/recommendation_pipeline.py#L261)
- [/api/sound/rebuild](../../components/storylens/hinglish_sound/report.py#L39)

[All source-declared screen controls and dropdown choices](../control-screens.json)
