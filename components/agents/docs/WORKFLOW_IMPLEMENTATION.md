# Workflow implementation

The five workflows extend the existing Agent Suite in `D:\Agents`. Requirements
come from `ai agent 1,2.pdf` (11 pages) and `ai agent 3,4,5.pdf` (12 pages), under
`E:\Cortana AI Agent\Agents`. Existing profiles, credentials, SQLite state and
pending production approvals are preserved.

## Requirements mapped to code

| Requirement | Implementation |
| --- | --- |
| Community discovery, contextual replies and memory | `agents/community/agent.py`, `profiles/community.yaml`, `core/lessons.py`; public RSS/Atom or supplied contexts, disclosure, saved review history and manual posting |
| Sponsorship prospecting, email and phone/form fallbacks | Existing sponsorship discovery, crawler and pitch modules; `core/mailer.py`, `core/delivery.py`; actual delivery receipts and operator-confirmed handoffs |
| Reply monitoring, classification and interest alerts | `core/inbox.py`, `core/imapbox.py`, `core/gmail.py`, shared reply graph and notifier; unsubscribe/bounce rules override model classification |
| Video samples, pricing, negotiation, proposal and deposit invoice | `agents/video_client/pitch.py`, `quote.py`, `docs.py`, `agents/sales_conversation.py`; saved agreed amount and reviewed MIME attachments |
| Development scope, deterministic prices and closure | `agents/fullstack_sales/pricing.py`, `packages.py`, `pitch_replies.py`, `agents/sales_conversation.py`; missing scope produces a question |
| Scheduled follow-up | `core/followups.py`; actual unanswered contacts only, review per reminder, maximum two, canceled after engagement |
| Job aggregation, scam screening and user pay preferences | Existing job source, relevance, location and scam modules plus `core/work_policy.py` |
| Truthful resumes and PDF output | Separate software/video master profiles, existing tailoring and unsupported-term guard in `agents/job_hunter/resume.py` |
| ATS inspection, form filling, uploads and submission | `core/browser.py`, `agents/job_hunter/application.py`; observed field plan, supplied answers, separate approval, changed-form detection and confirmation-based status |
| Interview availability and booking | `core/calendar.py`, interview graph, `agents/job_hunter/booking.py`; local working hours, real free/busy, reviewed slot/invite and stable event IDs |
| Durable state, review and cycle limits | `core/graph.py`, `core/hitl.py`, `core/registry.py`; checkpoints, isolated resume contexts, atomic decisions and registered subflows |
| Console and Telegram | `server/app.py`, `server/console.py`, `server/bot.py`; community category, subflow routing, editable application answers, handoff cards and live status |
| Laptop setup and operation | `setup.ps1`, `start.ps1`, `stop.ps1`, `scripts/configure_laptop.py`; local Python environment, Chrome, installed Ollama model and shared inference queue |

## Deployment choices

The selected installed model is `storylens-meaning:14b`, Qwen3 14B Q4, with an
8K context, GPU offload and one generation at a time across suite processes.
The 9B Q6 model was faster on the short email benchmark but produced inconsistent
JSON on a longer development draft. The 14B model completed all five workflow
fixtures and a real read-only tool call. Templates remain a configured fallback;
model smoke checks disable fallback to distinguish real inference from templates.

Immediate availability, INR 50,000/month salary minimum and INR 10,000/project
are confirmed user facts. Higher service floors remain effective after discounts.
Other currencies use separately configured floors; uncertain budgets stay visible
for review. Work authorization and sponsorship answers remain unspecified.

The implementation keeps the existing local durable graph and REST clients.
It does not run LangGraph, Letta, cloud databases and multiple browser/model
servers together on a 16GB laptop. The PDFs' hidden community identities,
fingerprint evasion and artificial warm-up networks are replaced by disclosed,
reviewed community drafts and ordinary browsers.

## Delivery and application states

An approved gig with a published email is sent through SMTP/Gmail and becomes
`contacted` after success. Form/social destinations become `ready_to_send`,
then require operator confirmation of the actual manual send. Dry runs are
stored as `dry_run` and do not spend the live allowance. Confirmed email receipts
prevent replay; an uncertain SMTP outcome blocks automatic retry.

Job review produces `ready_to_apply`, followed by an observed-form review with
answers, missing information and the resume path. A submission confirmation
produces `applied`. Missing information produces `needs_human`; ambiguous
submission produces `submission_unconfirmed` and is not automatically retried.
Changed fields return to review. Login, CAPTCHA and unsupported multi-step ATS
flows need human completion; this adapter does not cover every employer portal.

Calendar proposals come from actual free/busy results. Without a connected
calendar, the reply asks the recruiter for preferred times without claiming
availability. A booking review contains a specific slot and invitees. Booking
checks availability again and uses a stable Google event ID to support retries.

## Validation evidence

`data/test-results.json` records the full isolated suite; detailed output is in
`tmp/tests/results.txt`. Cases cover real localhost SMTP delivery, edits, receipts,
manual handoffs, agreed video prices and attachments, concurrent graph resumes
and decisions, deferred inbox routing, pay limits, calendar conflicts, changed
forms and real Chrome submission to a local ATS with a resume upload.

`data/local-model-validation.json` records all five real-model dry runs with
payloads, timing and call counts. `data/local-tools-validation.json` checks an
actual model tool call against the effective project floor. The initial model
comparison is in `data/model-benchmark.json`. The project review manifest lists
source/config/document files, hashes, line counts and Python compilation checks,
excluding generated state and downloaded dependencies. Compilation alone does
not establish semantic correctness.

Validation sent no real outreach email, job application or calendar invitation.
SMTP and ATS writes used local fixtures. Live accounts and employer portals
require their own successful connection.

## Account-dependent steps

Google Calendar requires OAuth client configuration and user sign-in. Gmail
push requires Pub/Sub and reachable HTTPS; polling works without public push.
Telegram needs the bot token, operator chat and owner binding. Sender DNS
authentication belongs to the provider and domain settings.

Fill in work authorization and sponsorship facts in
`profiles/application_answers.yaml`, or on the observed-form review card.
Required missing facts block submission. No unspecified screening or legal
consent answer is supplied automatically.

The console is the default launch. Inbox, scheduled drafts and Telegram start
when the corresponding `start.ps1` switches are selected. Every external write
still requires its review decision. Existing production cards were not approved
by the validation scripts.

## Official library references

- [Ollama chat API](https://docs.ollama.com/api/chat) and [structured outputs](https://docs.ollama.com/capabilities/structured-outputs)
- [Playwright form input APIs](https://playwright.dev/python/docs/input)
- [Google Calendar event creation](https://developers.google.com/workspace/calendar/api/v3/reference/events/insert)
