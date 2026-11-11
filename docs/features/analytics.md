# Analytics

Reviews saved performance for the two YouTube channels and two Instagram accounts. Overview compares accounts; Analytics shows account trends and content; Reports shows monthly, quarterly, and annual results; Connections manages read permissions and Chrome reads.

## Where to start

- [Visible screen](../../components/storylens/hinglish_app/static/creator-analytics.html)
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

- [hinglish_app/analytics_http.py](../../components/storylens/hinglish_app/analytics_http.py)
- [hinglish_app/analytics_sources.py](../../components/storylens/hinglish_app/analytics_sources.py)

## Buttons and their purposes

| Control | Purpose |
| --- | --- |
| Overview | Compares performance across the saved creator accounts. |
| Analytics | Opens the selected account's trends, recent content, and available metrics. |
| Reports | Opens the selected account's monthly, quarterly, or annual reports. |
| Connections | Shows which YouTube and Instagram accounts can supply analytics. |
| Refresh accounts | Refreshes analytics for the connected creator accounts. |
| All accounts | Includes all four creator accounts in Overview. |
| Cricket | Limits Overview to the cricket YouTube and Instagram accounts. |
| Gaming | Limits Overview to the gaming YouTube and Instagram accounts. |
| Account | Chooses which account the Analytics and Reports views show. |
| Report period | Changes Reports between Monthly, Quarterly, and Annual. |
| Month | Chooses the month shown in the monthly analytics report. |
| Quarter | Chooses Q1, Q2, Q3, or Q4 for a quarterly report. |
| Year | Chooses the calendar year for the quarterly or annual report. |
| Trend metric | Chooses which available metric the trend chart plots. |
| Download annual CSV | Downloads the selected account's annual report as a CSV file. |
| Show all | Expands the current content list to show all loaded entries. |
| Show fewer | Collapses the content list back to its shorter view. |
| Connect YouTube Analytics | Opens the Google permissions flow for the selected analytics account. |
| Connect | Starts the reviewed account’s analytics permission or read flow. |
| Include estimated revenue | Requests the additional YouTube analytics permission for estimated revenue. |
| Read Instagram in Chrome | Requests an analytics read through the paired Chrome session for the selected Instagram account. |
| Remove local data | Opens confirmation to remove this account's local analytics data and pause its collection. |
| Open StoryLens Chrome connection | Opens the Chrome Publisher pairing page for Instagram access. |
| Close | Closes the current video analytics dialog. |
| Cancel | Closes the current analytics connection dialog. |
| Back to editor | Returns to the main StoryLens editor. |

Common and dynamic button families are also documented in the source voice catalogue. Dropdown options are defined in the actual HTML and JavaScript.

## Checks and limits

Use the component tests and a representative task in the receiving application.
Requires authorized accounts or a dedicated review account. Credentials and live queues are outside this package.

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
- [/api/analytics/video](../../components/storylens/hinglish_app/analytics_http.py#L284)
- [/api/analytics/dashboard](../../components/storylens/hinglish_app/analytics_http.py#L293)
- [/api/analytics/export](../../components/storylens/hinglish_app/analytics_http.py#L295)
- [/api/analytics/refresh](../../components/storylens/hinglish_app/analytics_http.py#L314)
- [/api/analytics/connect-youtube](../../components/storylens/hinglish_app/analytics_http.py#L321)
- [/api/analytics/connect-instagram](../../components/storylens/hinglish_app/analytics_http.py#L324)
- [/api/analytics/disconnect](../../components/storylens/hinglish_app/analytics_http.py#L327)

[All source-declared screen controls and dropdown choices](../control-screens.json)
