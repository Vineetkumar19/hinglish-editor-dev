# Your cricket documentary editing memory

This upgrade stores observations from your finished documentaries and supplies them to the Cricket profile when it plans future edits. It adds a personal motion style named **Your Cricket Documentary**. General and Gaming keep their existing defaults.

The reference originals remain in `A:\after effects\documentry edit\final videos\final videos`. The analysis uses small images, audio derivatives and frame measurements in `output/reference-analysis/cricket-documentaries`. It never moves or changes the originals.

The completed visual review covers seven exports: Punjab/Kings XI (`a.mp4`), CSK, DC, KKR, MI, MI 2020, and RCB. Together they contain 83.85 minutes and approximately 41.11 GB of source media. All 301,866 native frames were measured; every saved one-second timeline page was visually inspected. There are 118 recorded chapter spans, with selected 50ms animation contact sheets. This does not claim individual semantic inspection of all 301,866 frames.

## What your editing style does

Photographs carry the story. Captions support it; they do not replace the pictures. Your strongest recurring compositions have one main photograph, smaller supporting cards at different sizes and depths, and a camera that travels between them. Card edges, texture, focus and light help the viewer understand which picture matters.

Your long videos alternate graphic passages with the narrator. A historical table, a player introduction and an emotional team montage should not all use the same composition. Readable source tables are often held longer than a transitional photograph.

Within a sustained chapter, photo compositions commonly change after roughly 3–6 seconds; readable table holds often last 4–7 seconds. Some narrator bridges last 15–30 seconds. These are observations to guide the planner, not a fixed rhythm applied to every sentence. Your CSK and RCB examples also use filmstrip walls, rounded photo journeys, torn-paper player dossiers and antique desk scenes. Those richer rigs are preserved as reference ideas; the seven implemented archive variants below do not reproduce all their props and masks.

The saved chapter looks include:

| Look | Visible approach | Appropriate use |
|---|---|---|
| Slate photo wall | Full-colour angled photographs, overlapping planes, soft foreground focus and continuous camera movement | Opening team montage; a major story point |
| Sepia archive board | Brown photographs, paper/handwriting texture, warm light, large focal image and smaller evidence cards | Historical season chapters |
| White ink montage | Organic image edges on pale paper; large masked background photograph and smaller bordered cards | Player story; emotional bridge |
| Dark map collage | Navy background, map-like decorative texture, rough white photo borders and paper label strips | Team comparison; documentary journey |
| Glass photo wall | Blue photographic reflections, clear image panels, translucent planes and moving prism light | Modern season or achievement montage |
| Physical album | Aged pages, dark photograph corners, perspective and a page-turn gesture | Opening history or nostalgia chapter |
| Dark photo board | Near-black atmosphere, subdued background portrait, thin warm frames and coloured foreground photos | Dramatic or troubled team chapter |

These are reusable adaptations. The renderer does not reconstruct the original editable After Effects project, its exact fonts, masks, camera rigs or every keyframe from a flattened MP4. The reference report records actual coverage and timestamp observations, including looks that remain richer in the source than in the implemented template.

## How the upgrade is connected

`library/creator-profiles/cricket-documentary.json` holds the persistent editing memory. It includes source references, chapter looks and instructions on visual hierarchy, camera movement and historical accuracy. Future Cricket jobs load that file as part of their planning context; it also affects the context used by the local model cache.

`library/motion-styles/card_cricket_documentary_user.json` defines the visible style choice. A Cricket motion request through the assistant uses this choice when the request does not already specify a different motion style. It does not override an explicit choice.

The new `archive_board` scene supports slate, sepia, ink, map, glass, album and night looks, plus colour or monochrome treatment. Those options are exposed to the Cricket planner. The normal General/Gaming planning schema does not gain that scene or the historical-player fields.

The renderer now separates the background look from the photo composition. Independent builders handle travelling road timelines, horizontal or vertical film reels, centred image succession, orbital journeys, printed photo sheets, a symmetric evidence fan, three equal hinged glass panels, and turning album pages. The former shared three-card position matrix has been removed. `archive_composition` is saved in scene data and exposed as a Photo movement choice on the review page, so an explicit timeline layout remains a timeline when the palette variant changes. Spoken-name entry times still take precedence over animation speed.

The current comparison is `output/reference-analysis/cricket-documentaries/motion-stories/report.html`: a one-minute video containing five twelve-second scenes at 1280×720 and 60fps. It uses the same three reference panels throughout so the motion can be judged directly. The road timeline advances rightward through different photo depths, the film strip uses aligned frame windows, the centred projection replaces one image with another, the glass panels open on hinges, and the album carries photographs on turning pages. Earlier previews remain available for comparison.

The latest user correction rejects flat grey stages. Each look now has its own background family: dark photographic projection, a tactical field overlay, ivory paper with halftone, a warm archive desk, blue photographic glass reflections, a walnut album desk, or floodlit ghost portraits. Large faint copies of the real source images move against the foreground camera. Supporting overlays are decorative; field lines are not a real map, and lined paper does not fabricate news articles or scorecards. Foreground frames adapt to source image proportions. Every image copy stays hidden until that asset’s entry cue.

Saving editing memory is not training model weights. It gives the model specific, reusable references and rules when it plans a job. Further examples can extend that memory, while corrections can change a preference without retraining a large model.

## Player, season and match accuracy

Player identity, the season and the specific match are separate checks. A recognisable photograph of Rohit Sharma does not establish that it shows Mumbai Indians in 2020, or the 2020 final.

The planner passes an asset request with the player's name and a historical context containing year, team and, when supplied, match ID. Year validation follows the narration chapter: an explicit season can carry into the next passage, a new year changes that context, and a comparison between several years suspends automatic inheritance. A year mentioned elsewhere in a long script cannot validate the current scene. Common spoken Hindi/English year forms are supported; an unrecognised or ambiguous date stays unresolved.

For a historical person image, Motion Graphics searches the reviewed local archive registry before its ordinary portrait search. A matching record requires:

- The correct canonical player name or a curated, unambiguous alias.
- The requested year; matching team and match ID when those are specified.
- An image file within `library/cricket-assets`.
- A source evidence URL and explicit verification/approval records.
- A recorded ownership/licence basis for using that image.

The registry's `verified` flag records editorial verification. The software checks that the declared metadata matches the request; it does not independently prove a photograph's match date from pixels or from the mere existence of a URL.

If the record is missing, the job reports **Historical player image needs review**. It does not silently substitute a contemporary Wikipedia portrait or fabricate a player likeness. The archive registry starts empty: this upgrade supplies the selection/checking mechanism, not a complete licensed image collection covering every cricketer and season.

See `library/cricket-assets/README.md` for the registry format. A match-specific request cannot use an image tagged only with a year. Verified season portraits can serve a season-level request, but do not become proof of a particular match.

## Appearing on the spoken name

For a video input, the production pipeline uses its aligned spoken words. A single-player scene can begin when the name is spoken. A scene with several players stores a separate entry time for each image, so the later player is not displayed before that name is mentioned. Animation speed changes do not shift those assigned source times.

Script-only jobs do not have recorded speech or exact name timestamps. They retain estimated script timing. Unresolved names or unaligned words do not receive an invented exact timestamp. The reference-analysis ASR transcript is also fallible and is not a verified factual source.

## Reading the analysis report

Open `output/reference-analysis/cricket-documentaries/report.html`. Each video has separate coverage and review notes:

- **Native scan:** every decoded frame measured after reducing it to 256×144. This identifies changes and preserves source timestamps; it is not semantic recognition of every frame.
- **Every-second pages:** a saved picture from each source second, used for visual review of composition and chapter changes.
- **Animation details:** selected windows retain native-rate small frames; their contact sheets show 50ms steps at 60fps.
- **Speech:** local transcription with timestamps. Names, numbers and interpretation still need review.
- **Review notes:** the pages/windows actually inspected and the resulting observations.

The seven exports run at 60fps, so their original frames are approximately 16.67ms apart. There is no additional source image every 0.1ms to inspect. Fine timing study uses those real frames rather than inventing intermediate frames.

## Validation

The tests exercise historical year/team/match selection, ambiguous aliases, missing evidence, chapter changes, separate spoken-name entry times, personal-memory isolation, and real rendered chapter variants. An existing Motion Graphics test also builds a full script video, checks its output and rebuilds one scene, to catch regressions in the normal editor pipeline.

The documentary checks include a rendered check of both sequences for every look, motion between sampled frames, and later-player visibility gates. The 63 existing checks in the broader Motion Graphics, niche, assistant and creator-memory run also passed during the earlier upgrade. An initial Unicode digit error in three documentary checks was corrected before the final documentary run. The checks include preserving historical restrictions when a saved Cricket project is reopened with General selected, and reporting a missing player even when enough other images exist to fill a board.

All seven automatic speech passes are complete. DC's saved transcript contains segment timing without a word-level receipt; it must not be treated as exact spoken-name alignment. These analysis transcripts do not replace the production editor's alignment stage.

The rendered style study in the analysis report is a local demonstration of the new layouts. Its extracted reference panels are labelled as study material; they are not automatically certified as new historical-match assets.

The motion-layout regression checks compare visible photo geometry without background colours, verify that reel windows stay aligned while travelling, and verify that the road camera carries old photos out and new ones into view. These are structural checks; artistic quality is assessed by visually reviewing the rendered motion samples.
