# Finance

Finance shows monthly cash flow from Pocket Tracker and recorded net worth from Finance Tracker. Use Month and Refresh to review the summaries, or open either tracker from the links at the top for its own tools. Storylens Finance is a read-only summary.

## Where to start

- [Visible screen](../../components/storylens/hinglish_app/static/finance.html)
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

- [hinglish_app/finance.py](../../components/storylens/hinglish_app/finance.py)
- [hinglish_app/finance_ui/finance.js](../../components/storylens/hinglish_app/finance_ui/finance.js)

## Buttons and their purposes

| Control | Purpose |
| --- | --- |
| Open Pocket Tracker | Opens the local Pocket Tracker companion for the paired phone ledger, reports, and pairing. |
| Open Finance Tracker | Opens the local Finance Tracker ledger for investments, cash, deposits, assets, and debts. |
| Refresh | Requests updated Pocket Tracker cash flow and Finance Tracker net worth for the Finance summary. |
| Month | Chooses the YYYY-MM month for the Pocket Tracker cash-flow summary. |
| Monthly cash flow | Shows money in, money out, and available recurring and budget information from Pocket Tracker. |
| Net worth | Shows the latest recorded net worth and the available asset and liability totals from Finance Tracker. |
| StoryLens | Returns to the main editor. |

Common and dynamic button families are also documented in the source voice catalogue. Dropdown options are defined in the actual HTML and JavaScript.

## Checks and limits

Use the component tests and a representative task in the receiving application.
Pocket Tracker and Finance Tracker are separate local services. Personal ledgers and pairing keys are outside this package.

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
- [/api/finance-tracker](../../components/storylens/hinglish_app/finance.py#L91)
- [/api/pocket](../../components/storylens/hinglish_app/finance.py#L91)
- [/api/finance-summary](../../components/storylens/hinglish_app/finance.py#L100)
- [/api/snapshot](../../components/storylens/hinglish_app/finance.py#L104)
- [/api/pocket?month=](../../components/storylens/hinglish_app/finance_ui/finance.js#L82)

[All source-declared screen controls and dropdown choices](../control-screens.json)
