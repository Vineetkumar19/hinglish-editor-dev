# Smart Visuals: requested behavior and validation

Owner request, 23 October 2026:

- Read the actual speech, find real named people, companies, team logos, places and events online, and place the matching visuals at the spoken moments.
- Use smoothly animated full-screen visuals, overlays/cutouts, or visuals behind the speaker. Do not substitute generated lookalikes or generic B-roll for a named person or event.
- For the current demonstration, hide the already-edited source pictures with black and retain their audio. Produce two separate outputs: `A:\Full Drive\thisis.vineet\e7\E7 final.mp4` and one cricket video selected by the local model from `A:\Full Drive\remove silence\All Shorts`.
- Keep rendering sequential to limit memory use. Show the actual results in Storylens and retain editor export options.

Implementation checks:

- Audio-on-black timeline generation; original file preserved.
- Smooth overlay entrance, continuous movement, exit, and rising cutouts.
- Gentle camera movement on full-screen photos and downloaded video.
- Event candidates retain the requested year and final/semifinal distinction.
- Source-folder selection accepts only IDs of existing files, with saved selection evidence.
- Smart Visuals constructor uses keyword arguments and keeps B-roll's optional subject field from shifting entity/presentation fields.
- 32 focused tests passed on 23 October 2026, including protection against a second window overwriting another run's saved status. These are supplementary checks, not live acceptance.

Live validation is **incomplete**. Shared-server restarts interrupted the original attempts. A separate local test instance is running on port 8768 with publishing disabled and the shared GPU lock retained. The final two previews still need inspection for identity, timing, motion and preserved audio. Behind-speaker segmentation and cutout rendering have not yet been validated on a real talking-head output.

Queued conversations on that test instance:

- E7: `8231d91d6c2c49c3`
- Cricket: `9ffdb7d4bcd64f1b`

The owner explicitly chose to let B-roll finish before these tests. Do not terminate other active editing work to accelerate this demonstration.

Latest attempt: E7 job `3fb56c1c1fb7` reached internet search, then its editing process exited with code 4294967295. Read-only inspection of the Add B-roll task confirmed it intentionally stopped this Smart Visuals worker on the owner's instruction: captions first, B-roll second. No finished preview was produced. Output directory `20261023-132424-b83e01` contains the audio-on-black base and candidate thumbnails only. Do not present it as a finished demonstration.

The failed attempt exposed two identity mismatches: a city mention selected a businessperson, and generic nightlife selected a song. Place filtering now rejects personal biographies, and a single Wikidata result still requires contextual model confirmation unless it is an exact matching brand. A focused regression check passed. The isolated server was restarted after this failed job to load those changes and the bounded cricket-source inventory. B-roll remains the priority; retry Smart Visuals after it finishes.

## Source choices and team-context verification — 23 October 2026

The owner subsequently confirmed B-roll works and requested five real internet references per named subject or specific fact, with manual selection before editor handoff. Agent Reach public web search/page reading is integrated with the existing local vision model. No social-account cookies or additional Agent Reach channels were configured. Preserve this requirement: a player must match both identity and the script's team/kit context (Kohli/RCB and Rohit/MI examples); the correct face in India kit is insufficient for an IPL-team request. Documents and scorecards receive a separate readable-evidence check rather than the photo check's screenshot prohibition.

Actual Storylens outputs on the isolated service, publishing disabled:

- E7: `output/visuals/20261023-210430-b495f4/001-0000-E7-final/report.html`. Original 33.3-second audio over black; five Instagram logo options. One selected logo saved through the review UI. Other place references remain uncertain; no invented city choice was added.
- Cricket: the local model selected `All Shorts/Shorts 35.mp4` (14.066 seconds). Review: `output/visuals/20261023-211449-a5edb0/001-0000-Shorts-35/report.html`. Twenty-four checked options: Gambhir 3, KKR 5, IPL Trophy 1, CSK 5, Mumbai Indians 5, IPL champions source tables 5. Six demonstration selections saved through the UI. Five-per-keyword coverage is therefore **incomplete** for Gambhir and the trophy; shortfalls remain visible instead of unrelated padding.

The live review exposed a false positive: Gambhir in blue India/BCCI training kit initially passed the general vision judgment. Independent grounded crest comparison with the source-checked KKR logo now rejects that file. The chosen purple/gold Nokia KKR portrait and the real IPL table screenshot were inspected directly. This is demonstrated rejection of one real failure, not a guarantee that vision can never misidentify an image.

Both saved browser previews played to their exact ends without a media error. A one-frame rendered-source mismatch stopped the first cricket save; frame-boundary-conformed generation repaired it, and the repeated UI save succeeded. Source audio and black backgrounds remain separate from selected animated visual clips. The screenshot evidence is under `output/visuals/live-validation`.

Premiere and CapCut preparation was exercised through the actual Storylens API for both saved results, without opening those memory-heavy editors. Both Premiere project files exist and decompress/parse; both CapCut drafts contain the original source track and a separate Selected Smart Visuals track (six selected segments for cricket, one for E7). Receipts: `live-validation/handoffs.json` and `native-files.json`. Native playback/import appearance remains **unverified**. The offered timeline layers are rendered animated clips that can be moved, trimmed and resized, not native editable image-motion keyframes. Original downloaded PNGs/photos remain accessible individually in the choice bank.

The final supplementary suite passed 64 tests, including real encoded frame-count verification. Behind-speaker segmentation, a full real cutout workflow, every-frame visual comparison, and complete five-option coverage are not acceptance-verified by these checks.
