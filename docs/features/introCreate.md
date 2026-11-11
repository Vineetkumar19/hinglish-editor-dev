# Intro Create

Reviews and retimes Instagram Reel and YouTube drafts. For a gaming replay, choose Gaming YouTube under Intro type, select the downloaded video and click Create gaming intro. It looks for complete funny commentary and makes a 30-second opener of 3–5-second clips. Review the intro or download the editable timeline with the full replay after the opener.

## Where to start

- [Visible screen](../../components/storylens/hinglish_app/static/hook-drafts.html)
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

- [hinglish_app/gaming_intro.py](../../components/storylens/hinglish_app/gaming_intro.py)

## Buttons and their purposes

| Control | Purpose |
| --- | --- |
| Intro type | Switches between Instagram Reel, YouTube and the 30-second Gaming YouTube opener. |
| Gaming YouTube | Shows the tools for making a 30-second comedy opener from a gaming replay. |
| Choose video | Opens the file picker for one downloaded gaming replay with commentary. |
| Create gaming intro | Finds complete funny commentary and creates a 30-second opener from 3–5-second clips. |
| Resume render | Retries the saved unfinished gaming intro using the same replay. |
| Gaming intro history | Shows previously submitted gaming intro jobs and opens the one you select. |
| Selected commentary | Shows the selected lines and the planner's reason for each choice. |
| Download intro | Saves the rendered gaming intro MP4. |
| Download editable intro + replay timeline | Saves an XML timeline with editable intro clips and the original replay starting after them. |
| Apply custom timing | Loads the intro matching the chosen format and duration into the preview. |
| Play intro | Starts playback of the selected draft with its current picture cuts and sound layers. |
| Stop | Stops playback and resets the intro clock. |
| Picture cuts | Expands the draft's shot timing controls. |
| Sound layers | Expands the draft's audio layer controls. |
| Save draft changes | Saves the current draft's edited cut and sound settings. |
| Load candidates | Loads footage candidates for building intro previews. |
| Restore saved preview | Reopens the saved intro preview. |
| Resume saved render | Resumes an unfinished intro render from the saved job. |
| Render three previews | Renders the three configured intro preview variants for review. |

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

[All source-declared screen controls and dropdown choices](../control-screens.json)
