# Your Cricket and Gaming upgrade

This is an optional personal layer on the existing editor. General remains the default for a new browser and for requests that do not specify a profile. General retains its existing editing behaviour, publishing account names, folders, prompts and creator memory. Your browser remembers the profile you explicitly select.

## Start here

Open the editor and choose **General**, **Cricket** or **Gaming** in **Optional creator profiles**. The selected profile applies to new chat requests and detailed tool runs. Finish the current edit before switching profiles.

Attach your videos in the right-side chat, then describe the result. You can still use **Show tools** and all the original controls. The two extra tools, **Gaming Highlights** and **YouTube Thumbnails**, appear for a personal profile. No large model is loaded merely by choosing a profile.

Open **My channel preferences & references**, write what this channel should prefer or avoid, and choose **Save this channel's preferences**. Cricket and Gaming keep separate notes. The five creator links you supplied are retained as references. The briefs reflect your description of the editing you want; the app has not analysed or copied those creators' videos.

## What changes for each existing feature

| Feature | Cricket / Gaming enhancement |
| --- | --- |
| Smart Clean | Same silence, pause and audio cleaning controls. Domain selection does not rewrite its deterministic cleaning algorithm. |
| Script Edit | Same meaning matching, retake selection and editable timeline. Chat interprets your domain request; its semantic matching engine remains unchanged. Supply a script/outline when arranging many recorded parts. |
| Auto Captions | All existing typography styles remain available. Personal spelling feedback is stored separately per profile. Spoken Hinglish remains Hinglish; English publishing copy does not translate your speech. |
| B-roll | The local planning model receives the profile's story, pacing and preferences when selecting supporting footage. Existing provider keys and rights review still apply. |
| Smart Visuals | Profile context guides entity and visual choices. Supplied evidence supports cricket names and facts. Retrieved assets still need identity and rights checks. |
| Smart Zoom | Model decisions receive the profile brief. Gaming prefers selective impact emphasis and full HUD visibility; the existing zoom/crop controls remain available. |
| Sound Design | Its model receives documentary/reaction or gaming guidance. Existing sound libraries, mixing and ducking remain in use. |
| Eye Contact | Existing hardware requirements and processing remain unchanged. |
| Long to Shorts | Cricket/gaming briefs guide the shared local planner. Gaming bundle requests extract Shorts from the original stream and default to template framing to avoid a face-only crop of gameplay. Requested counts are targets, not a guarantee of that many strong moments. |
| AI Images | Planning receives the domain brief for cricket/gaming scenes. Generating pixels still requires the configured RTX image model. |
| AI Video | Planning receives the same domain brief; the existing model setup and memory requirements remain. |
| Motion Graphics | Model planning receives the domain context. Cricket scoreboards/comparisons must use supplied or retrieved evidence; the profile does not invent statistics. |
| Publishing | Each personal profile has its own YouTube and Instagram connection, folders, schedule, queue identity and writing memory. Titles, descriptions, captions and hashtags remain English. |

Shared model context is included in inference cache keys and passed explicitly to each job. This prevents a cached General response being reused as a Cricket response, or the selected profile changing midway through a queued job. General model calls receive their original prompt and payload unchanged.

## Cricket: documentaries, reactions and current news

Example requests after choosing Cricket:

- `Clean these clips, combine them, and add captions using Typography 4.`
- `Add cinematic motion graphics and restrained sound design for this cricket documentary. Use only the statistics I supplied.`
- `Create three cricket thumbnail options. Story: Mumbai Indians' rise, setbacks and team identity. Avoid claims about a recent match.`

For a current match, open preferences and enter the **teams, tournament and match date** as the research topic. Add up to five public HTTPS article or scorecard links. Choose **Save & refresh sources**. The receipt displays retrieval time, source links, warnings and any returned match IDs.

Supported source domains include ICC, BCCI, IPL, ESPNcricinfo, Cricbuzz, national cricket boards including Japan, Olympics and Wikipedia. Not every website is readable: some block automated requests, and some pages primarily return navigation text. The app reports unreadable sources instead of treating them as evidence.

Optional provider setup:

1. Obtain a Brave Search API key from the official provider and set the environment variable `BRAVE_SEARCH_API_KEY` in the environment used to launch the editor.
2. Obtain a CricketData key and set `CRICKETDATA_API_KEY` for its third-party cricket feed.
3. Restart the editor so it inherits these variables. Do not put keys in chat or channel notes.

Without keys, supplied readable source links still work. Without keys or sources, the app explicitly reports missing current evidence. It cannot guarantee knowledge of every domestic or associate player.

The score feed first returns candidate matches. **Select an exact CricketData match ID, save it, and refresh again** to include that match's scores in model context. Candidate scores are not sent as though a match was already selected. A response with a different ID is rejected. Changing the topic or match ID removes the previous receipt from usable context.

Current research expires after 30 minutes for inference. The chat refreshes a configured Cricket topic before planning a new request. Retrieval time is not a claim that an article was published then, and search snippets are unverified leads. Confirm teams, match date, scorecard and conflicting claims before publishing. Feed coverage and delays depend on the provider. This is retrieval with evidence, not an always-current trained cricket model.

Provider documentation: [Brave Search](https://api-dashboard.search.brave.com/app/documentation/web-search/get-started) and [CricketData](https://cricketdata.org/live-cricket-score-api/).

## Gaming: stream to highlights and daily Shorts

Choose Gaming, attach your downloaded stream, and press **Highlights + 12 Shorts**, or send:

`Make 12 Shorts from my gaming stream, then create a 15-minute gaming highlights compilation.`

The bundle makes Shorts first, then independently builds the highlights compilation from the original stream. It does not use the extracted Shorts as the source for the long highlights edit. A later publishing request reuses those prepared Shorts rather than generating duplicates from the shortened highlights video.

**15-minute highlights** runs just the compilation. The detailed control lets you choose a target of 1â€“30 minutes and enable or disable approved meme inserts. A target of 10â€“15 minutes suits your requested format.

How selection works:

1. Reuse or create a chunked transcript of the stream.
2. Scan audio in small windows and low-resolution frames for additional cues. These scans stream through the media rather than decoding hours of video into one large array.
3. Ask the local model for complete setup/payoff moments within bounded transcript sections. Prioritise funny reactions, clutch wins, unexpected failures, drama and surprising gameplay. Skip waiting, menus, repetition, sponsor reads and donations.
4. Validate timestamps and line IDs; reject invalid, overlapping and low-scoring selections. Take strong moments within the duration budget and return them in source order.
5. Render a 1280Ã—720 MP4 with stereo audio and an editable XML timeline. Preserve the full gameplay frame with padding when needed. The report records original timestamps and selection reasons.

The compilation may be shorter than requested when insufficient strong moments are found. The current selector is transcript-led with simple audio/visual signals; it is not a semantic vision system that understands every silent gameplay event. A complete 4â€“5-hour gaming recording has not yet been benchmarked on this laptop. You should review the first full run and adjust preferences or supply timestamp notes.

Outputs are under `output/gaming/<run>/`: `GAMING_HIGHLIGHTS.mp4`, `GAMING_SEQUENCE.xml`, `gaming-project.json` and `report.html`. Shorts use the existing `output/shorts` reports. Additional requests can apply the existing captions, sound and zoom tools to the completed compilation.

### Your approved meme library

Place owned or licensed clips in `library/creator-memes` and register them in `manifest.json`. A clip needs `approved: true`, `rights: "owned"` or `"licensed"`, and tags such as `funny`, `clutch`, `dramatic` or `surprise`. See the README in that folder for a complete example.

The initial library is empty. The editor does not assume that reference creators' or Instagram clips are licensed. Inserts are selective, up to six brief inserts, each at most 1.5 seconds. Files outside this library and unapproved entries are rejected. Existing Sound Design remains available for effects; no new meme-scraping service was added.

## Cricket and gaming thumbnails

Choose **Create thumbnail options** and describe the actual story. Attach an optional PNG/JPG portrait first, then an optional background image second. A transparent PNG cutout works best; the supplied portrait is composited as provided, without automatic background removal.

The local text model proposes three short English hooks and text-free scene prompts. The renderer places readable typography on three 1280Ã—720 PNGs. Inspect hook accuracy, the creator/player identity and the composition before using one.

- **CPU mode:** use your supplied background/portrait or a styled solid background. It creates text concepts and layouts; it does not generate an AI illustration.
- **Generate AI backgrounds:** enable this in the detailed YouTube Thumbnails control after completing the existing RTX AI Images setup. The image model creates three backgrounds; text and your supplied portrait are then added separately for readability and identity control.

Output: `output/thumbnails/<run>/thumbnail-1.png` through `thumbnail-3.png`, `thumbnail-project.json` and a review page. Generated faces and kit logos can be inaccurate; use supplied licensed portraits for exact identities. This upgrade does not train a likeness model.

## Two channels and two Instagram accounts

Select Cricket or Gaming **before** opening its Publishing Studio. Connect that profile's YouTube channel and Instagram account there. Accounts never silently fall back to General or the other profile. Confirm the displayed account before authorization.

Default folders:

| Profile | Long videos | Shorts for both platforms | Matching YouTube thumbnails |
| --- | --- | --- | --- |
| General | `publishing/long-youtube` | `publishing/shorts-both` | `publishing/thumbnails-youtube` |
| Cricket | `publishing/cricket/long-youtube` | `publishing/cricket/shorts-both` | `publishing/cricket/thumbnails-youtube` |
| Gaming | `publishing/gaming/long-youtube` | `publishing/gaming/shorts-both` | `publishing/gaming/thumbnails-youtube` |

Use the same basename for a video and thumbnail, such as `Mumbai Indians Journey.mp4` and `Mumbai Indians Journey.png`. Use **Save & create folders** to create the selected profile's folders. Each profile can choose its own root folder and settings.

Daily Shorts/Reels default to **19:00 India time**. The same Short is reserved at the same time on YouTube and Instagram; the next Short takes the next day's slot. Cricket and Gaming have independent daily slots. Long-form videos do not consume a daily Short slot.

The chat prepares editable English drafts. Review copy, account, schedule, audience and synthetic-media declarations, then explicitly authorize the chosen posts. Enable publishing separately in each profile after setup. The laptop and editor must remain awake/running for pending uploads; this is not a cloud scheduler. An ambiguous upload result stops automatic retries to avoid duplicate posts. Pausing a profile prevents new publishing work for it, but cannot cancel an upload already scheduled at the platform.

All profiles start paused. Real publication still requires valid connected accounts, YouTube's applicable API setup/audit requirements, and Instagram's supported professional-account/media-hosting setup. These requirements are explained in the existing publishing guide. No public upload was performed during this upgrade.

## Learning from your corrections

Two kinds of personal memory are available:

- The profile notes guide editing taste: pacing, comedy, sound, factual caution, thumbnail style and examples.
- Publishing Studio's **Want / Avoid / Rejected / Approved** feedback and **Remember my changes** store writing examples separately for Cricket and Gaming. The existing publishing model uses these for later drafts.

This is persistent preference memory and retrieval, **not weight fine-tuning or a self-modifying model**. It does not automatically learn from views, retention or every unsaved edit. Save explicit corrections. All publishing copy remains English regardless of channel preferences. Caption spelling feedback remains scoped to the selected profile; it does not translate speech.

A future weight-training step would require enough approved/rejected examples, an evaluation set and a model-specific training plan. Your existing app should continue to work while that data is collected.

## Hardware and verification

Jobs use the existing work queue and run heavy editing/model work sequentially. No four-hour demonstration is started merely to show the controls. CPU thumbnail layouts and ordinary video exports work without image diffusion. AI Images, AI Video, optional AI thumbnail backgrounds and Eye Contact still require their existing compatible hardware/model setup.

Validation for this upgrade includes:

- General prompt compatibility, profile/context isolation and original-source routing for gaming bundles and publishing follow-ups.
- Protected HTTP routes, separate folders/settings/accounts/preferences and independent daily slots.
- Stale/mismatched scorecard rejection, URL restrictions and explicit missing-source warnings.
- Invalid highlight timestamps, overlap/budget checks and approved meme path checks.
- An actual short FFmpeg export verifying 1280Ã—720 output, stereo audio and editable XML.
- Three actual local-Qwen Cricket thumbnail concept layouts. This CPU demo used no supplied portrait and no diffusion model.
- Live browser verification of profile controls and Publishing Studio.

The checks do not prove editorial quality on your first full gaming stream, comprehensive cricket coverage, RTX diffusion quality or successful account publication. Those require your real footage, source/provider setup, connected accounts and compatible laptop.
