# AI Agents

Opens the connected Agent Suite and Comment replies workspace. It includes Editing clients, Sponsorships and SaaS sales, plus Community, Jobs, Development clients and All workflows under Developer tools. Review Connections and account-specific reply modes in Comment replies. Configured access is not proof that a platform can currently send; check the live account status before delivery.

## Where to start

- [Visible screen](../../components/storylens/hinglish_app/static/ai-agents.html)
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

- [hinglish_app/agents_http.py](../../components/storylens/hinglish_app/agents_http.py)

## Buttons and their purposes

| Control | Purpose |
| --- | --- |
| Refresh | Reloads the agent suite and its connection statuses. |
| Developer tools | Shows or hides the developer agents. |
| All agents | Returns to the full agent list. |
| Open in new tab | Opens the selected suite workspace separately. |
| Open replies | Opens comment-reply accounts and inbox. |
| Demand research | Opens the demand research agent workspace. |
| Open workflows | Opens the agent workflows workspace. |
| Check | Checks the corresponding account's current connection. |
| Run replies now | Starts a reply agent pass for the selected account. |
| Enable Chrome replies | Enables the selected account's Chrome reply workflow. |
| Draft reply | Generates a draft response for the selected comment. |
| Copy reply | Copies the current reply text. |
| Send reply | Submits the reviewed reply to the selected comment. |
| Editing clients | Opens the Editing clients card for gigs, quotes, and proposal work. |
| Sponsorships | Opens the Sponsorships card for pitches and reply tracking. |
| SaaS sales | Opens the SaaS sales card for lead and demand research. |
| Community | Opens the Community agent under Developer tools. |
| Jobs | Opens the Jobs agent under Developer tools. |
| Development clients | Opens the Development clients agent under Developer tools. |
| Connections | Shows current agent and account connection status. |
| Back to editor | Returns to the main StoryLens editor. |
| View comment | Opens the original comment on its platform. |
| Reply mode | Chooses Paused, Draft for review, or Automatic replies where the account supports it. |
| Daily reply limit | Sets the maximum number of replies per day for the named account. |

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
- [/api/storylens/status](../../components/storylens/hinglish_app/agents_http.py#L62)
- [/api/agents/status](../../components/storylens/hinglish_app/agents_http.py#L135)
- [/api/agents/comments/status](../../components/storylens/hinglish_app/agents_http.py#L136)
- [/api/agents/task](../../components/storylens/hinglish_app/agents_http.py#L137)
- [/api/agents/connect](../../components/storylens/hinglish_app/agents_http.py#L146)
- [/api/agents/open](../../components/storylens/hinglish_app/agents_http.py#L147)
- [/api/agents/run](../../components/storylens/hinglish_app/agents_http.py#L148)
- [/api/storylens/run](../../components/storylens/hinglish_app/agents_http.py#L150)
- [/api/agents/comments/](../../components/storylens/hinglish_app/agents_http.py#L151)

[All source-declared screen controls and dropdown choices](../control-screens.json)
