# Gaming Desk

Provides an inbox for game releases, updates and memes. Open Gaming Desk, browse or filter available items, and verify dates and original sources before using them as research. Gaming Highlights instead cuts a saved stream.

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

- [Service implementation](../../components/gaming-desk/app.py)

## Buttons and their purposes

| Control | Purpose |
| --- | --- |
| Launch / event preset ·30min,18:00–00:00 | Fills a 30-minute GPT interval, 18:00 to 00:00 IST and a 12-run daily cap. Save the settings to apply them. |

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
- [/api/state](../../components/gaming-desk/app.py#L168)
- [/api/selected](../../components/gaming-desk/app.py#L172)
- [/api/selected/prepare](../../components/gaming-desk/app.py#L174)
- [/api/config](../../components/gaming-desk/app.py#L180)
- [/api/scan](../../components/gaming-desk/app.py#L188)
- [/api/browser/connect](../../components/gaming-desk/app.py#L190)
- [/api/browser/finish](../../components/gaming-desk/app.py#L194)
- [/api/social](../../components/gaming-desk/app.py#L198)
- [/api/add](../../components/gaming-desk/app.py#L213)
- [/api/gpt](../../components/gaming-desk/app.py#L218)
- [/api/review](../../components/gaming-desk/app.py#L222)
- [/api/download](../../components/gaming-desk/app.py#L228)
- [/api/export](../../components/gaming-desk/app.py#L232)

[All source-declared screen controls and dropdown choices](../control-screens.json)
