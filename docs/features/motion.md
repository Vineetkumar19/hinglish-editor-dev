# Motion Graphics

Makes animated visuals for key moments in a story. Paste a script or select a video/timeline, choose a style, engine and preview quality, run Make motion graphics, then check the timing, text and layout before export.

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

- [hinglish_motion/assets.py](../../components/storylens/hinglish_motion/assets.py)
- [hinglish_motion/autonomous_reference.py](../../components/storylens/hinglish_motion/autonomous_reference.py)
- [hinglish_motion/capabilities.py](../../components/storylens/hinglish_motion/capabilities.py)
- [hinglish_motion/comparison.py](../../components/storylens/hinglish_motion/comparison.py)
- [hinglish_motion/creative.py](../../components/storylens/hinglish_motion/creative.py)
- [hinglish_motion/creative_export.py](../../components/storylens/hinglish_motion/creative_export.py)
- [hinglish_motion/curves.py](../../components/storylens/hinglish_motion/curves.py)
- [hinglish_motion/cutout_worker.py](../../components/storylens/hinglish_motion/cutout_worker.py)
- [hinglish_motion/element_motion.py](../../components/storylens/hinglish_motion/element_motion.py)
- [hinglish_motion/engines.py](../../components/storylens/hinglish_motion/engines.py)
- [hinglish_motion/native_engines.py](../../components/storylens/hinglish_motion/native_engines.py)
- [hinglish_motion/native_text.py](../../components/storylens/hinglish_motion/native_text.py)
- [hinglish_motion/native_text_repair.py](../../components/storylens/hinglish_motion/native_text_repair.py)
- [hinglish_motion/object_film.py](../../components/storylens/hinglish_motion/object_film.py)
- [hinglish_motion/object_recovery.py](../../components/storylens/hinglish_motion/object_recovery.py)
- [hinglish_motion/pipeline.py](../../components/storylens/hinglish_motion/pipeline.py)
- [hinglish_motion/plan.py](../../components/storylens/hinglish_motion/plan.py)
- [hinglish_motion/reference_composer.py](../../components/storylens/hinglish_motion/reference_composer.py)
- [hinglish_motion/reference_finish.py](../../components/storylens/hinglish_motion/reference_finish.py)
- [hinglish_motion/reference_motion.py](../../components/storylens/hinglish_motion/reference_motion.py)
- [hinglish_motion/reference_policy.py](../../components/storylens/hinglish_motion/reference_policy.py)
- [hinglish_motion/reference_run.py](../../components/storylens/hinglish_motion/reference_run.py)
- [hinglish_motion/reference_slots.py](../../components/storylens/hinglish_motion/reference_slots.py)
- [hinglish_motion/render.py](../../components/storylens/hinglish_motion/render.py)
- [hinglish_motion/report.py](../../components/storylens/hinglish_motion/report.py)
- [hinglish_motion/settings.py](../../components/storylens/hinglish_motion/settings.py)
- [hinglish_motion/speech_clock.py](../../components/storylens/hinglish_motion/speech_clock.py)
- [hinglish_motion/student_demo.py](../../components/storylens/hinglish_motion/student_demo.py)
- [hinglish_motion/style.py](../../components/storylens/hinglish_motion/style.py)
- [hinglish_motion/teacher_demo.py](../../components/storylens/hinglish_motion/teacher_demo.py)
- [hinglish_motion/teacher_memory.py](../../components/storylens/hinglish_motion/teacher_memory.py)
- [hinglish_motion/__init__.py](../../components/storylens/hinglish_motion/__init__.py)
- [hinglish_motion/__main__.py](../../components/storylens/hinglish_motion/__main__.py)
- [hinglish_motion/web/archive_cinematic.js](../../components/storylens/hinglish_motion/web/archive_cinematic.js)
- [hinglish_motion/web/archive_layouts.js](../../components/storylens/hinglish_motion/web/archive_layouts.js)
- [hinglish_motion/web/archive_motion.js](../../components/storylens/hinglish_motion/web/archive_motion.js)
- [hinglish_motion/web/creative.js](../../components/storylens/hinglish_motion/web/creative.js)
- [hinglish_motion/web/elements.js](../../components/storylens/hinglish_motion/web/elements.js)
- [hinglish_motion/web/native-text-binding.js](../../components/storylens/hinglish_motion/web/native-text-binding.js)
- [hinglish_motion/web/reference.js](../../components/storylens/hinglish_motion/web/reference.js)
- [hinglish_motion/web/teacher-world.js](../../components/storylens/hinglish_motion/web/teacher-world.js)
- [hinglish_motion/web/threeui-orbit.ts](../../components/storylens/hinglish_motion/web/threeui-orbit.ts)

## Buttons and their purposes

| Control | Purpose |
| --- | --- |
| Learn from pictures / videos | Selects reference files to save a motion style based on their visible design. |
| Learn from a folder | Selects a folder of motion references for style learning. |
| Make motion graphics | Generates motion graphics from the current script or footage and selected engine. |

Common and dynamic button families are also documented in the source voice catalogue. Dropdown options are defined in the actual HTML and JavaScript.

## Checks and limits

- [tests/caption-3d-motion.test.cjs](../../components/storylens/tests/caption-3d-motion.test.cjs)
- [tests/caption-3d-renderer-motion-blur.test.cjs](../../components/storylens/tests/caption-3d-renderer-motion-blur.test.cjs)
- [tests/caption-one-word-motion.test.cjs](../../components/storylens/tests/caption-one-word-motion.test.cjs)
- [tests/effects-toolkit-motion.test.cjs](../../components/storylens/tests/effects-toolkit-motion.test.cjs)
- [tests/quick-motion-integration.test.cjs](../../components/storylens/tests/quick-motion-integration.test.cjs)
- [tests/quick-motion-loader-scope.test.cjs](../../components/storylens/tests/quick-motion-loader-scope.test.cjs)
- [tests/quick-motion-native-apply-review.test.cjs](../../components/storylens/tests/quick-motion-native-apply-review.test.cjs)
- [tests/quick-motion-native.test.cjs](../../components/storylens/tests/quick-motion-native.test.cjs)
- [tests/quick-motion-repair-review.test.cjs](../../components/storylens/tests/quick-motion-repair-review.test.cjs)
- [tests/quick-motion-repair-ui.test.cjs](../../components/storylens/tests/quick-motion-repair-ui.test.cjs)
- [tests/quick-motion-repair.test.cjs](../../components/storylens/tests/quick-motion-repair.test.cjs)
- [tests/quick-motion-review.test.cjs](../../components/storylens/tests/quick-motion-review.test.cjs)
- [tests/quick-motion-ui.test.cjs](../../components/storylens/tests/quick-motion-ui.test.cjs)
- [tests/quick-motion.test.cjs](../../components/storylens/tests/quick-motion.test.cjs)
- [tests/test_creative_motion.py](../../components/storylens/tests/test_creative_motion.py)
- [tests/test_element_motion.py](../../components/storylens/tests/test_element_motion.py)

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
- [/api/chat](../../components/storylens/hinglish_motion/autonomous_reference.py#L84)
- [/api/bridge](../../components/storylens/hinglish_motion/report.py#L100)
- [/api/motion/rebuild](../../components/storylens/hinglish_motion/report.py#L102)

[All source-declared screen controls and dropdown choices](../control-screens.json)
