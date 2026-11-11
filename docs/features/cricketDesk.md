# Cricket Desk

Provides an inbox for cricket news and memes. Open Cricket Desk, browse the current items, then check their dates and original sources before using them as research. It is separate from the editing and posting tools.

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

- [Service implementation](../../components/cricket-desk/app.py)

## Buttons and their purposes

| Control | Purpose |
| --- | --- |
| Settings | Opens the desk's research settings. |
| Schedule & sources | Opens the desk's research schedule and source settings. |
| Details | Opens the desk's collection-health details inside its settings. |
| Prepare selected for editing | Creates a local editor handoff from the chosen items. |
| Close settings | Dismisses the research settings dialog. |
| Connect collection browser | Opens the dedicated collection browser for sign-in or verification. |
| Finish browser setup | Checks whether the dedicated collection browser completed setup. |
| Refresh Instagram + X | Requests the desk's browser-based refresh of the configured Instagram and X sources. |
| Source coverage & research status | Expands source diagnostics and recent research status. |
| Add a post I found | Expands the form for an individual social post URL and short context. |
| Add source | Adds the entered source to the current collection. |
| Post details | Expands the item's author, event and verification details. |
| View source | Opens the original post. |
| Reload inbox | Reloads the embedded desk inbox. |
| Inbox not available? | Expands the instructions for reconnecting to the desk service. |
| IPL / World Cup preset ·30min,18:00–00:00 | Fills a 30-minute GPT interval, 18:00 to 00:00 IST and a 12-run daily cap. Save the settings to apply them. |

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
- [/api/state](../../components/cricket-desk/app.py#L151)
- [/api/selected](../../components/cricket-desk/app.py#L155)
- [/api/selected/prepare](../../components/cricket-desk/app.py#L157)
- [/api/config](../../components/cricket-desk/app.py#L163)
- [/api/scan](../../components/cricket-desk/app.py#L171)
- [/api/browser/connect](../../components/cricket-desk/app.py#L173)
- [/api/browser/finish](../../components/cricket-desk/app.py#L177)
- [/api/social](../../components/cricket-desk/app.py#L181)
- [/api/add](../../components/cricket-desk/app.py#L196)
- [/api/gpt](../../components/cricket-desk/app.py#L201)
- [/api/review](../../components/cricket-desk/app.py#L205)
- [/api/download](../../components/cricket-desk/app.py#L211)
- [/api/export](../../components/cricket-desk/app.py#L215)

[All source-declared screen controls and dropdown choices](../control-screens.json)
