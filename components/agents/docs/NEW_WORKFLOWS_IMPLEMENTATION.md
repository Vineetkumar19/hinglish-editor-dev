# New workflows: implementation and acceptance

4 November 2026. Receiving adapters and model choices are installed and
live-tested. The owner explicitly accepted the selected internal delivery and
five drafts after technical verification. Receipt: `data/real-delivery-acceptance/owner-internal-acceptance.json`.
Commercial, creative and publication acceptance are separate gates.

Source: ten-page `specifications/Agent_Suite_New_Workflows_Architecture.pdf`,
SHA256 `dd5d311b2e23f2b57bd2f69a410b76794169934e0eff49bc953b99b2f716615c`.
All ten pages were read and rendered. This supersedes the earlier fixture-only
report; historical receipts are preserved.

## Brain choices

The Workflows form offers ChatGPT through existing Codex sign-in, installed
`storylens-meaning:14b`, installed `storylens-planner:9b-q6`, and prepared inputs
without inference. ChatGPT is selected first. All three models answered actual
structured requests; receipts are in `data/brain-validation`. The real delivery
plan and learning exercise used ChatGPT.

Official Codex CLI runs read-only with tools disabled and a strict output schema.
No API billing or credentials were created. Local inference participates in the
existing StoryLens GPU lock. No automatic fallback. Selected source text goes to
the chosen provider; local locators and unrelated configuration are excluded.
Models propose steps/copy, while deterministic executors retain permission,
revision, account and artifact checks. Cancellation prevents subsequent work;
an in-flight model call can continue until response or bounded timeout.

## Actual receiving integrations

`adapters/receiver.py` runs in each project's installed Python. Three authenticated
loopback receivers are configured in `profiles/workflow_integrations.json`.
They start no publisher worker, scheduler, desktop automation or model service.
`scripts/start_workflow_adapters.py` starts/reuses them. Tokens stay in local
files, outside task payloads and reports.

| Route | Actual outcome | Evidence under `data/real-delivery-acceptance` |
|---|---|---|
| StoryLens media | Native source inspection and GPU-coordinated NVENC excerpt; full decode, dimensions, duration and unchanged source verified | `result.json` |
| Cortana delivery | Hash-verified MP4, unsent EML with attachment, delivery manifest and native workspace | `result.json` |
| Cortana diagnostics | Native 30-second system sample | `integrated-result.json` |
| Repository | Bounded planning tests executed in installed receiver; no deployment | `integrated-result.json` |
| StoryLens Publisher | Exact native draft `ec947cd3640f4b09`; no authorized_at, upload or remote post | `release-draft-result.json` |
| Restart | Current receiver code loaded; five real receipts reconciled through GET without resubmission | `restart-verification.json` |

The publication-ledger job is not a PreparePost preparation. Current
`publisher.html` redirects to PreparePost, whose `?drafts=` expects preparation
IDs and correctly refuses this job ID. No preparation stages were fabricated.
The Suite displays the package and native receiving receipt; PreparePost UI
coverage is not claimed. Cached account identity matched; the old receipt field
`account_connection_verified` means this binding, not fresh platform OAuth/API
verification. Current code names it `account_binding_verified`.

The coordinated Cortana chat verified the exact restore in the running app:
review Resolved, outcome Opened, and an Explorer window for the exact folder.
Explorer was minimized before its contents could be visually inspected; computer
control interruption is recorded separately. File hashes and browser playback
independently verify the package.

## Real selected delivery

The owner delegated asset choice. We selected `D:/Chrome Downloads/reel1.mp4`
and recorded an owner-internal commission, INR 0, without inventing a customer
or commercial agreement. Task `task_ff6f9c08e87b4c4c9a12` retains scope review,
native render, revision 2 delivery handoff and duplicate-dispatch reuse.

The result is a straight ten-second 960 x 720 excerpt retaining source composition
and audio. Existing graphics were baked into the source. Output SHA256:
`63ce7034d190f7a54eb2bc91421f0b872c31c5729fa774f828baacd23fd2f45c`.
Chrome played this actual file through the end. Owner accepted it for internal
acceptance, without granting production publication approval. The local
draft recipient is deliberately non-deliverable; nothing was sent.

This is real media through real receiving executors using an isolated acceptance
database. It is not a paid-client enquiry, testimonial or claim that all native
editor routes in the separate StoryLens project passed. Production contacts and
settings were preserved.

## PDF coverage and remaining gates

| Requirement | Implemented and exercised | Scope or remaining gate |
|---|---|---|
| Shared console/contracts | Existing Store, contacts, approvals and runner; seven roles; current uniform Outcome, immutable revisions, leases, lineage | Historical outcomes are not fabricated |
| Health/recovery | Nine configured probes, native diagnostics, bounded transient retries, last success, failure categories, stale checkpoints | Model probes read actual-response receipts with 24-hour freshness; they do not generate on each health check. No automatic security/process changes |
| Inbox | Actual selected owner message, exact quotes, source/time provenance, reviewed commitment, duplicate-free reimport | Original clock time unknown; actual import time explicitly labelled. No deadline invented or mailbox collector enabled |
| Experiment | Six actual hash-verified StoryLens catalogue videos; token-overlap vs TF-IDF metadata lookup; fixed held-out labels and reproducible second run | Both MRR/recall 1.0: reject adoption for no gain on this small benchmark. No embedding/visual-quality claim or production replacement |
| Learning | Completed delivery evidence classified personal lab; ChatGPT exercise and factual summary | Owner summary review pending; not employer/client experience |
| Release | Exact source/copy/account/time binding; native local draft; one StoryLens ledger; per-platform reconciliation | No sending/publishing authority. Approved shared-body/three-intro production assets absent. Three-intro contract tests used labelled fixtures; actual Trial Reels account support unverified |
| SaaS demand | Twenty accessed public issue reports, 19 authors, five specific unsent drafts; source/date/quotes, support status and suppression/dedup; owner accepted all five for internal acceptance | Public product feedback is not buying intent. No sending approved; ongoing discovery/sending off |
| Durability | Atomic result journals, no uncertain replay, expiry/revision gates, cancellation propagation, consistent SQLite backup/restore, tombstones | No cross-device transfer installed; current receivers share one physical device and reject foreign-device refs |
| Observability | Actual elapsed/retries/model calls/tokens, revision/correction/blocked counters, duplicates and errors | Unmeasured cost and peak process RAM/VRAM remain null. Python allocations are not total process/GPU memory |
| Retention | Terminal task redaction preserves replay tombstones/shared contacts; unshared brain-cache entry removed | Source/output files, brain logs, backups, commitments and receiving records have separate retention; no global-erasure claim |

The PDF's commercial enquiry and owner creative/usefulness gates are not silently
satisfied by internal technical acceptance. Actual publication and a three-intro
production release require exact approved assets/destinations and release scope.

## Verification and operation

Final regression: **469 tests, zero failures/errors, one skipped**. The skipped
legacy PDF extraction test needs optional `pypdf`. Final authenticated HTTP
fixture run: **16 checks passed**. Synthetic fixtures remain labelled separately
from live receiver/media/model evidence. Reports: `data/test-results.json` and
`data/workflow-validation/latest.json`.

Real SQLite backup and separate restore passed integrity and preserved action
counts; see `data/real-delivery-acceptance/backups`. No production DB was replaced.
The real review console is on port 54725; its private access URL is saved in
`data/real-delivery-acceptance/console.json`. The browser review stays open.
This uses the actual app code with separate acceptance data. Normal startup keeps
the original profiles/database. Production `.env`, DRY_RUN and
JOB_AUTO_APPLICATIONS values were preserved.

```powershell
.\.venv\Scripts\python.exe scripts/start_workflow_adapters.py
.\.venv\Scripts\python.exe scripts/verify_real_delivery.py --serve --port 54725
```

Existing case receipts are reused. Do not delete them to retry; changed assets or
copy require a reviewed revision. Verification commands:

```powershell
.\.venv\Scripts\python.exe scripts/run_tests.py
.\.venv\Scripts\python.exe scripts/verify_workflows_live.py
.\.venv\Scripts\python.exe scripts/verify_receiver_restart.py
```

Localhost testing needed approved execution because the sandbox denied sockets
with Windows 10013; no firewall/security setting was weakened. Task-owned UI
actions cease at handoff; user applications, streams and outputs are preserved.
