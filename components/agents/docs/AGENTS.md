# The agents

All agents share a shape: a durable state graph that pauses at anything
consequential. What differs is who they contact and what they say.

Common commands:

```bash
python run.py run <agent>       # one pass
python run.py approvals         # what is waiting
python run.py approve <id>      # decide from the terminal
python run.py graph <agent>     # print the graph
python run.py leads --detail    # what has been found so far
```

---

## Running each agent

Four agents, four commands. Each one drafts, then stops and waits for you.

```bash
python run.py run sponsorship      # brands who might sponsor the channel
python run.py run video_client     # creators who need a video editor
python run.py run fullstack_sales  # businesses who need a site built
python run.py run job_hunter       # jobs, resumes and applications
```

To watch any of them work without setting anything up first, use the demo -
it uses bundled sample data, reaches nothing on the internet and sends nothing:

```bash
python run.py demo                      # all four, one after another
python run.py demo --agent sponsorship  # or jobs, video, dev
python run.py demo --pause              # stop and let you decide
```

From your phone, `/run sponsorship`, `/run video`, `/run dev` and `/run jobs`
do the same thing - see [TELEGRAM.md](TELEGRAM.md).

## Your data comes first

The agents draw only on what is in `profiles/`. Fill these in before running
anything; the quality of the output is almost entirely a function of how
specific this is.

### `profiles/targets.yaml`

The lead list. `SEARCH_PROVIDER=seeds` reads it directly; the web-search
providers (`brave`, `serper`, `searxng`) are there if you want discovery to be
automatic.

```yaml
targets:
  - name: Example Fantasy Sports Co
    url: https://fantasy.example
    category: fantasy_sports      # agents filter on this
    note: runs a creator partnership programme
    tags: [cricket, fantasy, india]
```

Categories in use: `fantasy_sports`, `sports_equipment`, `analytics` for
sponsorship; `creator` for video clients; `software_prospect` for dev sales.

For a niche like Indian fantasy cricket, twenty hand-checked companies beat a
thousand scraped URLs, and you can see exactly who is being contacted.

### `profiles/master_resume.yaml` and `profiles/master_resume_video.yaml`

Two profiles, because software engineering and video editing are two different
careers. A backend interviewer does not want to read about colour grading, and
a creator hiring an editor does not want to read about Spring Boot. Mixing them
weakens both, so they never share a file:

| File | `track` | Used for |
|---|---|---|
| `master_resume.yaml` | `software` | job applications, engineering roles |
| `master_resume_video.yaml` | `video` | editing clients and creative work |

`python run.py doctor` checks each profile for the other one's vocabulary and
warns you if material ever leaks across. There is a test for it too, and a
second test that deliberately plants a leak to prove the check can fail.

Whichever profile is in use is the **only** source the agent may draw on. It
selects, reorders and lightly rephrases what is there — anything it adds beyond
the file is detected and stripped before the PDF is written.

Two rules the builder enforces for you:

- **Jobs are listed newest first, never by relevance.** A recruiter reads the
  top entry as "where they are now", so relevance ranking would make an old
  internship look like the current role. The file is authored newest-first and
  that order is restored no matter what the ranker returns.
- **Three projects reach the page**, chosen per job by how well they match it.
  Mark your favourites with `featured: true` and they win ties. Keep every
  project in the file — the more there are, the better the match. Change the
  count with `RESUME_MAX_PROJECTS`.

Each experience entry needs a stable `id`. Bullets should be specific and
measurable where you honestly can be.

> A YAML note: a list item containing `: ` is parsed as a key/value pair. Quote
> such lines — `- "Handled the pipeline: edit, grade, mix"`.

### `profiles/dev_rate_card.yaml` and `profiles/video_rates.yaml`

Your prices. Quotes are computed in code from these; no model ever produces a
number. If `video_rates.yaml` is empty the agent writes `PLACEHOLDER` and flags
the draft rather than guessing.

---

## sponsorship

Finds brands in the channel's niche, locates whoever owns partnerships, and
sends one specific enquiry.

```bash
python run.py run sponsorship
```

Flow: `discover → pick_lead → research → qualify → draft → approve ⏸ → send`

**Qualification.** Scores on contact quality (a `partnerships@` address beats a
`support@` one; `firstname.lastname@` beats both), whether the site is readable,
and whether it mentions a partnership or creator programme at all. Below
`SPONSORSHIP_MIN_SCORE` it is skipped and the domain recorded so it is not
revisited.

**Phone-only leads are kept.** If a site has a number but no email, the lead is
saved as `manual_followup` with the number normalised to `+91…`, for you to
message by hand. It is not discarded.

**What it will not say.** It never states audience numbers, rates or
availability — it does not have them. Ask it to and it writes `PLACEHOLDER` and
flags the draft. Fill those in yourself; they are the numbers a brand will hold
you to.

Key settings: `SPONSORSHIP_MAX_LEADS`, `SPONSORSHIP_MIN_SCORE`,
`SPONSORSHIP_CATEGORY`, `YOUTUBE_CHANNEL_URL`.

---

## video_client

Finds creators who plausibly need an editor and offers samples.

```bash
python run.py run video_client
```

Same flow, different qualifier. It looks for explicit signals — "looking for an
editor", "editing everything myself", a demanding publishing schedule, a
work-with-me page — and weights them. No signal, no pitch.

First contact links to `PORTFOLIO_URL` (a Google Drive folder is fine) rather
than attaching anything: attachments on cold mail are a spam signal.

When someone asks about rates, the reply engine quotes only from
`profiles/video_rates.yaml`.

Key settings: `VIDEO_CLIENT_CATEGORY=creator`, `PORTFOLIO_URL`,
`VIDEO_RATES_FILE`.

---

## fullstack_sales

Two graphs: outreach, and quoting.

```bash
python run.py run fullstack_sales      # outreach
```

**Outreach** reads the prospect's stack from their page source. jQuery,
an old Bootstrap, Wix or Squarespace score as opportunity; React or Next.js
score slightly negative, because they probably do not need you. The pitch names
what was detected and says plainly that it is an outside guess.

**Quoting** runs when a prospect asks what something costs. Scope is inferred
from their own words, priced from `dev_rate_card.yaml`, and the graph stops:

```
analyse → price → draft_proposal → approve_quote ⏸ → send
```

At the gate you see the full line-item breakdown and can **override the total** —
the new figure is propagated through the body and the subject. Reject, and
nothing is sent.

If the message is too vague to scope, the graph ends at `insufficient_scope`
and produces no number at all. An estimate invented from nothing is worse than
no estimate: you will be held to it.

Pricing is a pure function — same scope in, same number out, every time.

---

## job_hunter

```bash
python run.py run job_hunter
python run.py run job_hunter --query "Backend Engineer" --query "Platform Engineer"
```

Flow: `aggregate → screen → tailor → render → review ⏸ → applied`

**Aggregation** across whichever boards you enable in `JOB_SOURCES`:
`greenhouse`, `lever`, `remotive`, `remoteok`, `adzuna` (best Indian coverage),
`jsonfeed`, or `fixture` for testing. Postings are deduplicated by company and
normalised title, so a role listed on three boards is processed once.

**Fraud screening**, in two stages:

1. Heuristics on near-conclusive indicators: a request for money, identity
   documents demanded before an interview, interviews held entirely on WhatsApp
   or Telegram, a recruiter on a free email domain for a named company,
   unrealistic daily earnings, pressure tactics. Tuned for near-zero false
   positives — wrongly binning a real job costs you an opportunity.
2. Consistency analysis on what survives: ten years of experience demanded at
   intern pay, a description too lexically thin to describe an actual job, a
   recruiter domain that does not match the company.

Rejected postings are recorded with their reasons, so you can audit the filter
rather than trust it.

**Resume tailoring.** The model is never asked to write a resume; it selects
and reorders from your master profile and may lightly rephrase a bullet. Then
every rephrasing is scanned against the master corpus and any unsupported
number, employer, technology or acronym is stripped. If too much is stripped,
the tailoring is abandoned in favour of untailored material. You see exactly
what was removed at the review gate.

The PDF is generated with real text operators, so an ATS can parse it. Check
for yourself:

```bash
pdftotext data/resumes/<file>.pdf -   # or open it and try to select the text
```

**Applications have two review stages.** Review the job and tailored PDF first.
With `JOB_AUTO_APPLICATIONS=true`, the browser then inspects the actual form and
queues its fields and factual answers for separate review. That approval permits
filling, upload and submission. Unknown required answers and unsupported portals
pause for human completion. See `WORKFLOW_IMPLEMENTATION.md`.

---

## Replies

```bash
python run.py inbox       # once
python run.py schedule    # continuously
```

New mail is matched to the lead it belongs to and classified:

| Intent | What happens |
|---|---|
| `interested` | you are paged immediately, then a reply is drafted for approval |
| `question` | reply drafted for approval |
| `objection_price` / `objection_timing` | reply drafted for approval |
| `referral` | reply drafted; the new contact is yours to add |
| `not_interested` | lead closed, no reply sent |
| `unsubscribe` | suppressed permanently, across all agents |
| `out_of_office` | snoozed 30 days |
| `auto_bounce` | address suppressed; you are warned if the rate passes 2% |

The last four are decided by rules, not by the model, and the rule wins even if
the model disagrees. Misreading an opt-out as interest is the one mistake with a
legal cost.

---

## Interviews

A reply that reads like an interview request is routed to the scheduler, which
reads your real calendar free/busy, proposes times that do not clash, and waits
for your approval before offering them. It will not offer a slot it did not
find. On confirmation, `confirm_slot()` creates the event with a Meet link and
invites the recruiter.

Settings: `INTERVIEW_MINUTES`, `SCHEDULE_DAYS_AHEAD`, `SCHEDULE_MAX_SLOTS`,
`SCHEDULE_LEAD_HOURS`, `TIMEZONE`.

---

## Running unattended

```bash
SCHEDULED_AGENTS=sponsorship,job_hunter python run.py schedule
```

Or cron:

```
*/10 * * * *  cd /path/to/agentsuite && python run.py inbox
0 9   * * 1-5 cd /path/to/agentsuite && python run.py run sponsorship
0 10  * * *   cd /path/to/agentsuite && python run.py run job_hunter
0 4   * * *   cd /path/to/agentsuite && python run.py watch
```

Unattended means unattended *drafting*. The approval queue fills up and waits;
nothing is sent while you are asleep.
