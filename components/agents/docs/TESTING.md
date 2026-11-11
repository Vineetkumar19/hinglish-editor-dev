# Testing

```bash
python run.py test              # everything
python run.py test -v           # verbose
python -m unittest tests.test_safety   # one module
```

No external network is needed. The isolated runner starts local protocol servers
and blocks non-loopback connections. Install `requirements-browser.txt` in the
project's Python 3.12 environment to include the Chrome ATS integration test.

## The fake servers are servers, not mocks

`tests/fakes/servers.py` runs actual HTTP and SMTP listeners:

| Fake | Speaks |
|---|---|
| `FakeWebServer` | prospect websites on real hostnames, with robots.txt, routed by `Host` header |
| `FakeGoogleServer` | OAuth2 token exchange and refresh, Gmail `watch` / `history.list` / `messages.get` / `send` / `modify`, Calendar `freeBusy` and `events` |
| `FakeAnthropicServer` | the Messages API, including malformed replies to exercise the repair loop |
| `FakeSMTPServer` | SMTP over a real socket, with configurable recipient rejection |

Nothing in `core/` or `agents/` is patched or stubbed. The agents make genuine
requests, parse genuine responses, and run every line of the production path.
Only the base URLs differ from production.

The test domains (`fantasy.example`, `saas.example`, …) are resolved to
loopback by patching `socket.getaddrinfo` inside the test process only. No
`/etc/hosts` editing, no admin rights, no port 80. The crawler still builds
absolute URLs, does a real lookup and opens a real socket — only the answer to
the lookup changes.

## What is covered

**Core** — schema validation and coercion; the YAML subset (round-trip, block
scalars, rejection of anchors); the store and its dedupe ledger; the PDF writer
(pagination, extractable text, font metrics); rate limiting and robots parsing;
JSON extraction from chatty model output.

**The graph engine** — interrupt and resume; cycles; stale resume values are not
replayed; multiple interrupts inside one node; the recursion limit fires as a
circuit breaker; a crashed run resumes without re-running completed nodes;
non-serialisable state is rejected with an actionable message; transient `__`
keys are not persisted; node retry with backoff.

**I/O** — OAuth exchange, silent refresh and a clear error for a bad refresh
token; Gmail history deltas returning only new messages; push notifications
resolving to the right delta; quoted history stripped and auto-replies flagged;
threaded sending; SMTP compliance headers and hard-bounce suppression; calendar
slots that avoid busy blocks; the Anthropic provider over real HTTP including
the schema repair round-trip.

**Agents** — each of the four driven from first call to final state, through
every approval gate, on all three paths (approve, edit, reject).

**Safety** — the guarantees in the README, each with a test that would fail if
the guarantee broke. The one worth reading is
`test_every_outbound_kind_has_a_gate`, which walks every registered graph and
asserts that no send node is reachable except through its approval node. It
inspects the graph structure rather than a particular run, so a future edge that
routed around a gate would fail it.

## Results

```
Ran 439 tests
OK (skipped=1)
```

The full result is saved in `data/test-results.json`; detailed test names and
skip reasons are in `tmp/tests/results.txt`. Real-model checks are separate:
`scripts/smoke_local.py` and `scripts/smoke_tools.py`.

## Bugs this suite caught while it was being written

Worth listing, because they are the kind that only show up under a real
protocol:

- **Stale resume values replayed.** Resuming a graph twice re-fed the first
  human decision into the second pause. Fixed by retiring resume values once the
  node that consumed them completes.
- **Orphan approval rows.** Replaying a node after approval created a second
  queue entry that nobody would ever decide. Fixed with `has_resume()`.
- **Non-serialisable state broke resume.** A `Quote` object in graph state came
  back from the checkpoint as a string. Now rejected at write time with a
  message naming the key, with `__`-prefixed keys available for live objects.
- **Crash recovery restarted from the beginning.** A run that failed mid-graph
  re-ran completed nodes on the next invocation, so an email could have been
  sent twice.
- **Total-recipient rejection skipped suppression.** `smtplib` raises rather
  than returning when *every* recipient bounces, so hard bounces were not being
  recorded.
- **A false positive in the fraud filter.** A genuine, concisely written job
  posting was flagged generic. The threshold was wrong; the test that caught it
  is now the regression test.
- **Invented contacts from prose.** "reach him at sanjay.kumar@saas.example"
  produced the address `him@sanjay.kumar` from the obfuscated-email pattern.
