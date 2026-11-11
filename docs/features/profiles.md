# Creator profiles

Keeps creator context and preferences organized by General, Cricket, or Gaming. Click Profile in the top bar, choose the intended profile, then use its shortcuts or save preferences. Check the destination account again in Prepare and Post.

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

- [hinglish_niche/continuous_motion.py](../../components/storylens/hinglish_niche/continuous_motion.py)
- [hinglish_niche/documentary.py](../../components/storylens/hinglish_niche/documentary.py)
- [hinglish_niche/documentary_memory.py](../../components/storylens/hinglish_niche/documentary_memory.py)
- [hinglish_niche/gaming.py](../../components/storylens/hinglish_niche/gaming.py)
- [hinglish_niche/gaming_lineage.py](../../components/storylens/hinglish_niche/gaming_lineage.py)
- [hinglish_niche/historical.py](../../components/storylens/hinglish_niche/historical.py)
- [hinglish_niche/image_design.py](../../components/storylens/hinglish_niche/image_design.py)
- [hinglish_niche/independent_trio.py](../../components/storylens/hinglish_niche/independent_trio.py)
- [hinglish_niche/kkr_thumbnail.py](../../components/storylens/hinglish_niche/kkr_thumbnail.py)
- [hinglish_niche/local_photo_studio.py](../../components/storylens/hinglish_niche/local_photo_studio.py)
- [hinglish_niche/photo_continuity.py](../../components/storylens/hinglish_niche/photo_continuity.py)
- [hinglish_niche/photo_thumbnail.py](../../components/storylens/hinglish_niche/photo_thumbnail.py)
- [hinglish_niche/profiles.py](../../components/storylens/hinglish_niche/profiles.py)
- [hinglish_niche/reference_dna.py](../../components/storylens/hinglish_niche/reference_dna.py)
- [hinglish_niche/research.py](../../components/storylens/hinglish_niche/research.py)
- [hinglish_niche/style_memory.py](../../components/storylens/hinglish_niche/style_memory.py)
- [hinglish_niche/thumbnail.py](../../components/storylens/hinglish_niche/thumbnail.py)
- [hinglish_niche/thumbnail_layout.py](../../components/storylens/hinglish_niche/thumbnail_layout.py)
- [hinglish_niche/thumbnail_memory.py](../../components/storylens/hinglish_niche/thumbnail_memory.py)
- [hinglish_niche/__init__.py](../../components/storylens/hinglish_niche/__init__.py)
- [hinglish_niche/__main__.py](../../components/storylens/hinglish_niche/__main__.py)

## Buttons and their purposes

| Control | Purpose |
| --- | --- |
| Profile | Opens the creator profile chooser. |
| General | Switches the workspace to the General profile. |
| Cricket | Switches the workspace to the Cricket profile. |
| Gaming | Switches the workspace to the Gaming profile. |
| Cricket Stories, match reactions & news | Activates the Cricket creator profile and its editing preferences. |
| Gaming Streams, highlights & Shorts | Activates the Gaming creator profile and its editing preferences. |
| My channel preferences & references | Opens the active creator's preferences and source references. |
| Save & refresh sources | Saves source settings and refreshes the active creator's sources. |
| Save this channel's preferences | Saves the current profile's preferences separately from the other profiles. |
| Close creator profile settings | Closes the creator profile panel. |
| My channel preferences & references | Expands saved preferences and sources for the selected creator profile. |
| Create thumbnail | Fills the editor prompt with a thumbnail request for the selected profile. |
| Prepare and Post | Opens Publishing Studio for the selected creator profile. |
| 15-minute highlights | Fills the editor prompt with the gaming highlight request. |
| Highlights + 5 Shorts | Fills the editor prompt with the gaming highlight and five Shorts request. |
| Video + 5 Shorts | Fills the editor prompt with the cricket video and five Shorts request. |
| Save this channel's preferences | Saves the selected profile's editing preferences and references. |
| Save & refresh sources | Saves the Cricket profile's source information and requests updated evidence. |

Common and dynamic button families are also documented in the source voice catalogue. Dropdown options are defined in the actual HTML and JavaScript.

## Checks and limits

- [tests/test_niche.py](../../components/storylens/tests/test_niche.py)

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
