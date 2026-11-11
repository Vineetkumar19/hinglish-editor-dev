# Agent Suite

Five connected workflows for community activity, sponsorship outreach, video
editing, development projects and job applications. Graphs save progress in
SQLite. External writes wait for your review in the console or Telegram.

The **Workflows** view adds readiness checks, client-delivery reviews, selected
inbox commitments, learning evidence, bounded retrieval experiments, release
packages and SaaS demand research. Installed StoryLens, Cortana and repository
receivers completed a real owner-internal media delivery, diagnostics,
repository checks and a saved native publication draft. The planning selector
offers **ChatGPT through existing Codex sign-in, local 14B, or local 9B**; all
three answered live requests. Creative/customer review and actual publication
remain separate gates. See [implementation and acceptance evidence](docs/NEW_WORKFLOWS_IMPLEMENTATION.md).

## Start on this laptop

Setup is complete in `D:\Agents\.venv` with Python 3.12.14, Playwright and the
installed Chrome browser. Open PowerShell in `D:\Agents` and run:

```powershell
.\start.ps1
```

The console opens with its local access token. Select an agent and review its
cards. Existing credentials and pending cards are preserved. The existing
`.env` has `DRY_RUN=false`, so approving an email or application can perform the
real action. Set `DRY_RUN=true` before starting for a simulation.

To enable inbox monitoring, daily drafting and Telegram control as well:

```powershell
.\start.ps1 -Scheduler -Telegram
```

Worker logs are in `data/logs/`. Use `Ctrl+C` for the foreground console and
`stop.ps1` for recorded background workers. `start.ps1 -Background -NoOpen`
starts a hidden console. Start only one console on a given port. For a fresh
installation, run `setup.ps1` first.

## Laptop and model

Measured hardware: Ryzen 9 8940HX, 16 cores / 32 threads, 15.2 GiB usable RAM,
and RTX 5070 Ti Laptop GPU with 12,227 MiB VRAM. The selected installed model
is **`storylens-meaning:14b`**, Qwen3 14B Q4, through Ollama. It uses an 8K
context and GPU offload, with thinking disabled. A shared file lock serializes
local inference across console, scheduler and Telegram processes.

Those settings describe the original agents. The new Workflows view defaults
to ChatGPT and permits explicit per-task 14B/9B selection. It does not silently
change existing agent profiles or fall back between providers.

The installed 9B Q6 model was faster on a short structured email test, about
51 tokens/s versus 41 for 14B. Longer development drafts exposed inconsistent
JSON from 9B. The 14B model completed all five workflow checks and a real
read-only tool call. These fixture checks do not establish accuracy on every
website. No additional model download or paid API is required.

Measurements are saved in `data/laptop-profile.json`,
`data/model-benchmark.json`, `data/local-model-validation.json` and
`data/local-tools-validation.json`.

## Confirmed work preferences

Immediate availability; at least **INR 50,000/month** for salaried roles; at
least **INR 10,000/project** for freelance work. Higher service floors remain
in effect. The separately configured USD project floor is USD 150; the suite
does not guess live exchange rates.

Known INR pay is compared by period. Unknown pay, other currencies and unclear
budget periods stay reviewable. Work authorization and sponsorship answers
remain blank in `profiles/application_answers.yaml` until supplied. Required
unknown fields block form submission.

## Workflows

| Agent | Workflow | Review and delivery |
| --- | --- | --- |
| `community` | Public RSS/Atom discussions or supplied contexts; useful replies; saved discussion context and lessons | Disclosed affiliation and manual posting handoff |
| `sponsorship` | Curated targets and discovery; published contacts; personalized pitch; replies and interest alerts | Approve each email; phone, form and social routes become saved handoffs |
| `video_client` | Editing work discovery; portfolio pitch; rate replies and counters; proposal and deposit invoice on acceptance | Approve each email and attachments; record the agreed deal after delivery |
| `fullstack_sales` | Project discovery; scope questions; component or package pricing; negotiation and closure | Approve pitches, quotes and replies; prices come from code and rate cards |
| `job_hunter` | Discovery; fraud/pay filtering; truthful resume tailoring; PDF; form inspection; factual answers; upload/submission; interview availability and booking | Separate job/resume and form reviews; only observed confirmation records `applied` |

The pre-existing `saas_sales` agent remains separate and parked until
`SAAS_ENABLED=true`.

Unanswered actual contacts can enter a reviewed follow-up queue after five
days, with a maximum of two reminders. Replies or changed lead status cancel
stale reminders. Manual handoffs count as sent only after you record the send.
Email receipts prevent replaying a confirmed delivery. An uncertain delivery
requires checking the mailbox before retrying.

## Accounts and applications

Existing SMTP/IMAP settings are preserved. The monitor uses IMAP for SMTP
mail, or Gmail for that transport. Google Calendar needs OAuth client settings
and sign-in:

```powershell
.\.venv\Scripts\python.exe run.py auth google
```

See `GMAIL-SETUP.txt` and `docs/SETUP.md`. Gmail push also needs Pub/Sub and
public HTTPS; polling works without a public push endpoint. Sender DNS remains
with the mail provider.

Browser support handles accessible forms, uploads and fields in frames. Login,
CAPTCHA, unsupported multi-step forms, unknown required answers and ambiguous
submit buttons stop for human completion. Changed forms require fresh review.
Dry runs never upload a resume.

```powershell
.\.venv\Scripts\python.exe run.py apply 'https://employer.example/apply' --resume 'D:\Agents\data\resumes\your-resume.pdf'
.\.venv\Scripts\python.exe run.py book --summary 'Interview' --start '2026-11-02T10:00:00+05:30' --end '2026-11-02T10:45:00+05:30' --attendee 'recruiter@example.com'
```

These commands create review cards. Booking approval creates the event and
sends the listed invitations after checking availability again. An explicit
choice of a previously emailed slot also creates a booking card.

Payment details are intentionally unset. An accepted editing deal can close
with its proposal while the invoice waits for payment instructions. No invoice
with placeholder payment details is attached to the closing email.

## Validate

```powershell
.\.venv\Scripts\python.exe scripts/run_tests.py
.\.venv\Scripts\python.exe scripts/smoke_local.py
.\.venv\Scripts\python.exe scripts/smoke_tools.py
.\.venv\Scripts\python.exe scripts/audit_project.py
.\.venv\Scripts\python.exe run.py doctor
```

Tests strip project environment settings, use isolated databases and block
external networking. Local fake SMTP, Google, Telegram, websites and ATS forms
exercise real client protocols. Model checks permit loopback connections only
and force dry-run delivery. Test results are in `data/test-results.json`, with
detailed output in `tmp/tests/results.txt`. The source manifest inventories
project files and compiles Python; semantic behavior is checked separately.

## Implementation

See `docs/WORKFLOW_IMPLEMENTATION.md` for PDF requirements, code mapping and
account-dependent steps. `core/` holds the runtime and shared clients;
`agents/` holds workflows; `server/` holds console and Telegram; `profiles/`
holds your facts, targets and rate cards.

The suite keeps its lightweight graph engine and SQLite rather than running
several extra orchestration and memory servers on a 16GB laptop. Community
replies disclose affiliation and remain reviewed manual posts. Hidden fan
personas, fingerprint evasion and artificial mailbox warm-up from the PDFs
are not enabled.
