# Cortana — live acceptance checklist

## 5 November spoken acceptance run

Played locally synthesized test phrases through the laptop's normal audio
output. The running Cortana application captured them through the Realtek
microphone array. No command text was injected for these cases.

| Spoken scenario | Observed receiving result | State |
|---|---|---|
| Cortana, can you hear me? | Provisional text appeared in the composer. The final chat turn showed `can you hear me?` and Cortana acknowledged it. | Pass |
| Fix a meeting in Gmail for tomorrow | The microphone captured the request. Cortana asked for a title, start time and duration for Google Calendar. | Intake pass only |
| Prepare calendar event Project sync tomorrow at 15:00 for 30 minutes | First acoustic run produced `15.00`, which missed the original syntax. After the fix, Cortana prepared the reviewed 6 November 15:00–15:30 IST event. Approval opened the exact Calendar account and event editor. The title was transcribed as `project, sync`. No guests were present. | Event editor verified; save and exact title still open |
| Open Calculator | Cortana heard `Open Calculator`, used the local command route and the Windows Calculator window was visible. | Voice pass |
| Answer with sources warranty | Cortana displayed page 2 of the demo warranty PDF and page 1 of the scanned receipt, with the unapproved date, fictional receipt number and limits of the evidence. | Voice retrieval pass; conflict and source lifecycle open |
| WhatsApp message Rohit saying this is a Cortana voice demo | The first recording was misheard as `RoKit` and exposed a routing bug. After replaying with the fix, Cortana selected `Rohit New`, the top visible WhatsApp result. The real app showed the draft beside `Rohit New` and Cortana displayed the exact body and full recipient on its review card. | Voice pass. Draft unsent |
| Instagram message Alex | Cortana heard Alex, retained Instagram and asked for a `Write` follow-up. | Voice intake pass only |
| WhatsApp message Neha, then spell Neha | Cortana initially heard `now`. The letter attempt was garbled and prompted a correction. The microphone then captured `November Echo Hotel Alpha`, and Cortana updated the pending recipient to `NEHA`. | Voice correction pass. No message body was supplied |
| Open Media Player, then open Photos | Cortana heard both commands separately, used the local launch route and both Windows application windows appeared. | Voice passes |
| Restore workspace Demo GCP Chrome | Cortana heard the workspace name and reviewed exact revision 1. The review was approved with the existing button. Restore `5ba9d41fbd9342b5b3e805a30ca110c3` reused the original Chrome tab, which was visibly paused at 0:27. The demo project, folder and notes were visible in their receiving applications. | Voice initiation and receiving result verified. Approval used the UI |
| Message myself on Gmail saying Cortana voice demo only | First pass reached the correct self address but Gmail invalidated a control during recipient verification. Saved and closed the incomplete test composer, then replayed the same audio after adding a bounded read retry. The actual Gmail composer showed the configured self address, the exact dictated body and an available Send button. | Voice pass. Draft unsent |
| Open Telegram, then the reported message request | Cortana opened the installed Telegram app from the spoken launch. The owner's earlier spoken draft request reached the capability check. Telegram's Windows window exposed no accessibility tree in the desktop probe. | Voice launch pass. Draft route blocked in the installed client |
| Open Instagram, then draft to a visible contact | The configured shortcut did not show a receiving window. The repeated voice command opened the signed-in Chrome inbox after selecting that route. One dictated name was misheard as `Vinit Kumar` and native search found ambiguous controls. Later speaker replays did not reliably recognize the replacement contact. | Voice launch pass. Composer unverified |

Short fixture comparisons found that the original vocabulary prompt could
turn a distinct spoken `Rohi` into `Rohit`. Final decoding now compares three
candidates with service-name vocabulary. An explicit recipient correction can
replace the pending recipient while retaining the existing message body.
The direct spoken correction was misheard as `ruined`. A phonetic spelling
attempt was misheard and passed as draft text, but WhatsApp did not find the
pending recipient and its composer received nothing. The route now asks for
another correction when it recognizes the recipient phrase but cannot parse
its spelling. A later owner voice turn reached `Rohit` and found multiple
search rows. The owner chose the top visible WhatsApp result in this case.
Cortana now checks the opened conversation against that search row and
displays its full name on the review card. Spoken follow-up body text requires
an explicit `Write` or `Say` cue after an observed unrelated utterance entered
the draft preview. WhatsApp rejected the ambiguous result in that earlier run,
and no message reached its composer.

Extended the exact launch configuration from 51 to 112 aliases using verified
Windows Start-menu shortcuts and registered app IDs. A spoken test opened the
installed Clock, though its transcript also captured the owner's nearby speech.
Fixed obsolete Paint, Photoshop and EA launch targets. App-by-app spoken
verification remains open. The additional speaker replay for Visual Studio Code
was misheard as `Business Studio Code` and is a failed voice recognition case.

## 5 November microphone recovery

Windows had about 737 MiB of available system RAM during the initial failure.
Speech admission used Ollama's model list to check residency, but Whisper is
loaded outside Ollama. A rejected request appeared as a corrupt recording in
push-to-talk. Speech now uses the resident model when admitted, can transcribe
locally on CPU if GPU admission fails, and reports resource and audio errors
separately. Short recordings use the lightweight decoder when the GPU speech
model is cold. The chat composer shows provisional text, and a failed reply
leaves the finalized transcript available for editing and retry.

After restarting Cortana and reloading the interface, the actual laptop mic
produced `What is 2 plus 2?` and the visible answer `2 plus 2 is 4.` Cortana
logged 1.407 s for recognition, 0.891 s for the fully GPU-resident 9B answer,
and 0.125 s for synthesis. The next live test displayed `What is 8 into 14?`
in the composer before final recognition. A cold GPU decode took 8.219 s and
changed it to `What is 18 to 14?`, which produced the wrong answer for the
spoken question. This prompted the short-recording change above. The live
conversation also transcribed `What is the LCM of 9 and 18?` and answered 18,
then displayed `Tell me about myself.` in both the composer and chat while
the model was thinking. The microphone remained on across those turns.
The backend was then restarted with the short-recording change. Two actual
short microphone clips ran through the base decoder in 1.00 s and 0.98 s.
The second reached chat and received a 9B Q4 response in 1.44 s, fully in VRAM.
Cold speech synthesis added 3.52 s in that turn. The exact multiplication
phrase still needs a successful repeat with the updated decoder.

The installed base decoder recognized the English, Hindi and Hinglish voice
fixtures under a simulated low-memory admission check. Its first decode took
2.203 s, the next two took 1.016 s and 1.063 s, and the silence fixture produced
no text. These figures exclude the time spent speaking and endpoint detection.

## 5 November latency follow-up

Real microphone records show 9.48 s for a cold 4.78 s clip and 0.45 s for a
subsequent 15.19 s clip. Cortana visibly answered the user's short greeting;
the later voice question displayed a garbled transcript and had no completed
model timing before the microphone was turned off. Voice acceptance is open.

Supplementary on-device benchmark used the existing labelled audio fixtures
under Cortana's shared GPU lease. The exact 9B Q4 runner loaded in 8.33 s and
reported 5,507,330,866 bytes fully resident. With that runner still loaded,
Whisper's cold English decode took 6.72 s and its next decode took 0.27 s.
The Hinglish fixture still transcribed `kholo` as `Colo`. A short 9B warm answer
took 0.22 s. Both stayed GPU resident through the benchmark, and only the test
weights were released. This supplements, rather than replaces, real voice tests.

Runtime change: retain the 9B runner and speech decoder together only when the
measured single NVIDIA device has enough free memory. 9B still requires full
VRAM placement. One reasoning/vision runner, serialized inference, idle release,
the shared coordinator, and the Stop/priority behavior remain in place. Backend
was restarted in the existing desktop app. A live cold typed turn took 9.20 s
(8.02 s before generation) and its warm follow-up took 1.39 s (0.031 s before
the inference request), both with full residency at 4096 context. The owner’s
new microphone retest with the resident pair remains open.

Calendar read retry reached the exact requested date and configured account in
the Chrome receiving app, but the first native account verifier did not see the
accessible header. Added a bounded tree fallback and restarted before the retry.
The Calendar retry again failed native account proof even though the receiving
Chrome page showed the configured account. Availability remains unverified.
Chrome's existing extension manager was restored using Chrome's Switch to this
tab control. The approved workspace extension loaded and showed enabled, ID
`dhoipjbmkaifapkmfegihklloeodlooh`. Registered its exact native host under
HKCU. The `Vineet` Chrome profile connected and the popup confirmed approved
YouTube access. The named workspace `Demo GCP Chrome` captured Cloud Run
Overview at 27.63 seconds, notes, the Terraform project, and its folder.
Restoring after changing the same tab to 55 seconds returned the existing tab
to 0:27 paused, confirmed in YouTube itself. Browser command receipt
`434f2dc5036a40d2990935817898f26d` records reuse of tab `1175195211`.
The first restore opened Documents in VS Code because fuzzy alias resolution
ran before exact path resolution. After fixing the order and restarting, the
same command opened `terraform-demo` in VS Code and returned the original
paused YouTube tab. The review now displays browser, profile, time and context.
Notepad reused the demo notes window. Explorer opened a second demo folder
window on repeat, so full duplicate-free desktop restoration remains open.
`Open Brave` through Cortana exposed the existing Brave window without a prompt.

Live Cortana document checks: imported `receipt-and-warranty-demo.pdf` (two
pages, ID `0f42635e6fed363be303e2c5`); `Answer with sources warranty` showed page
2's unapproved expiry and page 1's amount/date/reference, and said payment alone
does not prove coverage. Imported `scanned-receipt-demo.pdf` (one page, ID
`aa4f715b6bb80095fe622376`). Conflict, source invalidation, and tasks remain open.

## 5 November continuation

The owner restored Cortana priority, then clarified the ordinary messaging
handoff: open the configured app and prepare the draft automatically, report it
ready, and let the owner verify and press Send. A staged self-send control was
removed before any delivery attempt. AgentSuite was left paused.

| Live action through Cortana | Actual receiving result | State |
|---|---|---|
| Restart assistant, then reload desktop UI | Same desktop instance, Online, Hindi + English / Hinglish selected | Verified runtime recovery |
| Why does the sky look blue? One short sentence. | Correct answer, `cortana-local:9b-q4`, 5,507,330,866/5,507,330,866 resident bytes in VRAM. 12.4 s from submit to model completion. | Typed pass, microphone still pending |
| Open Gmail | Existing normal Chrome Gmail window for configured account. Local command, no confirmation. | Verified |
| Prepare exact Gmail self-addressed draft, subject `Cortana self-test 2026-11-05 A` | First attempt missed the loading Gmail window. After the repair, same account/recipient/subject/body visible in the actual composer. Native verification about 6 s; Cortana displayed “Draft ready. Verify it and press Send in Gmail.” No additional Open/Continue clicks and no send. | Pass on same scenario after recovery |
| WhatsApp kholo | Installed WhatsApp window opened; local command and no confirmation. | Launch pass; draft route pending |
| Open Google Calendar in schedule view | Initial model opened blank Chrome. Direct route reached expected Google account, but `/schedule` failed to load data. Manually observed canonical `/agenda` view on the same signed-in account and corrected source. | Corrected route retest in progress |

Original PDF release suite, browser extension and remaining app/document/workspace
routes stay open. Keep the fixture draft and user windows intact. Never infer a
voice pass from a typed command or a saved event from an opened Calendar form.

## Urgent voice latency correction — 4 November 2026

Owner reports no/very slow voice replies, describes roughly ten minutes as
unusable, and explicitly requests 9B Q4 fully in VRAM and immediate responses.
This is a FAILED owner acceptance result; the ten-minute duration was reported,
not independently timed. Visible Cortana replies identified
`cortana-local:9b-q4`, but selecting that tag alone does not prove GPU residency.
The actual UI was listening on Realtek Microphone Array with speech language
English. One owner `can you hear me?` turn received a local acknowledgement;
another transcript was visibly garbled. Verbal speed/accuracy are not accepted.

Source changes prepared (NOT yet loaded into the running application):

- Disable repeated whole-recording GPU preview decodes; transcribe the completed
  utterance once. One-time speech-language migration to automatic detection.
- Request all transformer layers plus output layer and a bounded prefill batch;
  verify full Ollama VRAM residency before answer generation. No silent CPU reply.
- Retain owned weights for a 20-second idle interval under the shared GPU lease,
  unload before releasing it, and honor Stop/shutdown/StoryLens pause. Speech and
  reasoning still hand off exclusively; simultaneous co-residency is NOT claimed.
- Record bounded transcription/model/load/residency timings without speech text
  or audio in `tmp/voice-latency.json`; display the shared-resource pause clearly.

Supplementary verification: 334 Python tests + 9 subtests passed; 29 desktop
tests passed; frontend build and lint passed. These do not establish voice speed.

The attempted local 9B timing probe failed to acquire the shared GPU lease and
exited before loading/inference. No successful latency or all-VRAM measurement
is claimed. The owner's later direct instruction in the StoryLens chat gives
that task exclusive GPU/native control until completion or reprioritization.
`memory/pause_model_work` is present. Cortana GPU/native actions ceased; no
task-owned background benchmark or UI agent remains. Read-only Ollama inventory
then showed no resident models. StoryLens independently reported 9.4 GiB free
and no compute-app entry before resuming its work. User applications preserved.

Next required live check after that resource boundary is released: remove only
this task's pause flag, restart the actual Cortana backend/frontend, verify
9B Q4/automatic speech mode, time two consecutive real owner microphone commands
and one nontrivial model answer, inspect timing records and GPU residency, and
repeat any failed scenario. The original architecture/extension/draft release
checks below remain unfinished. Do not treat a prepared build as a live fix.

## Local Architecture revision — 4 November 2026

All rows below are **PENDING**, waiting for the active editing chats to finish
before shared-desktop/GPU use. Owner chose a labelled demo workspace and approved
Chrome + Brave extension installation, native host registration and YouTube
access. No desktop actions have been performed by this chat in this run.
Later owner-authorized coordination and a Suite-reported failure are recorded
below. Earlier October results are historical, not acceptance of this code.

| Cortana command / visible action | Expected visible result | Observed in this run |
|---|---|---|
| Import document D:/Cortana/documents/Architecture Demo/scan.png | Fictional receipt text, date, amount and evidence; no invented warranty | PENDING; standalone Windows OCR only passed |
| Answer with sources warranty | Exact source/page/quote, uncertainty preserved | PENDING |
| Workbench: propose/confirm source deadline | Exact reviewed date and quote; overdue shown on wake | PENDING |
| Workbench: save labelled Demo GCP with notes/project/folder | Stored explicit items and fictional context | PENDING |
| Capture selected Chrome tutorial tab, then restore demo | Existing tab reused, observed timestamp, paused; notes/project visible | PENDING |
| Repeat capture/restore in Brave | Same checks independently in Brave/profile | PENDING |
| Missing demo file, duplicate workspace/tab, changed source | Specific per-item failure; unrelated work preserved | PENDING |
| Switch to 9B Q4; switch to 14B Q4 after review | Exact selected model; successful probe; residency and latency recorded | PENDING |
| Diagnose my PC | Real 30-second measurements, ranked evidence/hypotheses | PENDING; standalone backend sample only |
| Stop during workflow; restart after interrupted operation | No further steps/replayed effects; durable unknown/review state | PENDING |
| Authorized unsent email/chat drafts | Exact account/recipient/text, visible composer, zero sends | PENDING; owner authorized clearly identified visible recipients and assistant-written demo text |

The release suite of 30 routine, 20 draft, 10 stale/wrong-recipient and 10
diagnostic scenarios has not been run. Microphone acceptance requires the
owner's real speech. Latest supplementary checks: 328 Python tests + 9 subtests,
29 desktop tests, frontend build/lint. No end-to-end completion claim.

### Cross-chat live failure and repair — 4 November

Agent Suite reported typing `Restore workspace Suite delivery fef118292efa3031`
in the actual Cortana window and observing `Cortana returned 500.` Its saved
workspace ID is `72c8c32f1a3c4e0a953576675776465c`. This is a reported live
**FAILED** result, not a pass independently observed by this chat.

Source inspection found no deterministic named-restore route, so this phrase
entered model inference; GPU admission errors could escape as HTTP 500.
Named restore now resolves an exact name/ID and reviews its frozen revision,
with explicit ambiguity handling. Expected GPU waiting errors now return an
explanatory service response. 85 focused regression checks passed after repair.
Backend restart and the same visible command remain **PENDING** until the shared
desktop is free. No desktop input or model inference was performed by this chat.

Update: StoryLens released native control. This chat observed the prior 500 in
Cortana, opened Settings using verified keyboard focus, activated Restart
assistant, observed STARTING then ONLINE, and entered the same command in Cortana.
It now shows `local workflow` with an approval preview for revision 1 and the exact
Suite delivery folder. No model inference was needed. Before approval executed,
the control tool reported user input and then a minimized window. Native input
was paused; actual receiving-folder verification remains PENDING. The earlier
no-desktop-input statement above describes the pre-handoff checkpoint only.

The owner then explicitly answered `Yes, continue the Cortana tests`. Fresh
Cortana UI showed that approval had resolved and the folder was opened; the
matching Explorer window exists. SQLite has one restore receipt,
`58515a24a2e6484b8d8c5573bc6390d2`, with `opened_unverified`, copied to
`tmp/architecture/suite-restore-receipt.json`. This does not establish visible
folder-content acceptance. The native helper could not raise the minimized
Explorer window. Cortana was recovered using its configured Ctrl+Alt+Space.
A second exact restore is typed but not submitted: clicks/Enter/Space did not
activate Ask, including after resetting the CUA session. Input is paused while
the owner tests one manual Ask click to distinguish app from helper failure.
No second restore receipt exists at this checkpoint. No message was sent.

The owner's later `Yes, coordinate both chats` answer in Agent Suite was read
and verified before this chat sent coordination replies to Suite and StoryLens.
This supersedes the earlier no-coordination-message decision for that scope;
it does not authorize competing desktop/GPU work or any message sending in
WhatsApp, Instagram, Gmail or Telegram.

## Earlier acceptance records

Updated: 20 October 2026. All entries below require the real running Cortana
application on this laptop. Enter commands in Cortana, observe its response,
then inspect the target app. A chat claim alone never passes an action check.
Do not send any demonstration message or invite. Keep the app visible.

Status key: PENDING = not yet verified in this run; FAILED = observed failure;
PASSED = actual visible outcome verified; BLOCKED = specific prerequisite absent.

| # | Instruction / scenario | Required visible result | Status / actual observation |
|---|---|---|---|
| 1 | `WhatsApp: message Rohit New saying "Hello"` | Existing installed WhatsApp, exact Rohit New conversation, Hello in composer, unsent | PASSED on retry at 23:24: real Cortana command returned verified draft; actual WhatsApp screenshot showed Rohit New header and Hello in composer, Send untouched. Original failure was ignored Unicode packet input; repaired literal paste with clipboard restoration. |
| 2 | `Open WhatsApp and message Rohit Kumar Hello`, then correct name to `Rohit New` | Greeting is body, correction changes recipient only, one draft | PENDING |
| 3 | Confirm the correct selected conversation and say `Just message him hello` | Preserved context; no repeated recipient/body questions | PENDING |
| 4 | Gmail draft to `vineetkd132@gmail.com`, formal attendance request for 21 January | Normal Chrome Default, sender vineetdas1903@gmail.com; one Compose with correct To, Subject and English Body; unsent | PASSED on 21 October live retry: actual Gmail screenshot shows the exact To address, subject Attendance Required for the Meeting on 21 January, and a formal English attendance request. One Compose; Send untouched. Repaired stale inbox controls, field-loading timing, and placeholder text misread as existing input. Reused the existing blank Compose on retries. Action verification took about 3.9 seconds after submission of the existing draft card; no subsecond full-pipeline claim. |
| 5 | Gmail recipient first, then dictated body, then `I already told you; continue the email` | Only missing details requested; existing body/recipient retained; same Compose | PENDING |
| 6 | Repeat the identical Gmail draft request | Reuse/verify same draft; no extra blank Compose | PENDING |
| 7 | Instagram draft to `Vineet Kumar Das`: `Hi, hello, how are you?` | Signed-in installed Instagram PWA; uniquely verified user; actual composer populated, unsent | PASSED after resolving duplicate display names with the visible exact username `thisis.vineet`: actual profile link, header and complete composer text verified on screen. Initial retries repaired search-input replacement/readback, asynchronous result loading, profile URL reading, and title changes when the unread count disappeared. Current sender shown in the app is `fantasy_legends91`; no account switch or Send action performed. |
| 8 | `Open Chrome`, `Open YouTube`, `Open ChatGPT`, `Open Calculator`, `Open VS Code` | Each real requested app/site opens; no isolated-profile login window | PENDING |
| 9 | `Open C drive for me` | C drive visible in Explorer | PENDING |
| 10 | Ask about visible screen / second chat with screen button | Fresh underlying screen; correct visible names/details; no invented absence | PENDING |
| 11 | Ask to open the currently visible Instagram chat section | Real Messages section opens, no HTTP500 or fictitious success | PASSED: `Open Instagram messages` in Cortana opened the actual installed PWA inbox with visible conversations. |
| 12 | Start Cortana normally | Greeting, mic active automatically, accurate status | PENDING |
| 13 | Owner speaks multiple successive English commands | Transcript appears promptly; each command completes; listening resumes without a button | PENDING — requires owner's microphone interaction |
| 14 | Owner speaks Hindi/Hinglish; WhatsApp/Instagram draft stays Roman script | Accurate meaning; no unsolicited Devanagari outgoing message; clear voice | PENDING — requires owner's microphone interaction |
| 15 | Stop voice during long answer | Audio stops immediately; answer remains visible; conversation resumes | PENDING |
| 16 | Turn mic off while speaking to someone else; turn it on again | No captured/background command while off; continuous conversation after on | PENDING |
| 17 | Stop a running operation | No further app input; user apps/drafts remain open; next command works | PENDING |
| 18 | StoryLens active / idle transitions | Never interrupt active StoryLens; bounded clear wait status; Cortana works when idle | PENDING; current run started with Cortana model resident and StoryLens absent from loaded models |
| 19 | Create private demo meeting tomorrow 10AM, 15min, no guests | Correct private calendar entry or precise missing-integration blocker; no invitations | PENDING |
| 20 | Show a coding problem; request a concrete edit | Correct source inspected, reviewed change and actual result, no guessed file | PENDING — needs a specific authorized source task |
| 21 | Windows sign-in startup | Cortana starts after actual sign-in, mic preference respected | PENDING — requires real sign-in/reboot; do not reboot during user's work |
| 22 | `WhatsApp: message Vineet (You) saying "Hi, hello, how are you?"` | Switch from Rohit New to exact self chat; separate correct unsent draft | PASSED on live retry: actual WhatsApp screenshot shows exact self-chat header and the complete unsent text. Controller independently read back the text and returned draft_ready. Earlier retries exposed duplicate providers and SetFocus activating an embedded Chrome host; physical click plus verified native host-child focus fixed entry. Latest action stages completed in approximately 4 seconds; no subsecond full-pipeline claim. |
| 23 | Unknown WhatsApp contact, then correct to a known name | Clear no-match response; no message entered into wrong chat; correction retains body | PENDING |
| 24 | Recipient correction after an incomplete or failed attempt | Latest recipient overrides old one; only intended body typed | PENDING |
| 25 | Repeat a prepared WhatsApp request verbatim | Same chat and exact single body; no doubled text, no extra window | PENDING |
| 26 | Partial WhatsApp name matching multiple contacts | Ask for the exact contact; do not choose arbitrarily or alter the current draft | PENDING |
| 27 | Ask an unrelated question while a failed draft is pending, then resume | Answer the question without turning it into a message; preserve the pending message for explicit resumption | PENDING |
| 28 | Cancel after a failed or incomplete draft | Clear that pending request, leave user apps/drafts alone, accept the next independent command | PENDING |
| 29 | Repeat a request for a conversation with different existing draft text | Preserve that existing text and explain exactly why entry stopped | PENDING |
| 30 | Vision: identify WhatsApp header, search result and unsent text | Correct facts from the current underlying screen; distinguish search results from active chat | PENDING |
| 31 | Vision: describe an Instagram page and its Messages control | Correct visible facts without stale WhatsApp/Gmail context | PENDING |
| 32 | Vision: explain a visible error/code fragment | Quote/identify the actual visible error; do not invent a file or completed fix | PENDING |

Do not report a task as fully working while its row is pending or failed.
Observed GPU timings or build checks are supporting diagnostics, not acceptance.

## Added by the owner on 21 October

After five to six Instagram checks, prepare five distinct Gmail drafts for
Amazon, Flipkart, Myntra, Meesho and ASUS with fictional stories, all unsent.
Verify real To, Subject and Body for each; save previous drafts between checks.
Then test real laptop folders/files, invalid/ambiguous paths and app/website
open/close workflows. Never claim every file/path is supported from a sample.

Company inbox sources verified on 21 October, for unsent test drafts only:

- Amazon: grievance-officer@amazon.in — published organizational grievance channel, [Conditions of Use](https://www.amazon.in/gp/help/customer/display.html?nodeId=GLSBYFE9MGKKQXXM).
- Flipkart: grievance.officer@flipkart.com — published organizational grievance channel, [Grievance mechanism](https://www.flipkart.com/pages/grievance-redressal-mechanism).
- Myntra: customergrievance@myntra.com — published organizational grievance channel, [Grievance mechanism](https://www.myntra.com/grievanceredressal).
- Meesho: query@meesho.com — published official app support contact, [Official app listing](https://app.meesho.com/2yoV/r99th0qd?via=0&from=).
- ASUS: Online_India@asus.com — published India online store inbox, [ASUS Education Store](https://in.store.asus.com/asus-for-education).

These addresses are not a recommendation to send a test complaint. All stories
must be labeled fictional and stay unsent. No real order, payment, warranty or
private customer details are to be invented.

The earlier foreground coordination question was answered: continue the live
checks with Cortana/WhatsApp visible. The owner subsequently stopped Computer
Use with Escape, then explicitly resumed and requested retries until working.
StoryLens retains first GPU priority; the owner confirmed the GPU is free, and
the new run verified no Ollama models loaded before warming Cortana's 9B model.
The owner authorizes choosing visible WhatsApp/Instagram names and random demo
email addresses for unsent-only drafting checks. Use example.com for invented
email test addresses; never infer a real person's private email address.

## Multiple-recipient live demonstrations

| Service | Recipient | Exact body | Status |
|---|---|---|---|
| WhatsApp | Rohit New | Hello | PASSED: actual unsent composer verified |
| WhatsApp | Vineet (You) | Hi, hello, how are you? | PASSED: actual unsent composer verified |
| WhatsApp | Vineet Gaurav (visible in the app) | Hi, hello, how are you? | PASSED after replacing inert accessibility row action with verified physical row click; actual header and unsent text visible |
| WhatsApp | Gaurav Amrute (visible in the app) | Hello | PASSED: natural instruction “Open WhatsApp and message Gaurav Amrute Hello.” correctly separated name/body; actual header and unsent text visible |
| WhatsApp | Ashmit Dtu (visible in the app) | Hi, hello, how are you? | PASSED on exact live retry after adding “platform par NAME ko message karo, BODY” parsing. Real screenshot shows Ashmit Dtu header and complete unsent body; first attempt omitted recipient and was repaired. |
| Instagram | thisis.vineet (Vineet Kumar Das) | Hi, hello, how are you? | PASSED: exact active profile URL and complete unsent text verified in the actual installed Instagram app |
| Instagram | adityapratap2704 (Aditya Pratap Singh) | Hi, hello, how are you? | PASSED: switched to exact profile and complete unsent composer; repaired launcher title-based duplicate-window bug and blank-name Search field identification |
| Instagram | niteesh5127 (display name nitesh.ai) | Hi, hello, how are you? | PASSED: natural correction “Use the username niteesh5127 instead. Keep the same message.” retained the body and selected the exact account without asking again |
| Instagram | prince_jha_345 | Hi, hello, how are you? | PASSED: actual header profile URL and unsent composer verified; no retry needed |
| Instagram | vineet_2919 (Vineet Kumar) | Hi, hello, how are you? | PASSED after repairing account-result scoping and username mentions in mutual-follow descriptions. Actual DM thread/profile URL and complete unsent composer verified. Earlier failed selection opened a profile from a chat-history link; no message was entered there. |
| Gmail | vineetkd132@gmail.com and example.com demo addresses | English draft with explicit subject/body | PENDING |

The five WhatsApp demonstrations above were requested and submitted through
the visible Cortana chat. Direct WhatsApp navigation was used only to clear a
filter and read additional contact names, not to enter any message. No Send
button was pressed. These are typed-action acceptance checks, not full verbal
acceptance or a guarantee about every possible contact/layout.

Unknown-name observation: `CortanaNoSuchContact842` produced no search results;
the existing Ashmit Dtu body remained unchanged. The response incorrectly called
zero matches ambiguous. Separate no-match/multiple-match messages are written
and loaded into the private worker; retry and natural correction still pending.

21 October Instagram observations: all five requested practical recipient checks
now passed through Cortana. The installed app remains signed in as
`fantasy_legends91`; no sender/account switch was made. Duplicate display-name
checks stopped before message entry. The local correction model was confirmed
fully on GPU (7,173,308,414 bytes total and VRAM). Passing these typed examples
does not establish universal contact/layout support or verbal acceptance.

## Five company Gmail drafts — 21 October

All five were requested in Cortana and verified in the real Gmail Compose, using
the normal signed-in Chrome profile and sender vineetdas1903@gmail.com. None was
sent. Subjects start with `Cortana test - fictional` and stories explicitly say
there is no real order, complaint or purchase.

| Company | Verified To | Fictional story | Observed result |
|---|---|---|---|
| Amazon | grievance-officer@amazon.in | Gift book delivery | Correct To, Subject and English Body; saved unsent during recovery |
| Flipkart | grievance.officer@flipkart.com | Headphone return | Correct fields; Body repeats the Subject header — formatting repair pending; saved unsent |
| Myntra | customergrievance@myntra.com | Shirt size exchange | Correct fields; Body repeats the Subject header — formatting repair pending; Cortana saved it before Meesho |
| Meesho | query@meesho.com | Missing desk-organiser parcel | Exact requested body, no repeated subject; Cortana saved it before ASUS |
| ASUS | Online_India@asus.com | College coding-club workshop laptop | Exact requested body and subject, verified unsent |

This sequence needed adapter repairs and manual Save & close during reload
recovery. It was not a clean uninterrupted five-request pass. The last two
requests independently verified and saved the previous draft automatically
before opening the next Compose (approximately 1.7 and 2.0 seconds respectively).

## File, folder, vision and closure checks — 21 October

| Cortana command | Actual result |
|---|---|
| Open C drive for me | PASSED: Explorer shows OS (C:) and its root contents |
| Open D:/Cortana/docs | PASSED: Explorer breadcrumb is New Volume (A:) > Cortana > docs |
| Open "C:/Users/Vineet Kumar/Documents" | PASSED: exact user Documents folder opens; spaces and quotes handled |
| Open E drive | PASSED failure handling: accurately says the configured E: folder does not exist; only A: and C: are mounted |
| Open D:/Cortana/documents/does-not-exist-842.txt | PASSED on exact retry: deterministic open_path checked existence and reported No file or folder exists at that path. Initial inference-only handling of filenames containing “not” was repaired |
| Open "D:/Cortana/documents/Cortana live demo.txt" | PASSED on exact retry: actual Notepad shows the complete harmless three-line note. Initial association launch hit Windows' app chooser; text files now use the configured Notepad executable directly, without changing Windows defaults |
| Ask about my screen, then identify app/file and quote its three lines | PASSED: actual Cortana capture attached; local model correctly identified Notepad, Cortana live demo.txt, and all three lines. This is one current-screen vision example, not universal vision acceptance |
| Open Calculator | PASSED: actual Calculator window visible |
| Close Calculator | PASSED on exact retry: Cortana reported Closed Calculator, and the actual Calculator window disappeared. Initial failure missed the ApplicationFrameHost container; verified child-process matching repaired |
| Open example.com, then Close example.com | PASSED: real page opened in the existing normal Chrome; only that selected tab closed. Gmail and its unsent draft stayed open |
| Retry Myntra fictional size-exchange story | PASSED formatting retry: real To and Subject verified; body starts Hello and has no duplicate Subject header. Older saved test drafts remain unchanged |
| Unknown WhatsApp name, then Use Rohit New instead. Keep the same message | PASSED on retry: no-match reply accurately distinguishes absent contact; previous Ashmit Dtu composer preserved. Correction reached exact Rohit New and one Hello. Final verification initially hit stale WebView controls; repaired and Cortana's Continue action verified draft_ready; actual composer rechecked |

The relocated floating button still gives invalid automation geometry/blank
capture, so it is not accepted yet. Keyboard shortcut collision fallback is
implemented but not yet live-verified. These remain separate from the passed
main-window screen button. No verbal acceptance claimed.

## Fresh-session vision run — 21 October morning

The desktop session had changed: Cortana/Ollama were stopped. Starting Ollama's
desktop app exposed a model lookup failure through its home-directory junction.
Existing Q6_K 9B model and vision-projector blobs were present. The previous
Cortana manifest was backed up in tmp before re-registering those same blobs;
no model weights were downloaded. A directly started local server using the real
`C:/Ai Models/ollama` directory resolves the model and advertises vision/tools.
The desktop Ollama app's startup path still needs a permanent repair; this is a
live-session recovery, not verified Windows sign-in acceptance.

The first attempted Explorer description coincided with the StoryLens workflow
changing the foreground. Cortana described Chrome's Storylens Local Publisher
extension page, so that attempt does not establish Explorer accuracy.
The screen shortcut Ctrl+Alt+S attached a fresh capture successfully.
The floating button still failed Computer Use hit-target verification.

The visual action request “Open the folder named docs visible in this screenshot
using its full path from the Explorer breadcrumb. Identify the parent folder
first, then use the actual folder-opening tool.” failed with HTTP 400. Actual
Ollama diagnostics: 4,197 prompt tokens exceeded the 4,096-token context.
Image-bearing requests now reserve at least 8,192 context tokens. PASSED on the
exact live retry: Cortana identified D:/Cortana from the fresh Explorer image,
called open_path, and the actual D:/Cortana/docs Explorer window opened. The
response identified the docs folder, Cortana parent and A drive correctly.
Model and vision encoder were confirmed on CUDA.

PASSED changed-screen reading: a new capture after that action correctly yielded
folder docs, first filename cortana_architecture, last filename VOICE_MILESTONE_1,
and 9 items. Actual Explorer agreed. Ollama's warm processing diagnostic was
about 4 seconds for that read; no subsecond vision claim. This proves the bounded
folder example, not arbitrary mouse clicks or code edits on every application.

PASSED WhatsApp perception: fresh native app image showed the chat list and no
active conversation. Cortana correctly identified the second chat as Vineet
(You), the right pane as idle, and its Send document / Add contact / Ask Meta AI
buttons. It did not repeat the earlier claim that no chat list was visible.

Visual drafting initially FAILED: “Prepare a WhatsApp draft for the second chat
from the top visible in this screenshot. Use its exact visible name as recipient
and the message Hi, hello, how are you? Leave it unsent.” produced no tool call;
the false-success guard rejected the model's response. No draft was entered.
Visual communication requests now use image-backed structured extraction and
always delegate the extracted recipient/body to the verified draft controller.
The first structured retry still asked for a recipient despite the readable
second row. The extractor now has a focused, image-only contact-resolution
prompt instead of the normal chat prompt, counts group/self chat rows, and
preserves the user's quoted Roman-script message in code. Exact live retry is
still pending: StoryLens started another generation and desktop workflow, so
further GPU/desktop validation was deferred in accordance with its first
priority. No successful visual WhatsApp draft is claimed for this morning run.

Final guard added: visual recipient extraction cannot inherit an older pending
recipient, and old recipient names are excluded from its prior context. This
last guard is written but awaits backend reload and live retry. Cortana's mic
remains temporarily off during controlled testing. StoryLens was confirmed
actively rendering its first of three selected Shorts, so no further GPU or
desktop input was issued for Cortana.

## Expanded automation request — 21 October

The owner reaffirmed **Type only; I press Send** and then explicitly removed
Telegram from the current scope. The current communication work covers
WhatsApp, Instagram and Gmail. A requested recipient name should lead to contact search, exact
recipient verification and visible composer text, never an automatic send.
Ambiguous names require one choice; missing/unknown contacts must not receive
guessed identities or reused messages. Telegram integration work is deferred;
no Telegram installation, login, draft or message is part of this acceptance run.

Source changes made while StoryLens controlled the desktop (not loaded or live
accepted yet):

- Screen requests about a product, code, setting or visible contact on the
  current screen can trigger the capture flow. Quoted message text and body
  clauses cannot grant screen capture permission.
- A screenshot action phrased “Can you fix…” retains action tools instead of
  being treated as read-only. Read-only questions still receive no action tools.
- Code-edit requests retain file discovery and actual-source reading tools;
  applying an edit still requires the reviewed diff.
- Settings requests without code/file context receive live control inspection
  and reviewed click tools rather than source-code edit tools.
- A fully specified failed draft no longer captures every unrelated follow-up
  as replacement message text. Explicit corrections can continue the draft.
- Telegram messaging requests report that it is outside the current scope;
  generic inputs cannot bypass that limit. No Telegram fallback was added.

### Next visible acceptance scenarios

| Command through Cortana | Expected visible result | Observed/status |
|---|---|---|
| Repeat the second-visible-WhatsApp-chat draft with a fresh capture | Vineet (You) selected and exactly one greeting in the composer; unsent | Pending final extraction fix reload; StoryLens desktop activity blocks live retry |
| Tell me the details of this product on my screen | Current capture; accurately quote visible product/model/price, identify missing details | Pending |
| Can you fix the error in the code on my screen? | Current capture; locate/read actual source and present a specific reviewed diff | Pending; use a harmless local demo source |
| Can you change this setting on my screen? | Identify the actual setting and show a specific action for review; no false completion | Pending; use a reversible non-security setting |
| After a failed contact search, ask a product/screen question | Product question answered; prior unsent message not overwritten or executed | Pending |
| Speak two successive instructions without touching the mic button | Both real microphone turns transcribed and handled; microphone stays on | Pending owner's verbal interaction; typed checks cannot establish this |

StoryLens remained active in account-switch/upload checks during this work.
No Cortana GPU inference or desktop input was started concurrently. Python
syntax checks and the frontend build are supplementary checks only; they do
not establish that these new workflows work live.

## Qwen3-VL 8B Q4 vision migration — 22 October

Owner request: use Qwen-VL 8B Q4 for vision. Selected official artifact:
`qwen3-vl:8b-instruct-q4_K_M`; conversation stays `cortana-local:9b`.
Download started through the existing Ollama server. Initial GPU check: RTX
5070 Ti Laptop, 12,227 MiB total, about 1,204 MiB used; no Ollama model loaded.
Ollama version 0.40.5. No other project's model was stopped or evicted.

The main screenshot chat path previously ignored `ollama_vision_model` and sent
images to the conversation model. Routing now selects the vision model for any
image-bearing message history, including subsequent tool rounds and structured
visual contact extraction. The explicit screenshot analyzer uses the same
selected model and reserves at least 8,192 context tokens. Status exposes the
configured vision model separately, and Settings displays it.

| Command through the running Cortana app | Expected result | Current result |
|---|---|---|
| Read this fresh Explorer screen: identify folder, first/last item and item count | Correct visible facts; reply identifies qwen3-vl:8b-instruct-q4_K_M | BLOCKED: Windows WhatsApp camera-permission modal requires owner input |
| Open the docs folder visible on the current Explorer screen | Actual D:/Cortana/docs opens through the app tool | BLOCKED by the same modal |
| Inspect the fresh WhatsApp screenshot and identify a visible chat | Correct displayed name without invented hidden account details | BLOCKED by the same modal |

Source syntax checks are supplementary. Installation is verified below; GPU
placement and live screen acceptance are still unverified.

The real Cortana desktop was started visibly with `--mic-off`. A Windows
WhatsApp camera-permission dialog covered the desktop, so no app input was
issued through it. The owner was asked to handle this privacy prompt manually;
installation and source work continue independently. The new frontend build
contains the separate Vision model status in Settings.

Installation completed successfully on 22 October: Ollama verified SHA-256
digests and wrote the manifest. Local `/api/show` confirms family `qwen3vl`
with `clip`, 8.2B parameters, Q4_K_M, llama.cpp runner, and completion/vision/tools
capabilities. Installed size: 6,190,971,795 bytes. Manifest digest:
`70e58e37beb15464e19aa903dedb2cba828b89c0fb186f75ff2738c7347b96eb`.
The effective configuration reports conversation `cortana-local:9b`, vision
`qwen3-vl:8b-instruct-q4_K_M`, cloud fallback false. Cortana was launched after
the routing/configuration changes and with the new frontend build.

Final desktop observation still showed the Windows WhatsApp camera-permission
dialog. No input was sent through that modal. The three live acceptance rows
above remain BLOCKED by the owner-handled privacy prompt; GPU placement and
actual screenshot answer quality for this new model are not yet verified.
The microphone remains temporarily off for controlled setup. No communication
was sent and no other project's workload was stopped.
