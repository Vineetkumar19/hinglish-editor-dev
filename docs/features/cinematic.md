# Cinematic Footage

Extracts short, visually distinct shots from footage into Best Shots and Extras. Choose a folder or videos, click Extract shots, review both groups and open the output folder to select what you want to use.

## Where to start

- [Visible screen](../../components/storylens/hinglish_app/static/cinematic-footage.html)
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

- [hinglish_cinematic/body_render.py](../../components/storylens/hinglish_cinematic/body_render.py)
- [hinglish_cinematic/curation.py](../../components/storylens/hinglish_cinematic/curation.py)
- [hinglish_cinematic/footage.py](../../components/storylens/hinglish_cinematic/footage.py)
- [hinglish_cinematic/footage_review.py](../../components/storylens/hinglish_cinematic/footage_review.py)
- [hinglish_cinematic/intro_render.py](../../components/storylens/hinglish_cinematic/intro_render.py)
- [hinglish_cinematic/match_cut.py](../../components/storylens/hinglish_cinematic/match_cut.py)
- [hinglish_cinematic/match_cut_analysis.py](../../components/storylens/hinglish_cinematic/match_cut_analysis.py)
- [hinglish_cinematic/match_cut_media.py](../../components/storylens/hinglish_cinematic/match_cut_media.py)
- [hinglish_cinematic/media_index.py](../../components/storylens/hinglish_cinematic/media_index.py)
- [hinglish_cinematic/native_slot_plan.py](../../components/storylens/hinglish_cinematic/native_slot_plan.py)
- [hinglish_cinematic/planner.py](../../components/storylens/hinglish_cinematic/planner.py)
- [hinglish_cinematic/recipes.py](../../components/storylens/hinglish_cinematic/recipes.py)
- [hinglish_cinematic/render.py](../../components/storylens/hinglish_cinematic/render.py)
- [hinglish_cinematic/retrieval_loader.py](../../components/storylens/hinglish_cinematic/retrieval_loader.py)
- [hinglish_cinematic/semantic_windows.py](../../components/storylens/hinglish_cinematic/semantic_windows.py)
- [hinglish_cinematic/service.py](../../components/storylens/hinglish_cinematic/service.py)
- [hinglish_cinematic/sound_catalog.py](../../components/storylens/hinglish_cinematic/sound_catalog.py)
- [hinglish_cinematic/sound_loop.py](../../components/storylens/hinglish_cinematic/sound_loop.py)
- [hinglish_cinematic/sound_mix.py](../../components/storylens/hinglish_cinematic/sound_mix.py)
- [hinglish_cinematic/source_proxy.py](../../components/storylens/hinglish_cinematic/source_proxy.py)
- [hinglish_cinematic/story_graph.py](../../components/storylens/hinglish_cinematic/story_graph.py)
- [hinglish_cinematic/variant_assembly.py](../../components/storylens/hinglish_cinematic/variant_assembly.py)
- [hinglish_cinematic/visual_search.py](../../components/storylens/hinglish_cinematic/visual_search.py)
- [hinglish_cinematic/__init__.py](../../components/storylens/hinglish_cinematic/__init__.py)

## Buttons and their purposes

| Control | Purpose |
| --- | --- |
| Folder | Opens the footage folder picker. |
| Videos | Opens the picker for individual footage files. |
| Extract shots | Scans the chosen footage and saves ranked shot candidates. |
| Stop | Cancels the current extraction. |
| Best Shots | Shows the ranked selection of best shots. |
| Extras | Shows additional candidate shots. |
| Selection details | Expands the reasons and metrics for the selected shot. |
| Review saved candidates | Reopens the selected saved extraction for story review. |
| Resume interrupted extraction | Resumes the selected incomplete extraction. |
| Open last extraction | Reopens the most recently saved footage bank. |
| Search footage | Searches the current footage bank. |
| Find visual matches | Runs a visual similarity search for the selected reference. |
| Restore visual search | Restores the saved visual search and its results. |
| Propose story | Builds a draft sequence using the current story and footage candidates. |
| Save description | Saves the edited description for the selected shot. |
| Save label | Saves the edited label for the selected shot. |
| Approve candidate | Marks this candidate accepted in the local review. |
| Reject candidate | Marks this candidate rejected in the local review. |
| Preview original source | Plays the source footage at this candidate's location. |
| Pin to chosen phase | Assigns the selected candidate to the chosen story phase. |
| Use and lock | Keeps the chosen candidate fixed in its assigned phase. |
| Unlock | Allows the locked story selection to change again. |
| Move phase earlier | Moves the selected story phase earlier in the draft order. |
| Approve body plan | Saves the reviewed body arrangement as approved. |
| Render body-only preview | Renders a review video of the body plan. |

Common and dynamic button families are also documented in the source voice catalogue. Dropdown options are defined in the actual HTML and JavaScript.

## Checks and limits

- [tests/cinematic-preview-reader.test.cjs](../../components/storylens/tests/cinematic-preview-reader.test.cjs)
- [tests/cinematic-text-bridge.test.cjs](../../components/storylens/tests/cinematic-text-bridge.test.cjs)
- [tests/cinematic-text-gallery.test.cjs](../../components/storylens/tests/cinematic-text-gallery.test.cjs)
- [tests/cinematic-text-native.test.cjs](../../components/storylens/tests/cinematic-text-native.test.cjs)
- [tests/cinematic-text-selective-native.test.cjs](../../components/storylens/tests/cinematic-text-selective-native.test.cjs)
- [tests/cinematic-text-ui.test.cjs](../../components/storylens/tests/cinematic-text-ui.test.cjs)
- [tests/cinematic-text.test.cjs](../../components/storylens/tests/cinematic-text.test.cjs)
- [tests/test_beat_cinematic_component.py](../../components/storylens/tests/test_beat_cinematic_component.py)
- [tests/test_cinematic.py](../../components/storylens/tests/test_cinematic.py)
- [tests/test_cinematic_footage.py](../../components/storylens/tests/test_cinematic_footage.py)
- [tests/test_cinematic_http.py](../../components/storylens/tests/test_cinematic_http.py)
- [tests/test_cinematic_reference.py](../../components/storylens/tests/test_cinematic_reference.py)
- [tests/test_cinematic_semantic_windows.py](../../components/storylens/tests/test_cinematic_semantic_windows.py)

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
- [/api/tags](../../components/storylens/hinglish_cinematic/semantic_windows.py#L312)
- [/api/version](../../components/storylens/hinglish_cinematic/semantic_windows.py#L318)
- [/api/cinematic/jobs/](../../components/storylens/tests/test_cinematic_http.py#L32)
- [/api/beats/analyze](../../components/storylens/tests/test_cinematic_http.py#L41)
- [/api/beats/jobs/](../../components/storylens/tests/test_cinematic_http.py#L44)
- [/api/cinematic/assemble](../../components/storylens/tests/test_cinematic_http.py#L46)
- [/api/cinematic/video/](../../components/storylens/tests/test_cinematic_http.py#L51)
- [/api/cinematic/effects](../../components/storylens/tests/test_cinematic_http.py#L57)
- [/api/cinematic/import-manifest](../../components/storylens/tests/test_cinematic_http.py#L59)
- [/api/cinematic/cancel](../../components/storylens/tests/test_cinematic_http.py#L73)
- [/api/cinematic/upload?name=x.mp4](../../components/storylens/tests/test_cinematic_http.py#L73)
- [/api/cinematic/upload?name=bad.py](../../components/storylens/tests/test_cinematic_http.py#L77)
- [/api/cinematic/upload?host=premiere&name=clip.mp4](../../components/storylens/tests/test_cinematic_http.py#L87)
- [/api/cinematic/upload?host=untrusted&name=clip.mp4](../../components/storylens/tests/test_cinematic_http.py#L89)

[All source-declared screen controls and dropdown choices](../control-screens.json)
