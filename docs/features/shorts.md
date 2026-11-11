# Long to Shorts

Finds standalone hook and payoff moments in a finished long MP4 or MOV. Choose the video, exact count, duration and look, use Make my shorts, then review the cut, crop and captions. This creates clips for review; use Prepare and Post separately when you want to post.

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

- [hinglish_shorts/find.py](../../components/storylens/hinglish_shorts/find.py)
- [hinglish_shorts/pipeline.py](../../components/storylens/hinglish_shorts/pipeline.py)
- [hinglish_shorts/published_moments.py](../../components/storylens/hinglish_shorts/published_moments.py)
- [hinglish_shorts/render.py](../../components/storylens/hinglish_shorts/render.py)
- [hinglish_shorts/report.py](../../components/storylens/hinglish_shorts/report.py)
- [hinglish_shorts/settings.py](../../components/storylens/hinglish_shorts/settings.py)
- [hinglish_shorts/source.py](../../components/storylens/hinglish_shorts/source.py)
- [hinglish_shorts/title_review.py](../../components/storylens/hinglish_shorts/title_review.py)
- [hinglish_shorts/xml.py](../../components/storylens/hinglish_shorts/xml.py)
- [hinglish_shorts/__init__.py](../../components/storylens/hinglish_shorts/__init__.py)
- [hinglish_shorts/__main__.py](../../components/storylens/hinglish_shorts/__main__.py)

## Buttons and their purposes

| Control | Purpose |
| --- | --- |
| Make my shorts | Extracts short clips from the chosen long video using the selected count and framing. |

Common and dynamic button families are also documented in the source voice catalogue. Dropdown options are defined in the actual HTML and JavaScript.

## Checks and limits

- [tests/test_shorts.py](../../components/storylens/tests/test_shorts.py)
- [tests/test_shorts_output_collection.py](../../components/storylens/tests/test_shorts_output_collection.py)
- [tests/test_shorts_title_review.py](../../components/storylens/tests/test_shorts_title_review.py)

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
- [/api/bridge](../../components/storylens/hinglish_shorts/report.py#L63)
- [/api/shorts/rebuild](../../components/storylens/hinglish_shorts/report.py#L64)

[All source-declared screen controls and dropdown choices](../control-screens.json)
