# Using the local editor without an OpenAI subscription

The editing assistant uses the configured local Ollama model (`storylens-planner:9b-q6`, Qwen3.5 9B Q6).
Its editing tools and the Storylens Local Publisher extension do not call OpenAI or Buffer.
Keep the editor and Ollama running. Social uploads also need internet and a signed-in browser/account.

## Instagram through Chrome

Open `http://127.0.0.1:8765/` and attach one finished portrait MP4 (up to 3 minutes / 2 GB).
Use one of these chat requests:

- “Check which Instagram account is connected in Chrome.”
- “Prepare an Instagram Reel preview for @vineet_editz19. Do not post it.”
- “Upload this video to Instagram @vineet_editz19 with a caption about the video.”
- “Upload this video to my cricket Instagram account.”

Destinations are saved in the local Chrome connection page. Exact @usernames in a request take
priority. General currently selects `vineet_editz19`; Cricket selects `fantasy_legends91`.
Gaming is not assigned an Instagram default; give its exact username or save that destination yourself.

The local model plans the request. The bounded browser tool checks the account, transfers the selected
video, preserves portrait framing and original audio, inserts the caption, and checks the composer.
A preview stops before Share. An upload records the Share boundary first and only reports publication
after Instagram's shared confirmation and a new reel URL. Interrupted/ambiguous uploads require review;
they are not repeated automatically. The extension checks the queue every 30 seconds, or immediately
when you click Check now in its popup.

Version 0.3.0 reuses one Instagram working tab across jobs and account switches. It stops for an
unfinished composer instead of opening another tab. Normal page reloads during switching reconnect
with a bounded account check. A prepared upload interrupted before Share can be resumed from Chrome
connection without invoking the model or rewriting its caption. Recovery is refused when durable
state says Share started, or cannot establish that it did not start.

Publishing copy uses actual content and the saved English/content-only writing preferences. A supplied
English `.publish.json` is reused as creator-approved copy; otherwise the local model drafts/copy-edits
the text. The Chrome transport uses one paragraph with explicit spaces because Instagram
removes raw line breaks during text insertion; the formatted source metadata is retained. Attach an accurate transcript when speech recognition cannot recover the song or dialogue.
The browser tool cannot improve a bad transcript by itself.

## Existing YouTube connection

Private YouTube uploads can now finish inside the local chat. For example:

“Upload any random video privately on both my YouTube channels: one long and one Short, with titles
and descriptions.”

The saved workflow selects from attached MP4s or the configured source video folder, checks orientation,
makes up to 90-second landscape and 15-second portrait excerpts, and drafts English copy locally.
Originals stay unchanged. The chat shows the selected sources, channels and editable metadata. Choose
the audience and realistic synthetic-media disclosure, then use “Upload these privately”. You can also
reply “Upload these privately, not made for kids, no synthetic media” when those declarations are true.
Results return to the same conversation; no Publishing Studio redirect is required for this flow.

The source library is saved as `source_root` in publisher settings and can be changed in Publishing
Studio. The model cannot supply an arbitrary filesystem path, channel credential or upload authorization.
Both-channel requests use the saved Cricket and Gaming YouTube connections. Plain legacy publishing
draft commands and public publishing retain the Publishing Studio workflow.

Accepted remote IDs are retained. An ambiguous attempt is never repeated automatically; changed
channels or media require a new review. Already verified private uploads are returned as existing
results instead of being uploaded again. Manual chat uploads do not enable scheduled publishing.

The installed local Ollama runtime can now start on demand when the configured local model store is
available. It binds only to localhost and uses that existing store, with cloud inference disabled. This
creates no Windows administrator access, login, installation or startup/scheduled task.

This is a local tool-using assistant, not unrestricted access to every PC program or website. Existing
editing tools, the connected YouTube uploader, and the Instagram Chrome extension work without Codex;
new integrations still need an actual tool. Local model copy remains editable because the live demo
exposed factual errors and instruction leakage. No weight training was performed.

## Limits

- This is a local editor with bounded tools, not an unrestricted agent for every website or PC task.
- Stories are not verified in Instagram's desktop composer and currently return a clear limitation.
  A Story request never silently becomes a Reel or direct message.
- Complete passwords, verification and account recovery yourself. Interface/language changes can
  require a selector update; the tool stops rather than guessing.
- Scheduled publishing remains disabled. Connecting the extension does not enable daily posts.
- No weight training was performed. Saved writing feedback changes the model's instructions/memory.
- The requested desktop application remains a future option; none was built as part of this work.

## Connection and removal

The local setup page is `http://127.0.0.1:8765/chrome.html`.
The extension files are in `editor_plugins/storylens-chrome`. Version 0.3.0 is connected and includes
single-tab reuse and prepared-upload recovery. Reloading an extension invalidates its existing page
connection: refresh the Instagram tab before resuming. Reload the extension after changing its source.

Use Revoke Chrome connection on the setup page to invalidate its limited key, and remove the extension
in Chrome to uninstall it. No administrator account or remote debugging port is created. The code does not read passwords
or cookies. Native file selection uses Chrome’s debugger permission, which is broader browser access;
the implementation attaches only to its own Instagram tab for native file selection and queued caption
entry, and detaches after each operation.

Instagram caption writing has its own small local-model request instead of generating an unused
YouTube description. Malformed copy and unsupported numerical claims are revised before enqueueing.
Source-supported round names such as Qualifier 2 are retained. This does not guarantee factual accuracy;
review the caption, especially when speech recognition needs corrected source notes.

Evidence and test receipts: `output/validation/local-chrome-integration/`.

## Verified locally — 19 October 2026

Version 0.2.0 completed the local assistant → queue → Chrome preview flow for `@vineet_editz19`.
It selected the existing 12-second portrait MP4 through Chrome's native file input, confirmed original
audio, inserted the content-only caption, verified the destination and stopped before Share. The
finished composer is saved in `local-preview.png`; `live-preview-check.json` contains the receipt.
The earlier local Qwen account check and planning checks also passed. Python regression checks passed
69 tests and the JavaScript browser/controller checks passed 10 tests.

The later real demo posted through the local extension to both destinations:

- `vineet_editz19`: https://www.instagram.com/vineet_editz19/reel/DepacYtN5Du/
  The extension performed Share, but its original caption did not save. Codex repaired the caption
  and reconciled an incorrect old permalink. This was not an unattended successful upload.
- `fantasy_legends91`: https://www.instagram.com/fantasy_legends91/reel/DeqTptLqqag/
  Version 0.3.0 selected the local portrait video, preserved original audio, entered the exact prepared
  local-model caption and performed Share. One Instagram tab remained. No new model request was made
  during resume. Codex inspected the published article and confirmed the complete caption and hashtags;
  no caption repair or extra Share was needed. Automatic receipt polling timed out, so the final queue
  result is explicitly labelled `operator_browser_review` rather than automatic verification.

The receipt failure exposed Instagram rendering the new profile grid outside `main`. Source code now
handles that layout and accepts an actual new top entry plus its exact posted caption even if the
transient success notice has disappeared. These final content-script changes pass regression checks
but are not loaded in the running extension yet; they require its next reload and Instagram refresh.
No further public test or reload was requested to complete this demo. Fully unattended end-to-end
publication remains unproven. Current checks: 76 Python and 16 JavaScript tests passed.

Detailed receipts, manual-review distinctions and screenshots are in
`output/validation/local-instagram-demo-20261019/`. Both current Chrome account logins were verified.
