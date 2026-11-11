# Pocket Tracker

A private Android app that collects accessible SMS and selected Gmail alerts, reconciles transaction evidence locally, and generates monthly PDFs. Personal development build; no paid middleware or cloud AI.

## On your phone

1. Install the APK (the build agent can install over your approved USB debugging connection).
2. Open **Setup → Allow SMS access** and accept Android's prompt.
3. Complete [GOOGLE_SETUP.md](GOOGLE_SETUP.md), then **Connect / reconnect Gmail**.
4. Allow report notifications and, optionally, payment-notification access for Paytm, Slice and BHIM. On Realme, permit background activity for Pocket Tracker in app/battery settings.
5. Leave the app installed. Reports appear in **Reports** automatically after month end; previews are optional.

## Live tracking (0.2)

- New SMS is captured directly and signals the UI immediately; provider catch-up reconciles the same message without a second count.
- Optional Paytm, Slice and BHIM notifications appear as provisional alerts until strongly matched to bank evidence. Other apps are ignored before their notification content is read.
- Explicit payment notes in source alerts appear on cards and PDFs, including notes from uniquely matched email/app evidence. Notes kept only within the payment app are inaccessible.
- Gmail checks about every 15 minutes when Android permits. Initial-import batches continue automatically with a short scheduled delay and persist their progress.
- The actual installed phone completed its 292-message selected-email import. Google OAuth is now In production; Realme background activity is enabled. See BUILD_STATUS.md for detailed evidence and limits.
- Monthly PDFs are automatic. The October 2026 preview has been generated on the phone; previews remain marked as incomplete because the month has not ended.

## Build

Windows prerequisites: JDK 17/21, Android SDK platform 35, Gradle 8.12.1. The workspace uses AGP 8.8.2 and pinned dependency versions.

```powershell
.\build.ps1
.\build.ps1 -Install
```

APK: `app/build/outputs/apk/debug/app-debug.apk`.

Tests: `core/build/reports/tests/test/index.html`. Android lint: `app/build/reports/lint-results-debug.html`.

## Structure

- `core`: framework-free Java money extraction, matching and aggregation, with unit tests.
- `app`: native Android UI, encrypted SQLite message storage, SMS provider, WorkManager, Google AuthorizationClient, Gmail REST client and Android PDF rendering.
- `GOOGLE_SETUP.md`: project registration and user-consent steps.
- `ARCHITECTURE.md` / `FEASIBILITY.md`: original design and constraints. This implementation uses Java/native Android UI and SQLiteOpenHelper instead of the originally proposed Kotlin/Compose/Room, reducing the initial dependency surface. The domain remains independently testable.

## Boundaries of version 0.2

- First SMS/email window: 100 days. Older messages are not included automatically in this version.
- Extraction is conservative generic rules, not trained AI. Unsupported bank templates and ambiguous money amounts appear unresolved and are excluded from confirmed totals. Validate real bank templates before relying on totals.
- Reference matches combine evidence. Missing references remain conservative; legitimate events can be unresolved. Account/card last-four suffixes can collide across banks and require future explicit institution mapping.
- Recognizes refund, repayment, card-settlement and cash-withdrawal wording. Does not yet provide a fully audited loan ledger or link every partial refund to its original purchase. Own-transfer counterpart detection is an indication, not verified account ownership.
- All amounts currently supported are INR; other currency alerts are not supported.
- Gmail connects directly to Google. Tokens are acquired by Google Play services; no token, password or client secret is written into app storage by this app.
- Content is encrypted with an Android Keystore key. Minimal message IDs/source timestamps and settings are app-private, unencrypted metadata. PDFs are private unencrypted files, exposed to a PDF viewer only when opened by the user. No remote analytics or automatic backups.
- No actual fraud verdict: local suspicious-pattern flags only. The app never opens links, sends messages, blocks senders or moves money.
- Background timing is subject to Android/Realme scheduling. Force-stop pauses automation until reopened. PDFs disclose missing data; no requirement for routine user review.
- Gmail registration, consent and the initial import were verified on the actual account. Multi-day unattended execution and future token renewal remain ongoing operational checks; no claim of lifetime uninterrupted access.
- APK is currently a development build, not a reviewed production release. USB debugging can be turned off after installation; app operation does not need a laptop connection.
