# Talking-head B-roll

Current owner resource priority (23 October 2026): captions first, B-roll second.
The owner explicitly permits stopping the current Smart Visuals test, while
caption work must remain running. Do not terminate shared model services or
caption app servers to make B-roll proceed.

Owner requirements (23 October 2026): understand the actual speech, choose
relevant cutaways, and place them on the matching spoken lines. Latest correction:
VIDEOS ONLY, including named subjects. This supersedes the original image-fallback
permission. A missing relevant video leaves an empty moment; never fill a quota
with unrelated material. Read surrounding speech and negation before retrieval
and again during actual-frame verification. Skip filler/reaction shots and
vocabulary lessons for idiomatic speech.

Owner correction: the E7 test needs approximately four to five relevant video
cutaways across its narration. One three-second cutaway is too sparse. Use high
density for this requested preview and cover the distinct nightlife/street/
bar/club/cafe points without contradicting their negative context.

Later clarification from the owner: **show the mentioned venues**. Normal
bar/club/cafe footage may illustrate those concepts even when the narration
says they are unavailable locally. The earlier empty/closed-only interpretation
was too restrictive for these venue references. This is illustrative stock,
not a claim to show an actual establishment in the speaker's city. Keep exact
named identities correct and physical details (such as shut shutters) suitable.

Sentence analysis first joins adjacent ASR fragments into complete English
thoughts. Source ids remain attached, so a dangling "late-night cafe" followed
by "bhool jao" cannot become an affirmative cafe scene. The complete thought,
original surrounding speech and exact cutaway words travel to the pixel checker.
Preserve narration and keep cutaways separately editable in Premiere Pro.

## Sources and selection

- Creator footage folders, Pexels and Pixabay remain available.
- Commons provides videos without a key. Image candidates are rejected during
  retrieval, ranking, downloading, rebuilding and rendering, including stale settings.
- Web search includes YouTube and public stock pages. The page reader uses
  advertised VideoObject/OpenGraph/HTML video media; it skips subscription gates
  and does not execute website scripts or bypass blocked pages.
- Web source videos over 30 minutes and archived live streams are skipped in
  this lightweight preview workflow. Bounded downloads use input timeouts, so
  multi-hour ambience loops do not hold the editor queue for a tiny cutaway.
- Source pages, creators and available licence metadata are written to
  `CREDITS.txt` and shown on each selected cutaway. Web discovery alone does not
  establish permission to reuse a file.
- Local embeddings retrieve candidates. A separate local vision-language check
  must approve the actual downloaded frames against the scene, action, spoken
  meaning and picture quality. A high embedding score alone is insufficient.
- Search does not stop just because the first broad query returns a full page.
  Stock providers receive up to four country/scene variants; web and Commons
  receive up to two. Results are deduplicated before visual ranking. A second
  local editorial pass reviews proposed moments before timeline placement.
- The embedding model is unloaded before the visual reasoning model runs.
  The shared GPU queue prevents the two feature chats from exhausting VRAM.
- Scene planning uses the configured Storylens planning model, rather than the
  older meaning-only model. The editorial review enables its bounded reasoning.
- Unreadably dark openings trigger a small visibility scan within that source.
  The selected window is still checked against speech, setting and action. The
  checker sees the final canvas crop so lost subjects cannot pass on wide frames.

## Editable timing

The review page has Start, End and Source trim fields. Save & rebuild validates
timeline bounds, available source frames and neighbouring overlaps, then updates
the XML and small preview. Original narration is not retimed.

Prepared media includes up to three extra seconds at each end where the source
has footage. XML `in/out` values retain that trim range rather than flattening
each file to its visible timeline duration.

The Premiere button prepares a native `.prproj` for a single-source talking-head
timeline: V1 contains the source, A1/A2 retain its audio, and V2 contains separate
editable cutaways. Complex imported XML edits and custom scaling retain their
XML handoff rather than silently losing their existing tracks or effects.
Resolve and CapCut retain their existing handoff paths; native parity is not
claimed for them.

## Audio-only validation

Enable **Audio-only test: keep speech over a black background**. It makes a
small black-picture copy with the source audio; the original is untouched.
The creator footage library is excluded for this test, so existing edited
visuals cannot be recycled and mistaken for a successful internet search.

Authorized test inputs:

- `A:/Full Drive/thisis.vineet/e7/E7 final.mp4`
- Cricket videos in `A:/Full Drive/remove silence/All Shorts`

The first E7 baseline exposed false embedding matches (a vocabulary lesson and
starry sky for a street scene). It is not an accepted result. Strict visual
verification was added after this failure. Record the live retest outcome and
native editor verification separately; unit checks alone are not acceptance.

Live status, 23 October 2026: Pixabay video search responds successfully. Pexels
still rejects the saved key on both video endpoints. Earlier strict E7 runs
produced no approved cutaways; those black previews are incomplete tests, not
accepted output. A fresh Storylens run with expanded query coverage is being
validated. Do not mark this feature complete until its rendered content and
spoken timing have been inspected.

Provider references:
[Commons file metadata](https://www.mediawiki.org/wiki/API:Imageinfo),
[VideoObject metadata](https://schema.org/VideoObject).

## Workflow ownership and recovery

Owner instruction, 23 October 2026: Storylens' local models and tools must do
the work at every step. Read the full speech, plan timed shots, search sources,
rank candidates, inspect downloaded video in its final crop, prepare editable
clips and verify the rendered result. Codex repairs failed code and restarts
the actual Storylens workflow; it must not manually select footage to conceal
a failed local-model workflow. Saving guidance and changing prompts/tools are
not the same as retraining model weights.

The E7 five-shot run `20261023-152317-f48605` approved only two shots and remains
incomplete. It exposed a judge treating whole-edit coverage as a checklist for
each individual shot. Evaluate each timed shot against its own spoken thought;
do not require a highway shot also to show a cafe and club. Broad bar/lounge
queries and bounded venue-metadata backups now reach the mandatory pixel judge.

Live review, 23 October 2026: run `20261023-154616-6e8501` produced four videos
(opening street, nightclub, night highway, bar counter). The actual 33.33-second
Storylens preview was played and the four rendered shots inspected in the side
browser. Timing controls and three editor handoff buttons are visible. This is
a reviewable partial result: four of five requested, with the cafe slot empty.
The synonym-search retry `20261023-154832-726cbd` also produced four of five;
no cafe candidate passed. Do not call either a complete five-shot result or
claim fresh native Premiere validation. Side-browser evidence:
`tmp/broll-four-cutaway-side-preview.png`. Owner acceptance is still pending.

The saved workflow retrieval trigger now recognizes B-roll, brolls, cutaways and
stock footage. Its focused checks pass; live chat retrieval after loading that
change has not yet been tested. Existing caption services were left running.

Owner correction after reviewing that preview: the bar was too early, during
"log so chuke hote hain". That four-shot output is not accepted timing evidence.
Use a sleeping shot for people asleep, closed shutters for closed shops, the
bar only on the lounge/club clause, a cafe on its clause, and real enjoyment
activity on "enjoy karne aa rahe ho" when requested. The local model now groups
continuous word-timed speech into semantic clauses; code maps its boundaries
back to original ASR times and validates ordered full word coverage. Arbitrary
seven-word chunks must not determine a change between distinct actions.
For the audio-only black test only, contiguous clauses may have contiguous
cutaways. Normal talking-head face-time spacing remains unchanged.

## Human choice bank (latest owner direction)

The owner now wants plentiful relevant video choices, not a small final edit.
Discover visual nouns, venues and actions throughout the speech, then search
multiple videos per keyword. Around ten distinct keyword moments in a short
video is a starting point, not a limit of ten downloaded clips. The current
controls allow 1–20 playable choices per keyword and a 200-option run limit.
The person chooses the final clips and lengths in Storylens or their editor.
Keep illustrative bars/clubs/cafes available even when their availability is
negated. Keep sleeping, closed shops and enjoyment anchored to their own words.

Review mode uses the local LLM to select transcript word indices and concise
physical search terms, then checks the downloaded video against that keyword.
It does not require every choice to prove the whole sentence or final mood.
Each playable option retains source provenance and trim handles. Premiere
gets independent media choices; CapCut gets a separate choices section after
the original timeline. Native editor validation must be recorded separately.
The final-scene automatic edit mode retains its stricter contextual checks.

Live choice-bank validation, 23 October 2026: E7 run
`20261023-170346-964082/001-audio-only-source` saved 59 playable options from
46 distinct source videos across 12 timed keywords (five choices per group,
four for cafe). Storylens' real Add B-roll form ran the local models and tools.
The browser review successfully switched the opening suggestion to option 2
and saved/rebuilt the bank. Its 33.33-second audio-over-black preview decoded
and played; the sleeping image was inspected at 13.666 seconds. The sleeping
group starts at 13.3 seconds; lounge/bar is anchored separately at 14.78.
These are human-review candidates, not approval of every final editorial choice.

The actual CapCut preparation button created `Storylens B-roll 1`: one base
cut, 12 suggested overlays, and a separate 59-clip choices track after the
original. Every referenced video asset was present. CapCut and Premiere were
not launched for native playback validation; do not claim that check passed.
The Premiere adapter's independent choices/bin graph has structural tests only.
The cricket source has not yet had its live options-bank test.

Final packaging exposed fractional word timestamps rounding to one extra
timeline frame. New preparations use frame counts; saved-bank rebuild aligns
that one-frame boundary using available handles and retains real over-trim
errors. An unused short alternative no longer prevents editing the selected
cutaway. All 80 focused B-roll/workflow checks pass. Saved-bank recovery and
CapCut preparation were verified in the running Storylens UI after repair.
Evidence: `tmp/broll-options-side-preview.png` and
`tmp/broll-capcut-options-handoff.png`. Caption services were left running.

## Selected-clips handoff (owner follow-up)

Owner approval of the options bank was followed by a request to choose clips
in Storylens and send those selections to Premiere Pro or CapCut at the saved
speech times. These are the requested editors; After Effects was a corrected
misreading and is not part of this feature.

The default handoff now excludes unused alternatives. An optional Include
unused alternatives switch retains the larger separate choices bank. Open
editor when ready enables direct launch without downloading. Unsaved choices
must first use Save & rebuild; that guard preserves the pending selections.
Cutaways remain native independent media clips with source trim handles, so
the person can move, resize, retime, trim or extend within the footage available.
The local LLM/tools perform discovery and preparation. Code, prompts and saved
workflow guidance were improved; no weight fine-tuning was run.

Live validation used `selected-handoff-check/001-audio-only-source`, a separate
copy so the owner's active unsaved choices were not changed or reloaded. In
Storylens, option 3 was chosen for the first group, its timing changed to
2.0–2.6 seconds, and the second cutaway removed. The unsaved-handoff guard was
tested, the copy saved, and both editor preparation buttons exercised with
automatic editor opening off for RAM use. The generated native Premiere
project contained 11 V2 clips, the first at exactly 2.0–2.6 seconds with a
1.0-second source in-point and no unused-option bin entries. The actual CapCut
draft contained one source cut and 11 Selected B-roll clips, the same first
timing and source trim, all assets present, and duration 33.333333 seconds.
All 88 focused B-roll/workflow/editor-handoff checks passed. Native application
playback remains unverified; neither heavy editor was launched. Evidence:
`tmp/broll-selected-premiere-handoff.png` and
`tmp/broll-selected-capcut-handoff.png`.

## Testing another source without reusing its topic

For a new source, discover visual keywords again from that source's speech and
anchor them to its own word timestamps. Previously checked internet videos may
be retrieval leads, but must be checked again against the new keyword. Do not
reuse a previous video's requested venues as the new topic.

Illustrative options searches use the physical subject even when the speech
says it is unavailable: a missing fridge searches for a fridge, and unavailable
Wi-Fi searches for a wireless router. Keep visible physical states such as
closed shops. This repairs search wording; it does not choose an asset or
approve a final edit. The local model still discovers concepts and checks
downloaded footage. The regression and focused suites pass 89 checks.

Owner cap added during E3 review: a new highlighted word/sentence may have at
most five playable video choices (default five, fewer allowed). This is enforced
in the UI, local chat schema, server and worker. It limits choices per group,
not the number of useful keyword groups across a video. Existing saved banks
and pending selections are preserved. Searching more than five candidates is
allowed when necessary to reject unrelated/unavailable sources and find up to
five suitable playable choices.

Live E3 test, 23 October 2026: the actual Storylens Add B-roll form ran the
local models on `A:/Full Drive/thisis.vineet/e3/e3.mp4`, keeping original audio
over black. Run `20261023-181402-d26d15/001-audio-only-source` contains 45
playable choices from 43 distinct source videos across 13 discovered groups;
12 groups have choices, one ambiguous ASR term (`sher`) has none. Every group
has at most five. Room, router, washing machine, fridge, AC, table, laptop,
frustration and bed options were produced by the local pipeline. The browser
played the first room and router options, and the entire 37.466667-second
270x480 audio preview reached its end. The last `Rapidu` group contains two
questionable suggestions (a DJ and a masked performer): do not represent that
group as an accurate named-entity match or this draft as an approved final edit.
The quality report retains short-slot and weaker embedding-match warnings
(89/100); no criteria were weakened to make this test pass. Native editor
playback was not checked for E3, and the owner has not made final selections.

After collection, only the dedicated B-roll server was restarted to load the
new cap. In the running form, requesting six produced the shared plain-language
1-to-5 validation error without launching a footage search; five was restored.
All 90 focused B-roll/workflow/handoff checks pass. Evidence:
`tmp/broll-five-option-cap.png` and `tmp/e3-broll-options-preview.png`.
The owner's earlier E7 review tab and its unsaved selections were preserved.

Owner review UI follow-up: remove visible model explanations beneath option
videos; keep diagnostic/provenance data saved in the project. Use compact
Option 1/2/etc. and rectangular No B-roll controls. Arrange Means, Shows and
Search horizontally with responsive wrapping, and reduce excess vertical
spacing around timing and selected previews. The existing 45-choice E3 report
was regenerated without changing its saved selections or footage. A separate
visible tab shows the compact report because the owner's original E3 tab has
one unsaved selection. Do not reload that original tab to apply the design.
Live checks verified No B-roll and Option 1 selection states, zero visible
choice descriptions, 30-pixel No B-roll and 28-pixel option buttons, and all
three bed metadata labels on one row. Existing 28 option/editability checks
pass. Evidence: `tmp/broll-compact-review-ui.png`.

Latest review-header preference: show only B-roll review, the video name,
playable-video count, keyword-moment count, Save & rebuild, and the three
Premiere Pro / CapCut / DaVinci Resolve buttons above the preview. Remove the
topic/setting prose, default instructions and extra checkboxes from that area.
Preserve the project's black-background choice; default editor handoff sends
saved selections only and opens the chosen editor. Keep errors and unsaved
status when needed. Live E3 validation confirmed three editor buttons, no extra
switches, the clean counts, and the unsaved-selection handoff guard. No native
editor was launched. Existing 28 option/editability checks pass. Evidence:
`tmp/broll-simple-header.png`.

## Cricket-source trial — 23 October 2026

Used the owner's `All Shorts/Shorts 7.mp4` (29.1 seconds, RCB 2009/2016 finals)
through the real Storylens Add B-roll form, local speech/meaning/vision models,
original speech over black, eight keyword groups, maximum five choices/group.
Search repair: preserve full sport/year/action queries instead of replacing
them with a bare identity/year. Bare years and generic actions are not named
identities. Keep actual teams/players strict. Stock cricket queries now include
a broad cricket backup. Generic batting-lineup/final/wicket phrases can use
concrete cricket action search labels while retaining original word times.
Persist retrieval.json diagnostics. Metadata-backed video leads are a bounded
recall aid, never pixel approval.

Detailed diagnostics found relevant RCB/season highlights with strong image
scores; YouTube then blocked downloads with a sign-in/bot check. Do not mistake
that for absent search results or claim low embedding scores caused all missing
matches. Pexels still rejected its saved key. No cookies, bot checks, sign-in
gates or denied pages were bypassed. Public direct-video sources continued.

The trial exposed a local checker contradiction: it described a cricket stadium
but rejected generic relevance. A bounded local-model recheck is allowed only
for a clean real video whose observed description explicitly includes the generic
requested subject, and no separate named identity is required. It never sets
pass automatically. A broader recheck experiment accepted unrelated crowds,
feet/photographer and flags as hypothetical cricket context; that version was
reverted, and its bank `20261023-195825-febe39` is rejected validation evidence,
not an approved deliverable. Keep exact teams strict and require visible cricket
context rather than hypothetical spectator use.

Current deliverable: `20261023-200323-4bb650/001-audio-only-source` has TWO
playable choices across eight discovered groups: a cricket-stadium aerial
(6.08–6.66 seconds) and cricket ball/stumps (14.74–16.88 seconds). Six groups
remain unfilled. Both actual option videos were played to their ends in the
running browser. This is a partial trial, not adequate full coverage or approved
RCB archival footage. The quality report keeps the coverage and short-slot
warnings (89/100); no acceptance threshold was changed to hide those failures.
No native editor was launched. Code/prompt/workflow repairs are not model-weight
fine-tuning. Evidence: `tmp/cricket-broll-trial.png`.

The complete 29.1-second 270x480 browser preview also played to its end. It was
left paused at 15.423 seconds to show the wicket illustration at the saved speech
time. All 97 focused B-roll/workflow/handoff checks pass. This supplementary
verification does not change the partial two-of-eight coverage result.

## Durable B-roll recovery — 24 October 2026

The owner wants dependable local operation without repeated GPT repairs. New
B-roll runs checkpoint their timeline, timed model plan, per-keyword retrieval,
ranked candidates, every accepted option and rejected-candidate diagnostics.
Atomic saves tolerate brief Windows reader/antivirus locks. Repeating the same
unfinished request reuses its output folder and finished checks. Source/settings
changes invalidate incompatible plans; rotating an API key retains useful work.
Broken derived media is checked and rebuilt; creator footage is never deleted.

The B-roll service persists its own jobs and complete creator context across
restart. A stopped worker receives one automatic continuation, never an infinite
restart loop. Exhausted recovery preserves choices and presents the shared
plain-language error with diagnostics separately. Temporary search/download
failures have bounded retries; invalid keys and relevance vetoes do not. Rejected
stock keys are skipped until the credential changes. Local planning calls are
bounded to 300 seconds, video-check calls to 180 seconds. An unavailable source
or model cannot justify accepting an unrelated video. Saved-bank finalization
uses CPU preview work without acquiring the captions GPU lock, loading models or
unloading another feature's models. Ordinary discovery still uses the shared
editing/GPU queue.

Live validation used the normal Storylens Find B-roll button and a separate copy
of the saved local-model cricket bank. A controlled service interruption restored
the queued job; a subsequent actual worker interruption exposed a Windows rename
lock bug. After its repair, job bfb13432ea57 automatically continued on attempt 2
and reached the review UI, retaining both choices and all original speech/trim
times. The original bank stayed unchanged. The recovered 270x480 preview played
in the visible browser. This tests recovery, not a fresh footage search, adequate
cricket coverage, native editor playback or every possible failure. The previous
two-of-eight coverage limitation remains. 107 focused checks pass, including
mid-keyword recovery, bounded retries, changed/invalid credentials, broken media,
Windows save locks and job restoration. Evidence:
output/broll/recovery-evidence/validation.json and tmp/broll-recovery-ready.png.
Saved instructions/code are not model-weight training and cannot guarantee zero
errors. Prior creator guidance and all accepted caption renderers are preserved.


## Contextual relevance and bounded work — 24 October 2026

The fresh E2 trial exposed overbroad object labels, CGI/presenters inside accepted
windows, repeated weak web leads, and a literal natural-geyser match for a
household water heater. Trials 20261024-014111-623265 and
20261024-023028-8d062d are rejected relevance evidence, not approved results.
The latter worker completed automatically once, but semantic failures remained;
code repairs began after its failure was observed while its loaded worker finished.

Review candidates now pass specificity filtering, direct sources precede at most
two web leads, and recent dead links are negatively cached for ten minutes. A
75-second web timeout does not immediately trigger another 75-second download.
Cached footage leads must match their prior pixel observation to the current
subject. Three active-window frames must each show clean relevant filmed footage;
the checker separately approves the contextual word sense. An unavailable local
checker stops with saved progress rather than failing fifteen candidates.

The planner saves an English physical meaning per keyword and keeps concrete
Hinglish household nouns specific. Compound nouns begin at their first spoken
word. Search/embedding/model caches remain normal runtime optimization, not proof
of a fresh Internet download. Native editor playback remains a separate check.
119 focused checks pass; real application acceptance of the latest correction is
still pending. The saved Pexels credential remains rejected; other sources run.
No caption renderer, creator profile or previous instruction was removed.

A further live trial exposed a shared WebSearch counter that was never reset
between B-roll keywords. Later subjects consequently exhausted an allowance
spent by earlier ones. gather_candidates now calls begin_subject(45) for each
shared web client on every keyword. A regression test covers three consecutive
subjects; 120 focused checks pass. Trial 20261024-025250-846df5 was explicitly
stopped for this repair and is not acceptance evidence. Latest live validation
is pending.

Trial 20261024-025754-caeb1f verified independent later-keyword searches and
usable empty-room/wardrobe footage, but exposed unexplained context=false
responses for correctly observed refrigerators and washing machines. It was
rejected/stopped for repair. Canonical physical-object sense is now derived from
the observed exact noun and all three good frame checks; unrelated objects,
CGI, overlays and named-identity failures remain vetoes. Generic concepts retain
the independent context check. 121 focused checks pass. Latest fresh live run
is pending; previous trials remain saved and are not one-go acceptance evidence.
