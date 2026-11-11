# Optional weekly YouTube refresh

Owner scope: V8 only; 1–4 weeks; title, description and its hashtags; optional
weekly thumbnails. Weekly edits use the existing Local Publisher Chrome
connector and YouTube Studio, with no new YouTube API calls or OAuth permissions.
The existing API upload and browser scheduling/recovery paths remain available.

## Owner workflow

1. Prepare a YouTube Long video or finished Gaming Highlights. Shorts/Reels are
   excluded. A saved, already-posted Long preparation may also generate a plan.
2. Open **SEO & thumbnail review → Weekly YouTube refresh**. Choose 1, 2, 3 or
   4 weeks, then **Generate weekly packages · V8**. This does not enable changes.
3. Review/edit each title and description. Hashtags are included in the description.
   Weekly search-tag replacement is not part of this browser operation.
4. Optionally select **Also change the thumbnail each week**. Each week requires
   its own finished local image path. Per-week thumbnail briefs open the existing
   Thumbnail Studio; no image is generated merely by opening a brief.
5. **Enable this N-week browser plan** approves those exact sets for that exact
   preparation and channel. No other Long video automatically inherits the plan.
   There can be only one enabled plan for a preparation/remote video.
6. For a new upload the plan waits for its existing, verified public receipt.
   For an already verified public video, its first weekly window begins when the
   supported Chrome connector binds the approved plan. Week1 is the first set;
   later sets are due seven days after the previous set is actually saved and
   verified. An offline delay extends the plan; it does not consume a set.
   One week means one set, not a second replacement after the end of that week.
   The final set stays in place.
7. Keep Storylens, Chrome, the extension and the logged-in Studio session running.
   Use **Pause future weekly changes** at any time. A Save already submitted may
   finish; the worker stops before its next browser action when it sees the stop.

The UI shows each saved date and receipt state. An overdue set waits until the
laptop, Storylens, Chrome, internet and Studio are ready, then runs automatically.
Later sets shift to seven days after its successful Save/readback. Multiple
missed sets are not rapidly applied together. A Google identity challenge waits
for the owner to finish sign-in. Saved manual title/description changes do not
pause the plan: the next approved set replaces them. Unsaved Studio edits wait
until the owner saves or discards them, without cancelling later weeks.

Windows task **Storylens Weekly Resume** runs30seconds after this user's login,
with limited interactive-user privileges. It checks for an enabled actionable
weekly plan before doing anything; no plan means no app/browser startup. For an
enabled plan it starts the same saved Storylens command if its service is absent,
then the installed Chrome Default profile if disconnected. Internet readiness is
handled by the existing connector. Sleep/resume uses that connector's normal
heartbeat; this cannot run while Windows is shut down or before user login.
The launcher does not start inference, enable a plan, retry an upload, or change
account credentials. Startup config: `work/weekly-startup-config.json`.

## V8 planning and SEO limits

`storylens-publishing:14b-v8-candidate` is selected explicitly for discovery and
weekly planning. V14 is not used and global model configuration is not changed.
The model receives the actual transcript/source excerpts, complete creator
profile and saved writing preferences. The four roles are search, comparison,
cause and takeaway, with no invented facts to fill a role. Public copy must not
contain planner labels such as “Week1”. An independent local factual critique
checks the proposed claims before the plan is offered.
Each weekly angle selects an ID from exact spoken excerpts prepared by the
executor. The model does not retype the evidence. A separate guard rejects the
observed mistake of turning roster continuity into unsupported player-development
history. These checks support review; they do not guarantee flawless copy.
An identified faulty week receives one focused V8 correction and full validation
again, instead of automatically regenerating all four packages. An unresolved
failure keeps the baseline and cannot be enabled as an approved plan.

This is a sequential refresh plan, not a controlled A/B test or a promise of
fresh recommendation traffic. YouTube explains that title/thumbnail changes
can affect viewers' responses; the change itself does not force redistribution.
Do not replace a successful package merely because a calendar changed if the
owner prefers to keep it. Use the pause control.
Source: https://support.google.com/youtube/answer/141805?hl=en

No search volumes, CTR, impressions or watch-time figures are invented. This
implementation records execution/readback receipts, not YouTube Analytics or a
claimed statistical winner between weeks.

## Execution and recovery

- Plans live in `cache/publisher/weekly-seo.sqlite3`, separately from upload jobs.
- The existing Chrome claim heartbeat binds enabled plans to exactly one published
  Long receipt with matching source hash, preparation, account and profile.
  A cancelled source/upload remains cancelled. It never re-uploads deleted content.
- Fixed `youtube_weekly_metadata` tasks use Local Publisher0.4.38. Older extensions
  cannot claim them; the plan waits for the extension update. No new optional host
  permissions, general browser scripts, selectors from an LLM or OAuth scopes
  are added.
- The executor reuses the existing Studio tab/channel switcher. It checks the exact
  channel ID, exact video details URL and Public visibility. It never opens a
  visibility dialog or clicks Schedule/Publish for weekly refreshes.
- Saved manual copy is accepted as the current starting text. The exact desired
  next set still must match before Save and after reload. An owner edit does not
  cancel future weeks. Unsaved edits defer only this attempt; cleanup can discard
  only fields the worker actually began editing. Exact channel/video checks and
  explicit Pause remain enforced.
- A thumbnail is normalized to a bounded JPEG using the existing thumbnail helper;
  each approved plan receives private image copies, and their frozen file
  identities are checked before the browser selects them or saves.
- Save is preceded by an exact entered-text check and durable submission boundary.
  The worker waits for Save to settle, reloads Studio, and checks the exact saved
  text, video, channel, Public visibility and disabled Save control. A trusted
  extension receipt records these checks; local queue insertion is not success.
- Pre-submit cleanup can discard only fields matching the worker's own expected or
  desired values. It does not discard unrecognized manual edits. Uncertain Saves
  require review and are never automatically replayed as a new video upload.
- Readiness/network failures before submission return to the queue with a60second
  retry delay. Restarted pre-Save work resumes the same task. A submitted/uncertain
  Save cannot enter that automatic retry path.

Thumbnail confirmation currently means the approved file was selected, its preview
loaded, and the saved uploaded-thumbnail control was present after reload.
Independent pixel matching against YouTube's recompressed CDN image is **not**
implemented. Do not label that as pixel-exact or visual acceptance.

## Validation evidence and limits

Evidence is under `output/publishing-discovery-20261031`.

The base workflow was exercised in the real isolated Storylens application with
the owner's existing47.87second cricket clip, normal local transcription and V8.
Title/description/tag application, save/reopen, thumbnail handoff, exact image
binding and invalid-image recovery were checked without publishing.

The four-set plan uses real V8 inference in that same isolated application.
Its first output repeated one angle and leaked week labels into public copy;
that result was not accepted as the final planner quality. Corrective schema,
source-supported angle guidance and public-label normalization were added.
The status file records the latest run and acceptance separately.

Read-only inspection of the existing Studio video `etl0AHXMsfM` on31October2026
confirmed the actual title/description controls, hidden JPEG/PNG thumbnail input,
visibility component and disabled Save control. Nothing was edited, uploaded,
scheduled or saved there. No live public metadata replacement is authorized by
that read-only inspection. Browser DOM/worker tests and simulated calendar tests
are supporting evidence, not a real28day or platform-write acceptance test.

The latest resume-policy suite passed188Python checks and72JavaScript checks. Two
older fixtures were brought into line with the existing40K/root policy and
already-existing schedule payload fields; production context budgets and
schedule wire payloads were not changed to make these tests pass.

Resume-policy follow-up: the actual Windows scheduled task was registered and
run successfully (LastTaskResult0). With no enabled plan it opened no apps.
Offline dates, delayed-success spacing, saved manual edits, unsaved-work deferral,
stale pre-Save leases and refusal to replay uncertain Saves have scoped regression
coverage. An actual shutdown/login and live YouTube overwrite are not verified.
Current deployment state is recorded separately in `resume-policy-status.json`.
