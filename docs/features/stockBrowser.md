# Stock Browser

Shows and configures the dedicated stock-site browser connection for website footage discovery.

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

- [hinglish_app/stock_browser.py](../../components/storylens/hinglish_app/stock_browser.py)

## Buttons and their purposes

| Control | Purpose |
| --- | --- |
| Connect Chrome | Starts pairing for the dedicated stock-site Chrome connection. |
| Check connection | Rechecks the stock browser connection status. |
| Disconnect | Revokes the stock browser pairing. |
| Access details | Expands the current stock browser connection details. |

Common and dynamic button families are also documented in the source voice catalogue. Dropdown options are defined in the actual HTML and JavaScript.

## Checks and limits

- [tests/stock_browser_policy.test.cjs](../../components/storylens/tests/stock_browser_policy.test.cjs)
- [tests/test_stock_browser.py](../../components/storylens/tests/test_stock_browser.py)
- [tests/test_stock_browser_client.py](../../components/storylens/tests/test_stock_browser_client.py)
- [tests/test_stock_browser_http.py](../../components/storylens/tests/test_stock_browser_http.py)
- [tests/test_stock_browser_setup.py](../../components/storylens/tests/test_stock_browser_setup.py)

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
- [/api/stock-browser](../../components/storylens/hinglish_app/stock_browser.py#L155)
- [/api/stock-browser/pairing](../../components/storylens/hinglish_app/stock_browser.py#L156)
- [/api/stock-browser/job](../../components/storylens/hinglish_app/stock_browser.py#L157)
- [/api/stock-browser/request](../../components/storylens/hinglish_app/stock_browser.py#L163)
- [/api/stock-browser/disconnect](../../components/storylens/hinglish_app/stock_browser.py#L165)
- [/api/panel/config](../../components/storylens/tests/test_stock_browser_http.py#L22)
- [/api/stock-browser/worker/hello](../../components/storylens/tests/test_stock_browser_http.py#L27)
- [/api/stock-browser/worker/claim](../../components/storylens/tests/test_stock_browser_http.py#L29)
- [/api/stock-browser/worker/finish](../../components/storylens/tests/test_stock_browser_http.py#L31)
- [/api/stock-browser/job?id=](../../components/storylens/tests/test_stock_browser_http.py#L32)

[All source-declared screen controls and dropdown choices](../control-screens.json)
