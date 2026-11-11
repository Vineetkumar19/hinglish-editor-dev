# Editor Handoff

Transfers compatible rendered media or editable work between Premiere Pro, After Effects, DaVinci Resolve and CapCut. Choose From and To, select the supported source, choose what to Send, then prepare the transfer and use the result's import action. Editability depends on the chosen route and format.

## Where to start

- [Visible screen](../../components/storylens/hinglish_app/static/editor-link.html)
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

- [hinglish_app/editor_link.py](../../components/storylens/hinglish_app/editor_link.py)
- [tools/editor_link/cache_to_xml.py](../../components/storylens/tools/editor_link/cache_to_xml.py)
- [tools/editor_link/conform_audit.py](../../components/storylens/tools/editor_link/conform_audit.py)
- [tools/editor_link/from_capcut.py](../../components/storylens/tools/editor_link/from_capcut.py)
- [tools/editor_link/resolve_handoff.py](../../components/storylens/tools/editor_link/resolve_handoff.py)
- [tools/editor_link/send_to_resolve.py](../../components/storylens/tools/editor_link/send_to_resolve.py)
- [tools/editor_link/serve.py](../../components/storylens/tools/editor_link/serve.py)
- [tools/editor_link/timing_audit.py](../../components/storylens/tools/editor_link/timing_audit.py)
- [tools/editor_link/to_after_effects.py](../../components/storylens/tools/editor_link/to_after_effects.py)
- [tools/editor_link/to_capcut.py](../../components/storylens/tools/editor_link/to_capcut.py)

## Buttons and their purposes

| Control | Purpose |
| --- | --- |
| Transfer format | Expands the media, XML, native project or active-project transfer choices. |
| Copy transfer location | Copies the saved transfer artifact path. |
| Retry in After Effects | Retries the prepared transfer in After Effects. |
| Retry in Premiere Pro | Retries the prepared transfer in Premiere Pro. |
| Retry in DaVinci Resolve | Retries the prepared transfer in DaVinci Resolve. |
| Retry in CapCut | Retries the prepared transfer in CapCut. |

Common and dynamic button families are also documented in the source voice catalogue. Dropdown options are defined in the actual HTML and JavaScript.

## Checks and limits

Use the component tests and a representative task in the receiving application.
Requires the named native editor and integration. Cross-editor editability and Mac compatibility require route-specific validation.

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
- [/api/native-tools/](../../components/storylens/hinglish_app/editor_link.py#L67)
- [/api/pick](../../components/storylens/tools/editor_link/serve.py#L16)
- [/api/editor-link/prepare](../../components/storylens/tools/editor_link/serve.py#L17)
- [/api/editor-link/apply](../../components/storylens/tools/editor_link/serve.py#L17)
- [/api/editor-link/capcut-drafts](../../components/storylens/tools/editor_link/serve.py#L17)

[All source-declared screen controls and dropdown choices](../control-screens.json)
