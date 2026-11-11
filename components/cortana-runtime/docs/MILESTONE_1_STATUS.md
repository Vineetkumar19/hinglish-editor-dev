# Milestone 1: laptop control

Implementation and verification date: 20 October 2026. This is the first usable laptop-assistant baseline, not completion of every specialist PDF or a guarantee that every command works.

## What is implemented

The Electron desktop supervises its own Python agent, authenticates requests with a fresh private session token, and remains accessible through a draggable floating button and tray. Closing the main window hides it. Ctrl+Alt+Space opens it; Ctrl+Alt+S hides Cortana, captures the underlying primary display and attaches that moment to the next typed or spoken question. Screen images live in RAM, expire after five minutes and are consumed once. They are not continuously recorded or uploaded.

Explicit app/website commands use a deterministic English/Hindi/Hinglish parser. Other requests use local Qwen3.5 9B vision and tool calling with a bounded number of steps. The assistant can read real code, prepare an exact change, show the diff, apply it after approval, and retain a recovery copy. Code displayed in an editor must be saved to disk for file edits; unsaved editor buffers are not edited directly.

Speech recognition uses local faster-whisper large-v3-turbo on CUDA/int8_float16. Conversation now starts automatically and resumes after every reply until the owner turns the microphone off. There is no per-question activation or conversation timeout. Stop cancels the task; Mic off ends background listening and releases capture. Windows lock also releases capture. The mic preference is remembered. English uses local Lessac high Piper; Hindi uses the existing Piper voice. Provisional text appears in the right-hand feed while speaking. The reasoning model preloads in the background, and routine greetings bypass the model. See [voice timing and limitations](VOICE_MILESTONE_1.md). Actual microphone accuracy and complete response latency remain under live verification.

The desktop **Connect** tab and chat cards open installed WhatsApp and Instagram apps for drafting. Gmail and website fallbacks use the existing Vineet Chrome profile (`Default`), targeting `vineetdas1903@gmail.com` for Gmail. An isolated accessibility worker verifies editable controls and recipient information; uncertain layouts require selecting the conversation manually and resuming. Existing text and recipients are preserved. Cortana prepares drafts only; the owner presses Send. App-first routing and native safeguards have automated coverage; real-account composer acceptance remains pending.

Instructions remain English/Hindi/Hinglish. Outgoing WhatsApp and Instagram text must be English or Roman Hinglish; Gmail body and subject must be English. The exact-message form asks for the final text in that language and rejects non-Latin letter scripts without silently changing it. Natural-language drafting handles the instruction separately from the outgoing message.

## Evidence from this machine

Live observation after the continuous-conversation update: the owner spoke How are you doing? and What are your capabilities? on consecutive turns; Cortana answered and remained in Conversation on / Listening. The next Chrome/Gmail request appeared provisionally during speech and was transcribed in full. Its drafting portion was initially missed due to the Okay, so prefix; that routing fix and recent-user-context recovery have now been loaded. Successful Gmail composer population and Instagram activation remain unverified. No end-to-end sub-second guarantee has been established.

GPU repair: large-v3-turbo now uses CUDA/int8_float16 with private cuDNN and startup warmup. The same saved clip decoded in approximately 0.16–0.17 seconds when warm; the 9B model and large speech recognizer were verified concurrently on the GPU. Provisional speech feedback is implemented in the right-hand feed. Exact launches now handle polite question punctuation and skip model inference even with an attached screen. A blocking UI Automation focus fallback was removed from app launches. These are component checks; complete voice-to-action under one second remains unverified and is not guaranteed. See [voice timing and limitations](VOICE_MILESTONE_1.md).

Current live repair status supersedes older acceptance entries below: the owner's English utterances opened C: and the signed-in Instagram app. The native WhatsApp action verified an unsent “Hi, hello, how are you?” draft in Vineet (You); this was action-stage diagnosis, not acceptance of the full verbal pipeline. Instagram inbox loading failed with a provider error. Gmail composer debugging created repeated blank composers without completing the email demonstration; that demo has been stopped. The new addressing gate, microphone stop behavior, and screen fixes still require the owner's live verbal acceptance. The complete assistant milestone remains incomplete.

| Check | Observed result |
|---|---|
| Python environment | Repaired to private Python 3.12; dependency checks pass |
| Actual desktop | React UI and floating controls render in Electron 44.9.1; no renderer errors |
| Backend lifecycle | Starts automatically; restart rotates the token and closes the old service; parent/launcher death tests exit the owned backend |
| Windows startup registration | Cortana is running with its current-user startup entry enabled. Windows argument parsing and a launched Electron fixture verified paths with spaces and enabled/disabled state; test entry removed. A real sign-in/reboot remains pending |
| Chrome / YouTube / ChatGPT | Actual launch requests succeeded through the API in 17–38 ms; website page loading is distinct from process handoff |
| Real screen path | 1920×1200 controlled editor fixture; capture 458 ms; local model correctly explained the TypeError and fix, 13.4 seconds overall |
| Local code edit | Model read the disposable file, prepared the exact diff, waited, then approved edit passed the expected calculation; duplicate approval returned 409 |
| Voice | Generated English/Hindi/Hinglish clips recognized offline; Hindi/Hinglish STT about 3 seconds, English cold about 5 seconds; silence ignored |
| Communication desktop flow | Hidden Electron UI/IPC test passed app-first status, manual conversation/resume recovery, exact draft preview, Stop/lock cancellation and rejection of late responses; no accounts accessed or messages sent |
| Draft intent extraction | Actual local model preserved English WhatsApp and Roman-Hinglish Instagram text; translated Hindi Gmail dictation to “Let's meet tomorrow evening at 7 PM.” with the correct recipient/subject. Browser actions were replaced by fixtures |
| Python regression checks | Final combined run after app-first changes: 260 passed, 9 subtests passed |
| Desktop regression checks | 20 unit tests passed, including draft validation, expired draft invalidation, startup arguments/status and rejection of send routes; lint and production build passed |
| Native drafting safeguards | Controlled tests cover main Chrome profile/sender routing, duplicate UIA nodes, existing drafts/recipients, extra Cc/Bcc rejection, changed/sent draft resume, cancellation races and leaving external apps open |
| Legacy communication browser | Earlier isolated-browser fixtures and lifecycle tests remain regression coverage; this browser is no longer the active drafting path |
| Communication accounts | Installed WhatsApp and Instagram identities and Chrome Default/Vineet profile metadata were inspected. Real-account draft entry for the new native path remains pending. Computer-use inspection was closed at the owner's request |
| Local model cold start | Initial load about 59 seconds; later cached load about 12 seconds; loaded model generated a short Hinglish reply at about 56 tokens/second |
| Cloud | Disabled; no provider calls used for these checks |

Detailed test outputs are under `tmp/runtime-smoke/`, `tmp/screen-acceptance-*/`, `tmp/voice-validation/`, `tmp/draft-intent-smoke.json`, and `tmp/desktop-smoke.png`. Synthetic voice tests do not establish accuracy for the owner's actual microphone, accent or room noise.

## Security boundary

All operating endpoints require the per-launch bearer token, which remains in Electron main and the backend. Browser origins, remote hosts, unrelated frames, arbitrary IPC routes and external app navigation are rejected. The renderer is sandboxed with context isolation and a restricted content policy. External applications do not inherit Cortana's credential environment.

The user authorized all laptop files with permission before crucial tasks. Current A:, C:, E: roots are available under normal Windows permissions; searches have time/depth bounds and skip heavy/system/credential trees. This is not administrator access. File changes, generic clicking/typing/shortcuts and model-generated website URLs require review. Confirmations are one-use, expire, and bind code edits to the reviewed file hash and computer actions to the reviewed window. System security changes, credential stores, Cortana self-modification, arbitrary shell commands and file deletion stay blocked.

Communication uses installed applications first and the owner's existing Chrome profile for websites. No cookies are copied and no browser debugging port is opened. The legacy isolated browser is no longer called by draft routes or tools; its reserved profile remains protected from general file access. Only the dedicated draft tool may fill messaging composers; generic messaging input stays blocked. The IPC allowlist has no send endpoint. Stop/Escape and Windows lock terminate only Cortana's accessibility worker, leaving external applications and already entered drafts open. The worker has a credential-stripped environment, private pipes, a parent watchdog and bounded operations. Accessible labels and app layouts can change; unresolved recipient, sender, extra-recipient or field ambiguity stops entry.

Authentication is based on the signed-in Windows session and desktop token. Voice recognition is not speaker identity verification. Existing malware or another person using an unlocked Windows account is outside the protection offered by a local API token. Local conversation/audit history is stored in SQLite, not encrypted by Cortana.

## Remaining acceptance and limits

- Verify a real Windows sign-in/reboot and the owner's actual microphone/speaker with several commands in each language. Startup registration is enabled and its command was checked; a reboot has not been performed during development.
- Verify the owner's sign-in, recipient lookup, exact composer contents and manual handoff separately for WhatsApp, Gmail and Instagram. Controlled fixtures do not establish that the live sites work, especially Instagram's changing recipient/header layout. Unknown layouts and ambiguous identities refuse; no automatic Send test is part of acceptance.
- Translation is model-generated and must be reviewed. The exact-message form preserves final text; its script check cannot distinguish English from Roman Hinglish. Chat applies the requested English-only Gmail policy and preserves relative dates/times in the tested example.
- Primary-display captures are supported. Continuous video watching and multi-monitor selection are not implemented.
- Use the screen button for ambiguous questions. Automatic capture recognizes a tested set of direct screen phrases; broader phrasing is not guaranteed.
- Reading and editing saved files works with reviewed diffs. IDE unsaved buffers, terminal execution and complete autonomous debugging are later work.
- File discovery is bounded; a negative search result does not prove a file is absent anywhere on the laptop.
- Natural Hinglish pronunciation and real-room wake accuracy need owner testing. Background wake detection currently uses short local speech clips, not a custom acoustic wake model.
- The Hindi voice's noncommercial dataset license is suitable for this personal assistant baseline; choose another licensed voice before commercial content production.
- The supported installation runs from D:\Cortana. A signed installer/updater is not delivered. Eight moderate npm advisories remain in the development packaging chain; no high/critical findings were reported after the compatible dependency update.
- No software can honestly be certified impossible to hack from these tests. This milestone establishes concrete protections and regression coverage.

## Operating commands

Launch with `StartCortana.cmd`. Startup was enabled for this user's Windows sign-in on 20 October 2026. `StartCortana.cmd --enable-autostart` can re-register the current checkout. Settings can disable startup or the floating control. Do not move/delete the project, its private runtime, or installed model files while relying on this registration.

Run backend checks with `agent\.venv\Scripts\python.exe -m pytest tests -q`; run desktop checks with `npm test`, `npm run lint`, `npm run build` from `desktop`. `node scripts/smoke_live_pipeline.cjs` uses only a disposable coding fixture. Add `--open-apps` only when intentionally opening Chrome/YouTube/ChatGPT. Screen acceptance is `npm run test:screen` and briefly displays a test window. `npm run test:integrations` uses simulated account/draft responses in the actual hidden desktop UI.

`npm run test:startup` uses a temporary named startup entry and an inert Electron fixture, then removes that entry. `agent\.venv\Scripts\python.exe scripts\smoke_draft_intent.py` tests local model extraction/translation with browser actions replaced by fixtures.
