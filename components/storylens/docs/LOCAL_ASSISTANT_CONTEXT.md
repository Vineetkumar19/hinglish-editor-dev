# Local assistant context and execution

The active chat supplies at most five user exchanges. Each exchange includes its
user message and last assistant reply, capped at 600 characters each. The latest
request is also passed separately in full. Archived prose is not searched during
planning. Reopening another chat switches to that chat's context; older history
remains available in the history UI.

Current files, campaign IDs, selected clips, release times and verified receipts
are separate structured task state. They survive the conversation window.
Editing-source and planning-campaign catalogs are restricted to the active chat.
Configured channels, explicit creator preferences and cricket vocabulary remain
application settings, not retrieved conversations.

The local 14B model remains selected. Routine structured inference defaults to
non-thinking mode; features can explicitly request reasoning when required. The
8,192-token ceiling and GPU handoff before media inference remain in place.
Duplicate history is removed from planner inputs. Context-limit errors get one
bounded retry with compact context instead of becoming repeated HTTP 400 failures.

## Live validation on 20 October 2026

The owner subsequently disabled captions to prioritize extraction and publishing.
`config.workflow.local.json` now sets `content_features.burn_in_captions` and
`instagram_captions` to false and `publishing_copy` to `minimal`. Automatic Shorts
workflows enforce that choice even if a model returns captions=true. The completed
clip's locally selected title supplies minimal YouTube metadata; no separate
caption, hashtag, or description-writing pass is required. Instagram may be posted
with an empty caption, verified against its account, permalink, absent caption and
publication time. Existing prepared uploads are not retroactively re-rendered.

The MI regression run is observed in `output/diagnostics/live-mi-caption-free-observation.json`.
It has one extract-and-upload chat command. Optional writing cannot block its
handoff. A separate Instagram inbox exposed a tab-selection bug; version 0.4.13
selects the destination profile and leaves unrelated inbox tabs alone. The durable
supervisor may retry known browser failures only when the saved record proves
Share has not started, up to three attempts. Uncertain submissions are preserved.

The caption-free MI run subsequently completed through the same saved browser
job `b8d76941da6b4eda`: https://www.instagram.com/fantasy_legends91/reel/DeuPsqzKfJ4/.
The live post was observed on the target account without an Instagram caption.
Its rendered project records captions=false. It took three automatic recovery
attempts and used extension 0.4.13; this was not an uninterrupted first-attempt
pass. The greyed-out per-site switches were not changed. Chrome showed its main
automatic-access switch enabled, and publication succeeded without changing it.
Version 0.4.14 additionally waits for a new tab to finish navigating before
reattaching its adapter, distinguishes missing host access, and reports the
checked origin/tab for injection errors. This version was reloaded through the
native computer controls; it was not the version that performed this publication.

The next DC request exposed another profile-layout assumption: Instagram showed
the exact destination profile and grid without an Edit Profile control. Version
0.4.15 verifies the signed-in navigation avatar separately from profile content,
then checks the requested route, main handle heading and loaded post grid. Viewing
another account's public profile cannot satisfy the signed-in identity check.
The explicit request "no captions, just add title" now retains disabled subtitles
and uses the locally selected clip title as the sole Instagram post text. Safe
pre-Share metadata correction retains the original upload job. Changing text after
Share cannot create a second upload. A known pre-Share profile failure can resume
automatically once the corrected adapter version is connected.

## Live account-switch investigation after 0.4.15

The owner requires real application scenarios with the editor visible; isolated
checks alone are not acceptance. This instruction is saved in root AGENTS.md.
The live check in chat 9f54a7dad5dd409a used normal Storylens chat commands to
switch to @fantasy_legends91 without uploading. It exposed overlapping routing
with old publishing context, ambiguous sidebar/bio More controls, and a minimized
Instagram app window. Those paths were repaired in the account-check contract
and the local extension. Native account-switch controls are now measured after
one debugger attachment, retained across the complete switch sequence.

The live browser also logged missing Polaris modules and unauthorized logged-out
queries. One guarded pre-composer refresh was added for an unresponsive switch
menu. Restoring the minimized Instagram app then exposed a remembered-login
"Continue as vineet_editz19" dialog. Human sign-in is required before further
live validation. Screenshot: output/diagnostics/instagram-live-signin-required.png.
No new KKR extraction/upload has been started during this investigation, and the
full fresh-prompt acceptance run remains incomplete. 0.4.22 adds explicit
recognition of that login dialog; it still needs activation/live validation.

- Storylens selected clip 2 from the DC batch and the Fantasy Legends destination.
- Its extension switched the account, selected the saved video, entered the saved
  locally generated caption, and submitted the Reel.
- A page disconnect interrupted receipt recording. The repaired read-only recovery
  opened the exact-caption Reel and verified its account and posting time, without
  uploading again.
- Verified URL: https://www.instagram.com/fantasy_legends91/reel/DeuHPqSKosA/
- The local model subsequently reported that verified receipt correctly.
- A later status request used 10,545 input JSON bytes versus 20,685 in an earlier
  request: a 49% smaller payload. These were different requests in the same chat;
  this is not a controlled speed or VRAM benchmark.
- YouTube was check-only because its upload quota was reached.

Detailed evidence is in `output/diagnostics/local-assistant-optimization.json`.
The live repair involved retries. It does not establish that every editing task,
caption, or future unattended scheduled release is failure-free.
