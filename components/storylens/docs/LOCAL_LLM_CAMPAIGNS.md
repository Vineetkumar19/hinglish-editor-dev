# Local-model Shorts campaigns

The configured Storylens planning model makes the source choice, moment choices,
ranking, editorial rationale, titles and descriptions. Local tools enforce source
folder access, non-overlapping source ranges and the requested duration cap
(below 50 seconds by default; up to a strict below-60-second cap).
Each model input and answer is retained as a decision receipt. No weight training is
claimed or performed by this workflow.

Selection and word refinement receive the probed source duration. Optional
breathing room is capped at the file boundary while selected speech is retained.
Timing stays at full precision through refinement; display rounding must never
push an export beyond EOF. Campaign selection also disallows repeated footage.
`tools/check_campaign_bounds.py` replays the failing KKR decisions without any
new inference or media/publishing execution.

Boundary options support Romanized Hinglish, Hindi and English using punctuation,
pauses and clause-ending cues. No team-name allowlist controls whether a moment
exists. The original local moment stays available, and later planned moments are
reserved during refinement. These cues do not prove editorial completeness: the
local model still selects the interval and the independent review checks it.
The local writing stage owns titles, descriptions and hashtags; a planning reply
asking the user to supply these is sent back to the local model for correction.

The chat routes requests such as “Extract seven cricket Shorts and schedule
one every day on YouTube at 6 p.m.” Give a future start date and, optionally, a
folder inside the authorized source library. It prepares exports, runs local speech
and copy checks, and returns the actual files. It does not claim that local exports
have already been scheduled remotely.

The installed local planning model now interprets the whole campaign request,
including source folder, source topic, destination channels, duration, dates and
whether to avoid previously used sources. Mentioning a gaming destination does
not exclude cricket footage. Conflicting destinations produce a local-model
clarification; its follow-up retains the original folder and plan. Quoted,
cancelled and preview-only requests do not execute. Invalid tool arguments are
returned to the local model for correction, never filled in by Codex.
The planner receives only the current campaign's chronological user instructions.
A new full campaign replaces previous tasks; assistant replies and tentative old
plans are excluded from semantic evidence. Latest user corrections override earlier
values. `tools/check_campaign_dialogue.py` evaluates the recorded three-turn failure
with actual local inference, without submitting a chat or executing media/publishing.
Campaign planning receipts are stored under
`cache/assistant/campaign-decisions-<session>/decision-*.json`.

The public API readiness flag remains false. Campaign chat now presents one batch
review for exact exports, destination, disclosures and dates. After confirmation,
the existing YouTube connection uploads ALL reviewed exports privately first.
Only their returned video IDs are sent to the local Chrome Studio scheduling tool.
The app independently reads back video ID, channel ID, title, description and exact
UTC release time before recording `scheduled`. No remote receipt means no success.

Storylens Local Publisher 0.4.0 adds the optional host `https://studio.youtube.com/*`
and the scripting permission for its fixed Studio adapter. Reload the installed
extension once, then choose **Enable YouTube Studio scheduling** in its popup and
accept Chrome's site permission. This persists until removed in Chrome. No YouTube
task is claimed by an old extension or one lacking that permission. No upload starts
when the Studio worker is unavailable. The editor and Chrome stay open through
upload/verification; YouTube handles release after scheduling. The global unattended
publisher stays disabled. The new adapter has automated contract tests; actual
seven-video scheduling must be tested by the user through Storylens after activation.

Follow-ups such as “you didn't schedule the shorts on yt, please do that” are
classified by the local model against the current campaign and reuse the same seven
exports. They no longer enter generic two-platform drafting. Only unstarted accidental
Instagram drafts recorded in that chat for those exact exports are cancelled.

First requested campaign: `output/campaigns/cricket-20261019/campaign.json`.
The dedicated CLI has prepare, review, quality and upload stages; durable queue IDs
and remote upload IDs prevent duplicate retries. Uploads require successful local
review. Ambiguous outcomes stop for reconciliation.

The chat workflow saves its moment plan first and refines word boundaries before
rendering. It does not render an initial set and render it all again. Valid reviewed
copy with the required hashtags is reused, avoiding another writing pass.

Prime ASR failure is recorded instead of bypassed. The alternate installed local
Whisper large-v3 CUDA model may provide a transcript with Hindi text and word times.
Final viewer-facing metadata is still English. ASR, selection and copy-review receipts
identify the actual model used; machine approval does not guarantee factual perfection.
