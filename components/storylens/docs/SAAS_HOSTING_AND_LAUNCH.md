# Hinglish Editor: website and subscription launch

**15 October update:** the public marketing site is now live, and Desktop/Plugin
edition checkout, signed device activation and customer download checks are added.
See [the updated release guide](CUSTOMER_RELEASE_AND_PLUGINS.md) for current status.
The older worker-focused notes below describe the optional hosted-rendering adapter,
not a requirement for the new local processing editions.

Prepared 14 October 2026. This is a working local launch preparation build,
not an already operating public GPU SaaS. No merchant account, domain or
paid cloud infrastructure has been created. Real payments are disabled.

## What is built

- A responsive minimalist website with local Albert Sans / Barlow Condensed
  fonts, white/graphite surfaces, restrained teal controls, real licensed
  coastal photography and a realistic editing preview, an interactive tool demonstration,
  feature catalogue, pricing and account pages. No copied FireCut assets,
  testimonials, invented customer counts or reference creator footage.
- ₹2,000 monthly and ₹20,000 annually. The annual option saves ₹4,000 versus
  twelve monthly payments. One creator account. These are fixed-term access
  purchases with **manual renewal**, not recurring mandates yet.
- Account registration and login; Argon2id password hashes; random sessions
  with only their hashes stored; HTTP-only cookies; production Secure cookies;
  email verification and single-use password recovery when SMTP is connected.
- Server-side Razorpay orders, server-owned amounts in paise, callback HMAC
  checks, provider capture/amount/currency checks, duplicate protection, raw
  signed webhooks and refund/dispute revocation. A browser success animation,
  checkbox, local storage flag or payment screenshot cannot grant access.
- The server checks subscription expiry on uploads, job requests, job reads
  and downloads. It checks account ownership on upload IDs, job IDs and export
  IDs. The subscriber editor page also requires an active entitlement.
- A separate private sequential rendering worker reuses the existing Python
  editor. Customer-specific work folders; no public local bridge; no client
  paths, arbitrary commands, XML imports or private profile selection.
- One active edit per customer; one private renderer at a time; upload size
  and upload storage limits; job allowance; a private process timeout that
  stops only that job's process tree. Downloadable MP4/caption/image files,
  rather than HTML reports with executable scripts or XML with server paths.
- A real Smart Clean integration trial: account → simulated payment → real
  video upload → private engine → authenticated download. This proves the
  starter integration, not all GPU features under public customer load.

## Tool migration map

| Existing tool | Engine | SaaS preparation status |
| --- | --- | --- |
| Smart Clean | `hinglish_clean` | Private worker adapter; real integration tested |
| Script Edit | `hinglish_semantic` | Adapter present; provision transcription/alignment models before enabling |
| Auto Captions | `hinglish_captions` | Adapter present; provision speech models and browser renderer |
| B-roll | `hinglish_broll` | Adapter present; provision server-side media-provider keys and licensed library |
| Smart Visuals | `hinglish_visuals` | Adapter present; provision search/evaluator and enforce production asset permissions |
| Smart Zoom | `hinglish_zoom` | Adapter present; provision required face/speech models |
| Sound Design | `hinglish_sound` | Adapter present; provision a permitted sound library; do not redistribute it |
| Eye Contact | `hinglish_eyecontact` | GPU/SDK configuration and commercial usage review required |
| Long to Shorts | `hinglish_shorts` | Adapter present; provision speech/highlight models and render capacity |
| AI Images | `hinglish_aiimage` | GPU worker and generation-model installation required |
| AI Video | `hinglish_aivideo` | Suitable GPU worker, model installation and usage budget required |
| Motion Graphics | `hinglish_motion` | Adapter present; provision browser, fonts, licensed assets and permitted generic styles |
| Publishing Studio | `hinglish_publish` | Kept intact locally; not exposed to SaaS customers. Requires per-user OAuth, token isolation, consent and provider approval |

General-purpose editing remains the public product direction. Your personal
cricAddict / vineet documentary memories, Cricket / Gaming channel accounts,
reference videos and private publishing credentials are not copied to customer
workspaces. The quick-command selector on this first web workspace is a bounded
tool selector, not an Ollama chat model. Full multi-step conversational editing,
domain profiles, gaming compilations and thumbnail routing remain in the local
editor and need a separate tenant-safe web migration before they can be sold
as web features. Do not advertise them as live online yet.

## Architecture

```text
Browser: website, account, subscriber editor
          │ HTTPS, session cookie and CSRF token
          ▼
Small Python API: accounts, captured payments, entitlements, uploads, queue
          │ persistent database and customer-specific private storage
          ▼
Private rendering worker: one claimed job, bounded process lifetime
          │ existing editing engines and provisioned CPU / GPU models
          ▼
Owned output IDs → authenticated download

Razorpay → signed webhook → grant / revoke the affected paid access period
```

The public Docker image copies **only** `hinglish_saas`, website assets and
light web dependencies. It does not copy your engine source, model weights,
input clips, personal memories, reference libraries, source ZIPs or publishing
credentials. The private renderer has the actual engine installation. Public
frontend HTML, CSS and JavaScript are visible to browsers; keeping algorithms
and secrets on private workers protects the valuable implementation, rather
than pretending that frontend obfuscation is security.

SQLite is the prepared single-instance database. A persistent volume is
mandatory. Do not point multiple independent cloud replicas at separate local
SQLite files. For scale, migrate this schema and atomic job/payment operations
to PostgreSQL, use private object storage, resumable signed uploads, container
resource quotas, a persistent job queue and isolated rendering containers.

## Free hosting: what is and is not possible

| Option | Suitable use | Important limit |
| --- | --- | --- |
| Cloudflare Pages free | Public website and read-only interactive demo | Does not run this Python GPU renderer or private database |
| Free `pages.dev` address | Initial official internet URL | A custom branded domain is a separate purchase |
| Render free web service | Disposable API experiments | Sleeps after inactivity; local filesystem is ephemeral. Unsuitable for this live SQLite subscription service |
| Vercel Hobby | Personal/non-commercial projects | Its terms restrict commercial use; do not use it for this paid SaaS |
| Your existing laptop | Small private rendering experiments | Electricity, internet, availability and limited concurrency still apply |
| Paid persistent API / GPU worker | Reliable subscriber processing | Costs money; capacity must be measured before promising allowances |

Cloudflare Pages documentation: https://developers.cloudflare.com/pages/
Limits: https://developers.cloudflare.com/pages/platform/limits/
Worker CPU/memory limits: https://developers.cloudflare.com/workers/platform/limits/
Render limits: https://render.com/docs/free
Vercel commercial restriction: https://vercel.com/docs/plans/hobby

### Lowest-cost sensible sequence

1. Keep the build local while reviewing design and merchant setup.
2. Publish **only the marketing site and read-only tour** on Cloudflare Pages
   using a generated safe static bundle. This can have a free `pages.dev`
   address. Account/purchase links in that bundle explain that the service is
   not open; no false payment or authentication functionality is presented.
3. Set up a small persistent API host with HTTPS and backups. For a first
   limited pilot, a private dedicated machine can run the existing worker.
   Do not expose the desktop bridge on port 8767, personal drives or Ollama.
4. Connect and test Razorpay and email delivery. Perform a real Razorpay test
   checkout/webhook/refund trial before live keys are used.
5. Measure each tool's minutes, RAM, VRAM, output size and concurrent capacity.
   Decide processing allowances that ₹2,000/month can actually support.
6. Finalise customer policies and configure live sales only when the actual
   advertised tools are provisioned and tested on the service.

Fully hosted AI video generation for all paying customers is **not free** just
because the website is free. Do not advertise unlimited images/videos under
these prices without a measured compute budget. This preparation build defaults
to 2 GiB per upload, 10 GiB of upload storage and 20 edit jobs in a rolling 30
days. These are conservative, editable pilot settings, not a tested commercial
service commitment. Total render-work/output disk quotas and automatic retention
need OS/container/object-storage enforcement before customer launch.

## Payment costs and setup

Razorpay's standard headline fee is 2% plus 18% GST on that processing fee.
At that rate, illustrative deductions are ₹47.20 on ₹2,000 and ₹472 on ₹20,000,
leaving ₹1,952.80 / ₹19,528 before your other taxes, refunds and running costs.
No setup/annual maintenance fee is advertised. Product-specific pricing,
methods and temporary offers can differ; confirm the merchant agreement.
Official pricing: https://razorpay.com/pricing/

A personal UPI QR image can be displayed at little cost, but it cannot reliably
prove payment, payer identity or the purchased access period by itself. Do not
activate accounts from a user-uploaded screenshot or claimed UTR. A manual QR
option needs the operator to reconcile the actual bank transaction before
granting access; it is not implemented as an automatic shortcut here. Stripe
also charges processing fees; the chosen integration is Razorpay for India.

1. Create your merchant account and complete required activation/KYC.
2. Add the real business/support information, privacy/refund/service pages
   required for approval. The current notes page is **not** final customer terms.
3. Start with `rzp_test_...` credentials. Store the key secret and webhook secret
   in host environment secrets. Never paste them into frontend JavaScript,
   publish them in a source archive, or share them in chat.
4. Set the public webhook URL to `/api/billing/webhook`. Enable
   `payment.captured`, `refund.created`, `refund.processed` and
   `payment.dispute.created`. Use the configured webhook secret.
5. Configure automatic payment capture in the merchant dashboard. The API grants
   no access merely because the payment is `authorized`.
6. Run provider-side tests for success, failure, duplicate delivery, refund and
   disputes. A partial refund conservatively suspends the affected grant pending
   operator review; later capture callbacks cannot resurrect it.
7. Only then configure live keys and enable sales. Recurring debit mandates
   and automatic renewal are a future billing feature, not this Orders flow.

Official server integration:
https://razorpay.com/docs/payments/server-integration/python/integration-steps/
Webhook signature/idempotency guidance:
https://razorpay.com/docs/webhooks/validate-test/

## Run the local preview

```powershell
Set-Location -LiteralPath 'E:\remove silence'
.\.venv\Scripts\python.exe -m pip install -r requirements-saas.txt
.\.venv\Scripts\python.exe -m hinglish_saas
```

Open http://127.0.0.1:8788/. `Run Website Preview.bat` starts the same preview.
The current live preview has sales and worker processing disabled. It keeps
local account records in `cache/saas`; all real application secrets and this
runtime directory are excluded from source packages.

### Prepare the web API host

The repository includes `saas_site/Dockerfile.api`. Build from the repository
root, mount a private persistent `/data/hinglish` volume, and place it behind
an HTTPS reverse proxy. Configure one exact origin without a trailing slash.
Keep the proxy's incoming Host set to that public domain. Do not expose SQLite
files or the rendering worker's filesystem through your web server.

The API disables arbitrary forwarded-header trust. If a trusted reverse proxy
is used, configure Uvicorn's forwarded-header allowlist to its **actual fixed
proxy IPs**, rather than `*`. Otherwise IP rate limits aggregate at the proxy.
Configure edge rate limits, request/body size limits, monitoring and backups.
Run the prepared single SQLite API instance; additional instances need the
database migration described above.

The `.env.example` lists the required environment variable names. The app
does not load that file automatically: use your host's secret manager or your
private process environment. Start the private worker separately with:

```powershell
.\.venv\Scripts\python.exe -m hinglish_saas.worker
```

Worker and API must see the same persistent queue and private storage for this
single-host starter. Do not start a second worker while a job is running. After
an unexpected host failure, inspect private logs and mark interrupted jobs
failed before resuming; automatic lease recovery is not included yet.

Each private job deliberately begins without your personal libraries and API
keys. Provision permitted generic assets, read-only shared models, required
speech configs and GPU settings per tool before setting `HINGLISH_SAAS_TOOLS`.
Only Smart Clean was executed through this new web adapter in the current test.
Other tools' adapters do not mean their remote models are installed. The first
adapter chooses CPU; a production GPU scheduler/configuration is still required
for expensive tools. Keep renderer subprocesses in non-root containers with
resource caps and no merchant/mail secrets. A private process timeout is
implemented; complete OS/container isolation is a separate deployment step.

## Verification and honest launch limits

`tests/test_saas.py` covers 31 cases: password/session storage, unpaid and
anonymous access, price tampering, forged/uncaptured/mismatched payments,
foreign orders, replay, expiry, refund, out-of-order revocation, CSRF/origin/Host,
upload limits and names, owned downloads, private-file exposure, logout,
single-use recovery, rate limits, single worker claims, real-output requirements
renderer credential isolation and production config.
These are automated implementation checks, not a certified penetration test.

`tools/test_saas_live_edit.py` uses an eight-second clip from your existing
recordings. Payment and email are explicit test fixtures; the actual engine
and owned upload/export flow execute for real. It touches no live merchant or
preview accounts. Receipts/results are under `output/saas/live-test`.

Before selling: real provider test-mode checkout, email deliverability, model
and asset permissions, every advertised web feature, tenant isolation under
load, protected backups, retention/deletion/export cleanup, hard resource quotas,
container isolation, recovery of interrupted jobs, GPU costs and a staging
security review are still required. No system can guarantee that it cannot be
hacked. This build implements specific protections and reports their tested
limits instead of promising that guarantee.
