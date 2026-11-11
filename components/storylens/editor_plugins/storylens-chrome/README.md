# Storylens Local Publisher

This extension connects the local editor's bounded Instagram queue to Chrome. The configured local
Ollama/Qwen planner chooses the tool and writes metadata. Neither OpenAI nor Buffer is used by this
connection. This is not a general browser agent, and it does not execute model-generated scripts.

Version 0.4.0 also provides an optional YouTube Studio scheduling adapter. Reload
the unpacked extension once, then click **Enable YouTube Studio scheduling** in
the popup. Chrome requests persistent access to `https://studio.youtube.com/*`;
declining leaves this feature disabled. Scripting is used only for the fixed
adapter in its dedicated Studio tab. The editor uploads the reviewed MP4 exports
privately through the already connected YouTube uploader first. Only those new
video IDs, their channel and release instants reach this adapter. Browser submission
is provisional: the editor independently verifies the exact YouTube schedule before
reporting completion. It never schedules a video picked from old browser rows.

## Install and pair once

1. Keep the local editor running. Open `http://127.0.0.1:8765/chrome.html` in your usual Chrome profile.
2. In `chrome://extensions`, enable Developer mode, choose Load unpacked and select this directory.
3. Open the extension popup, paste the connection code from the editor setup page, and connect.
4. Check the signed-in account. Save exact destinations for General, Cricket and Gaming as needed.
5. Attach a finished vertical MP4 in the editor chat and ask: “Upload this video to Instagram @username
   with a caption about the video.” Attach its transcript too if the lyrics/speech recognizer needs help.

The extension checks for explicitly queued requests every 30 seconds. “Check now” starts sooner.
Connecting does not enable a daily schedule. Keep Chrome, the editor, and internet available during an upload.

## Supported scope

- Check the currently signed-in account.
- Switch to an already signed-in account, verify identity, and publish one existing portrait MP4 Reel
  (up to 180 seconds and 2 GB). Caption generation and saved writing preferences stay local.
- Preserve portrait crop and original audio. Stop if the expected preview, controls or caption change.
- Record the Share boundary before submission. Verify the shared confirmation and a new reel URL.
- Preserve receipts and stop ambiguous attempts instead of automatically repeating the upload.
- Pause for login/checkpoint or unsupported interface/language changes. No CAPTCHA/password automation.

Stories are not verified in the desktop composer and currently return an explicit unsupported result.
The extension never substitutes a Reel or sends a direct message for a Story request.

## Access and removal

The required hosts are `https://www.instagram.com/*` and local `http://127.0.0.1/*`.
Studio access is optional as described above. The code does not use cookies,
password APIs, a remote debugging port, administrator rights, external AI services or analytics.
It reuses one Instagram working tab and stops for an unfinished composer instead of creating another tab.
Account switching changes the shared login session in that Chrome profile.

The extension stores a separate revocable queue key in Chrome's local extension storage. It cannot use
that key to call editing endpoints or read arbitrary files. Only media attached to a claimed upload can
be read. Use “Revoke Chrome connection” in the editor to invalidate the key, then remove the extension
in Chrome if desired. A crash after Share requires checking the actual Instagram account before retrying.

## Validation

Python tests cover queue authorization, scoped file transfer, identity receipts, cancellation, restart
handling, deduplication, HTTP boundaries and planner wiring. Isolated JavaScript tests cover the worker
sequence and failure cases. Live Qwen planning receipts are in
`output/validation/local-chrome-integration/live-planner.json`.
These tests do not establish a successful live upload from this new extension. That requires installing,
pairing, and verifying it against Instagram. Earlier Codex-driven uploads are separate evidence.

Chrome references: [host permissions and cross-origin requests](https://developer.chrome.com/docs/extensions/develop/concepts/network-requests),
[extension service worker lifecycle](https://developer.chrome.com/docs/extensions/develop/concepts/service-workers/lifecycle).

Version 0.2.3 uses a trusted Chrome file-chooser interaction and waits for video decoding before
advancing. Caption entry also uses native Chrome text input so the editor commits it. The debugger
permission is broad browser access; this code attaches only to its dedicated Instagram tab for
the selected file and queued caption, then detaches. This permission was explicitly approved by the creator.

Publication verification waits for a new top profile entry and reads the exact caption on its actual
Reel page. A lazy-loaded old post cannot become the receipt. If Instagram labels a remembered account
with an email rather than its username, a single unambiguous alternative can be tried; the real signed-in
username must still match before file selection. Ambiguous account lists require the creator's choice.

Version 0.3.0 consolidates this workflow into one working tab, reconnects after the normal account-switch
page reload, and supports explicit recovery of a prepared upload only when Share never started.
Recovery retains the selected video and caption; it does not regenerate metadata or rerun the model.

Version 0.4.10 reconnects the packaged Instagram adapter after an extension reload, before checking
the signed-in account. Media loading and decoding each have a two-minute timeout. A failed attempt
before Share closes only the composer created by that attempt, when its DOM identity still matches;
manual drafts and uncertain submissions are kept. Each new upload resets its own publication lookup.
The backend allows a new authorized request to retry the same unsubmitted job without duplicating
it; submitted jobs still require receipt verification.

Version 0.4.11 activates the working tab to reduce background-timer delays, allows up to 90 seconds
for a switched account to finish loading, and recovers a disconnected post-submission page by
reading the exact existing caption, account, and publication time. Read-only recovery may follow
one unambiguous matching Reel link from the profile grid. It never opens the upload composer.

Version 0.4.13 supports caption-free Reels and selects the destination profile even when Instagram
Messages is open in another tab. Empty caption text is checked before Share; a resulting caption-free
post still needs its account, new permalink and posting-time evidence. The backend can resume an
authorized saved attempt after a known pre-Share browser failure, without re-extracting the video.
