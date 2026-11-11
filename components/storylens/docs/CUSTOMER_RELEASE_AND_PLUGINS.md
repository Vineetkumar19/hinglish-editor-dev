# Storylens: Desktop and Editor Plugins

Prepared 15 October 2026. **Launch preparation, not a completed commercial release.**
The public marketing website and read-only tour are live. Real purchases are disabled.
The account, payment and licensing service is implemented locally and packaged for deployment.
No merchant account, code-signing identity or paid hosting has been created.

Public website: https://storylens.magicpearl129.chatgpt.site

## One bundled subscription

₹2,000 monthly or ₹20,000 annually includes both the standalone Desktop application and all Editor Plugins on one registered Windows computer. There is no separate edition charge. Billing is fixed-term with manual renewal.

The current MySQL, owner dashboard and reviews setup is documented in **STORYLENS_OWNER_GUIDE.md**. It supersedes older edition-specific instructions.

## Customer journey implemented

1. Create an account and verify the email address.
2. Choose Monthly or Annual; both include Desktop and Editor Plugins.
3. Complete Razorpay checkout. The server checks the signature, provider capture, amount and currency.
4. Download the verified installer. Preparation builds cannot appear as customer downloads.
5. Open the editor/plugin, choose Activate, and enter its device code in the account page.
6. Check the displayed computer name and edition, then approve it.
7. Process locally and import the generated result into a new timeline or composition.

Purchases and downloads remain closed until the release requirements below pass.
The preparation ZIPs are **not customer installers**.

## Editor support and import boundaries

| Editor | Integration prepared | Validation status | Output |
| --- | --- | --- | --- |
| After Effects | CEP panel and ExtendScript adapter, targeting AE 2024 | Installed 24.2.1. A headless host smoke-test was attempted but returned no successful receipt. In-host verification remains required. | Plain Smart Clean / Script Edit cuts become a new composition with source trims. Unsupported effects require rendered footage. Composition finishing renders the work area with a temporary queue item and restores existing queue flags. |
| Premiere Pro | CEP panel for 2022–2024, UXP source for newer versions | Installed 24.4.1. No complete in-host customer acceptance test. UXP minimum 25.6; its timeline export path requires the API introduced in 26.2. | Selected media or active timeline sent to the local engine; generated XML or footage imported into the project. |
| Resolve Studio | Native Python UIManager scripting window | Resolve is not installed here. Requires Studio, installed Python scripting support and UIManager. Timer availability is detected; manual progress refresh is available as a fallback. | Media Pool selections or current timeline; reviewed results imported as a new timeline or media. |

These are editor extensions/integrations, not native effect DLLs or OFX effects.
Not every generated effect becomes a native editable host effect. Do not claim
Resolve Free, all editor versions or macOS support. Signed ZXP/CCX and Windows
installer artifacts have not been produced. Customer installation must not depend
on enabling Adobe PlayerDebugMode.

All twelve entry points are represented: Smart Clean, Script Edit, Auto Captions,
B-roll, Smart Visuals, Smart Zoom, Sound Design, Eye Contact, Long to Shorts,
AI Images, AI Video and Motion Graphics. Actual operation depends on installed
models, hardware and import support. Existing owner features remain intact.
Personal documentary reference media, channel tokens and model folders are not
copied into the public site or deployment package.

## Payment and licensing checks

- Server-owned prices and immutable edition per order.
- Provider capture verification and signed webhooks, idempotent grants and refund/dispute revocation.
- One shared renewal period for Desktop and Editor Plugins.
- Argon2id passwords, hashed sessions, secure production cookies, Origin checks and CSRF protection.
- Activation approval requires the account session and the bundled subscription.
- Ed25519-signed leases bind the edition, permitted hosts, installation public key, expiry and payment grant.
- Renewal requires installation proof, a credential, timestamp and an unused nonce.
- Commercial editing requires online verification before starting and every 30 seconds during processing.
  Signed leases last at most five minutes and cannot enable editing after a network failure.
- Installation keys and activation credentials use current-user Windows DPAPI and a hashed
  Windows/firmware identity. Copying an activation folder to a different computer is rejected.
- One active account session; new sign-in invalidates the previous website session.
- Only the verified support operator with an authenticator code can approve a computer replacement.
  Replacement is audited and waits for the old lease to drain before another computer can activate.
- The compiled release pins the server public key; merchant and license signing secrets stay server-side.
- Downloads check entitlement, release status, allowed path and SHA-256 hash.
- Live sales refuse to start without payment/email/support/signing settings and release manifests for both editions.
- The Docker build-context allowlist excludes personal inputs, reference media, keys and model folders.

Local software can be inspected or modified by a determined computer owner.
Compiled distribution, signing and server licensing reduce misuse; they do not make software impossible to crack.
Firmware identifiers can be spoofed by administrators or cloned virtual machines;
TPM-backed key attestation is not implemented. A determined modified client remains a risk.
The optional cookie-only hosted rendering worker is blocked in production until
browser-to-device proof is implemented; local licensed editing is the commercial path.

## Gmail support and private tickets

Customer support address: **vineetkd418@gmail.com**. Email only; no phone or WhatsApp.
The full account service has private ticket threads at `/support` and a verified
operator inbox at `/support/inbox`. The public marketing preview provides an email
link; it does not host the account database or accept support tickets yet.

1. Enable Google 2-Step Verification on the support Gmail account, then create an
   App Password for the hosted service: https://support.google.com/mail/answer/185833 .
2. In private hosting settings, set `HINGLISH_SAAS_SMTP_HOST=smtp.gmail.com`,
   `HINGLISH_SAAS_SMTP_PORT=587`, `HINGLISH_SAAS_SMTP_USER=vineetkd418@gmail.com`,
   `HINGLISH_SAAS_MAIL_FROM=vineetkd418@gmail.com`, and the App Password in
   `HINGLISH_SAAS_SMTP_PASSWORD`. Do not use your normal Gmail password or paste
   either password into chat. Transport uses certificate-verified STARTTLS.
3. Keep `HINGLISH_SAAS_SUPPORT_EMAIL` and `HINGLISH_SAAS_SUPPORT_ADMIN_EMAILS`
   set to `vineetkd418@gmail.com`. Sign up and verify that account on your service.
4. Generate a separate private support-inbox authenticator key:
   `.venv\Scripts\python.exe -m tools.provision_support_auth --output cache\saas\support-auth.private.txt`.
   Import the private provisioning URI into your authenticator; store its secret as
   `HINGLISH_SAAS_SUPPORT_TOTP_SECRET` in hosting settings. Keep a private recovery
   backup. The key is never placed in the public website or printed in chat.
5. Open `/support/inbox`, sign in with the verified owner account and enter the
   current authenticator code. Answer there so replies remain in the ticket history.

Notifications go to Gmail and customer emails. Direct replies in Gmail are **not**
imported back into ticket threads; use the private inbox. Queued messages retry on
delivery failure, and the owner can inspect pending/failed counts and retry failures.
Tickets remain stored if email is offline. No real support message has been sent or
Gmail connection validated during preparation. Delivery must be tested after setup.

Security assessment and remaining dependency findings: `docs/SECURITY_REVIEW_2026-10-15.md`.

## Owner steps: Razorpay and payment setup

1. Create your merchant account: https://dashboard.razorpay.com/signup .
2. Complete Razorpay's business, bank and identity/KYC requirements using your own accurate details.
3. Publish your actual operator identity, support contact, privacy, refund/cancellation and delivery terms.
   The current service-information page contains preparation guidance, not final customer policy.
4. Begin with Test Mode. Store Test Key ID, Test Key Secret and a unique webhook secret in hosting secret settings.
5. Connect email delivery: SMTP host/port/user/password and a verified sender.
6. Configure payment capture using the current Razorpay dashboard instructions.
7. Configure `https://YOUR-API-HOST/api/billing/webhook` for `payment.captured`,
   `refund.created`, `refund.processed` and `payment.dispute.created`.
8. After merchant activation, release testing and test-mode verification, switch to Live Mode keys securely.
9. Perform a small real purchase, activation and refund test; verify settlement in your dashboard.

Never paste merchant secrets into chat or put them in browser JavaScript.

Primary references:
https://razorpay.com/docs/payments/payment-gateway/web-integration/standard/integration-steps/
https://razorpay.com/docs/payments/dashboard/account-settings/activation-details/

## Host the complete account service

The public ChatGPT Site contains marketing and the read-only tour. It does not run
this Python/SQLite account service. Accounts and payments there remain disabled.

The server deployment ZIP includes the complete API, website, Dockerfile, requirements,
secret-variable template and Render deployment template. Serve the website and API
from the **same HTTPS origin**. Do not split them across domains without a tested session/CORS design.

Use persistent storage. `saas_site/render.yaml` specifies a **paid** service with a
persistent disk. No paid service has been provisioned. Render free web services
cannot attach persistent disks: https://render.com/docs/free and https://render.com/docs/disks .

Keep `HINGLISH_SAAS_SALES_ENABLED=0` during preparation. Set
`HINGLISH_SAAS_ORIGIN` to the actual account-service HTTPS origin,
`HINGLISH_SAAS_PRODUCTION=1`, and `HINGLISH_SAAS_DATA_DIR` to the persistent mount.
The local Desktop/Plugin product does not require a cloud rendering worker for licensing.

Generate a private signing key from the project folder:

```powershell
.venv\Scripts\python.exe -m tools.provision_license_key --output cache\saas\operator-license.key
```

Place its private value only in the hosting secret `HINGLISH_SAAS_LICENSE_PRIVATE_KEY`.
Back it up privately. The printed public key is compiled into releases. Changing
the key later requires a deliberate rotation/migration, rather than silently breaking installations.

Back up the database to encrypted private storage, and test restoration:

```powershell
.venv\Scripts\python.exe -m tools.backup_saas --data-dir cache\saas --output output\private-backups\subscriptions-backup.sqlite3
```

## Customer build steps prepared

1. Deploy the actual HTTPS license service and retain its public key.
2. Generate an isolated compilation checkout:

```powershell
.venv\Scripts\python.exe -m tools.stage_customer_runtime --destination output\saas\build\release-04 --origin https://YOUR-ACTUAL-LICENSE-HOST --public-key YOUR-PUBLIC-KEY
```

3. Install engine dependencies and PyInstaller in a controlled build environment.
   Compile `editor_plugins/release/runtime.spec` from that isolated checkout.
   It defines a windowed editor and separate engine executable. The recipe is not
   proof of a working frozen binary; dependency hooks must be validated.
4. Implement/test first-run model provisioning and hardware checks on clean CPU and GPU machines.
   Review model, font, SDK and media-library licenses before redistribution.
5. Sign CEP extensions as ZXP, and package Premiere UXP as CCX using the Adobe tools.
   Marketplace distribution requires an Adobe-issued plugin ID and review.
6. Build `editor_plugins/release/windows-installer.iss` using Inno Setup, then sign
   the runtime, engine and installer with the publisher's code-signing identity.
7. Test fresh install, activation, all advertised tools/imports, upgrade and uninstall in each supported host.
8. Place verified signed artifacts in the account server's persistent `releases` directory.
   Publish `release.json` with `release_ready: true` and artifacts containing
   `id`, `label`, `edition`, `version`, `file` and `sha256`.
9. Verify downloading and activation on a clean machine, then enable live sales.

Adobe primary references:
https://developer.adobe.com/premiere-pro/uxp/plugins/distribution/package/
https://developer.adobe.com/developer-distribution/
https://github.com/Adobe-CEP/CEP-Resources/tree/master/ZXPSignCMD

## What is verified and what remains

Automated tests cover existing account/payment security and local editor behaviour,
new edition isolation, device activation/renewal, license tampering, and adapter contracts.
The previous Smart Clean integration test processed a real recording with a simulated
payment provider. No real money moved. The public site deployed successfully and was checked in a browser.

A commercial release still needs merchant activation, account-service hosting,
email, final policies, compiled/signed installers, first-run model provisioning,
and actual in-editor acceptance testing. Do not distribute the preparation archives as customer installers.
