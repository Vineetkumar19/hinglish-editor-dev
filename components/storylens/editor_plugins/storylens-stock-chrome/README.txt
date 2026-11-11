Storylens Stock Search 0.1.2 — separate opt-in Chrome extension

1. Keep Storylens running. Open http://127.0.0.1:8765/stock-browser.html.
2. In your regular Chrome open chrome://extensions, enable Developer mode,
   Load unpacked, and select THIS storylens-stock-chrome folder.
3. Open this extension's popup, choose your Storylens port, click Connect.
   Chrome asks for Pexels and Pixabay site access. Approve only if you agree.
4. The popup opens the local pairing page. Click Connect Chrome there.
   Verify the page reports Connected and the enabled sources.
5. Run Add B-roll normally and choose Vertical or Horizontal. Six choices max.

This is NOT Storylens Local Publisher. Do not replace or reload that extension.
The stock extension requests storage, alarms and fixed packaged DOM scripts;
optional site access is only www.pexels.com and pixabay.com. Localhost access
is for the typed stock queue. No cookies/debugger/native-messaging permission.
It owns up to two working tabs and never selects existing account/photo tabs.
Pexels and Pixabay can search simultaneously, one task per website. Public
Mixkit, Coverr and Videezy metadata searches also run concurrently in Storylens.
Metadata batches are bounded; video downloading and decoding stay sequential.
Search pages/detail players are read normally in your Chrome profile. We do
not copy cookies or solve security challenges. If verification reappears,
complete it yourself in the shown stock tab; other websites can continue.

Public media is still downloaded through Storylens's bounded CDN downloader.
The selected video may be read from its public advertised edit-link media URL
when the background player has not loaded. Unknown dimensions are verified by
the actual local video decoder before any option is offered; no crop is used
to pretend that a horizontal source is a native vertical video.
Site access/playback does not guarantee every CDN download or keyword succeeds.
Videos are human-reviewed suggestions; check their individual source licence.
Only source-public video IDs/URLs/metadata return to Storylens. No owner video
or full transcript is uploaded; searches send the planned stock keyword.

Disconnect on the local page rotates the stock key and fails pending searches
without removing saved results. Disable/remove this extension in Chrome to
revoke persistent site permissions. It needs Chrome and Storylens running,
not ChatGPT/Codex. Native editor handoff is a separate acceptance check.
