# Pocket Tracker 0.4.0 transfer and Money Tracker handoff

This is the working Windows/Android Pocket Tracker source and a signed APK for package **in.pocketledger.app**, version code **4**. The Android app collects bank SMS, selected Gmail, and optional Paytm, Slice, and BHIM notifications. It reconciles evidence on the phone, serves a private laptop dashboard, and generates monthly PDFs. The laptop companion reads the same phone ledger through certificate-pinned TLS. There is no paid middleware or cloud AI.

## On your other Windows laptop

1. Copy the transfer ZIP and its matching .key file using a private transfer method. Extract the ZIP. Keep the .key outside the extracted project, away from Git and chat uploads.
2. Open the extracted project folder in Codex. Have it read this file and TRANSACTION_UPDATE_STATUS.md first. README.md and BUILD_STATUS.md include older version history.
3. With Node.js installed, restore the private files into this extracted Pocket Tracker folder before building an update. Run this in PowerShell, replacing the example path with where you saved the key file:

   ~~~powershell
   node .\restore-private.cjs "C:\path\to\Pocket-Tracker-0.4.0-Transfer.key"
   ~~~

   The restore script verifies the encrypted bundle and preserves any existing files. It restores the original Android signing keystore under .android-home, the laptop pairing file under laptop/.private, and the private reference material under transfer-private-reference. Keep these folders out of Git and uploads. The .key file unlocks the encrypted bundle. Store or transfer it separately from the ZIP where practical.

4. For the existing phone and laptop dashboard, double-click Start-Pocket-Tracker.cmd. It expects Node.js at the standard Windows installer location. The dashboard is at http://127.0.0.1:43820. The restored pairing works if the phone still uses the same Wi-Fi address, certificate and token. If any changed, use Pocket Tracker on the phone, then **Setup → Pair laptop**, and pair from the dashboard. The phone and laptop need to be on the same network with the phone service running.
5. For a standalone Android build, use JDK 17 or 21 and set JAVA_HOME. Install Android SDK platform 35 and build-tools 35.0.0 in the normal Android SDK location for your Windows user. Run .\build.ps1. The included Gradle wrapper downloads Gradle and dependencies as needed. Restore the original signing key before building an in-place Pocket Tracker update. The APK already included under install/ is signed with that key.

## Merge into your Money Tracker project

Keep the extracted Pocket Tracker folder alongside the existing Money Tracker project. Open both folders in Codex and give it this instruction:

> Use the extracted Pocket Tracker 0.4.0 folder as a reference and merge its features into my existing Money Tracker project. Read TRANSFER.md and TRANSACTION_UPDATE_STATUS.md first. Inspect Money Tracker's framework, Android package ID, signing identity, storage model, transaction schema and existing auth before changing it. Preserve existing records and IDs. Port the verified parsing, matching, permissions, reports and dashboard flow in small steps. Keep the original Pocket Tracker APK and phone ledger intact while verifying the merge. Never commit or display the restored private files.

- core/src: plain Java INR parsing and conservative evidence matching with regression fixtures. Keep amounts in integer paise, stable transaction identities, one event for matching SMS/Gmail, distinct events for repeated payments with distinct references, and separate unresolved or provisional items.
- app/src/main/java/in/pocketledger/app: SMS, Gmail, payment-notification intake, encrypted storage, work scheduling, PDF reports, local dashboard API and paired phone server. Preserve consent boundaries and background scheduling behavior. Payment notes are available when a source alert includes them.
- app/src/main/assets/dashboard and laptop/: responsive UI, monthly Insights, bank/source/card filters, budgets, recurring payments and PDF access. The companion binds to localhost and talks to the authenticated phone API. A target project with its own frontend can reuse the behavior and API contract while adapting the UI.
- app/src/androidTest and core/src/test: regression checks. VerifiedReceiptImportTest is a one-time, operator-only recovery path and should never be run automatically. The private receipt reference and audit artifacts are for local verification.
- GOOGLE_SETUP.md: the existing Google project is noble-mantis-513214-g1. Gmail uses the Android app's package ID and signing certificate, with authorization on the phone. The APK and included keystore match SHA-1 2D:CF:C4:E6:35:D8:2C:32:2F:75:F3:29:A4:86:D0:DF:12:67:1B:88. If Money Tracker has a different package ID or signing certificate, configure a matching Android OAuth client in the user's Google project and reauthorize Gmail there. Keep its existing signing identity if it already has users or stored data.

The transfer contains the available Pocket Tracker laptop credentials and reference artifacts. The ledger, saved budgets, recurring items, Gmail authorization, and Android Keystore keys remain on the existing phone. The paired companion can access the existing phone ledger. A different Android app package needs its own authorized data import or a fresh SMS/Gmail import. This project uses no laptop-side Gmail API key or client secret. Android USB debugging uses fresh authorization on the other laptop.

### Verify after merging

Test parsing, distinct equal-amount payments, duplicate SMS/Gmail evidence, refunds, pending/excluded alerts, app permissions, PDF totals, and pairing with sample data before any live install. Existing laptop checks can be run with node --test laptop/server.test.cjs. The Android build script runs the core tests, APK assembly and Android lint.
