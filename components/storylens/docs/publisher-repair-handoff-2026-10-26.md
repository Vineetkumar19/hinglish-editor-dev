# Publishing Studio repair handoff — paused for single-owner transfer

Receiver: **Uploading Ai editor**, `01a147ee-67b7-7310-bcfc-76a5fc16139d`.
Owner explicitly requested this transfer. Sender stops all implementation/testing now and stays read-only. No source/service/Adobe work may be done concurrently by sender after acknowledgment.

## Reproduced original failure

Exact saved request is in `cache/assistant/53e43db766b6476c.json`, on 25 October around 21:08–21:13 UTC:

- `A:\Full Drive\remove silence\All Shorts` followed by `take the shorts2 clip and post my cricket channel`.
- App asked Instagram or YouTube. User answered `youtube short`.
- App lost that publishing continuation and requested attachments as an edit. User attached `Shorts 2.mp4` and said `take this`.
- Actual app ran **Gaming Highlights**, creating `output/gaming/20261025-211011-c1009d/001-stream/GAMING_HIGHLIGHTS.mp4`.
- User then said `post it on my cricket yt channel`. App prepared that derived highlight as a **General-profile long-video** draft, ID `2a79ca585e5a4283`.
- Read-only SQLite evidence: draft, attempts=0, remote={}. No upload receipt for this request. The erroneous draft and all historical receipts are untouched.

Confirmed orchestration causes: `preflight()` did not consider a platform-only response an answer, so it cleared pending publishing intent. `assistant_publish.request()` rejected ordinary simple YouTube requests, allowing the generic planner/legacy publish branch to run with General profile and old last_paths. Raw original model prompt/response receipts were not recovered; structured saved chat records prove the actual route/result. Do not claim a full token-to-platform trace.

## Current account evidence, no account changes

`output/publisher-repair-2026-10-26/live-readiness.json`:

- Existing Cricket/Fantasy Legends and Gaming/Vineet Kumar YouTube DPAPI credentials decrypt. Both have saved refresh credentials and expected IDs.
- Actual read-only Google refresh attempts returned **invalid_grant**, with `RefreshError`, for BOTH profiles. Do not speculate whether expired/revoked/test-mode/etc. No credential write, OAuth grant, login or account replacement was performed. Source token mtimes remain 21 October; receipt records hashes.
- **Instagram uses the existing browser path**, not the optional API path. Live `/api/local-browser` reported bridge connected, Cricket `fantasy_legends91`, Gaming `vineet_editz19`. Preserved historical published browser receipt counts were 34 and 13. This is not a new account-composer/upload check. Absent optional Instagram DPAPI files are NOT a blocker for the browser integration.
- Main 8765 health read succeeded. No service was restarted or stopped; no model/GPU/media job or real upload/schedule was started. No Adobe interaction/application launch occurred. Existing Chrome publisher-tab claim timed out on CDP focus setup, so no screenshot/reload or live UI acceptance was obtained.

## Changed source files — preserve these edits

- `hinglish_app/assistant_publish_intent.py`: retain platform-only clarification, retained attachment IDs, exact literal/named source attachment; preserve Cricket wording.
- `hinglish_app/assistant_publish.py`: recognize YT alias; ordinary exact finished uploads dispatch to draft-only route instead of generic edit planner. Existing private/campaign paths retained.
- NEW `hinglish_app/assistant_finished_upload.py`: exact one attached MP4, no old-output substitution/excerpt, existing local metadata writer, explicit profile/account binding, YouTube-only durable draft, no upload authorization. Recheck selected account during preparation; retry uses existing canonical queue identity.
- `hinglish_publish/service.py`: existing prepare endpoint supports explicit video_path/kind/platform scope and a diagnostics operation. Existing routes need no additional server edit for this first slice.
- `hinglish_publish/channel_queue_service.py`: destination-bound finished drafts receive the same account binding check before authorization as proposal drafts.
- NEW `hinglish_publish/readiness.py`: safe local/in-memory-refresh/read-only channel diagnostic; no secret strings, no saved credentials, no upload. Distinct browser Instagram report. CLI: `.venv/Scripts/python.exe -m hinglish_publish.readiness --profile cricket --online` (online is an existing-account GET/refresh only).
- Publisher-only UI: `hinglish_app/static/publisher.html`, `publisher.js`, `publisher.css`; NEW `publisher-intake.js`. Compact visible Cricket/Gaming selection, exact path, finished/stream mode, video kind, destination, N, notes, draft review, pre-demo check. YouTube-only path calls actual existing prepare API. Paired/stream path submits an ordinary bounded request to existing local assistant API/new chat, preserving gaming stream -> ONE ~15-minute highlight -> N shorts FROM it and DRAFT ONLY. This is connected source, NOT a verified working paired/gaming product milestone.
- Tests: NEW `tests/test_publisher_regression_repair.py`, `test_publisher_readiness.py`, `publisher-intake.test.cjs`, `publisher-studio-ui.test.cjs`.
- No edits to `server.py`, `assistant.py`, shared editor/CEP/Adobe files, AGENTS.md or PROJECT_TASK_MAP.md. `.agents` directory is absent in this checkout. No Git repository was available for git diff; source hashes are in evidence.

## Executed validation and limits

- Initial backend regression tests observed failures before implementing; evidence `tdd-red.txt`, `readiness-red.txt`, `binding-red.txt`. Initial UI markup contract checks also failed before those changes (`ui-red.txt`). Pure intake helper checks were authored after that helper implementation: do not call those particular checks TDD.
- **16 focused Python checks pass**, including actual Assistant.send controller flow in a temporary AppState, reported two-turn request, exact bytes/profile/type/platform draft, no general planner, attachment retention, account binding and safe diagnostics. Models/transports use fixtures; NOT actual local-model acceptance.
- **6 Node checks pass** for intake and markup contracts; `node --check publisher.js` passes. Not a screenshot/responsive/browser acceptance.
- Broader component run: **143 tests, 10 failures + 9 errors**, evidence `component-regression.txt`; do not claim full suite green. Errors include old Instagram metadata fixture mismatches/Mock serialization, and old private/campaign chat cases routing elsewhere. A full original-function reconstructed baseline attempt aborted with OpenBLAS memory allocation failure. Two representative original-function baseline samples reproduced 1 failure + 1 error (`prior-behavior-sampled.txt`); this does NOT establish all 19 failures pre-existed.
- No real media rendering or source-byte modification. Production draft/queue/history/receipts are unchanged by tests; test data lived in workspace tmp roots. Avoid duplicate broad tests while the 16 GB laptop is under load.

## Unfinished scope and next gates

1. Receiver alone coordinates safe idle main-service activation. Current loaded 8765 Python modules may predate these source edits; publisher static files are already on disk and may be served before matching backend reload. Do not demo the new controls against stale loaded methods. No uncoordinated restart of Copy Paste/Template Text services.
2. Actual visible Storylens/local-model request with a realistic explicit path must validate metadata semantics and dispatch through this repair; no Codex-authored metadata or manual publishing to pass acceptance. Coordinate GPU queue first. No model inference has yet been run in this repair.
3. Safe connection blocker: user must restore/reconnect the SAME existing YouTube accounts when specifically authorized; no new grants in current scope. Do not equate this later invalid_grant with the original orchestration failure.
4. Paired per-profile/per-platform browser queues, varying saved daily 17:00–21:00 Asia/Kolkata slots, weekly append, chosen N, cancellation/checkpoints/restart/idempotency need actual product wiring/acceptance. Existing channel_queue_* internal draft helpers and older campaign/browser flows are present; do not call their fixtures live acceptance or replace their saved data.
5. Gaming 2–3h -> ONE ~15m highlights -> N shorts from finished highlights must retain lineage and semantic choices by configured local models. No expensive stream run authorized merely by transfer.
6. Metadata review must show correct account/profile/source/date; all viewer text in proper English, full creator context retained. Preserve compact familiar dark Storylens UI and full Learning Memory editor; no separate image UI/rebuild of unrelated editor.
7. Final product must run via independent local Python/Ollama/app paths; no Codex subscription dependency. This source repair adds none, but a fresh normal application acceptance remains outstanding.

## Final adversarial findings — held per AGENTS.md

`final-review.json` records these and they were NOT repaired after final review:

- Confirmed safe sentinel: `Publisher.prepare_file` validates an invalid platforms list AFTER calling metadata item preparation. Expected reject before ASR/model work. Impact: wasted model work for malformed requests; no queue rows created. One mocked item call and zero rows observed.
- Source inspection finding, not live reproduction: shared assistant publisher navigation passes command but not destination profile/IDs, while publisher filters by global creator profile. A correct Cricket draft can therefore be hidden if the UI remains General until Cricket is selected. Needs exact originating chat/publish_ids restoration or coordinated navigation handoff. Do not silently guess a draft from old outputs.

AGENTS.md says: “Do NOT fix failures found during this final adversarial review unless the owner subsequently asks.” Receiver must disclose/preserve these findings and obtain subsequent owner authorization if treating them as final-review repairs. Transfer alone is ownership, not proof of acceptance or blanket account/publication permission.

## Authorization and ownership

Current authorization: reversible implementation, safe local fixtures/dry transports, read-only existing account checks. **No live upload/publication/real scheduling, new OAuth grant, credentials/account changes, spending, Adobe control, extra competing heavy job, or stopping other jobs.** Existing user upload attempt is context, not fresh authorization to post now.

Sender has stopped at this checkpoint and will remain paused/read-only. Parent's source thread was not found by Codex messaging (local or observed durable host), so early parent checkpoint is saved in `checkpoint.json` and this handoff rather than claimed delivered. Destination receiver has explicit new human messaging authorization. Delivery and receiver acknowledgment must be recorded separately.
