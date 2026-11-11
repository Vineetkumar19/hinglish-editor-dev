# Photo Collector

Collects candidate photos based on a screenshot. Choose or paste the screenshot, select Submit, then review the matches, resolution and source before selecting the photos you need.

## Where to start

- [Visible screen](../../components/storylens/hinglish_app/static/photos.html)
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

- [hinglish_app/photo_collector_http.py](../../components/storylens/hinglish_app/photo_collector_http.py)
- [hinglish_photos/aftereffects.py](../../components/storylens/hinglish_photos/aftereffects.py)
- [hinglish_photos/analysis.py](../../components/storylens/hinglish_photos/analysis.py)
- [hinglish_photos/core.py](../../components/storylens/hinglish_photos/core.py)
- [hinglish_photos/downloads.py](../../components/storylens/hinglish_photos/downloads.py)
- [hinglish_photos/editor_plugin.py](../../components/storylens/hinglish_photos/editor_plugin.py)
- [hinglish_photos/native_host.jsx](../../components/storylens/hinglish_photos/native_host.jsx)
- [hinglish_photos/network.py](../../components/storylens/hinglish_photos/network.py)
- [hinglish_photos/previews.py](../../components/storylens/hinglish_photos/previews.py)
- [hinglish_photos/quality.py](../../components/storylens/hinglish_photos/quality.py)
- [hinglish_photos/search_agents.py](../../components/storylens/hinglish_photos/search_agents.py)
- [hinglish_photos/service.py](../../components/storylens/hinglish_photos/service.py)
- [hinglish_photos/sources.py](../../components/storylens/hinglish_photos/sources.py)
- [hinglish_photos/__init__.py](../../components/storylens/hinglish_photos/__init__.py)

## Buttons and their purposes

| Control | Purpose |
| --- | --- |
| Submit | Searches for images matching the supplied screenshot and collection settings. |
| Download | Downloads the chosen candidate image from the current results. |

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
- [/api/photos/file](../../components/storylens/hinglish_app/photo_collector_http.py#L15)
- [/api/photos/history](../../components/storylens/hinglish_app/photo_collector_http.py#L19)
- [/api/photos/job](../../components/storylens/hinglish_app/photo_collector_http.py#L20)

[All source-declared screen controls and dropdown choices](../control-screens.json)
