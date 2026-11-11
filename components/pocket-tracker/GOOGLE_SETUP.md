# Pocket Tracker — your Google setup

- Project selected by you: **Pocket Tracker**, ID **noble-mantis-513214-g1**.
- Use your usual signed-in Chrome. No paid billing trial, API key, hosting or server is needed for this Android connection.
- Never paste passwords, tokens or client secrets into chat.

## 1. Enable Gmail

Open https://console.cloud.google.com/apis/library/gmail.googleapis.com?project=noble-mantis-513214-g1 and click **Enable**.

## 2. Configure Google Auth Platform

Open https://console.cloud.google.com/auth/overview?project=noble-mantis-513214-g1 . If you see **Get started**, configure:

- App name: **Pocket Tracker**.
- User support email: your own Gmail address selected in the dropdown.
- Audience: **External** for a personal Gmail account.
- Contact email: your own email.
- Data access: add **https://www.googleapis.com/auth/gmail.readonly** only.
- During initial testing, add your Gmail address as a test user.

For ongoing personal use, move the consent configuration out of Testing into the appropriate production publishing status. A personal-use exception can avoid verification submission; an unverified-app warning and user cap can remain. Do not submit a public verification application or pay for a security assessment for this personal local-only prototype without reassessing the scope. Do not claim month-long access has been tested just because the initial consent succeeds.

## 3. Register this Android app

Google Auth Platform → Clients → Create client → **Android**:

- Name: **Pocket Tracker Android**.
- Package name: **in.pocketledger.app**.
- SHA-1 certificate fingerprint: **2D:CF:C4:E6:35:D8:2C:32:2F:75:F3:29:A4:86:D0:DF:12:67:1B:88**.

This SHA-1 belongs to the development APK built in this workspace. It is a public certificate fingerprint, not a password. Keep the local `.android-home/debug.keystore` so future updates use the same certificate. Do not commit the keystore. Switching signing keys requires a new client registration and cannot silently update the installed app.

The Android authorization library identifies the app by package/signature. No client secret belongs in the APK. No web-server OAuth client or paid backend is needed for this flow.

## 4. Authorize on your phone

Pocket Tracker → Setup → **Connect / reconnect Gmail** → choose your account → approve read-only access. Google Play services handles subsequent on-device token acquisition. If Google needs renewed consent, the app shows a connection error rather than silently omitting email coverage.

Default email selection uses transaction-related subject words. Setup shows the exact query, which you can change once to a Gmail label such as `label:Finance` or your bank senders. The app fetches only matches, but Google's authorization itself is mailbox-wide read-only.

## Verification to perform

- Confirm Google API is enabled in **this** project, and the Android package/SHA-1 match.
- Confirm the actual project quota and billing status; do not enable billing to work around errors.
- Connect Gmail and verify successful collection on the phone.
- Recheck token acquisition after more than an hour and after process restart; do a later multi-day check before claiming unattended operation is fully validated.
- Confirm nonmatching email bodies are never fetched and the report marks any source failure.

## Sources

- Android authorization: https://developer.android.com/identity/authorization
- Gmail access scopes: https://developers.google.com/workspace/gmail/api/auth/scopes
- Personal-use exception: https://developers.google.com/identity/protocols/oauth2/production-readiness/restricted-scope-verification
- Gmail quotas/pricing: https://developers.google.com/workspace/gmail/api/reference/quota

## Completed setup (2026-10-30)

Gmail API is enabled; the phone authorized read-only Gmail and completed the initial 292 matching emails. Google Audience now shows In production after the user explicitly approved that status. Branding URLs are https://vineetkumar19.github.io/pocket-tracker-info/ , privacy.html and terms.html under that path, with authorized domain vineetkumar19.github.io. No paid service was activated. Personal-use scope and unverified-app limitations still apply; do not confuse production publishing with verified branding/scopes.
