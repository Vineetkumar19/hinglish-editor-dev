# Font runtime callbacks — 25 October 2026

**Component handoff; installer activation and native acceptance remain blocked.**
New `hinglish_captions/font_runtime.py` supplies explicit exact-manifest resolution,
bounded official-source fetch, per-user installation and per-target preflight
callback contracts. Its 31 tests execute with **29 passing and two new final-review
failures**, preserved without production repair. Combined with the earlier intake
and runtime suites: **96 executed,92 pass,four expected failures** (two earlier
protected findings plus two new findings). This is not a clean acceptance gate.

Only the new source, dedicated `tests/test_caption_font_runtime.py`, documentation
and dedicated evidence were changed. The original intake modules/tests and prior
reference runtime source/tests remain hash-identical. No server/UI/installer script,
accepted caption/font/profile, native adapter, package or task map was changed.
No actual download, Windows font installation/registry/activation, model/GPU,
Adobe, service or owner reference/font-state action was performed. Test file copies
and simulated registrations are isolated under temporary fixture directories.

## Existing implementation inspected and reused

- `tools/install_caption_fonts.names`: reused as the read-only sfnt name parser.
  The new wrapper checks a bounded TTF/OTF signature and reads exact family/style,
  PostScript and full face names. A bundled Great Vibes read confirms the parser;
  no existing installation routine was invoked.
- `hinglish_captions/fonts/sources.json` and `tools/prepare_laptop_fonts.py`:
  existing source/hash metadata and supported sfnt signatures inform explicit
  bundle associations. No font catalogue, filesystem-wide font discovery or
  network crawl was introduced. The existing preparation script is not called.
- `tools/install_caption_fonts.install` and `install_caption_three_fonts.py`:
  existing batch routines are hardcoded to bundled directories and shared receipts.
  They cannot install one supplied asset through the frozen callback contract
  without changing existing code. The additive `WindowsUserFontOS` adapts the
  same HKCU registration, AddFontResourceExW and bounded font-change notification
  approach for one caller-approved asset. It does not call either batch installer,
  overwrite their receipts, request elevation or change security settings.
- `hinglish_app/premiere_captions.font_name/check_fonts`: existing file/receipt
  preflight checks source bytes and PostScript metadata. It does not establish
  actual current-session Adobe recognition, so it is not used as native proof.
- Frozen `font_intake` identity/hash/official-source helpers and durable review
  owner are reused. The feature dispatch mutex comes from the previously added
  reference runtime; no GPU lock is acquired by this font adapter.

## Callable suite integration

Imports, construction and `callbacks()` perform no transport, registry,
installation, native query, watcher or state activation. The suite must explicitly
provide approved manifests, roots, execution gates and actual native callbacks:

```python
from hinglish_captions.font_runtime import FontRuntime
from hinglish_captions.font_intake import FontIntake

adapters = FontRuntime(
    application_root,
    records=approved_exact_ofl_manifests,
    allowed_roots=approved_source_and_intake_cache_directories,
    install_root=approved_per_user_windows_font_directory,
    allow_download=suite_font_download_is_permitted,
    allow_install=suite_font_install_is_permitted,
    allow_preflight=suite_native_check_is_permitted,
    native_sessions=suite_current_font_sessions,
    native_preflight=suite_actual_font_recognition,
)

# Construction only. Do not enable install/native execution before the recorded
# findings have a separately authorized repair and actual validation cycle.
intake = FontIntake(
    application_root,
    allowed_roots=approved_source_directories,
    install_roots=[approved_per_user_windows_font_directory],
    **adapters.callbacks(),
)
```

All gate callbacks default to unavailable/disabled. Literal `True` is required
for download/install/actual preflight execution. No permission prompts are
auto-clicked. `WindowsUserFontOS.expected_root()` permits the current Windows
user's `LOCALAPPDATA/Microsoft/Windows/Fonts`; a supplied production install root
must match it. Tests inject an isolated OS implementation instead.

| Callback / API | Contract |
| --- | --- |
| `resolve(request)` | Request must contain exact `family`, `style`, `postscript` and a supplied/licensed-manifest origin. Require one exact matching approved record. No fuzzy family match, guessed weight, pixel-only/vision identity or ambiguous font-version selection. Paid/proprietary, unsupported licence/source and unknown identities raise `FontReviewRequired` (ValueError). Frozen intake persists one `needs_review`, not a prompt on every render. |
| Approved record | Exact identity, `filename`, official HTTPS `source`, expected font `sha256`, and `license:{id:'OFL-1.1',source,sha256}`. This first adapter supports explicit OFL-1.1 only. An approved record is source/identity evidence supplied by the suite; a reference video alone cannot prove exact font identity or licensing. Actual downloaded metadata must still match. |
| `bundle_record(font,license_path,sources)` | Caller explicitly associates one existing font with one licence and its existing source manifest. Validates allowed roots, source hashes, exact parsed names and licence proof; returns a manifest with the licence's local path. It never guesses which neighbouring licence applies. The suite may pass this manifest to existing `register_local`; no download is needed for verified local files. Unsupported/derived records need review rather than a substitute. |
| `download(url)` | Requires a permitted URL present unambiguously in approved records. Default transport lazily opens an isolated Requests session with environment credentials/proxies disabled; redirects are handled explicitly. Each hop/final origin must stay within the existing narrow official raw GitHub namespaces. URL credentials/query/fragment/traversal are rejected by the shared policy. Expected SHA256 is checked; fonts require supported sfnt signatures and licence bytes require OFL-1.1 proof. |
| Transport bounds | Defaults:32 MiB body cap,45-second checked budget, at most three redirects, connect/read timeouts capped at five seconds, streamed chunks. Header/body size and hash mismatches fail; responses/sessions close. Budget checks run between requests/chunks, not as an independently verified hard wall-clock cancellation of a blocking transport. Real network latency/trickle behavior and laptop performance remain untested. |
| Transport injection | `transport(url,timeout=(connect,read),stream=True,allow_redirects=False)` returns response with `status_code`, `url`, `headers`, `iter_content(chunk_size)`, `close()`. The suite must preserve these bounds/redirect controls. Tests use only fake response objects; no actual HTTP request was made. |
| Fetch lineage | `fetch_receipts` retains up to100 in-memory entries with requested/final URL, redirect chain, hash, bytes, kind and elapsed time. Suite job receipts must persist relevant entries; this module creates no second durable font catalogue/review store. |
| `install(asset)` | Requires permitted execution, allowed canonical source, exact bytes/metadata/licence and approved per-user target. Source aliases are deliberately not searched: the earlier protected canonical-alias finding remains intact. A feature mutex serializes installs. Exclusive target creation and existing-registration checks preserve owner files/registrations. Matching installed bytes/identity may reuse the registered file without moving it or repeated activation. See both new findings below before activation. |
| Install receipt | `{installed:true,scope:'user',path,sha256,postscript,status:'installed_pending_preflight',native_recognition_verified:false,reused}`. Registration/file receipt is not native font recognition. Existing outer intake independently verifies the installed file; no global readiness is computed here. Uncertain activation/registration errors propagate for review; no automatic rollback removes owner files. |
| `preflight(asset,targets)` | Missing permission/session/native provider yields explicit per-target `recognized:false,status:'unverified'`. Request at most one Adobe host per call (Hyperframes plus one Adobe host is permitted). Never launch either host automatically. Unknown targets stop for review. |
| Session provider | `native_sessions(targets)` returns `{target:{session_id,font_epoch}}` grounded in the actual running target/session and font reload state. The adapter queries before and after observation; changed contexts invalidate the returned recognition. Keep context values stable for the same session. |
| Native provider | `native_preflight(asset,targets,contexts)` must inspect the actual intended renderer/host. Return per-target `recognized`, `target`, exact `postscript`, verified font `sha256`, matching `session_id`/`font_epoch`, plus evidence references. The adapter only validates this contract; it cannot make a fabricated provider receipt genuine. No actual provider implementation was added or executed here. |

Provider exceptions propagate deliberately. The new wrapper does not catch and
convert full-preflight exceptions to hide the earlier protected stale-global-
readiness failure. It never reads/merges previous target receipts or overrides
the frozen `FontIntake.check` aggregator. Do not trust that aggregator's global
READY before its separate protected repair and live/session-fresh acceptance.

## TDD and final safe review

Before implementation, the new test module failed with missing `font_runtime`.
The first implementation run exposed an invalid UTF-8 BOM codec spelling (five
errors and one integration failure); the initial implementation loop repaired
it, then25 passed. Three additional initial cases reproduced a current-session
change that could leave an old direct preflight accepted. A before/after session
comparison fixed that new adapter issue; the28 font checks then passed alongside
the earlier suites (93 executed,91 pass,two protected expected failures).

Final safe review added three more probes. The injected actual Windows registry
boundary used HKCU only and preserved an existing conflicting registration.
The other two probes found failures below. They were observed as two real failing
assertions before receiving explicit expected-failure markers. **Production code
has not changed after that review.** All registry/GDI calls in these probes were
fake; no real font, executable, process or native host was activated.

- **Direct installer ignores an explicit paid flag.** Trigger:
  `install({...verified_fixture_asset,paid:true})`. Expected review before any OS
  callback; actual direct callback copied/registered the fixture and returned
  `installed_pending_preflight`. Evidence/test:
  `test_final_review_direct_installer_must_reject_explicit_paid_asset` and
  `output/caption-font-runtime-evidence/review-direct-paid-asset.json`.
  Scope: the normal resolver already rejects paid/proprietary records, and the
  earlier outer intake rejects paid manifests. This confirmed weakness is at
  the new direct installer callback boundary; it is not evidence that normal
  resolution downloaded a paid font. Activation remains gated pending repair.
- **Destination changes between verification and activation.** Trigger: a fake
  OS registration callback changes the just-copied target bytes. Expected a final
  byte/identity check and refusal to activate; actual callback reached fake
  activation and returned `installed:true` with the old expected hash. Evidence/
  test: `test_final_review_changed_destination_must_not_be_activated_or_report_installed`
  and `output/caption-font-runtime-evidence/review-changed-before-activation.json`.
  Impact: an equivalent concurrent destination change could reach activation.
  The frozen outer intake's post-callback byte check can reject that receipt,
  but occurs after this activation boundary. Only simulated activation occurred
  in this review; real Windows race behavior remains unverified.

The standing `AGENTS.md` rule says: “Do NOT fix failures found during this final
adversarial review unless the owner subsequently asks.” The two new findings
and the two earlier protected findings are preserved for a separate authorized
repair cycle. No owner question was sent in this feature thread.

Final command:

```text
.venv/Scripts/python.exe -m unittest tests.test_caption_font_runtime tests.test_caption_reference_intake_runtime tests.test_caption_reference_intake tests.test_caption_font_intake tests.test_caption_reference_library -q
```

Result:96 executed in5.522 seconds,92 pass,four expected failures, zero unexpected
failures/errors, exit zero. Expected-failure markers preserve reproductions;
`OK (expected failures=4)` is not production or startup/native acceptance.

Evidence under `output/caption-font-runtime-evidence`: `validation.json`, captured
combined summary, normal simulated pending-native receipt and the two actual
fixture review receipts. `build_receipts.py` creates these examples with fake
OS functions and synthetic bytes only; it does not rerun tests or call actual
Windows/network/model services. Earlier evidence remains intact. Hash comparisons
confirm all six earlier protected/intake-runtime source/test files are unchanged.

## Exact remaining blockers

1. Separately authorized repair cycles for the two earlier protected font findings
   and these two new adapter findings. No source repair after final review was
   performed. Preserve each exact failing reproduction.
2. Suite-owned approved manifest selection, execution gates, allowed roots, lifecycle
   activation and durable fetch-lineage persistence. The pure metadata/resolver
   callbacks may be wired without enabling installation or relying on global READY.
3. Actual configured local-model selection grounded in exact metadata and licence
   evidence, using normal app requests. No local-model plan was executed here;
   fixture answers do not count. No Codex/OpenAI client/session dependency was
   added to the runtime callbacks, and no zero-breakage guarantee is made.
4. Actual official-free fetch, per-user registration/activation and native font
   recognition, serialized with exactly one Adobe host and shared resource owner.
   Real transport/registry errors, fresh-session behavior, short/long laptop
   timings and application error presentation remain unverified.
5. Earlier reference stage-checkpoint consumption and long-running cancellation
   limitations remain as recorded in the reference runtime handoff. This font
   adapter changes neither of those components or their acceptance status.
