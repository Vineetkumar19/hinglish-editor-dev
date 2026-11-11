# Storylens feature context upgrade — 30 October 2026

Owner requested the larger per-feature architecture, with reliability ahead of speed, and corrected B-roll/Smart Visuals to text-only website retrieval. Protect the active RCB Ask Editor upload → Shorts → publishing workflow until it finishes. No model substitution or saved-guidance removal is authorized by this change.

## Installed source changes

`config.context.local.json` supplies explicit feature limits. It is separate from the unchanged `config.models.local.json` and publishing configuration. Untagged calls and registered publishing request guards retain their existing behavior.

| Feature | Text budget | Vision budget |
| --- | ---: | ---: |
| Ask Editor | 40,960, deferred | — |
| Shorts / Gaming | 40,960, deferred | — |
| Template Text | 40,960 | — |
| B-roll / Smart Visuals | 40,960 | None |
| Sound | 40,960 | 16,384 |
| Thumbnail / local-model captions | 16,384; expands to 32,768 when necessary | 16,384 |
| Publishing | Existing 40,960 unchanged | Unchanged |

Text planning counts the installed model's tokens for the final messages and schema, reserves the complete reply and 512 framing tokens, and rejects overflow before inference. This is an envelope count with a framing allowance, not an exact count of Ollama's internal chat template. Required source and creator guidance stay intact. Context-sensitive text caches use separate keys. Longer requests have at least the existing one-hour inference allowance; this is not a completion-time guarantee.

Vision budgets do not pretend that base64 length equals image tokens. Existing bounded frame batches remain; actual image-token use requires runtime verification. The 9B model is not added to B-roll or Smart Visuals. Their existing website/manual-review routes are preserved. Abandoned motion/video/eye-contact workflows are not enabled.

GPU-first placement, allowed RAM offload and the existing shared GPU queue are retained. No global Flash Attention/KV-cache change was made while the publishing workflow runs. 64K/128K YaRN is disabled until a real extended-context runtime and the upgraded machine are validated; raising `num_ctx` alone is insufficient.

## Protected activation

Exact protected workflow: `b44f9b0f8a9e4620be090a17316a96bd` (RCB), session `d832701d570f4046`. The earlier MI workflow completed; it is not the currently protected job. Do not change remote uploads, schedules, receipts, saved source IDs, accounts or recovery state.

Seven protected dependency files are staged under `output/context-architecture-20261030/staged`; originals remain unchanged. They add the feature tags, preserve up to twenty full recent chat exchanges subject to the final budget, and remove the beginning/middle/end-only Shorts overview for the enlarged-context path. Longer sources receive consecutive-section summaries with coverage receipts; detailed clip selection still uses original timestamped source words. Saved chat history remains on disk when an individual request must omit older conversation.

`work/activate_context_deferred.py --apply` requires the exact workflow's status to be complete, no active publishing rows, free GPU locks and unchanged source/staged hashes. It changes no publishing record and performs no restart. Before running it, also check the running application's chats/jobs and other workers. Concurrent source edits require a reviewed merge and fresh checks, not overwriting.

The owner explicitly approved a temporary five-minute follow-up and a verified-idle-only restart on 30 October. Automation ID: `finish-storylens-context-upgrade-after-upload`. Its first creation was rejected by automatic approval review; creation succeeded after explicit owner approval. Never use `work/restart_main_for_voiceover.py`: it contains an obsolete PID. Discover the currently listening service and its exact launch command, and restart only when all work is idle. No UI/computer-control approval was granted. Disable the follow-up after completion.

## Evidence and limits

- New feature-policy tests were run red before implementation and then passed, including transport integration, protected publishing precedence, exact guidance retention, overflow, extended history and full-source coverage. Deferred history tests demonstrated the old limits before being run against staged modules.
- The staged component/regression run executed 190 cases: 189 passed; the existing caption atomic-status read case intermittently raised Windows `PermissionError`. Its `save()` function is AST-identical to the saved original. The isolated recheck passed. Two broad runs reproduced the same failure. This is recorded, not silently fixed or represented as an all-green suite.
- Confirmed breaking point: concurrent caption progress writes and repeated reads can produce a transient `PermissionError` on `status.json`. Expected: every read succeeds; actual: the read fails during the stress test. Impact: that caption progress-reader stress scenario is not reliable. Evidence: `checks-staged.json`, `caption-race-recheck.json`, and the unchanged original under `before/hinglish_captions/auto_caption.py`. Do not repair this final-review finding without a further owner request.
- Six final isolated context/security probes found no new context failure; this is bounded evidence only.
- The real installed tokenizer counted a 16,842-token request and accepted it with 2,400 reply plus 512 framing tokens under the 40,960 budget. This was CPU-only tokenization, not model generation.
- No heavy inference, media render, new publishing test, app restart or UI control was performed for this upgrade while the RCB task was active. Actual full-context model quality, memory residency and complete feature workflows remain unverified. Running processes keep already imported modules until safe activation.

Run `work/check_context_architecture.py --staged` before applying and without `--staged` afterward. Preserve the distinction between the documented unrelated caption stress failure and failures in the new context policy. Update `output/context-architecture-20261030/status.json` and the existing cumulative checklist after activation and verification.

## Activation and owner stop — 30 October 2026

Owner subsequently authorized activating while the repaired RCB workflow was failed/idle, then resuming. Staged changes were rebuilt around the newer assistant progress/streaming repairs, preserving those changes. All 190 staged checks passed on this run. The activation guard now accepts an explicitly owner-approved FAILED workflow only; active workflows remain blocked. Its three new tests were run red then green. Seven staged files were applied, all deferred feature flags cleared, and the verified-idle service was restarted with its exact current command and environment (readiness receipt reload.json). Twenty post-activation context checks passed. No model inference was started.

Before any workflow resume request was sent, the owner withdrew resume authorization because Sound Design training was using the machine. RCB remains failed with its original saved long upload and three rendered Shorts. No uploads, scheduling, new extraction or resume were started. The follow-up automation was deleted. Stop here: do not resume RCB or run further heavy validation until the owner explicitly requests it. Full-context generation and per-feature end-to-end validation remain unperformed.
