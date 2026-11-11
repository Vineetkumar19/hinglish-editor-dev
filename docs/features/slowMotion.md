# Selective Slow Motion

Finds moving moments for selective slow-downs and lets you edit speed points. Add a folder or videos, click Find moments, review recommended speeds or tune the ramp, then render previews.

## Where to start

- [Visible screen](../../components/storylens/hinglish_app/static/selective-slow-motion.html)
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

- [hinglish_app/selective_slow_motion.py](../../components/storylens/hinglish_app/selective_slow_motion.py)
- [hinglish_app/selective_slow_motion_http.py](../../components/storylens/hinglish_app/selective_slow_motion_http.py)
- [hinglish_app/selective_slow_motion_native.py](../../components/storylens/hinglish_app/selective_slow_motion_native.py)
- [hinglish_app/selective_slow_motion_review.py](../../components/storylens/hinglish_app/selective_slow_motion_review.py)

## Buttons and their purposes

| Control | Purpose |
| --- | --- |
| Browse folder | Adds a source footage folder. |
| Add videos | Adds selected video files to the footage input. |
| Find moments | Scans the selected sources for movement that may suit slow motion. |
| Stop | Requests cancellation of the current scan or render. |
| Resume job | Restarts the saved interrupted slow-motion job. |
| Render recommended speeds | Renders the suggested variants for review. |
| Scan details | Expands the scan findings and any skipped or failed sources. |
| Add point | Adds a speed key point to the current variant. |
| Ramp from 1× | Creates a speed curve that transitions from normal speed. |
| Reset variant | Restores the selected variant's original speed points. |
| Remove | Removes the corresponding speed point. |
| Render selected previews | Renders the selected variants for visual review. |
| Open Slow Motion folder | Opens the output directory for this slow-motion job. |
| Download speed points | Downloads the editable timing recipe. |
| Download export index | Downloads the manifest of the selected job's output files. |
| Open last review | Restores the last saved slow-motion review. |
| Approve export | Marks the selected preview approved for export. |
| Reject preview | Records rejection of the selected preview. |
| Adobe comparison | Expands the native Adobe render comparison workflow. |
| Prepare native request | Writes a native comparison request for the selected variant. |
| Check and attach native render | Checks for and attaches the native output to this review. |
| Approve native export | Marks the attached Adobe comparison approved. |
| Reject native render | Records rejection of the attached native render. |

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

[All source-declared screen controls and dropdown choices](../control-screens.json)
