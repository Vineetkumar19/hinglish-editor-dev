# Suite workflow adapter v1

The client and three local receivers are installed. Actual acceptance evidence
and limits are in `NEW_WORKFLOWS_IMPLEMENTATION.md`.

`profiles/workflow_integrations.json` (or `SUITE_INTEGRATIONS_FILE`) maps receivers
to dynamic `connection_file`, private `token_file` and device identity. Fixed
`base_url`/`token_env` remain supported. Remote transport requires HTTPS; no
redirects. Local servers bind loopback, authenticate requests and reject browser
Origin headers. Requests/responses are capped at 2 MB, client calls at ten
seconds. Long work returns an ID for reconciliation. Configuration alone starts
no services.

- `GET /capabilities`: version, project/device/runtime/source hash, active jobs,
  actual actions, ledger owner and verified Trial Reels account map (empty now).
- `POST /tasks`: TaskEnvelope, exact approved body, approval and immutable
  `action_<payload-hash>`. Receiver rechecks capability/role, expiry, target,
  device and artifact bytes, then commits the claim before execution.
- `GET /tasks/<action-id>`: reconcile existing receiver/native publisher state;
  never resubmit. Includes exact hash/ID, status, evidence and actual result.
- `POST /tasks/<action-id>/cancel`: cooperative executor cancellation or existing
  publisher cancellation. Uncertain external effects remain uncertain.

A verified package receipt means the local draft was saved, not published.
Publication verifies only through native remote evidence. Known submissions can
be reconciled after approval expiry; expiry still forbids a new submission.
Atomic result journals recover a completed result whose DB acknowledgment was
lost. Restart does not replay unfinished actions. Partial output stays available;
new execution requires a reviewed revision.

| Receiver | Action | Boundary |
|---|---|---|
| StoryLens | `storylens.prepare` | Explicit source excerpt <=180 seconds; native inspector, GPU lock and renderer; full decode/source hash |
| StoryLens | `storylens.package` | Exact native publisher draft; unapproved previews stay drafts |
| StoryLens | `storylens.publish` | Approved artifact/copy/account/time/audience/visibility; existing ledger/worker only |
| Cortana | `diagnostics.read` | Native system sample |
| Cortana | `delivery.package` | Verified local files, unsent attached EML and native workspace; no desktop input/Send |
| Repository | `repository.prepare` | Bounded existing test file in registered D:/Agents; isolated runner, no deployment |

Arbitrary editor mutation, model-written commands, automatic UI, mail sending and
foreign-device paths are not admitted. Artifacts must be selected non-credential
A: files with matching hashes. Models plan separately and cannot broaden these
capabilities. Desktop input stays with one explicit controller.

`scripts/verify_receiver_restart.py` checks actual persisted receipts.
`tests/test_workflow_receivers.py` separately covers crash journals, uncertain
replay, credentials, model schema, expiry reconciliation and backup restore.
Neither fixture checks nor a native draft prove platform publication.
