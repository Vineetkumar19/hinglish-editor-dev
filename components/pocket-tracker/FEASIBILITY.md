# Feasibility check — 30 October 2026

- Scope: private personal Android application, Gmail collection, local processing, automatic monthly PDF.
- Verdict: technically feasible with zero required recurring service fees under current documented limits. Not yet validated on the user's phone or Google account. Do not treat the full build as cleared until the access tests below pass.
- This is a documentation check, not a working integration test. No app, account authorization, billing configuration or scheduled job has been created.

## Cost and quota

- Local parsing, matching, storage, classification and PDF generation can use the Android SDK and free/open-source components. No paid AI service, hosted backend or PDF subscription is required. Dependencies and licenses must be checked when selecting concrete libraries.
- Gmail currently documents 6,000 quota units/minute/user for new projects and an 80,000,000-unit daily/project threshold below which there are no extra charges. Project rate limit: 1,200,000 units/minute. Older projects may have different quotas.
- A full/raw message fetch costs 60 units; a message-list request costs 5. Illustration: 1,000 full messages in a day plus four single-page lists = 60,020 units, before retries or extra pagination. This is well below the daily threshold, but retrieval still must be throttled to respect the per-minute limit.
- Use app-level daily request caps, rate limiting, bounded retries and checkpoints. A cap prevents runaway fetch loops; it is not a promise that Google will never change pricing.
- Standard use is currently no-additional-cost, not an unlimited or forever-free guarantee. Google's documentation explicitly describes planned over-quota charging. Do not enable billable cloud services or attach billing to solve a limit without an explicit new decision. Verify the actual project's setup and quotas in the access prototype.
- Private developer installation via ADB is supported without developer verification. Public distribution is a separate scope with fees/policies; it is not required for this personal app. Free limited-distribution options also exist, but current documentation has differing device-cap figures, so do not rely on an exact cap for this single-device plan.
- Existing hardware, electricity/internet, implementation effort and any coding-assistant usage are outside zero runtime-service cost.

## Who grants access

- SMS: the user grants READ_SMS and RECEIVE_SMS through Android. These are hard-restricted: the installer must allowlist them. Test the chosen installation route and target Android version; consent alone is not proof of availability. This is not a bank API and needs no bank integration approval merely to parse messages already received.
- SMS publication: Play distribution normally requires a qualifying default handler or an approved exception. Personal sideloading does not remove Android's own restrictions. Sensitive/OTP content and RCS must not be assumed accessible.
- Gmail: the account owner authorizes gmail.readonly through Google. We configure a developer project/OAuth client. This authorization can read the mailbox; our code limits retrieval to the configured senders/queries/labels. There is no label-only read scope for this design.
- Personal OAuth use: Google's documentation provides a personal-use verification exception. Consent, warning screens, account restrictions and user caps can still apply. A public service has different requirements and may require verification/security assessment.
- Unattended OAuth: external projects in Testing issue refresh tokens expiring after seven days for Gmail scopes. Use an appropriate deployment configuration and test renewal/restart behavior. Revoked access, password changes or account policy can still force a new sign-in.
- Network: fetching Gmail requires internet and contact with Google. Extraction, reconciliation and PDF rendering remain local. No fully offline app can fetch new server-held emails.

## Reliability limits

- Android background scheduling is best effort. Phone shutdown, force-stop and battery restrictions can delay collection/report generation. Test catch-up and report missing coverage rather than claim an exact guaranteed time.
- Routine copy/paste and transaction approval are unnecessary. Genuine missing/ambiguous evidence cannot be guaranteed correct; retain an unresolved appendix and generate the PDF anyway.
- Fraud classification is a risk signal, not a guarantee. Bank message format changes can need parser updates.

## Required checks before full implementation

1. Actual phone: install a minimal private prototype; verify old SMS read, new SMS receive, permission state and catch-up after reboot/background delay.
2. Actual Gmail account: establish read-only access without paid middleware; query only selected messages; verify active quota/billing state, renewable credentials and unattended access configuration beyond the seven-day testing limitation.
3. Local sample: process matching SMS/email, repeated same-amount transactions, refunds and ambiguous cases; render a PDF offline. Check totals and retry idempotency.

Needed from user: phone model and Android version. Initial device permission and Gmail consent are user actions; no credentials should be pasted into chat. If any gate fails, reassess before dashboard/full-app development.

## Official references

- Gmail cost and method quotas: https://developers.google.com/workspace/gmail/api/reference/quota
- Gmail scopes: https://developers.google.com/workspace/gmail/api/auth/scopes
- Personal-use verification exception: https://developers.google.com/identity/protocols/oauth2/production-readiness/restricted-scope-verification
- Token expiry: https://developers.google.com/identity/protocols/oauth2
- SMS permissions: https://developer.android.com/reference/android/Manifest.permission#READ_SMS
- Play SMS restrictions: https://support.google.com/googleplay/android-developer/answer/10208820?hl=en
- Developer installation: https://android-developers.googleblog.com/2026/03/android-developer-verification-rolling-out-to-all-developers.html
- Background scheduling: https://developer.android.com/develop/background-work/background-tasks/persistent/getting-started/define-work
