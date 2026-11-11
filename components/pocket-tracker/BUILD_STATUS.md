# Pocket Tracker — current implementation status

Updated 2026-10-30, Asia/Kolkata. User wants short English bullets and completion, not repeated offers to continue.

## Installed application

- Personal Android app: Pocket Tracker 0.2.0, package `in.pocketledger.app`, installed on Realme RMX5003 / Android 15.
- Original signing key retained. App-private records preserved through upgrades. SQLite schema v2 adds SMS receipt/provider reconciliation.
- SMS and report-notification permissions granted. User additionally enabled payment-notification access; listener reported connected for Paytm, Slice and BHIM.
- Incoming SMS is parsed and persisted directly through the SMS broadcast receiver's asynchronous short handler. The UI receives a private change broadcast; there is no intentional 10-second worker delay in the live path. Inbox reconciliation remains a separate catch-up task.
- A live SMS and its later provider row are reconciled without adding two transactions. Distinct provider rows are retained.
- Optional notification capture filters by installed package before reading content: `net.one97.paytm`, `indwin.c3.shareapp`, `in.org.npci.upiapp`. Payment-app alerts remain provisional until strongly matched to banking evidence, preventing totals from doubling.
- Explicit Note / Remarks / Memo text is extracted without treating the memo as another payment amount or status. Notes from matched email/app evidence appear in activity, latest payments and PDFs. Notes absent from SMS/email/notification content cannot be recovered from another app's private storage.
- Newest confirmed payments and provisional payment-app alerts appear on Overview. UI refreshes on stored data changes; cached messages and revision checks avoid repeatedly decrypting unchanged history.
- SMS capture works offline. Email is polled approximately every 15 minutes when Android allows it. Unfinished email batches schedule a continuation after 30 seconds, subject to Android scheduling and network availability; no six-hour batch gap remains.
- Email page position and fixed search-window anchor persist across batches. Daily local quota protection remains. Initial history window is 100 days.
- Local monthly PDFs are generated after month-end by scheduled work, with source gaps and unresolved evidence marked. PDFs are app-private; raw message content is encrypted with Android Keystore. PDFs themselves are not additionally encrypted.

## Google configuration

- Project: Pocket Tracker / `noble-mantis-513214-g1`, project number 9114737510.
- Gmail API was actually disabled despite earlier user confirmation. Enabled it through signed-in Chrome and verified Status: Enabled. The original HTTP 403 is resolved.
- Android OAuth client package/signature match the installed APK. Read-only Gmail connection and live message fetching succeeded.
- User explicitly approved changing OAuth status to production after automatic approval review blocked the final confirmation. A fresh browser observation subsequently showed **In production**. Do not click the confirmation again.
- A free static information website was prepared and published under the user's GitHub account: https://vineetkumar19.github.io/pocket-tracker-info/ . Privacy and terms pages are deployed and returned HTTP 200.
- Google branding homepage, privacy, terms and authorized domain `vineetkumar19.github.io` were saved successfully. Adding real URLs enabled the previously disabled Publish app button.
- Public repository `Vineetkumar19/pocket-tracker-info` contains only static information pages, no APK, source messages, account data or credentials. Source is in `public-info/`.
- Publishing is distinct from full Google verification. Personal-use exception applies to intended use; unverified-app warnings/user cap may remain. No paid assessment, billing trial, or paid service was activated.

## Validation

- 31 core tests passed, including ₹10 debits/credits, memo isolation, cross-source note matching, provisional notification handling, and a whitespace-heavy HTML email regression.
- 15 device tests passed after the final parser and provider-first race fixes: encryption, tampering, PDFs, Gmail diagnostics, live/provider SMS reconciliation, separate identical payments, source allowlist and a read-only local audit.
- Latest build/lint passed: `live-reconciliation-build.log`. APK installed; app restarted after instrumentation to resume work.
- Actual local audit processed 1,007 stored messages: 517 confirmed events and 164 unresolved alerts. Cold decrypt took 7,214 ms; full parsing/matching 2,767 ms. These are local aggregate diagnostics, not exported messages. Warm UI refreshes use cached messages; no absolute instant-delivery claim.
- The audit exposed a slow whitespace regex in the new memo parser. Fixed bounded horizontal whitespace matching and added a regression test. The earlier stalled audit was deliberately stopped; the final audit passed.

## Remaining verification / practical limits

- Initial selected-email import completed: 292 processed IDs; nonzero Gmail checkpoint 1793374183826; status `Connected · selected emails up to date`; gmail_more=false. September report status became `Ready · 2026-09` without the partial-source suffix. This means configured-source import completed, not that every financial event is perfectly parsed.
- Current initial account audit has unresolved alerts (93 multiple amounts, 33 unknown account, 23 no amount, 11 possible duplicates). They are excluded from confirmed totals and included in the PDF appendix. No fabricated amounts or automatic manual-review requirement.
- Need actual new incoming bank/payment alert to observe end-to-end delivery in normal use. Synthetic device tests prove persistence/reconciliation logic, not a real bank's delivery latency. Do not initiate a payment for the user.
- Realme Battery usage initially had Allow background activity OFF. Enabled it via the app-specific control and confirmed the dialog; verified ON and Don’t optimise. Android background app-op defaults to allow. This removes the observed OEM background restriction; Android can still defer work.
- Long-term multi-day operation and future token renewal cannot be proven within one session; handle revoked permissions and missing coverage visibly.
- Future Notes cannot be guaranteed if Paytm/Slice/BHIM omit them from available alerts. No accessibility scraping, private app database access, or bank credentials are used.
- INR only. Conservative matching; no perfect fraud detection, no complete bank statement reconciliation, no full loan or partial-refund pairing engine.

## Final handoff state

- Final installed update retains all permissions and data. App restarted to Overview after the final 15-device-test run; periodic work resumes. No laptop connection is required.
- October preview exists as `files/reports/PocketTracker_2026-10_preview_v1.pdf` (120,884 bytes at creation). Its current-month partial marker reflects the unfinished month; September completed-source monthly report is also present.
- User explicitly approved production status after the review block; browser then showed In production. No outstanding approval-review block remains.
- No real payment was initiated by the assistant. Real bank/payment-app delivery and future unattended operation remain external dependencies.
