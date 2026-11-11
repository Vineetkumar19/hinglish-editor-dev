# Smart Zoom

Adds editable zooms for key script moments or alternate framing at cuts, with optional face focus. Choose a video or timeline XML, select the zoom strength and relevant options, run Add smart zooms and review framing and timing.

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

- [hinglish_zoom/curve.py](../../components/storylens/hinglish_zoom/curve.py)
- [hinglish_zoom/cut_pacing.py](../../components/storylens/hinglish_zoom/cut_pacing.py)
- [hinglish_zoom/effects.py](../../components/storylens/hinglish_zoom/effects.py)
- [hinglish_zoom/effects_quality.py](../../components/storylens/hinglish_zoom/effects_quality.py)
- [hinglish_zoom/events.py](../../components/storylens/hinglish_zoom/events.py)
- [hinglish_zoom/faces.py](../../components/storylens/hinglish_zoom/faces.py)
- [hinglish_zoom/overlays.py](../../components/storylens/hinglish_zoom/overlays.py)
- [hinglish_zoom/pipeline.py](../../components/storylens/hinglish_zoom/pipeline.py)
- [hinglish_zoom/planner.py](../../components/storylens/hinglish_zoom/planner.py)
- [hinglish_zoom/preview.py](../../components/storylens/hinglish_zoom/preview.py)
- [hinglish_zoom/provenance.py](../../components/storylens/hinglish_zoom/provenance.py)
- [hinglish_zoom/report.py](../../components/storylens/hinglish_zoom/report.py)
- [hinglish_zoom/settings.py](../../components/storylens/hinglish_zoom/settings.py)
- [hinglish_zoom/shots.py](../../components/storylens/hinglish_zoom/shots.py)
- [hinglish_zoom/sound_policy.py](../../components/storylens/hinglish_zoom/sound_policy.py)
- [hinglish_zoom/sound_timing.py](../../components/storylens/hinglish_zoom/sound_timing.py)
- [hinglish_zoom/subjects.py](../../components/storylens/hinglish_zoom/subjects.py)
- [hinglish_zoom/word_candidates.py](../../components/storylens/hinglish_zoom/word_candidates.py)
- [hinglish_zoom/xml_apply.py](../../components/storylens/hinglish_zoom/xml_apply.py)
- [hinglish_zoom/__init__.py](../../components/storylens/hinglish_zoom/__init__.py)
- [hinglish_zoom/__main__.py](../../components/storylens/hinglish_zoom/__main__.py)

## Buttons and their purposes

| Control | Purpose |
| --- | --- |
| Add smart zooms | Finds zoom moments and prepares zoom keyframes with the chosen strength and options. |

Common and dynamic button families are also documented in the source voice catalogue. Dropdown options are defined in the actual HTML and JavaScript.

## Checks and limits

- [tests/test_smart_zoom_chat.py](../../components/storylens/tests/test_smart_zoom_chat.py)
- [tests/test_zoom.py](../../components/storylens/tests/test_zoom.py)
- [tests/test_zoom_cut_pacing.py](../../components/storylens/tests/test_zoom_cut_pacing.py)
- [tests/test_zoom_effects.py](../../components/storylens/tests/test_zoom_effects.py)

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

[All source-declared screen controls and dropdown choices](../control-screens.json)
