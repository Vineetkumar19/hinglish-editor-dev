# Setup

Three things need configuring before the agents do anything real: Google
access, outbound mail, and your own data in `profiles/`. Work through them in
that order. `python run.py doctor` tells you where you are at any point.

Leave `DRY_RUN=true` until the end.

---

## 1. Google (Gmail + Calendar)

The agents read replies, send threaded responses, and check your calendar for
free slots. All of it runs on OAuth against your own account — there is no
service account and no password anywhere.

### Create the OAuth client

1. Go to the [Google Cloud Console](https://console.cloud.google.com/) and
   create a project (or pick an existing one).
2. **APIs & Services → Library**: enable **Gmail API** and **Google Calendar
   API**.
3. **APIs & Services → OAuth consent screen**: choose **External**, fill in the
   app name and your email. While the app is in *Testing*, add your own Gmail
   address under **Test users** — without that, consent will be refused.
4. Add these scopes:
   ```
   https://www.googleapis.com/auth/gmail.readonly
   https://www.googleapis.com/auth/gmail.send
   https://www.googleapis.com/auth/gmail.modify
   https://www.googleapis.com/auth/calendar.events
   ```
5. **Credentials → Create credentials → OAuth client ID → Desktop app**.
   Download the JSON.

### Authorise

Either put the two values in `.env`:

```
GOOGLE_CLIENT_ID=....apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=...
```

or point at the downloaded file:

```
GOOGLE_CLIENT_SECRETS_FILE=./credentials.json
```

Then:

```bash
python run.py auth google
```

A browser opens; approve, and the refresh token is stored in the database.
Access tokens refresh silently from then on. It prints the account it signed in
as — check that it is the one you meant.

> A refresh token for an app still in *Testing* expires after 7 days. Publish
> the app (still private to you) to stop that, or just re-run the command.

### Real-time replies (optional)

Polling every few minutes is fine and needs nothing further:

```bash
python run.py inbox       # once
python run.py schedule    # on a loop
```

For instant notification, Gmail pushes to Cloud Pub/Sub:

1. **Pub/Sub → Create topic**, e.g. `gmail-push`.
2. Grant `gmail-api-push@system.gserviceaccount.com` the **Pub/Sub Publisher**
   role on that topic. Gmail cannot publish without this.
3. Create a **push subscription** pointing at your dashboard:
   `https://your-host/gmail/push?token=<PUBSUB_TOKEN>`
   The endpoint must be public HTTPS with a valid certificate.
4. In `.env`:
   ```
   PUBSUB_TOPIC=projects/your-project/topics/gmail-push
   PUBSUB_TOKEN=some-long-random-string
   PUBLIC_BASE_URL=https://your-host
   ```
5. Register the watch — it expires every 7 days, so renew it on a schedule:
   ```bash
   python run.py watch
   ```
   `run.py schedule` renews it automatically. On cron:
   ```
   0 4 * * * cd /path/to/agentsuite && python run.py watch
   ```

The push payload carries only a `historyId`. The agent compares it against the
cursor in its database and calls `users.history.list` for exactly the delta —
it never re-lists the inbox.

---

## 2. Outbound mail

You have two options, and they are not equivalent.

### Gmail (simplest)

```
MAIL_TRANSPORT=gmail
SENDER_EMAIL=you@gmail.com
```

Sends through the account you just authorised. Fine for a handful of messages a
day. Gmail's own sending limits apply, and cold outreach from a personal Gmail
address is not a good look to a recruiter or a brand.

### Your own domain (better)

```
MAIL_TRANSPORT=smtp
SMTP_HOST=smtp.yourprovider.com
SMTP_PORT=587
SMTP_USER=...
SMTP_PASSWORD=...
SENDER_EMAIL=you@yourdomain.com
```

### The DNS records that actually decide deliverability

Without these, well-written mail still lands in spam. With them, ordinary mail
lands in the inbox. Add all three to the sending domain.

**SPF** — one record only. If you already have one, merge into it; two SPF
records is itself a failure.

```
yourdomain.com.  TXT  "v=spf1 include:_spf.yourprovider.com ~all"
```

**DKIM** — your provider gives you the selector and public key. Publish it and
enable signing in their dashboard.

```
sel1._domainkey.yourdomain.com.  TXT  "v=DKIM1; k=rsa; p=MIGfMA0..."
```

**DMARC** — start at `p=none` with reports so you can see what is failing, and
tighten to `quarantine` after a couple of weeks of clean reports.

```
_dmarc.yourdomain.com.  TXT  "v=DMARC1; p=none; rua=mailto:dmarc@yourdomain.com; adkim=s; aspf=s"
```

Verify before sending anything real:

```bash
dig +short TXT yourdomain.com
dig +short TXT sel1._domainkey.yourdomain.com
dig +short TXT _dmarc.yourdomain.com
```

Then send one message to a [mail-tester.com](https://www.mail-tester.com)
address and read the score. Below 8/10, fix it before going further.

### Volume

`DAILY_SEND_CAP` defaults to 30 per mailbox and is enforced in code. The
temptation is to raise it. Don't, at least not early: a new domain sending 200
cold emails on day one is the single clearest spam signal there is, and the
damage to a domain's reputation takes months to undo. Thirty well-targeted
messages a day is 600 a month, which is more outreach than most people
actually follow up on.

There is deliberately no "warm-up" feature here. Warm-up services work by
exchanging fake mail between accounts that open and reply to each other to
manufacture a reputation you have not earned. Sending real mail to real people
who are pleased to hear from you is the version of that which is not a lie.

### Unsubscribes

Every bulk message carries `List-Unsubscribe` and `List-Unsubscribe-Post`
headers and a footer link. Gmail and Yahoo require these for bulk senders. The
link points at `PUBLIC_BASE_URL/unsubscribe` — if the dashboard is not
reachable from the internet, the header still works but the link will not, so
either expose it or accept reply-based opt-outs.

Anyone who opts out, by link or by replying "unsubscribe", goes on a permanent
suppression list shared by all four agents.

---

## 3. Your data

See [AGENTS.md](AGENTS.md). Briefly:

| File | Used by | What happens if it is empty |
|---|---|---|
| `profiles/master_resume.yaml` | job_hunter | it cannot tailor anything |
| `profiles/targets.yaml` | the three outreach agents | no leads to work |
| `profiles/dev_rate_card.yaml` | fullstack_sales | falls back to built-in defaults |
| `profiles/video_rates.yaml` | video_client | writes PLACEHOLDER rather than guessing a price |

---

## 4. Running it

```bash
python run.py doctor      # should be clean
python run.py serve       # dashboard on 127.0.0.1:8080
```

Set `DASHBOARD_TOKEN` to something long. Anyone who can reach that port and
knows the token can approve outbound mail on your behalf. Keep the bind address
on localhost unless it is behind a reverse proxy with TLS.

Docker:

```bash
docker compose up dashboard              # SQLite
docker compose --profile pg up           # with PostgreSQL
```

The compose file mounts `./profiles` from the host, so you can edit your resume
and rate cards without rebuilding.

### Going live

1. `DRY_RUN=false`
2. Run one agent with `SPONSORSHIP_MAX_LEADS=1`
3. Read the draft properly before approving it
4. Check it arrived, and check where it landed

Then raise the limits.
