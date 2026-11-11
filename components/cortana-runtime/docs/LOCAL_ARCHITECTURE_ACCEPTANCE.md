# Local Architecture implementation and acceptance

## 5 November resumption

The owner lifted the resource hold and assigned Cortana the only active project
slot. The prior pause marker was archived. Reused the visible desktop instance,
restarted its owned backend from Settings, and reloaded its interface. No second
service instance was started. The original 12-page PDF hash matched the saved
extraction. Calendar and verified email delivery are additional owner requirements.

| Page | Reconciled capability | Current acceptance |
|---|---|---|
| 1 | Local assistant, reasoning/voice, app and workspace functions | Actual 9B Q4 typed reply passed. Real microphone timing and remaining actions open. |
| 2 | Tray, typed controller, brokers and local state | Existing visible runtime recovered. Broader route verification open. |
| 3 | Exact model profiles, switch, vision, offline | 9B Q4 observed fully in VRAM at 4K. 14B switch, image grounding and offline demo open. |
| 4 | Desktop/file/app/browser/action tool registry | Named workspace repair recorded below. File/app inventory and remaining actual outcomes open. |
| 5 | Both browser profiles, timestamps and four messaging surfaces | Workspace extension staged. Both browser installs and live capture pending. Telegram and verified chat sender identities remain gaps. |
| 6 | Exact review and guarded delivery | Durable approval broker implemented. Latest owner instruction is manual Send after Cortana prepares and verifies the draft. Staged self-delivery route removed before sending. |
| 7 | Document extraction, retrieval, tasks and lifecycle | Local OCR supplemental evidence exists. Live retrieval, conflicting dates, embedding and wake checks open. |
| 8 | Labelled GCP capture and restore | Demo notes/project exist. Chrome and Brave time/pause and local receiving apps need proof. |
| 9 | Measured diagnostics and remedy comparison | One backend measurement exists. Live reports and approved before/after checks open. |
| 10 | Permissions, retention, stop, restart and reconciliation | DPAPI/WAL, revision checks and request recovery exist. Interrupted write, auth expiry and Stop need live cases. |
| 11 | Live release gate | The 70-case suite is incomplete. Contract checks remain supplementary. |
| 12 | Setup and receiving-app handoff | Source identity confirmed. Each unfinished route above remains a release blocker. |
| Added | Calendar availability, private event/meeting creation and verification | Account-bound opening and scoped Schedule read implemented. Frozen timezone-aware event review opens the provider form. Live availability and persisted save acceptance remain open. |

Live 9B reasoning test: `Why does the sky look blue? Answer in one short sentence.`
Cortana visibly answered with Rayleigh scattering and displayed `cortana-local:9b-q4`.
Ollama reported 5,507,330,866 resident bytes and the same number of VRAM bytes at
4096 context. Submission 1793821031.046, residency logged 1793821042.1228342,
inference finished 1793821043.4405923. Roughly 12.4 s backend total from submit,
including 0.866 s prompt and 0.416 s generation. No voice timing inferred.

Source: `D:/Chrome Downloads/Cortana_Local_Architecture.pdf`, 12 pages, SHA256
`30569f65373b694dc9cf168b3337f18d203d82c2894709ad9b86d59098d087e3`.
All twelve pages read on 4 November 2026; page 2 rendered and inspected.
Existing application/source reviewed before implementation. Earlier acceptance
records are historical evidence, not passes for this revision.

## 4 November implementation checkpoint

The matrix below preserves the initial gap assessment. Current implementation:

- Independent 9B/14B Q4 aliases and exact license provenance are recorded.
  Profile switching, shared GPU locks and tool-call admission are implemented;
  actual model probes/residency/latency acceptance remain pending.
- WAL records, request/action recovery, revision checks and cancellation are
  integrated. Restart/Stop still require actual application checks.
- Chrome/Brave extension, native host, selected-tab capture and paused YouTube
  restore are prepared. Owner approved both installations, host registration
  and YouTube access. Neither browser has been installed/verified in this run.
- Device-bound workspaces support explicit files, folders, VS Code projects,
  apps and browser profiles with per-item restore results. Owner selected a
  labelled demo. Reviewed periodic capture is implemented and remains disabled;
  it refreshes only the saved selection. Live restoration remains pending.
- Atomic source indexing, FTS, local embeddings, source-backed deadlines,
  invalidation, reviewed export/removal/history pruning are implemented.
  Windows OCR read both the fictional image and scanned PDF locally; these were
  backend checks, not Cortana UI passes. A local Poppler copy removes dependence
  on Codex's PATH. Embeddings and wake notification acceptance are pending.
- Diagnostic sampling, evidence/hypothesis separation, process inspection,
  reviewed own-model unload and report comparison are implemented. One real
  backend sample exists; actual Cortana UI tests remain pending.
- Draft version/hash/expiry/single-use/uncertain-send contracts exist. Native
  adapters remain manual-send-only. Telegram integration and native transaction
  acceptance remain unfinished. Owner authorized clearly identified recipients
  visible in the apps and assistant-written demo text, with zero sends.
- New audit entries redact argument values and free-text summaries. Cortana's
  unused legacy cloud key was migrated from its .env to a Windows user-bound
  DPAPI vault and round-trip verified. No cloud request/account change occurred.
  Ordinary document/file readers now exclude Cortana's private memory/logs.

Windows PDH disk activity, transfer latency, queue, commit and paging counters
and the current power plan were read successfully without changing settings.
Diagnostic sampling now includes these measurements with missing-sensor markers.
Native WhatsApp/Instagram sender-account proof is still a live-integration gap;
recipient/header checks alone do not establish the sender account.

Supplementary checks: **328 Python tests + 9 subtests and 29 desktop tests pass**;
frontend build and lint pass. These are not the PDF live release suite.
No desktop input has been issued in this run while editing chats remain active.
Owner initially instructed waiting without coordination messages. A later direct
owner reply in Agent Suite authorized coordination with both chats; that reply
was verified before coordination messages were sent. Desktop/GPU use still waits
for availability. Labelled demo files are under `documents/Architecture Demo`.

Suite subsequently reported a real Cortana named-workspace restore HTTP 500.
Named restores now resolve locally to an exact reviewed revision, and expected
GPU admission failures return a clear service response. 85 focused checks passed;
the exact visible retry remains pending. See LIVE_ACCEPTANCE_CHECKLIST.md.
Native messaging also now explicitly sets Windows stdin/stdout to binary mode,
per https://developer.chrome.com/docs/extensions/develop/concepts/native-messaging.

## Initial gap assessment (historical)

| ID | Pages | Requirement | Initial state before implementation |
|---|---|---|---|
| L01 | 1–3,11 | 9B Q4 default, installed 14B Q4 alternative, exact tags/digests/license/probes | Inventory confirmed; integration pending |
| L02 | 3,10 | Checkpointed explicit switch; no silent fallback; memory/latency evidence | Pending |
| L03 | 2–3 | On-demand vision; one heavy model; StoryLens priority | Existing vision; resource admission pending |
| L04 | 1–3,10 | Local-only, authenticated loopback, English response, Hindi/Hinglish inputs | Existing authentication/cloud denial; English correction pending |
| L05 | 2,4,10 | Typed tools, scopes, durable outcome ledger, cancellation/input lease | Existing validation/lease; durable lifecycle pending |
| L06 | 4,11 | Installed apps, normal close/save handoff, files/ambiguous names | Existing routes; fresh live checks pending |
| L07 | 4 | Incremental metadata search, canonical identity, permission filtering | Bounded scan exists; incremental index pending |
| L08 | 5,8 | Chrome/Brave native extension, profile/tab identity, versioned adapter | Missing |
| L09 | 5,8 | YouTube observed timestamp and paused restore, tab reuse | Missing |
| L10 | 8 | Named snapshots: notes/project/folders/apps/context/device; per-item restore | Missing |
| L11 | 8 | Explicit/opt-in snapshots, ambiguity, missing sources, preserve unrelated work | Missing |
| L12 | 7 | Selected imports, original hashes, page extraction and scan OCR confidence | Readers exist; index missing |
| L13 | 7 | FTS + local embeddings, permission-filtered sources and conflict evidence | Missing |
| L14 | 7 | Source-backed tasks, explicit/inferred dates, timezone, review and overdue reminders | Basic reminders exist; source tasks missing |
| L15 | 7,10 | Source change/deletion invalidation; inspect/export/delete/retention | Missing |
| L16 | 5–6 | WhatsApp/Instagram/email/Telegram draft adapters, exact identity and capabilities | First three exist; Telegram missing; fresh verification pending |
| L17 | 6,10 | Exact-payload approvals, expiry, edit invalidation, single-use send/reconcile | Existing manual-only send policy; transaction missing |
| L18 | 6,11 | Voice approval addressing/replay protection; no automatic demonstration send | Existing manual-only boundary retained |
| L19 | 9 | 30–60s RAM/CPU/disk/GPU/model/events/sensors measurements | Missing |
| L20 | 9 | Ranked evidence vs hypothesis, approved remedies, before/after comparison | Missing |
| L21 | 10 | WAL, secret protection, redacted logs, durable recovery/waiting states | Partial |
| L22 | 11 | 30 routine, 20 draft, 10 stale/recipient, 10 diagnostic scenarios | Not run; never infer release gate passed from unit tests |
| L23 | 3,11 | Offline local workflow, restart/auth expiry, model switching | Pending |

## Verified inventory

Ollama inventory on 4 November: `qwen3.5:9b-q4_K_M` (9.0B Q4_K_M,
digest `56671c2ab9385f9cfcb404638e32cd62d88e3501d44822208363c010179a3c90`),
`storylens-meaning:14b` (14.8B Q4_K_M,
digest `3e063cc851850dd66d654e180af6da339f1c603b6a11eb774a3bac69a57a8609`),
and `qwen3-vl:8b-instruct-q4_K_M` are installed. StoryLens model definitions
must not be edited. An independent Cortana alias can reuse installed weights.
No Ollama models loaded at initial inspection. RTX 5070 Ti Laptop: 12,227 MiB,
2,012 MiB used at that instant; this is not workload or thermal acceptance.

## Boundaries and pending external prerequisites

Live tests must originate in the visible Cortana app and inspect receiving apps.
Other editing chats are active; no simultaneous shared-desktop input or competing
GPU workload. Real microphone/sign-in and browser-extension permission steps
require the owner where applicable. Demonstration communications remain unsent.
No release, general reliability, or complete acceptance claim is made here.
