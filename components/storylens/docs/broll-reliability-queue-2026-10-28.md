# Resumed B-roll reliability work — 28 October 2026

## Stock Chrome connector prepared — 29 October 2026

### Latest delivered results and parallel search — 29 October 2026

- Owner explicitly objects to token-heavy repeated validation and late delivery.
  Give completed review links promptly and concise updates; do not launch extra
  full-video trials merely to repeat passing checks. Owner now requests using
  all connected B-roll websites together. Preserve earlier pending/deferrals.
- E2 full35.7s result5ca6cbe8a0db COMPLETE:60 options/10 moments,6 each. Actual
  metadata60/60 native portrait H264;47 Pexels-browser options and13 Mixkit
  options (counts include per-moment reuse, NOT60 unique videos). No owner choice
  was made. Full browser playback of first41.066667s clip ended without error,
  1080x1920. Saved full-e2-result.json, full-review-playback.json and desktop PNG.
  Collection elapsed907.313s from job submission; this was a RECOVERED run after
  server restart/orphan cleanup, not proof of uninterrupted execution.
- E3 fresh UI job36b680dc82d1 used cached transcript and local planning9 moments;
  two bounded local keyword repair replies were logged. Windows shutdown stopped
  it (events at02:43:02, observed LastBootUpTime02:43:36 Asia/Calcutta). Existing
  saved work persisted; restored main service created02:44:46. Do not claim the
  shutdown codes prove a model/library bug or that the original run completed.
  Evidence e3-restart-evidence.json retains raw history.
- Normal UI continuationa7c438b645f4 completed in ONE worker attempt after boot,
  using saved local-model plan:40 options/9 moments,451.089s for resumed collection.
  PG6,WiFi/router6,washer1,fridge1,AC6,table2,laptop6,room-frustration6,bed6.
  All decoded native portrait. Source options33 Pexels-browser,7 Mixkit; no manual
  footage/choices. Interruption fix revisits only empty groups while preserving
  previous_attempts and existing options. Red-first regression passes. This is
  recovery acceptance, NOT a fresh uninterrupted from-scratch full-video pass.
- Finished reviews:
  /broll-output/20261029-021804-52d2ed/001-e2-1-/report.html
  /broll-output/20261029-023717-82cf91/001-e3/report.html
- Catalogue version4 now submits Mixkit,Coverr,Videezy,Pexels,Pixabay metadata
  together, max5 producer threads and6 candidates/site, independent HTTP sessions,
  round-robin output. Other catalogue availability probes remain bounded; download
  and actual decoding stay sequential. Child-owned worker lease remains enabled.
- Stock Chrome0.1.2: two simultaneous provider jobs, exactly one/Pexels and
  one/Pixabay in own tabs. Typed provider claims and server/extension capability
  negotiation retain safe serial compatibility with0.1.1; no permissions added.
  Read-only script call has a bounded timeout. No stock API or Vision restored.
- Reloaded only verified-idle8765 after both jobs completed, no active B-roll/
  Visuals records or child workers, with publishing/supervisor disabled. Owner
  then explicitly reloaded extension0.1.2. Actual heartbeat confirms paired sites.
- REAL concurrent browser probe: both jobs observed running together; Pexels
  refrigerator7.368s and Pixabay9.344s; both returned an actual clip, downloaded
  and decoded sequentially. live-parallel-012/result.json. Separate REAL production
  WebsiteFallback query started all5 providers within0.001s, finished41.032s:
  metadata Mixkit6,Coverr6,Pexels6,Pixabay4,Videezy0. Source pages accessible for
  these5; Vidsplay/Dareful still403, Mazwai unsupported redirect. Do not claim
  all internet sites are usable or every candidate is relevant. Evidence:
  live-parallel-012/all-sources/result.json. This was one query, not another video.
- Python54/54,Node8/8 pass; seven final isolated concurrency/failure probes pass,
  no new issue in those probes. Existing automatic-edit quality still reports
  score93/zero SELECTED cutaways; preserve it and do not call it collection failure
  or a passing native edit. Human has not selected clips. New native AE manual-bank
  import, other editors, long-form and a new uninterrupted full-video pass remain
  separate pending acceptance; no fresh native permission/control was requested.
- Current search request is delivered and both review files remain available.
  Avoid more unrequested renders/full-source repeats. Keep the cumulative queue.

### Version0.1.1 connected; full video validation is ACTIVE

- Owner reloaded0.1.1; actual heartbeat confirms both sites connected. Actual
  installed-extension probes now return2 videos per site: Pexels wifi router /
  vertical6.825s; Pixabay wifi / horizontal9.275s. Storylens acquired/decoded
  the first returned MP4 from EACH: router1080x1920/12.345667s and WiFi
  1920x1080/16.015s. Evidence live-connection-011/result.json. Second suggestions
  include looser website matches; these are human-review options, not a claim
  that every result is semantically correct. No API/Vision was used.
- Actual Chrome Storylens Add B-roll settings6 -> Find B-roll -> Vertical
  launched job5ca6cbe8a0db on full35.7s e2(1).mp4. Saved transcript reused;
  normal local planner produced10 timed moments. Output currently ACTIVE:
  output/broll/20261029-021804-52d2ed/001-e2-1-/report.html. Side-browser tab7
  shows the actual updating result. Do NOT restart or interrupt this worker.
- Main service was restarted after submission (progress PID22392 ->53192),
  independently of this chat's control, and restored the same saved job while
  original child chain remained alive. It reached recovery_attempts2. This is
  NOT an uninterrupted one-go pass. Preserved bank snapshot and exact orphan
  command lines in live-connection-011; stopped ONLY orphaned original chain
  31800/51680/29784/31256 after validating former parent22392 no longer existed.
  Current monitored recovery under main53192 was kept, no owner choices made.
  Do not infer this was an LLM/schema failure or claim Codex never intervened.
- Added child-owned workspace B-roll OS lease in worker_lease.py and normal
  CLI, with lazy pipeline import after acquisition. Future restored workers
  wait rather than write the same bank concurrently; exit releases OS lock.
  Red-first real separate-process tests verify exclusion and release on exit.
  This guard was NOT injected/reloaded into the already healthy active worker.
- Focused Python46/46, Node6/6 pass. Eight final isolated public-edit-link
  boundary probes pass, no new failure in those cases. Evidence final-python-
  checks.txt, final-node-checks.txt and reader-final-review.json. Actual browser
  playback/full result/native editing/long-form and a new clean one-Run test
  are still separate acceptance work. Keep all prior queues and findings.

### Installed and paired; real retrieval repair awaiting Chrome reload

- Owner installed/enabled Storylens Stock Search0.1.0 (supplied screenshot)
  and approved both stock sites. Main8765 was offline at the next check; restored
  only that service with --no-publisher-worker --no-supervisor. Other instances
  and Adobe work were left alone. Actual local pairing-page Connect Chrome
  click succeeded: Connected · Pexels · Pixabay. Evidence connected-live.png.
- Actual installed-extension first probes completed without crash: Pexels
  wifi router/vertical85.639s and Pixabay wifi/horizontal54.197s, BOTH ZERO
  results. This is a confirmed retrieval failure, NOT lack of available footage
  or end-to-end success. Preserve live-connection/result.json unchanged.
- Background pages expose the selected public video in their visible Canva
  edit-link URL while their primary player is unloaded. Version0.1.1 now reads
  that DOM link without visiting Canva, matching source video ID/CDN. Filename
  dimensions may aid early filtering; unknown dimensions defer to acquire_video
  and its mandatory real-decoder orientation validation before human offering.
  Do not infer vertical from a crop or treat filename as final media proof.
- Red-first regressions reproduced missing public links, unknown-dimension
  rejection and24h empty-result caching. Fixes pass Python35/35 and Node6/6,
  including local HTTP/client roundtrip. Corrected PURE DOM function returned
  the real router1080x1920 MP4 and Pixabay WiFi1920x1080 MP4 in actual Chrome.
  This function check is NOT the reloaded extension roundtrip.
- Empty completed searches now permit another request; collected nonempty
  results retain cache. Reloaded only verified-idle main PID56572/36888 to
  activate that server change, with publishing/supervisor still disabled.
- Owner has been asked to press ↻ on the installed extension card ONCE to
  load0.1.1. Browser policy still prohibits operating that internal page via
  alternate methods. Last actual heartbeat remains0.1.0; pairing IS saved.
  NEXT: detect0.1.1, rerun the same two bounded probes, inspect downloads, then
  normal Storylens local-model workflow if successful. Native/long-form pending
  checks and all old queues remain; do not call the feature fixed end-to-end.

- Owner subsequently APPROVED installing and connecting the separate extension
  with Pexels/Pixabay/localhost access. Do not ask for that approval again.
  Attempt to open chrome://extensions via Chrome browser control was explicitly
  rejected by the browser URL/security policy (HTTP/HTTPS only), with an explicit
  no-workaround/no-alternate-surface instruction. No native input/CDP/terminal
  installation fallback was attempted. Installation remains NOT done.
  Human must Load unpacked from the prepared folder, use popup Connect, approve
  site access and click Connect Chrome in local Storylens. Resume the actual
  extension keyword roundtrip when human confirms installation; all code/tests,
  saved banks and other feature queues remain preserved.

- Owner confirms normal Chrome plays videos on BOTH Pexels and Pixabay; no
  further owner screenshots are needed. Direct Python HTTP blocking is distinct
  from Chrome access. Do not claim website absence from an HTTP403.
- Separate opt-in extension prepared in editor_plugins/storylens-stock-chrome.
  Existing publishing extension/permissions are untouched. Only storage, alarms,
  scripting and localhost are required; Pexels/Pixabay host access is optional
  and requires owner approval. No cookie/debugger/native-messaging capability.
  Fixed public video search/detail readers, own bounded tabs, typed keyword
  requests, scoped leases/key and human verification handoff. No model code,
  API key or local Vision. Six choices maximum, native-orientation checks.
- New stock_browser.py queue/HTTP routes, stock_browser_client.py subprocess
  client and catalogue-v3 browser preference are connected in source. Offline
  Chrome falls back to existing public adapters. Results remain human reviewed.
  Setup: http://127.0.0.1:8765/stock-browser.html; compact settings link added.
- Actual live8765 setup/Check connection correctly reports Not connected and
  disables pairing until opened by the installed extension popup. No service
  restart, model job or Adobe action was performed in this connector pass.
- Actual Chrome public-video observations: Pexels router39918565 exposes its
  main1080x1920/12.345667s MP4; Pixabay WiFi22739 exposes1920x1080/16.02s MP4.
  Pexels includes unrelated advertisement players; red-first regression added
  to bind DOM media to the selected page video ID. Public router download and
  actual decode through acquire_video succeeded in a SEPARATE proof folder.
  No manually chosen clip was injected into an owner bank.
- Focused Python checks33/33 and Node4/4 pass. HTTP tests exercise the real
  localhost subprocess-client/queue/fixture-worker receipt roundtrip. Eight
  safe isolated final boundary probes pass; no new failure IN THOSE probes.
  This is NOT an installed-extension roundtrip, full-video acceptance or native
  editor proof. Evidence: output/broll/stock-browser-proof, setup-live.png.
- NEXT: obtain action-time approval for local extension installation and its
  persistent site access; install/pair, test ONE focused keyword through the
  actual extension, then a normal local-model run if that passes. Do not claim
  it fully automatic yet. Retain native manual-bank AE and long-form pending
  checks, all prior queues, frozen findings and owner deferrals.

## Latest: broader public catalogues and different-video test — 29 October 2026

- Owner requested broader website access and retirement of API/Vision B-roll.
  Main UI no longer offers strict/API/Vision mode; saved credentials remain on
  disk, hidden legacy settings remain compatible. New runs are forced to the
  human-review website path; retired API hooks/strict CLI requests cannot load
  those models/providers. Preserve historical strict banks and raw verdicts.
- New website_catalogs.py: Coverr and Videezy public-page adapters alongside
  Mixkit; Pexels/Pixabay public searches remain included. Check Vidsplay/Dareful
  once per run (403 currently); Mazwai redirects to Freepik, unsupported here.
  Three functioning search adapters is NOT all-internet access or proof all
  sources supplied videos. Round-robin results prevent one catalogue hiding the
  others. Coverr requires explicit isPremium=false/isAiGenerated=false; Videezy
  requires resource_is_premium=false. Ads, templates, paid/unknown records are
  skipped; licence/source pages remain attached. Public page/media host bounds,
  byte limits and no-challenge-bypass rules remain.
- Owner then requested another source, explicitly NOT current E3. Transcript
  audit: “To flat nahin mila. PG le lie” IS E3; used other supplied housing clip
  A:/Full Drive/thisis.vineet/e2/e2(1).mp4. Explained this assumption to owner.
  Original full file (35.7s), no hand-authored keywords, no repeated E3 run.
- Actual main Storylens Find B-roll + Vertical clicks launched job98c9864760cc.
  Normal pipeline reused cached transcript and locally generated a FRESH summary
  and ten keyword moments. Finished in ONE worker attempt, recovery_attempts=1,
  quality attempt1, no manual restart or intervention in the running worker.
  Website collection took274.242s; this excludes earlier local planning. Do not
  describe internal model/schema retry counts as zero without separate evidence.
- Actual result now visible:
  http://127.0.0.1:8765/broll-output/20261029-010517-707096/001-e2-1-/report.html
 26 videos across NINE of TEN moments, all720x1280: street6, apartment2, room2,
  room2, bed6, wardrobe4, heater0, fridge1, washer1, room2. All ACTUAL offered
  videos in this run came from Mixkit (raw source label “website” is generic,
  not an additional provider). Source source_url/page_url remain authoritative.
- Coverr was skipped in that worker; Videezy was reachable but supplied no
  accepted free portrait files. Pexels/Pixabay/Vidsplay/Dareful403, Mazwai redirect.
  Independent checks found a large-page ValueError was wrongly treated as a
  site-wide redirect failure. Red-first repair now uses a bounded12MB Coverr
  page cap, preserves raw diagnostics, and skips that query rather than the
  whole host for non-redirect ValueErrors. This fix was NOT injected into the
  healthy E2 worker and no supplemental clips were hand-added. Its exact Coverr
  failure cause was not retained; do not retrospectively certify it as size.
- Bank remains human-review suggestions, no owner choices automatically made.
  Existing automatic-edit quality score93 flags zero SELECTED clips/coverage;
  that is not zero collected footage. Keep the original quality report; do not
  claim all quality checks passed or native AE import verified.
-49 focused Python unit/HTTP checks pass after catalogue repair. Actual Coverr
  free-record extraction and Videezy premium exclusion checked from public-page
  fixtures. Final adversarial review/evidence for this expansion is recorded
  separately; earlier protected findings and unrelated Instagram context failure
  remain unchanged. Actual E2 bed preview played to17.100417-second end, no media
  error,720x1280; screenshot e2-expanded-live.png and e2-expanded-trial.json saved.
  Final three safe policy probes pass: private/credentialed media rejected,
  unknown free status excluded, retired Vision path stops before model loading.
  No new breaking point in those checks; see catalogues-final-review.json.
- Latest user asks how THEY can fix Pexels/Pixabay403. Clarified current adapter
  fetches background HTML, not Chrome automation; API keys are unrelated. Existing
  Storylens Chrome extension is publishing-only (Instagram/YouTube), NOT a stock
  browser connector. Do not imply that opening sites alone unblocks requests,
  copy/replay cookies, bypass challenges, or silently expand browser permissions.
  Asked owner to open both stock-search pages in regular Chrome, complete any
  verification personally, and report whether pages/playback work. A proper stock
  browser connector is still missing; manual verification helps only that route.
  No browser extension install, permissions, login or native AE control performed.

## Latest: six choices and explicit source orientation — 29 October 2026

- Owner approved the website-only approach, requested SIX options per keyword,
  and a compact Vertical / Horizontal choice before searching. This supersedes
  the previous five-option cap for this manual website workflow. Keep website
  search / human review, no stock APIs or local Vision. Do not crop horizontal
  originals and represent them as native portrait matches.
- Main Find B-roll now asks through a two-button modal, with small frame icons;
  Escape cancels before any job. Review pages have the same two short controls.
  Each orientation gets its own saved bank, preserving older media/selections.
  Normal CLI/server payloads carry orientation and a maximum of six. Local chat
  schema/defaults also use six; missing orientation yields “B-roll format?” with
  two quick buttons. Do not guess a source orientation from earlier work.
- Mixkit requires its actual /free-stock-video/discover/{query}/?orientation=
  route; category pages can ignore this filter. Source video dimensions are
  checked independently before offering a clip. Wi-Fi queries expand to wifi
  router / internet connection / wireless network / wifi, keeping exact saved
  speech and timestamps. Public Pexels/Pixabay continue to return403, not API-key
  errors; the trial used the accessible Mixkit website.
- Live Vertical button started E3 variant:
  http://127.0.0.1:8765/broll-output/20261029-003413-website-vertical-e7859d/001-e3/report.html
  Completed in74 seconds with NO repair, interruption or manual restart
  during collection. Reused the saved nine-keyword plan; this does NOT test new
  transcription/planning.16 real portrait clips across five moments: washer1,
  fridge1, table2, laptop6, bed6. PG, Wi-Fi, AC and room-frustration empty.
  Every offered file is720x1280. Six is the requested maximum, not a fabricated
  guarantee when the website has fewer relevant vertical videos.
- Actual main-screen format modal observed with precisely two buttons; cancelled
  without a job. Actual washer clip played to18.018-second end, no media error,
  videoWidth720/videoHeight1280. Screenshot and exact evidence: vertical-trial.json,
  orientation-picker-live.png, vertical-live-preview.png under reliability evidence.
- Separate Codex research found a real Coverr Wi-Fi router listing, explicit
  isPremium=true. Native orientation was not verified; no paid/preview asset was
  inserted to manufacture autonomous coverage. See wifi-public-catalogue-audit.json.
-42 focused Python unit/HTTP checks passed; changed browser scripts parse. Broader
  run49/50: existing Instagram preview-planner context-limit test fails; reproduced
  with the ORIGINAL B-roll guidance/schema. Kept that unrelated failure separate.
  The B-roll prompt was condensed with its meanings retained; full creator profile,
  saved guidance and older raw verdicts remain intact. Chat format path is component
  checked, not a fresh chat LLM-generation demo. Other caption/publishing features
  were not edited or run. Final four safe live orientation/limit/auth checks pass,
  no new breaking point in those checks. Protected earlier findings stay unfixed.
- Native AE validation of the human-review contract remains pending owner quality
  selection; no native editor launch/save/close/input occurred. Premiere/CapCut and
  long-form validation remain deferred. Next different-video trial waits for the
  owner's review/source; do not start more full E3/E2 runs on your own.

## Latest owner steering and website-only trial — 29 October 2026

- Owner briefly proposed API-first with website fallback, then explicitly set
  that aside for this trial: NO API calls, NO local Vision. Search keywords on
  websites, show up to FIVE playable videos per keyword, owner judges relevance.
  Do not silently re-enable automatic relevance approval. API-first remains
  deferred; the strict older bank and all raw negative verdicts are preserved.
- Reused E3's saved nine-moment local-model plan, original phrase timestamps and
  full 37.454-second source. No new transcription/planning/vision inference.
- New separate website_review.py contract, explicit human choices, page-level
  failures, media decoding/hashes, local posters, all planned moments shown,
  compact After Effects control, persisted choices and empty-keyword-only retry.
  Default normal review mode is websites; old strict mode remains separately
  available. This does not retrain model weights or certify visual relevance.
- Actual Storylens browser button started the public-site trial. First pass:
  18 videos / four filled moments. Found same-site Mixkit search redirects were
  mistakenly skipped. Red-first repair permits bounded same-host HTTPS redirects,
  rejects external redirects. Continued ONLY empty groups; kept existing files.
  Also repaired a live-page truncation race with atomic HTML replacement.
  Therefore this is NOT an uninterrupted first-attempt reliability pass.
- Current visible result:
  http://127.0.0.1:8765/broll-output/20261029-001032-website-448e4b/001-e3/report.html
  29 videos / SEVEN of NINE moments: washer5, fridge5, AC3, table5, laptop5,
  room-frustration1, bed5. PG and wireless router remain empty. These are search
  candidates, not approved matches. In particular owner must judge abstract-room
  footage. Five is a maximum, not fabricated minimum coverage.
- Pexels and Pixabay PUBLIC WEBSITES both returned 403 challenge pages in this
  trial. Per-run circuits skip repeated blocked requests and retain the reason.
  No challenges bypassed; actual collected videos are from Mixkit. Source links
  and restricted/personal-only labels remain with each option. Missing results
  are NOT proof these objects are globally unavailable.
- Live validation: visible 29-video/nine-moment page; fridge video played through
  its full 6.96 seconds with readyState4 and no media error. Browser Option1 saved
  without AE connection, No B-roll cleared it. Temporary operator approval moved
  to website-choice-ui-check.json and removed from owner decisions afterward.
- 37 affected Python unit/HTTP integration checks and nine JS checks passed.
  Final safe live HTTP review: unauthenticated403, outside-output400, forged
  option400, original bank unchanged. No new breaking point found in THOSE four
  checks. Existing frozen findings remain protected. Evidence and screenshot:
  output/broll/reliability-evidence-20261028/website-*.json/txt/png.
- New human-review AE prepare route reuses receipt-bound native insert/swap and
  conforms only explicitly chosen media. Native validation of THIS new contract
  remains pending; prior strict-bank browser insert/swap evidence is separate.
  No AE actions/project save/close, Premiere/CapCut work or heavy model jobs were
  performed for this trial. Owner now reviews candidate quality before next work.

### Earlier E3 continuation root cause

- Job f2d6d15300ed passed the repaired Windows embedding loader, then FAILED in
  Ollama's actual server log with std::bad_alloc / HTTP500. Two washing-machine
  choices survived. Saved plan count9 was never nine successful matches.
- The old partial report now honestly says stopped and shows all nine planned
  moments, preserving its original JSON backup. No historical negatives became
  positives. Website-only human review is a separate result and contract.

Owner requested normal one-button Storylens operation, a visible realistic demo,
and individual timestamped insertion/replacement in Premiere Pro, After Effects
and CapCut. Keep five video choices for short content and two for long content;
reduce only after a measured limitation and explain it. Existing accepted results,
raw negatives, creator guidance and protected adversarial findings remain saved.

Latest owner steering: AFTER EFFECTS FIRST. Premiere and CapCut are deferred;
do not spend further validation/render time on them now. Prioritize the four
empty categories and explain whether retrieval or checking failed. The owner
also explicitly requested reduced token use and no more repetitive full runs.

NEWER clarification: six good matches out of ten are acceptable. Do not spend
extended effort forcing difficult concepts such as water heaters/PGs; failures
on very common objects remain a problem. STOP repeating E2. Owner supplied the
different source A:\Full Drive\thisis.vineet\e3\e3.mp4 for ONE normal live test.
That full file is37.454 seconds; job8756c46561b3 was started through the visible
main Storylens Run button, script field empty, five-option cap and Pexels disabled.
Let it finish normally. No extra full runs or rare-keyword repair while it is
healthy. The four-gap repair list below is now superseded by this cost/priority
clarification; retain its diagnostics rather than silently deleting them.

E3 update: initial job8756c46561b3 FAILED. Local planning automatically tried
two schema corrections, saved nine valid moments, then both original/recovery
workers crashed at visual-model loading (3221225477 /0xc0000005). Do NOT describe
this E3 test as an uninterrupted first-attempt success. Windows Application1000
records identify torch_cpu.dll. A single loader-only faulthandler reproduction
pinpointed torch/storage.py __getitem__ from Transformers' lazy safetensor slicing.
GPU had10.4GiB free at diagnosis; context overflow was not observed.

B-roll-only Windows repair: use installed safetensors0.8's supported pread reader
within the model load, restoring Transformers' alias afterward. Keep weights,
BF16 precision, direct CUDA placement and other features/installations unchanged.
Three loader contract checks pass. The same failing loader-only probe now loads
and releases the model successfully in12.85s. Evidence: e3-loader-diagnostic.txt
and e3-loader-pread-diagnostic.txt. No library upgrade or model download occurred.

Actual UI continuation jobf2d6d15300ed was then started with the same E3 source
and settings. It reports continuing saved work, skips planning and has passed
the former loader crash into footage-library checking. Let it finish. Record
its final result as repaired/resumed E3, not an autonomous first-attempt proof.

## Persistent queue

- [x] Inspect the configured local runtime: meaning/planning storylens-meaning:14b;
  vision storylens-planner:9b-q6; configured context 12,288. Ollama 0.40.5 responds;
  no loaded model at initial inspection. Configuration is not a per-call receipt.
- [x] Open the visible main Storylens instance on port 8765 and Add B-roll settings.
  Five choices, video-only sources and both saved provider credentials are present.
- [x] Coordinate with the existing Smart Visuals chat under explicit owner approval.
  B-roll owns the first heavy-job lane and shared editor insertion contract;
  Visuals may repair feature-owned Flat/PG retrieval on CPU without stopping jobs.
- [x] Check the former stale-preview collector gate: broll_preview_result.py now
  excludes retained preview.mp4 when the project declares deferred/failed state.
  Live deferred playback/save/rebuild remains a separate gate.
- [x] Run the real short e2 workflow through the normal website; record elapsed
  time, model calls, empty groups, failure/recovery and any manual interventions.
- [ ] Repair fresh integration failures with bounded/checkpointed processing;
  retain all source words/context and do not manufacture five weak matches.
- [ ] Measure a realistic long-form run and bounded per-keyword planning/retrieval.
- [ ] Verify option playback, explicit selection, save/rebuild and current report.
- [x] Add stable source-bank/slot/asset/host/operation identities for individual
  insertion and same-item replacement, preserving host trims, position and effects.
- [ ] Validate Premiere Pro native insertion/replacement and receipts.
- [x] Validate After Effects shared host API insertion/replacement and receipts.
- [ ] Validate the installed AE Storylens button/CEP receipt roundtrip; the API
  test above is a separate gate and did not reload the owner's current panel.
- [ ] Validate CapCut native insertion/replacement and receipts; an exported draft
  or new sequence is not proof of swapping an existing timeline item.
- [ ] Share the proven common contract and remaining limitations with Smart Visuals.

## Constraints and previous unfinished work

Use one heavy job/editor at a time. Do not disturb the owner's open unsaved
captions.aep or independently running jobs. Browser demonstration is authorized.
Existing typed candidate/owner-choice contracts, residential criteria, deferred
combined preview and earlier 117 CPU checks remain supplementary evidence.
Earlier real run a87c39c6a791 completed with seven choices across four of ten
moments, six empty groups, and incomplete quality acceptance. It is not a fresh
one-go success. Its provider-denial marker was historical, not a fresh 401 proof.
Retain its raw model negatives and timing evidence. Other project tasks remain
on their existing queues; Publisher Studio and OpenCut remain deferred.

## Runtime evidence and current corrections

- Recovery UI job 194ffceef9c3 resumed 20261024-031225-b90409 and completed in
  332.892 seconds without a manual restart. Five options in three of ten groups;
  this was recovery evidence, not a new generation or acceptable coverage.
- Fresh UI job 0b50ae89308e generated 20261028-210210-eeaef1, completing in
  1185.470 seconds in one attempt without a crash/manual rescue. Eleven options
  in four of ten groups; three options followed the ambiguous ASR word "pan".
  Six groups remained empty. Quality was NOT accepted. Concurrent code edits
  were for subsequent workers, not a manual rescue of this run.
- A fresh credential probe returned Pexels401 and Pixabay200. Owner chose
  "Continue without Pexels"; use_pexels is now false, saved credentials retained.
- Owner explicitly accepts healthy 20–30-minute runs: prioritize correctness,
  durable progress and one-button operation over a speed target.
- Long review planning now has bounded 180-word/1800-character/60-second windows,
  original word times and job-local partial checkpoints; two choices per long
  keyword. This is component-tested, not a real 15-minute-video acceptance.
- Initial regression repairs: preserve wardrobe's closet/cupboard queries;
  quarantine unresolved household pan/cooking sense until the local model resolves
  it; avoid borrowing the preceding object's identity; clarify unfurnished-room
  criteria and generic-object/presenter flags. Raw negative model answers stay
  unchanged. New explicit talking-presenter flags map into the existing contract;
  a negative flag cannot be turned positive by that mapping.
- Actual small local9B checks in actual-object-v3-checks.json now pass the same
  bed34474 and prepared refrigerator79665 windows. The wardrobe YouTube sample
  is visibly CGI and remains rejected. These are targeted checker checks, not a
  normal UI collection, native acceptance or owner choices. Per-call timing/token
  evidence is saved locally; no profile/credential/image payload is in that trace.
- Completed human-choice collections are evaluated once with failed findings
  retained, rather than automatically regenerating the bank for sparse coverage.
  Ordinary automatic-edit correction attempts remain unchanged. Empty report
  wording now distinguishes videos rejected by checks from failed downloads;
  an empty bank no longer claims that stock footage does not exist.
- Adobe individual-choice prototype: receipt-bound pending operation, private
  per-slot media, original speech frames and same-item replacement guards.
  Nine Python and five mocked-host Node checks pass at this checkpoint. It is
  NOT yet wired to CEP/UI or verified in Premiere/AE. The owner's unsaved AE
  project has not been operated on. CapCut currently supports new editable drafts,
  not a supported transaction against an open timeline; do not edit live draft JSON.
- Smart Visuals reported a frozen final-review geography-negation finding:
  "South India, not North India" can satisfy its lexical filter. Keep it unfixed
  under the standing final-review rule and do not claim geographic acceptance.
  Their feature-owned Flat/PG fixes and CapCut investigation are in their queue.

Evidence folder: output/broll/reliability-evidence-20261028. The current full
corrected e2 retest was started through the visible main UI after these changes;
record its actual terminal result before any acceptance statement.

### Later live evidence and remaining gates — 28 October, evening

- Fresh UI job 0b50ae89308e finished in 1185.470 seconds in one attempt,
  without Codex rescue. Its 11 options across four of ten moments were NOT
  accepted quality: the household pan sense was wrong and six moments empty.
- Corrected job cc7c4f45f7f0 failed twice: Windows paging allocation error 1455
  during model startup, then NVIDIA CreateBitstreamBuffer out-of-memory followed
  by native exit 3221226356. Automatic recovery preserved its plan and choices.
  This is not a successful one-go demonstration.
- Repairs for the next worker: release Ollama before importing Torch, load the
  embedding model directly onto its intended device, and use CPU H264 encoding
  for review clips while retaining CUDA for local inference. Targeted loading
  and encoding checks pass. Fresh startup acceptance remains pending.
- UI recovery c3cd872fa7e5 is running against saved output
  20261028-213814-b1536d. It has collected bed and refrigerator choices after the
  repairs. Do not restart it or launch another heavy test while it is healthy.
- With explicit owner permission, a separate 10-second quarter-resolution AE
  comp (2633) was created in the existing unsaved captions.aep. Actual insert at
  original speech frames and alternative replacement both used layer 2647.
  Trim, stretch, transform, opacity keys and a test effect were preserved;
  repeated delivery kept one layer. Receipts and visible capture are saved.
  Existing owner comps were not saved, closed or changed. Playback stopped
  before input when user interaction was detected; playback is unverified.
- That AE test exercises the actual shared host API, not the production
  Storylens-button/installed-CEP roundtrip. Source hooks are prepared but the
  loaded owner panel was not reloaded. Premiere remains mocked-host only.
  CapCut selected-only new-draft spec is component-tested; active-timeline swap
  has no supported API and is not implemented. Do not present a new draft as swap.
- Panel HTTP checks passed (16) when rerun in the host network context. The new
  memory-message regression passed; three existing caption-page HTML subcases
  fail in test_user_messages and are outside this B-roll patch.
- Still required: complete/inspect recovery, fresh UI one-Run validation,
  realistic long-form validation, production button/native receipt roundtrip,
  Premiere and CapCut actual results, then final adversarial review. Preserve
  existing frozen review findings and report any new final-review findings.

### Fresh one-Run result and follow-up source wiring

- Recovery c3cd872fa7e5 completed in 459.528 seconds with 15 options / seven
  filled moments. Inspection found the model had inconsistently approved a CGI
  wardrobe, so this result is NOT quality acceptance.
- Fresh UI job 4245d317841d completed in 775.913 seconds, one attempt, no crash,
  recovery or Codex restart. It produced ten options / four of ten moments.
  Runtime passed that scope; coverage did not. Evidence: fresh-run-4245d317841d.json.
- Object criteria v4 explicitly classified capture medium and rejected the CGI
  wardrobe, but also misread subsecond real footage as a still. Version5 adds
  two wider capture-only frames and explicit fridge-interior criteria. The three
  original active-window subject checks stay mandatory; wider frames cannot
  override a bad active frame. Actual local-model calls now pass bed34474
  prepared / fridge79665 original and reject wardrobe CGI. Histories are retained.
- Full v5 UI job 655e33bcfc86 is running. Record its terminal result and inspect
  its actual media; targeted checker calls are not that workflow's acceptance.
- Browser/native source wiring now includes broll_native_mailbox.py,
  timed-choice-panel.js and broll-editor-choices.js: three software choices,
  offered-video IDs only, one connected Adobe timeline, same pending operation
  on retry, receipt-only success, selected-only CapCut new drafts, and honest
  No B-roll handling. Component/HTTP checks pass so far. Loaded main service and
  installed CEP have NOT been reloaded; the owner has an active 3D form there.
- New keyword-bank quality check accepts valid subsecond spoken timestamps;
  automatic finished-cut minimum lengths remain unchanged. Missing matches
  still fail coverage; this repair does not manufacture an accepted result.
- Persistent source/model reference guidance is not weight training. The actual
  short run's autonomous scope and manual software repairs are reported separately.

### Latest working-source and browser-to-AE results

- Pexels remains disabled at repeated explicit owner instruction. Do not retry it.
- Full job655e33bcfc86:726.600 seconds,11 options/five filled moments, one attempt,
  no automatic recovery/manual restart. Actual bed/fridge checks passed; wardrobe
  still empty. See fresh-run-655e33bcfc86.json.
- Working Pixabay audit proved wardrobe wording missed real source163116 while
  bare closet returned it. Added stock_keyword wardrobe/closet/cupboard fallback
  to closet with red/green test. No clip was manually inserted into a bank.
- Full normal UI job56618bf3d897:498.877 seconds (8m19s),12 options/six of ten
  moments, one attempt, no crash/recovery/Codex rescue. Local checks approved
  original AND prepared real wardrobe163116. Bed and fridge also present.
  Quality95 still fails coverage; do not call ten-of-ten complete. Three
  successive full short runs have completed without interruption.
- Actual provider/primary-page audit from Smart Visuals:
  output/visuals/reliability-evidence/wardrobe-source-availability-20261028.json.
  Mixkit personal-only/commercial terms stay distinguished; availability alone
  is not pixel/download suitability. Frozen geography finding remains untouched.
- Main Storylens was reloaded ONLY when idle with owner permission, keeping
  --no-publisher-worker. Latest launch PID38608 (may be a venv launcher; resolve
  actual listening process before any future action). All original jobs saved.
- New broll_ae_direct.py provides fixed Adobe -r execution to the already-running
  trusted Adobe host, controller-owned private media, invocation nonce and native
  receipts. No arbitrary browser code, project opening/saving/closing or new
  host launch. Authenticated HTTP and component checks pass (36 affected checks).
- Actual BROWSER workflow, not just a mocked host: opened real report, clicked
  After Effects, captured isolated comp577; clicked street Option1 and received
  native layer591 at frames3–64. Operator then edited only that test layer's trim,
  stretch125%, position, scale, opacity keys and slider17. Browser Option2 replaced
  the SAME layer591, kept ONE layer and preserved every tested edit. Clicking
  Option2 again confirmed the same choice. Actual receipts and before/after JSON:
  ae-browser-insert-receipt.json, ae-browser-swap-receipt.json and
  ae-browser-button-verification.json. Original source bank was not curated.
- Temporary operator choices were moved to browser-test-only-selections.json;
  the original owner's decisions (initially absent) were restored. See cleanup.
  Existing owner comps were not edited/saved/closed; the separate35.7-second
  quarter-resolution test comp remains in the unsaved captions.aep.
- Native control initially misreported the window as minimized. Documented
  app.activate executed. A later capture became available but showed the owner's
  current 3D comp; switching to the B-roll test tab was blocked by detected input.
  Therefore actual B-roll native appearance/playback remain unverified. Do not
  disturb their 3D work or claim visual acceptance from API properties.
- Main B-roll result buttons now use three destinations and navigate to review
  before any import. Other caption handoffs are unchanged. Multi-result index
  pages remain supported. Report supports the selected destination hint. These
  latest main-button changes are component-tested; native AE browser clicks above
  used the report directly.
- Final bounded source/receipt security regression review:14 checks passed;
  no new breaking point found IN THOSE checks. Full native visual/long-form and
  other hosts remain outside that evidence. No frozen finding was repaired.

### Four remaining empty groups: diagnosed, not called globally unavailable

- slot1 flat/apartment: seven candidates checked. Real empty-room16399 rejected
  for ambiguous residential identity. Other candidates include office/salon/CGI.
  web4d1967f109902d72 passed original but prepared failed as static CGI.
- slot2 bachelor room:12 leads.16399 original passed; prepared rejected because
  it lacks furniture/personal items despite unfurnished-room allowance. Clear
  offices/CGI/dark/ruined footage were correctly rejected. Some website files
  and a real room with a presenter/overlay also failed.
- slot9 PG room:12 leads, same room inventory;16399 rejected for missing furniture,
  and a residential loft rejected as commercial-style. This is over-strict or
  inconsistent checking plus weak search diversity, not proof of no footage.
- slot6 water heater:three leads, only one reached actual checks (Pixabay267,
  a steaming pot, correctly rejected). Two web leads failed before frame checks.
  This proves insufficient successful retrieval, NOT global unavailability.
- NEXT: keep full source context/raw negatives; repair generic room query
  fallback and room checker (wider capture-only samples, no furniture mandate),
  trace heater download/query failures, then use focused saved-bank gap tests
  instead of restarting the whole video repeatedly. Verify AE batch handoff
  of explicit saved choices and separate it from source-bank generation.


### Owner-approved five-source workflow — 29 October 2026

- Preserve all five source connections; current website-only/manual-review workflow accepted.
- New generations: Instagram/vertical maximum five options, YouTube/horizontal maximum two. Historical reviews preserved.
- Saved local-model guidance: publishing_workflow.json, newest chunk broll-approved-parallel-manual-bank-2026-10-29.
- [ ] One real new E5 run: A:/Full Drive/thisis.vineet/e5/e5 zomato_chf3_prob3.mov (33.228s, portrait). Show actual review and record elapsed scope.
- Native website-bank handoff and long-form validation remain separately pending.

- E5 submitted once through visible Storylens Run → Vertical: job a4070852f976, max five. Currently queued behind active caption timing job 1a245f7b49c322c3bfbed53f13209244. Do not interrupt captions or submit a duplicate. Tests: 40 Python + 1 Node passed; 11 final safe policy/source probes passed, no new finding in those probes. Evidence: output/broll/e5-approved-workflow-evidence/status.json and settings.png. Full E5 result and native handoff are not verified yet.


### GPU-first owner request — 29 October 2026

Latest owner preference: use the RTX 5070 Ti Laptop GPU for every supported B-roll inference stage. Retain CUDA speech recognition, speech detection/alignment and GPU-offloaded local language planning. Do not silently replace these with CPU-only inference. Existing selected meaning model is storylens-meaning:14b, model parameters num_gpu=41 (40 transformer blocks plus output layer); CUDA/runtime settings were already enabled before this request. Preserve the model and full creator guidance, sequential heavy-job queue and caption priority. Website navigation, HTTP searches/downloads and original-video integrity checks still require CPU/network work; do not claim those have been moved to GPU. Retain the five-source website-only manual-review workflow; no stock API or Vision gate is re-enabled. A CUDA arithmetic probe proves runtime availability, not full E5 or full-model GPU residency.
- E5 a4070852f976 remains submitted once and queued. No shared service restart or other worker interruption.

- E5 completed: one worker attempt, 50 offered videos (five per each of ten moments), 49 unique media files. 663.523s from output creation; 690.053s queued beforehand. All portrait files exist, source timestamps valid; actual browser playback passed. Full14B model residency verified on GPU, no mid-run repair/restart. Review: http://127.0.0.1:8765/broll-output/20261029-040204-1f8fe4/001-e5-zomato_chf3_prob3/report.html. Human relevance acceptance/native import remain pending. Evidence final-result.json, final-playback.json, final-review.png.
