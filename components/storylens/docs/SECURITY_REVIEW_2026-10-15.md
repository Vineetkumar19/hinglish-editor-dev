# Security and single-computer licensing review

Assessment date: 15 October 2026. Project: Hinglish Editor.
Support contact: **vineetkd418@gmail.com**. Gmail only.

**This is a source review, dependency audit and targeted regression assessment, not
a guarantee that every vulnerability is eliminated or a completed external penetration test.**
Public marketing is live. Commercial checkout, account-server deployment and signed
customer installers remain launch blockers. Do not start charging based on this report.

## What was examined

- Account registration, verification, login, recovery, sessions, Origin and CSRF boundaries.
- Razorpay server-owned prices, capture checks, webhook authentication, payment revocation.
- Edition-specific activation, signed leases, concurrent device claims, replay protection,
  local credential storage, license enforcement during local rendering, download ownership.
- Local HTTP bridge host/origin/token rules and JSON size boundaries; Adobe import integration.
- Customer ticket ownership, staff authorization/MFA, device replacement and email retries.
- Installed Python packages, the smaller web-service dependency set and static source findings.
- XML import boundaries used by timeline tools. Real Gmail, live payments, code signing,
  hostile production load and a clean-machine installer were not tested.

## Fixed or hardened

| Finding | Result |
| --- | --- |
| Previous two-device policy allowed multiple computers. | Exactly one device per purchased edition; startup refuses a larger limit. |
| Self-deactivation could be used to cycle a subscription between computers. | Binding remains after deactivation. Only the verified support operator can release it after reviewing a customer ticket. |
| Concurrent activation approvals could compete for a slot. | Binding/approval/issuance use transactions; two pre-approved codes cannot both activate different devices. |
| Copyable local installation credentials. | Current-user Windows DPAPI protects keys and credentials, with a hashed Windows MachineGuid/firmware UUID binding and restricted folder ACLs. Raw hardware IDs are not transmitted. |
| Long offline access delayed subscription revocation. | Before-edit online verification and 30-second in-process checks. Leases last at most five minutes. Network failure does not grant offline editing. |
| Old and replacement devices could overlap. | Replacement revokes the old device, clears pending codes, records the reason/operator, and drains the last issued lease before allowing activation. Legacy 24-hour leases are drained conservatively. |
| Shared website sessions. | A new sign-in invalidates other active sessions for the account. Account management does not move the licensed computer. |
| Optional hosted rendering used only payment cookies, without device possession. | Production configuration refuses the hosted worker until device proof exists. Local Desktop/Plugin processing remains the supported licensed path. Development-only worker tests still run. |
| Different rate-window counters could erase hourly login throttles. | Expiry is stored explicitly; pruning no longer compares incompatible minute/hour bucket numbers. Regression test included. |
| No private customer support workflow. | Verified customers get private ticket threads; owner allowlist plus TOTP protects the staff inbox. Customer-controlled roles are rejected. CSRF, ownership, length limits and rate limits apply. |
| Support delivery failures could be confused with success. | Persistent outbox with claim leases, bounded retries and visible pending/failed counts. No SMTP means no false delivery claim; tickets remain available. |
| Arbitrary UXP origins could request the local bridge token. | Only this plugin's exact origin and approved local origins are accepted. Unrelated plugin-origin access is tested and denied. |
| Local JSON requests lacked a tight body boundary. | JSON bodies must be objects and at most 1 MiB; negative/oversized lengths are rejected. Streaming media has separate limits. |
| Plugin host import used eval for JSON parsing. | Removed eval; host accepts validated path arrays. Generated AE panel is prepared from the same hardened source. |
| Timeline XML could contain entities or external references. | Nine import modules use defusedxml for parsing; malicious entity input is rejected while normal timeline regression cases pass. Standard XML writing remains intact. |
| Outdated HTTP/install packages had known advisories. | Installed pip 26.2.1, setuptools 83.0.0 and urllib3 2.8.0. Dependency ranges were raised. |

## Dependency results and limits

Machine-readable results are in `output/security/`:

- `dependency-audit.json`: initial full installed environment, 28 advisory records in four packages.
- `dependency-audit-after.json`: nine advisory records in Transformers 4.57.6 only;
  six unique PYSEC IDs, including duplicate/aliased database entries.
- `server-dependency-audit.json`: separately resolved `requirements-saas.txt`:
  **no known advisories reported** at scan time. This does not certify the application.
- CPU-specific `torch 2.9.1+cpu` and `torchaudio 2.9.1+cpu` could not be matched by
  this PyPI-based scanner. They are **not reported as verified clean**.

Remaining Transformers IDs: PYSEC-2025-217, PYSEC-2026-2288, PYSEC-2026-2289,
PYSEC-2026-2290, PYSEC-2026-3929 and PYSEC-2026-4174. They cover checkpoint/model
loading, tokenizer save paths and custom generation. Some suggested fixes require
Transformers 5.x; some entries do not list a fixed version. A major version upgrade
was not applied blindly to the existing AI runtime. Compatibility testing and
model provenance restrictions remain required before distributing that runtime.

The public account-server image does not install Transformers or process user media.
Local semantic model loading explicitly disables remote code, but this is **not a
complete mitigation** for advisories that bypass that setting. Use only reviewed
models/checkpoints; do not accept arbitrary model repositories from customer input.
Pin model revisions and verify model assets before customer redistribution.

## Static source scan triage

Bandit scanned 25,205 source lines after hardening and reported 111 findings:
19 high, 26 medium and 66 low. These are scanner findings, not 111 confirmed exploits.

- All 19 high findings are SHA-1 cache/file identifiers; they are not password hashes,
  payment signatures or license signatures. Review identified this distinction;
  the raw report remains unchanged instead of being suppressed to claim a clean scan.
- Model downloads without immutable revisions remain a supply-chain concern.
- Subprocess call sites use argument lists and existing engine/tool constraints;
  a generic subprocess warning is not proof of command injection. Native media
  decoders still require sandboxing and updates against malicious files.
- XML writers still import the standard ElementTree module; untrusted import paths
  now parse with defusedxml. Static import warnings can remain for writing code.
- Dynamic SQL fragments examined use fixed internal identifiers or fixed suffixes;
  user values are bound parameters. New queries still require review.

Strix was not installed/configured and no paid/cloud LLM pentest was started.
No scanner output is represented as a successful full production penetration test.

## Verification

98 targeted security/account/licensing/local HTTP/editor integration checks passed.
Coverage includes edition isolation, duplicate activation prevention, copied-machine
identity rejection, offline denial, owner MFA, ticket isolation, CSRF and failed-mail retries.
113 additional timeline/media regression checks passed (211 automated checks total).
The pinned web-service dependencies also passed an isolated startup/support/access-denial
smoke test without Transformers installed. The Docker image itself was not built here.
Windows DPAPI encryption/decryption was exercised on this computer, including rejection
with the wrong machine context. Hardware-spoofing resistance was not penetration tested.

Browser checks used isolated fixture accounts, not the owner's customer database.
Creating a ticket and replying through the MFA-protected operator inbox succeeded;
mobile and desktop layouts had no horizontal overflow. No real email or payment was sent.

## Residual risks and release gates

1. Local software cannot be made impossible to copy or patch. Administrators may
   extract credentials, modify the runtime or spoof hardware/VM identifiers. DPAPI
   is useful protection, not hardware attestation. TPM-backed proof is future work.
2. Resolve the AI runtime advisories and supply-chain review before a customer release.
3. Finish compiled/signed installers and test activation, upgrades and every advertised
   host on clean machines. Existing source/preparation ZIPs are not customer installers.
4. Deploy the HTTPS account service with persistent private storage, tested backups,
   monitoring, an edge rate limit and final operator/privacy/refund policies.
5. Connect owner-controlled Razorpay and Gmail using hosting secrets, then perform
   real delivery, payment, activation and refund tests before opening sales.
6. Shared passwords can still expose account management to the password holder;
   one active session and device binding do not make credential theft harmless.
7. Gmail notifications are one-way. Reply in the private web inbox to preserve the
   ticket thread; inbound Gmail replies are not synchronized automatically.

Owner setup instructions: `docs/CUSTOMER_RELEASE_AND_PLUGINS.md`.
