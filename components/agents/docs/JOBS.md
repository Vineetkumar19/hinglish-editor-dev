# The job agent: getting the right jobs, not just any jobs

A public job board's search endpoint matches loosely and ranks by recency. Ask
one for "engineer" and it will hand back Inside Sales Contractor, Tier III
Service Desk Engineer and Freelance Writer, because all three contain a word
you searched for. That is what the filter in this agent exists to stop.

## Three gates

Every posting has to pass all three before it reaches your phone.

**1. Is it the kind of work you want?**
The title is matched against role families. Anything that matches none is
dropped, and a list of hard exclusions (sales, recruiting, support, service
desk, writing, data entry) is checked first, so "Sales Engineer" is rejected
even though it contains "Engineer".

| Family | Catches |
|---|---|
| `software` | Software/Backend/Frontend/Full Stack Engineer, SDE, Platform |
| `java` | Java Developer, Spring Boot, Java Full Stack |
| `python` | Python Developer, Django, FastAPI |
| `ai_ml` | ML Engineer, AI Engineer, Applied Scientist, MLOps, NLP, CV |
| `agentic_ai` | AI Agent, Agentic, LLM Engineer, GenAI, AI Automation |
| `forward_deployed` | Forward Deployed Engineer, FDE, Solutions Engineer |
| `data_engineering` | Data Engineer, Analytics Engineer, ETL, Data Platform |
| `data_analysis` | Data Analyst, Business Analyst, BI, Data Scientist |
| `devops` | DevOps, SRE, Cloud, Infrastructure |

Change which are active from Telegram: `/roles ai_ml agentic_ai software`, or
`/roles all`. `/roles` on its own shows what is currently on.

**2. Is the seniority within reach?**
Senior, Staff, Lead, Principal, Architect, Manager and Director in a title all
imply years you do not have yet. With your experience at 0 they are dropped.

**3. Does the description demand more years than you have?**
The description is scanned for "5+ years", "minimum of 3 years", "3-5 years",
"at least 2 years", and for fresher signals like "new grad", "entry level" and
"freshers welcome". A posting that never mentions years is kept — most do not
mention it, and dropping all of them would throw away most of the market.

## Your experience level

Set it from Telegram. It is written back into `.env`, so it survives restarts.

```
/exp          shows what you are set to
/exp 0        fresher (the default)
/exp 1        after a year
/exp 2        after two
```

There is deliberate slack of 2 years on top (`JOB_EXPERIENCE_SLACK`). At `/exp 0`
you still see postings asking for up to 2 years, because plenty of those
interview strong freshers. You do not see ones asking for eight.

## What each job card shows

```
Backend Engineer (Python)
Razorpay  |  FRESHER OK

Pay        not stated
Experience open to freshers
Where      Bengaluru  (remote)
Type       software

Skills they ask for
Python, Django, PostgreSQL, Redis, Docker, AWS, REST API

Your resume covers 43% of their keywords
Nothing on the resume was made up
```

With three buttons: **Send me the resume** (the tailored PDF for this specific
job, so you can read it before deciding), **Approve** / **Reject**, and **Open
the application** which takes you straight to the form.

## Where the jobs come from

| Source | Needs a key | Good for |
|---|---|---|
| `greenhouse` | no | The best signal by far — a company's own board, full descriptions |
| `remotive` | no | Remote-only, skews senior, useful as a top-up |
| `remoteok` | no | Remote-only, tag-based |
| `lever` | no | Same idea as greenhouse, different ATS |
| `adzuna` | free key | **Indian non-remote listings, with salaries** |

`GREENHOUSE_BOARDS` ships with a verified list. To add a company: open their
careers page, and the board token is the path segment in the URL —
`job-boards.greenhouse.io/razorpaysoftwareprivatelimited` means the token is
`razorpaysoftwareprivatelimited`.

### Worth doing: add Adzuna

Greenhouse boards almost never publish salary, and they skew towards remote and
global roles. Adzuna covers the Indian market properly and does carry salary
figures. A key is free and takes a minute at
[developer.adzuna.com/signup](https://developer.adzuna.com/signup). Then in
`.env`:

```
ADZUNA_APP_ID=your_id
ADZUNA_APP_KEY=your_key
ADZUNA_COUNTRY=in
JOB_SOURCES=greenhouse,adzuna,remotive,remoteok
```

## When nothing comes back

That is usually correct rather than broken — at 0 years, on a given day, most
of what is posted is genuinely too senior. Options, in order of how much they
cost you:

1. `/roles all` — turn on every family including devops
2. `/exp 1` — if you are about to cross a year
3. Add more companies to `GREENHOUSE_BOARDS`
4. Add Adzuna, which roughly doubles what is reachable

The end-of-run message lists what was filtered out and why, so you can see
whether the filter is being too strict rather than guessing.

## Interview calls

The inbox monitor handles SMTP/IMAP or Gmail and queues interview replies.
Calendar availability requires Google OAuth (`python run.py auth google`).
An explicit choice from previously offered slots creates a booking review;
approval checks free/busy again before sending invitations. Run the inbox
poller with `python run.py inbox` or the continuous `python run.py schedule`.
