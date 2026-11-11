# Storylens personal encrypted mailbox

One owner, two credentials, one Durable Object named `personal-v1`. The laptop remains the engine. This project does not deploy itself, register users, authenticate Cloudflare accounts, contact target URLs, or run commands.

## Endpoint agreement

HTTPS only. Bearer tokens go **only** in `Authorization: Bearer <token>`. Tokens must be independent cryptographically random base64url strings, 32–256 characters; 32 random bytes encoded as unpadded base64url is recommended. Neither token nor an AES key belongs in a URL, repository, Worker variable, or log.

Only these public endpoints exist:

| Request | Result |
| --- | --- |
| `GET /health` | Public HTTP 200: `{"service":"storylens-personal-link","version":1}`. Not an authenticated readiness check. |
| `POST /v1/push` | Authenticated HTTP **200**, both first acceptance and identical retry. |
| `GET /v1/pull?wait=20` | Authenticated HTTP 200: `{"messages":[envelope,...]}`. Empty at timeout. |

`wait` is an integer 0–20, default 20. `wait=0` polls immediately. Extra/duplicate query parameters are rejected. Use `Content-Type: application/json` (optionally `; charset=utf-8`) for push; content encodings are rejected. No CORS headers or OPTIONS support are provided. Every response has `Cache-Control: no-store`.

The exact, four-field envelope is:

```json
{
  "v": 1,
  "id": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
  "nonce": "AAAAAAAAAAAAAAAA",
  "data": "AAAAAAAAAAAAAAAAAAAAAA"
}
```

This is a **format-only example**, not a valid encrypted command. `nonce` is canonical unpadded base64url encoding of exactly 12 bytes. `data` is canonical unpadded base64url of AES-GCM ciphertext **including** its 16-byte authentication tag; decoded length 16–184,320 bytes. `id` is 1–80 hexadecimal/hyphen characters, starting with a hexadecimal character; UUID strings work. No filenames, commands, paths, content types or other plaintext fields are accepted.

AES-GCM encryption/decryption, associated-data validation, peer verification, nonce uniqueness and application-level receipts belong to the phone/laptop. The Worker has **no AES key**, cannot decrypt or verify a GCM tag, and cannot distinguish arbitrary opaque bytes from genuine ciphertext. Endpoints must never send plaintext encoded as base64 instead of encrypting it. IDs/nonces, sizes, traffic timing, role authentication and connection metadata are necessarily visible to the relay/operator.

### Routing, retry and limits

- A phone push can be pulled **only by laptop**; a laptop push only by phone. Public role headers are ignored and overwritten after authenticating both configured token hashes using Workers' native constant-time primitive.
- Each accepted push returns `{id,status,duplicate,expires_at}`. `expires_at` is Unix milliseconds, 120 seconds after initial acceptance. `status` is `queued` or `delivered`; `delivered` means assigned to a pull response, **not** received/decrypted/executed by its endpoint.
- Within the active object's 120-second receipt window, same role + same ID + identical envelope returns HTTP 200 with `duplicate:true`, without queuing again. Same ID with changed nonce/data returns 409 `id_conflict`. Reusing a nonce under another ID in that role returns 409 `nonce_conflict`. Opposite roles may use the same ID for request/response. Every separate file frame needs a fresh transport ID and nonce.
- Queue capacity is **64 frames or 8 MiB of serialized envelopes per destination**, whichever comes first. Overflow returns 429 `mailbox_full`; nothing already queued is evicted. The rejected frame can be retried unchanged once capacity is available.
- Pull drains up to **8 FIFO frames**, with a worst-case response below the laptop's 2 MiB read cap. One outstanding longpoll per role; another pull receives 409 `pull_in_progress`. Opposite-direction traffic cannot wake it. Aborted/expired waiters are removed.
- Expired payloads/receipts are discarded in memory, with an expiry timer and pruning on each operation. No Durable Object storage, SQL, alarms, KV, R2 or queues are used. A SQLite-backed DO **class** migration is declared solely for Workers Free compatibility, not for storing messages.
- Rolling per-role admission is 600 push/pull calls per minute by default, configurable from 1–600 via `RATE_LIMIT_PER_MINUTE`. Retries and conflicting polls count. 429 replies include `Retry-After` seconds. Authentication and envelope validation occur before the DO, so malformed/unauthenticated edge requests do not use its per-role counter. Cloudflare's own request/CPU quotas still apply.
- Request body cap: 256 KiB, enforced on actual streamed bytes as well as declared length before JSON parsing. Body read deadline: 10 seconds. Decoded ciphertext cap is separate. 128 KiB raw file chunks remain suitable when the encrypted application message contains base64 file content. Transfer sequentially with endpoint acknowledgements; never enqueue a whole 256 MiB file at once.

**Delivery is deliberately ephemeral.** Object eviction, restart, deployment or TTL expiry can lose messages and dedup receipts. Pull is destructive; a lost pull response can lose its frames. Identical push retry does not requeue an already drained frame. For recovery, use a new transport ID/nonce with the same encrypted application operation ID, and deduplicate that application ID at the engine. There is no durable exactly-once delivery or offline file storage. Old ciphertext can be replayed after the receipt window; endpoints must enforce their own replay/expiry policy. Never treat a push receipt as completion of a laptop command.

### Error statuses

| Status | Codes / meaning |
| --- | --- |
| 400 | `https_required`, `invalid_query`, `invalid_length`, `invalid_envelope` |
| 401 | `unauthorized` (missing, malformed or incorrect bearer) |
| 403 | Internal DO role missing/invalid; DO has no public route |
| 404 | `not_found` |
| 405 | `method_not_allowed`, with exact `Allow` header |
| 408 | `body_timeout` |
| 409 | `id_conflict`, `nonce_conflict`, `pull_in_progress` |
| 413 | `body_too_large` |
| 415 | `unsupported_media_type` |
| 429 | `mailbox_full`, `rate_limited`, with `Retry-After` |
| 499 | `request_cancelled` for an aborted pending pull |
| 503 | `unavailable`, including missing/equal/invalid secret hashes, invalid rate, runtime failure |

Errors are `{ "error": "code" }`; no credentials, payloads, URLs, exception messages or stacks are reflected. There are no application logging calls. Observability/invocation logs and preview URLs default off. Do not enable payload logging or `wrangler tail` for production. Account-level Cloudflare processing/metadata is outside this application's no-logging guarantee.

## Local checks

Only `wrangler` 4.160.0 is a dev dependency. Runtime has no npm dependencies. `package-lock.json` pins the toolchain. Node's built-in test runner exercises a memory-only state fixture and fake clock; the optional local runtime smoke uses the Miniflare/workerd delivered by that pinned Wrangler, not another declared dependency.

Run from this directory on Windows. Keep tool scratch output in this project:

```powershell
New-Item -ItemType Directory -Path '.\build-cache' -Force | Out-Null
$env:TEMP = Join-Path (Get-Location) 'build-cache'
$env:TMP = $env:TEMP
$env:WRANGLER_LOG_PATH = Join-Path (Get-Location) 'build-cache\wrangler.log'
$env:WRANGLER_SEND_METRICS = 'false'
npm.cmd ci --ignore-scripts --no-audit --no-fund --cache '.\build-cache\npm'
npm.cmd test
npm.cmd run check
npm.cmd run test:runtime
.\node_modules\.bin\wrangler.cmd deploy --dry-run --outdir '.\build-cache\bundle'
```

The local smoke binds a temporary loopback-only runtime and disposes it in `finally`. It uses random test-only credentials, no Cloudflare account, no remote deployment and no endpoint AES key. It is not a deployed phone-to-laptop acceptance test.

## Parent-managed deployment

`wrangler.jsonc`: name `storylens-personal-link`, compatibility date `2026-10-01`, binding `PERSONAL_MAILBOX`, class `PersonalMailbox`, migration `v1` with `new_sqlite_classes`. The only public setting is `RATE_LIMIT_PER_MINUTE`. There is no account ID, paid-resource declaration or new API-scope request. SQLite Durable Objects are Free-compatible but Cloudflare Free quotas/availability still apply; this is not a promise of unlimited free traffic.

The parent privately generates independent phone/laptop tokens and stores their **64-hex-character SHA-256 hashes** as Workers secrets. The endpoints receive their respective original tokens separately. The AES key stays solely at endpoints. The implementation never opens an existing account config or token file.

Using the parent's already authorized Cloudflare account/CLI, and **only when the parent decides to deploy**:

```powershell
.\node_modules\.bin\wrangler.cmd deploy
.\node_modules\.bin\wrangler.cmd secret put PHONE_TOKEN_HASH
.\node_modules\.bin\wrangler.cmd secret put LAPTOP_TOKEN_HASH
```

Enter only each SHA-256 hex hash at the private prompt. The first deployment fails closed for authenticated operations until both distinct secrets exist; health remains generic. No `wrangler login` or permission changes were performed here. The parent supplies the final HTTPS Worker URL to both apps and validates real authenticated encrypted traffic. Rotate lost bearer credentials through the existing secret mechanism, independently of endpoint AES-key rotation.

## Validation scope

See `validation.json`: red-first tests, passing Node unit/in-memory integration checks, local actual workerd smoke and Wrangler dry-run bundle. Safe boundary probes cover forged origin/role, excessive credentials, noninteger version, plaintext extra fields, internal credential stripping and post-timeout delivery. No new confirmed failure was found in those checks. Ephemeral-loss/replay/quota limits above are intentional boundaries, not claims of durable reliability. No login, deployment, production secrets, external platform action, browser/Adobe control or parent-file edits were performed.
