# Important words

Adds selective captions for meaningful words such as names, teams, scores and dates, with a glow and optional supporting sounds. Open Auto Captions → Important words, provide the source and reviewed wording, then preview timing and readability.

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

- [hinglish_captions/audio_evidence.py](../../components/storylens/hinglish_captions/audio_evidence.py)
- [hinglish_captions/auto_caption.py](../../components/storylens/hinglish_captions/auto_caption.py)
- [hinglish_captions/candidate_review.py](../../components/storylens/hinglish_captions/candidate_review.py)
- [hinglish_captions/caption_five.js](../../components/storylens/hinglish_captions/caption_five.js)
- [hinglish_captions/caption_five.py](../../components/storylens/hinglish_captions/caption_five.py)
- [hinglish_captions/caption_four.js](../../components/storylens/hinglish_captions/caption_four.js)
- [hinglish_captions/caption_four.py](../../components/storylens/hinglish_captions/caption_four.py)
- [hinglish_captions/caption_one.js](../../components/storylens/hinglish_captions/caption_one.js)
- [hinglish_captions/caption_one.py](../../components/storylens/hinglish_captions/caption_one.py)
- [hinglish_captions/caption_three.js](../../components/storylens/hinglish_captions/caption_three.js)
- [hinglish_captions/caption_three.py](../../components/storylens/hinglish_captions/caption_three.py)
- [hinglish_captions/caption_two.js](../../components/storylens/hinglish_captions/caption_two.js)
- [hinglish_captions/caption_two.py](../../components/storylens/hinglish_captions/caption_two.py)
- [hinglish_captions/cinematic_reference.js](../../components/storylens/hinglish_captions/cinematic_reference.js)
- [hinglish_captions/cinematic_reference.py](../../components/storylens/hinglish_captions/cinematic_reference.py)
- [hinglish_captions/core.py](../../components/storylens/hinglish_captions/core.py)
- [hinglish_captions/demo.py](../../components/storylens/hinglish_captions/demo.py)
- [hinglish_captions/editing.py](../../components/storylens/hinglish_captions/editing.py)
- [hinglish_captions/export_video.py](../../components/storylens/hinglish_captions/export_video.py)
- [hinglish_captions/font_intake.py](../../components/storylens/hinglish_captions/font_intake.py)
- [hinglish_captions/font_runtime.py](../../components/storylens/hinglish_captions/font_runtime.py)
- [hinglish_captions/hyperframes_preview.py](../../components/storylens/hinglish_captions/hyperframes_preview.py)
- [hinglish_captions/important_words.py](../../components/storylens/hinglish_captions/important_words.py)
- [hinglish_captions/kinetic.js](../../components/storylens/hinglish_captions/kinetic.js)
- [hinglish_captions/kinetic.py](../../components/storylens/hinglish_captions/kinetic.py)
- [hinglish_captions/kinetic_gold.js](../../components/storylens/hinglish_captions/kinetic_gold.js)
- [hinglish_captions/kinetic_gold.py](../../components/storylens/hinglish_captions/kinetic_gold.py)
- [hinglish_captions/lyrics.py](../../components/storylens/hinglish_captions/lyrics.py)
- [hinglish_captions/numbers.py](../../components/storylens/hinglish_captions/numbers.py)
- [hinglish_captions/pipeline.py](../../components/storylens/hinglish_captions/pipeline.py)
- [hinglish_captions/project.py](../../components/storylens/hinglish_captions/project.py)
- [hinglish_captions/proofread.py](../../components/storylens/hinglish_captions/proofread.py)
- [hinglish_captions/reference_intake.py](../../components/storylens/hinglish_captions/reference_intake.py)
- [hinglish_captions/reference_intake_runtime.py](../../components/storylens/hinglish_captions/reference_intake_runtime.py)
- [hinglish_captions/reference_library.py](../../components/storylens/hinglish_captions/reference_library.py)
- [hinglish_captions/renderer.py](../../components/storylens/hinglish_captions/renderer.py)
- [hinglish_captions/repair_project.py](../../components/storylens/hinglish_captions/repair_project.py)
- [hinglish_captions/report.py](../../components/storylens/hinglish_captions/report.py)
- [hinglish_captions/scene_capture.py](../../components/storylens/hinglish_captions/scene_capture.py)
- [hinglish_captions/script_preview.py](../../components/storylens/hinglish_captions/script_preview.py)
- [hinglish_captions/serif_circle.js](../../components/storylens/hinglish_captions/serif_circle.js)
- [hinglish_captions/serif_circle.py](../../components/storylens/hinglish_captions/serif_circle.py)
- [hinglish_captions/shared_knowledge.py](../../components/storylens/hinglish_captions/shared_knowledge.py)
- [hinglish_captions/studio.js](../../components/storylens/hinglish_captions/studio.js)
- [hinglish_captions/styles.py](../../components/storylens/hinglish_captions/styles.py)
- [hinglish_captions/subtitles.py](../../components/storylens/hinglish_captions/subtitles.py)
- [hinglish_captions/template_patterns.js](../../components/storylens/hinglish_captions/template_patterns.js)
- [hinglish_captions/template_patterns.py](../../components/storylens/hinglish_captions/template_patterns.py)
- [hinglish_captions/xml_export.py](../../components/storylens/hinglish_captions/xml_export.py)
- [hinglish_captions/__init__.py](../../components/storylens/hinglish_captions/__init__.py)
- [hinglish_captions/__main__.py](../../components/storylens/hinglish_captions/__main__.py)

## Buttons and their purposes

| Control | Purpose |
| --- | --- |
| Transcribe video | Transcribes the selected input so its words can be reviewed. |
| Add word or phrase | Expands the control for entering a caption highlight manually. |
| Add | Adds the entered word or phrase to the highlight list. |
| Remove | Removes the corresponding highlight from the list. |
| Start caption | Builds the captions using the reviewed word and phrase selections. |

Common and dynamic button families are also documented in the source voice catalogue. Dropdown options are defined in the actual HTML and JavaScript.

## Checks and limits

- [tests/test_captions.py](../../components/storylens/tests/test_captions.py)
- [tests/test_kinetic_captions.py](../../components/storylens/tests/test_kinetic_captions.py)
- [tests/test_premiere_captions.py](../../components/storylens/tests/test_premiere_captions.py)
- [tests/test_song_captions.py](../../components/storylens/tests/test_song_captions.py)

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
- [/api/chat](../../components/storylens/hinglish_captions/auto_caption.py#L147)
- [/api/generate](../../components/storylens/hinglish_captions/auto_caption.py#L154)
- [/api/bridge](../../components/storylens/hinglish_captions/kinetic.js#L58)
- [/api/captions/capabilities](../../components/storylens/hinglish_captions/kinetic.js#L61)
- [/api/captions/rebuild](../../components/storylens/hinglish_captions/report.py#L339)

[All source-declared screen controls and dropdown choices](../control-screens.json)
