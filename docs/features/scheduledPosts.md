# Scheduled posts

Shows saved publishing schedules and their status. Open Scheduled posts in the top bar, find the item, and confirm platform, account, and scheduled time. An item waiting in the queue has yet to publish.

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

- [hinglish_app/scheduled_posts.py](../../components/storylens/hinglish_app/scheduled_posts.py)
- [hinglish_app/scheduled_posts_cancel.py](../../components/storylens/hinglish_app/scheduled_posts_cancel.py)
- [hinglish_app/scheduled_posts_delete.py](../../components/storylens/hinglish_app/scheduled_posts_delete.py)

## Buttons and their purposes

| Control | Purpose |
| --- | --- |
| Cricket | Filters the queue to the Cricket creator channel. |
| Gaming | Filters the queue to the Gaming creator channel. |
| Other | Filters the queue to entries outside the two creator channels. |
| Delete | Removes the selected failed attempt from the queue history. |

Common and dynamic button families are also documented in the source voice catalogue. Dropdown options are defined in the actual HTML and JavaScript.

## Checks and limits

- [tests/scheduled_posts_actions.test.cjs](../../components/storylens/tests/scheduled_posts_actions.test.cjs)
- [tests/test_scheduled_posts.py](../../components/storylens/tests/test_scheduled_posts.py)
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

[All source-declared screen controls and dropdown choices](../control-screens.json)
