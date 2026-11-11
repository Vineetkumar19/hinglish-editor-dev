# Storylens — owner guide and deployment handover

Prepared 15 October 2026. Storylens is the approved product name.
The complete account/review/dashboard service runs locally on MySQL. Public
backend hosting is deliberately deferred, as requested by the owner.

**16 October addition:** [Beat Studio](BEAT_STUDIO.md) adds local music markers
and a separate beat-effects action in Premiere Pro and Resolve Studio. Native
host visual validation is still required; the local detector and API checks pass.

[Cinematic Reels](CINEMATIC_REELS.md) adds the separate music-and-performance-shot
assembly workflow: beat intervals, measured shot selection, supported retiming,
continuous soundtrack and a separate effects pass.

## The subscription customers receive

| Plan | Price | Included |
| --- | --- | --- |
| Monthly | ₹2,000 | Desktop application and all Editor Plugins |
| Annual | ₹20,000 | Desktop application and all Editor Plugins |

One purchase activates both ways of working on **one registered Windows computer**.
There are no separate Desktop and Plugin charges. Old edition-specific order
requests are accepted for compatibility but are normalized to the bundled product.
Existing paid Desktop/Plugin orders both grant bundled access. Future renewals
extend the common access period. Billing remains fixed-term with manual renewal.

After Effects, Premiere Pro and DaVinci Resolve Studio share the local runtime.
The host-specific license files use the same installation identity; the server
rejects attempts to place Desktop on one computer and Plugins on another.
Computer replacement revokes both, drains outstanding leases and is audited.

Internal Python package names, environment keys, license audience, plugin IDs and
old installation directory names are retained for compatibility. Customer-facing
website pages and the local editor display Storylens. Existing customer installers
still require compilation, signing and host acceptance testing before distribution.

## Start the actual local service

1. Double-click **Start Storylens Website.cmd** in the project folder.
2. Wait for the ready message, then open http://127.0.0.1:8788/ .
3. Keep that terminal running while using the local website. Closing it stops the
   website and the separately launched Storylens MySQL instance.

Use **Stop Storylens Website.cmd** for a graceful stop. It affects only this
Storylens instance, not your existing MySQL80 Windows service. If Storylens is
already running, the Start shortcut opens its website instead of starting a copy.

This laptop has MySQL Server 8.0 installed. The launcher uses that official binary
with a **separate data folder and port 3308**. It does not modify your running
MySQL80 service or existing databases. Its own schema is named `storylens`.

The launcher creates random database passwords and saves them inside
`cache/storylens-local/connection.private.json`, restricted to the current Windows
user. Never upload that folder or file. No passwords are printed or embedded in
the public website. The application uses its own database account, not root.

The first launch copies an existing `cache/saas/subscriptions.sqlite3` account
database to MySQL if one exists and the new target is empty. Counts are checked
inside the transaction. The original SQLite database remains unchanged. A target
containing records is never overwritten. Back up both before moving the project.

## Set up your private owner account

1. Leave the Storylens website running.
2. Double-click **Set up Storylens Owner.cmd**. Enter and confirm your password
   privately in the terminal; it must contain 12–128 characters.
3. This creates the local owner `vineetkd418@gmail.com` if it does not already
   exist. An existing account is never overwritten. If your old account was
   migrated, use its existing password and normal recovery when email is connected.
4. Add the key from `cache/storylens-local/owner-authenticator.private.json` to an
   authenticator app. Keep that private file as a recovery backup. If the account
   already existed, the support key is also in `connection.private.json`.
5. Sign in at http://127.0.0.1:8788/account and choose **Owner dashboard**, or open
   http://127.0.0.1:8788/dashboard . Enter the current six-digit authenticator code.

The operator email allowlist is server-controlled. Merely visiting `/dashboard`,
editing browser code or knowing its address does not grant access to user data.
The dashboard API checks the verified owner account and MFA on every request.

## What your dashboard shows

- Registered users, verified accounts and new accounts over the last 30 days.
- Active subscribers, captured paid-order totals and payment revocation counts.
- Registered computers and open support tickets.
- Searchable, paginated account records and current access expiry dates.
- Reviews awaiting moderation and controls to publish or hide a review.
- Local editing activity, grouped by tool and outcome, for the last 30 days.

The captured-payment total is the sum of paid orders in the account database,
not an accounting or bank-settlement report. Test fixtures are explicitly marked
in the QA service and never copied into the real local database or public site.

## Ratings and reviews

Open http://127.0.0.1:8788/reviews . A verified signed-in account can give 1–5 stars,
choose a public display name and write a title and review. One account has one
review. Editing replaces that review and returns it to moderation. Customers can
delete their own review.

The public average and star distribution use **published reviews only**. Email
addresses, internal account IDs, passwords and session data are not public. The
Verified customer badge requires an actual recorded paid order; customers cannot
set that badge themselves. An expired subscription can still have a genuine
purchase badge. Refunded/revoked orders do not qualify on their own.

Use the same moderation standards for positive and critical feedback. Hide spam,
abuse or leaked private information. Moderation actions are recorded in the audit
log. Public pages display review text as text, so HTML is not executed.

## Usage reporting and privacy

Commercial installations have an optional **Share tool usage statistics** checkbox
on the activation/settings page. It is **off by default** and can be disabled later.
Reports contain the tool, result, duration, application version and an event ID.
They do not contain video/audio, filenames, captions, scripts or error text.

Signed device proof, an active subscription and the registered computer identity
are required. Duplicate event IDs are ignored. Counts are operational estimates,
not fraud-proof evidence: modified clients can omit or misreport usage. Customers
who decline reporting do not appear in the local-tool activity totals.

## MySQL implementation and expected scale

- InnoDB, UTF-8 (`utf8mb4`), foreign keys and indexed account lookups.
- A bounded SQLAlchemy/PyMySQL connection pool: 8 regular connections plus 4 overflow.
- Short account/payment/device write transactions use an InnoDB row lock to keep
  activation, renewal, moderation and rate-limit changes consistent.
- Two simultaneous password-hash workers bound memory use during sign-in.
- Paginated lists, bounded request bodies, server checks, CSRF and owner MFA.

The local QA test used 30 authenticated fixture customers and 600 API requests,
including simultaneous review submissions. Results are in
`output/storylens/load-test.json`. This is evidence for the account/review workload
on this laptop, not a promise that every host or workload can never fail. It excludes
video uploads, GPU generation and AI rendering. Customers render on their own PCs.

## Move from SQLite to another MySQL server

Create an empty MySQL 8.0+ database and a dedicated application user. Store a
`mysql+pymysql://...` connection URL in `HINGLISH_SAAS_DATABASE_URL` privately.
Use URL-encoded passwords. For remote production databases configure `ssl_ca`,
`ssl_verify_cert=true` and `ssl_verify_identity=true`; use the provider's CA file.

Initial schema: `saas_site/mysql-schema.sql`. The account service creates it when
starting against an empty database. The schema export contains no passwords or
customer records. Future schema changes need explicit migrations; `create_all`
does not silently alter existing columns.

To copy an existing SQLite database into an **empty** configured MySQL target:

```powershell
.venv\Scripts\python.exe -m tools.migrate_storylens_mysql --source cache\saas\subscriptions.sqlite3
```

Do not paste the connection URL into chat, commit it or put it in frontend code.
The migration uses a read-only source connection and verifies copied table counts.
It deliberately refuses to merge or overwrite a populated target.

## Publish the full service when you choose hosting

The current public Site contains the Storylens marketing pages, tour, pricing,
support contact and an honest reviews-availability notice. It does not contain
the MySQL database, real account registration or the private owner dashboard.
Its static pages must not pretend to accept reviews or payments.

1. Use an always-on server for the Python account service and MySQL. You do not
   need a cloud GPU server for this local-rendering product. A small VPS with
   MySQL on loopback is one deployment option; no paid service was purchased.
2. Deploy `STORYLENS_SERVER_DEPLOYMENT.zip`. Install the pinned
   `requirements-saas.lock`; configure the included environment template.
3. Set the actual public HTTPS origin and `HINGLISH_SAAS_PRODUCTION=1`.
   Production requires MySQL and refuses development fixture mode.
4. Serve the website and API from the same origin behind HTTPS. Keep MySQL off
   the public internet. For external managed MySQL, validate the server certificate.
5. Use a persistent private data directory for release files, support records and
   backups. The optional Render template needs an external MySQL service and its
   CA certificate. It is a paid hosting template, not free hosting already set up.
6. Configure your owner account, authenticator key, Gmail delivery and merchant
   settings as described in `CUSTOMER_RELEASE_AND_PLUGINS.md`.
7. Test restore, real email delivery, real payment/refund, signed installers and
   activation on a clean computer before opening sales.

MySQL backups can be exported privately through MySQL Workbench's Data Export
or `mysqldump --single-transaction`. Store backups encrypted and test restoration.
The old `tools/backup_saas.py` is for the legacy SQLite database only; it does not
back up MySQL. Enable automated MySQL backups through the chosen host.

Support remains Gmail only: vineetkd418@gmail.com. No WhatsApp or phone service.
