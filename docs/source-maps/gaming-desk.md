# gaming-desk source map

Use this map to jump from a module to its definitions. Links refer to this source snapshot. Static imports and definitions show where code lives. Runtime acceptance is recorded separately.

## app.py

[Open source](../../components/gaming-desk/app.py)

Imports pathlib, sqlite3, json, hashlib, time, threading, datetime, re, html, urllib.parse, xml.etree.ElementTree, secrets, sys, os, zipfile, io, html.parser, contextlib, email.utils, requests.

- [now](../../components/gaming-desk/app.py#L15) — function
- [db](../../components/gaming-desk/app.py#L17) — function
- [init](../../components/gaming-desk/app.py#L24) — function
- [get](../../components/gaming-desk/app.py#L28) — function
- [put](../../components/gaming-desk/app.py#L31) — function
- [platform](../../components/gaming-desk/app.py#L33) — function
- [canonical](../../components/gaming-desk/app.py#L46) — function
- [ingest](../../components/gaming-desk/app.py#L54) — function
- [Extract](../../components/gaming-desk/app.py#L69) — class
- [fetch](../../components/gaming-desk/app.py#L76) — function
- [rss_rows](../../components/gaming-desk/app.py#L80) — function
- [reddit_rows](../../components/gaming-desk/app.py#L93) — function
- [media_allowed](../../components/gaming-desk/app.py#L101) — function
- [collect](../../components/gaming-desk/app.py#L105) — function
- [download](../../components/gaming-desk/app.py#L138) — function
- [export](../../components/gaming-desk/app.py#L153) — function
- [protect](../../components/gaming-desk/app.py#L163) — function
- [index](../../components/gaming-desk/app.py#L167) — function
- [state](../../components/gaming-desk/app.py#L169) — function
- [selected](../../components/gaming-desk/app.py#L173) — function
- [prepare_selected](../../components/gaming-desk/app.py#L175) — function
- [health](../../components/gaming-desk/app.py#L179) — function
- [config](../../components/gaming-desk/app.py#L181) — function
- [scan](../../components/gaming-desk/app.py#L189) — function
- [browser_connect](../../components/gaming-desk/app.py#L191) — function
- [browser_finish](../../components/gaming-desk/app.py#L195) — function
- [social_scan](../../components/gaming-desk/app.py#L199) — function
- [add](../../components/gaming-desk/app.py#L214) — function
- [gpt](../../components/gaming-desk/app.py#L219) — function
- [review](../../components/gaming-desk/app.py#L223) — function
- [media](../../components/gaming-desk/app.py#L229) — function
- [exports](../../components/gaming-desk/app.py#L233) — function
- [mediafile](../../components/gaming-desk/app.py#L235) — function
- [worker](../../components/gaming-desk/app.py#L236) — function
- [__init__](../../components/gaming-desk/app.py#L70) — function
- [handle_starttag](../../components/gaming-desk/app.py#L71) — function
- [handle_data](../../components/gaming-desk/app.py#L75) — function
- [run](../../components/gaming-desk/app.py#L200) — function

## finalize.py

[Open source](../../components/gaming-desk/finalize.py)

Imports pathlib, datetime, json, shutil, sys, urllib.request.


## install-feature.py

[Open source](../../components/gaming-desk/install-feature.py)

Imports pathlib, datetime, json, shutil.

- [replace](../../components/gaming-desk/install-feature.py#L11) — function

## research.py

[Open source](../../components/gaming-desk/research.py)

Imports pathlib, datetime, json, subprocess, threading, shutil, re, urllib.parse, os.

- [localnow](../../components/gaming-desk/research.py#L5) — function
- [minute](../../components/gaming-desk/research.py#L6) — function
- [validate](../../components/gaming-desk/research.py#L8) — function
- [slot](../../components/gaming-desk/research.py#L25) — function
- [cancel](../../components/gaming-desk/research.py#L37) — function
- [run](../../components/gaming-desk/research.py#L39) — function

## selected_assets.py

[Open source](../../components/gaming-desk/selected_assets.py)

Imports datetime, hashlib, json, pathlib, shutil, uuid.

- [rows](../../components/gaming-desk/selected_assets.py#L9) — function
- [manifest](../../components/gaming-desk/selected_assets.py#L24) — function
- [sync](../../components/gaming-desk/selected_assets.py#L31) — function
- [prepare](../../components/gaming-desk/selected_assets.py#L38) — function

## social.py

[Open source](../../components/gaming-desk/social.py)

Imports pathlib, datetime, re, urllib.parse, json, time, threading, contextlib, msvcrt, requests, playwright.sync_api.

- [browser_state](../../components/gaming-desk/social.py#L19) — function
- [save_browser_state](../../components/gaming-desk/social.py#L23) — function
- [browser_lock](../../components/gaming-desk/social.py#L29) — function
- [connect_browser](../../components/gaming-desk/social.py#L40) — function
- [direct_url](../../components/gaming-desk/social.py#L67) — function
- [is_search_redirect](../../components/gaming-desk/social.py#L85) — function
- [resolve_result](../../components/gaming-desk/social.py#L91) — function
- [publication](../../components/gaming-desk/social.py#L112) — function — Search-result age is approximate evidence, never a precise post timestamp.
- [collect](../../components/gaming-desk/social.py#L141) — function

## test_inbox.py

[Open source](../../components/gaming-desk/test_inbox.py)

Imports unittest, tempfile, json, datetime, uuid, pathlib, app, research, email.utils, xml.etree.ElementTree.

- [Contracts](../../components/gaming-desk/test_inbox.py#L4) — class
- [setUp](../../components/gaming-desk/test_inbox.py#L5) — function
- [tearDown](../../components/gaming-desk/test_inbox.py#L7) — function
- [test_off_never_invokes_model](../../components/gaming-desk/test_inbox.py#L8) — function
- [test_csrf](../../components/gaming-desk/test_inbox.py#L12) — function
- [test_dedupe_and_review_preservation](../../components/gaming-desk/test_inbox.py#L13) — function
- [test_window_and_dates](../../components/gaming-desk/test_inbox.py#L19) — function
- [test_validation_and_ssrf](../../components/gaming-desk/test_inbox.py#L23) — function
- [test_news_feed_excludes_stale_or_future_dates](../../components/gaming-desk/test_inbox.py#L26) — function
- [forbidden](../../components/gaming-desk/test_inbox.py#L9) — function

## validate-live.py

[Open source](../../components/gaming-desk/validate-live.py)

Imports pathlib, json, re, urllib.request, datetime.

- [get](../../components/gaming-desk/validate-live.py#L9) — function
- [post](../../components/gaming-desk/validate-live.py#L12) — function

## Frontend and native source files

### storylens-integration/backup-20261104-020248/app.js

[Open source](../../components/gaming-desk/storylens-integration/backup-20261104-020248/app.js)

- [updateCaptionReference](../../components/gaming-desk/storylens-integration/backup-20261104-020248/app.js#L12)
- [api](../../components/gaming-desk/storylens-integration/backup-20261104-020248/app.js#L28)
- [setMode](../../components/gaming-desk/storylens-integration/backup-20261104-020248/app.js#L35)
- [uploadOne](../../components/gaming-desk/storylens-integration/backup-20261104-020248/app.js#L113)
- [addVideos](../../components/gaming-desk/storylens-integration/backup-20261104-020248/app.js#L131)
- [countWords](../../components/gaming-desk/storylens-integration/backup-20261104-020248/app.js#L173)
- [renderLibrary](../../components/gaming-desk/storylens-integration/backup-20261104-020248/app.js#L183)
- [showSettings](../../components/gaming-desk/storylens-integration/backup-20261104-020248/app.js#L190)
- [loadBrollSettings](../../components/gaming-desk/storylens-integration/backup-20261104-020248/app.js#L200)
- [syncResultBar](../../components/gaming-desk/storylens-integration/backup-20261104-020248/app.js#L212)
- [showQuality](../../components/gaming-desk/storylens-integration/backup-20261104-020248/app.js#L228)
- [loadEyeStatus](../../components/gaming-desk/storylens-integration/backup-20261104-020248/app.js#L270)
- [loadSoundSettings](../../components/gaming-desk/storylens-integration/backup-20261104-020248/app.js#L278)
- [changeSoundFolder](../../components/gaming-desk/storylens-integration/backup-20261104-020248/app.js#L280)
- [aiPayload](../../components/gaming-desk/storylens-integration/backup-20261104-020248/app.js#L285)
- [videoStudioPayload](../../components/gaming-desk/storylens-integration/backup-20261104-020248/app.js#L288)
- [updateVideoMethod](../../components/gaming-desk/storylens-integration/backup-20261104-020248/app.js#L289)
- [showStyles](../../components/gaming-desk/storylens-integration/backup-20261104-020248/app.js#L300)
- [loadAigen](../../components/gaming-desk/storylens-integration/backup-20261104-020248/app.js#L304)
- [showMotion](../../components/gaming-desk/storylens-integration/backup-20261104-020248/app.js#L321)
- [loadMotionStyles](../../components/gaming-desk/storylens-integration/backup-20261104-020248/app.js#L341)
- [updateMotionEngine](../../components/gaming-desk/storylens-integration/backup-20261104-020248/app.js#L344)
- [learnMotion](../../components/gaming-desk/storylens-integration/backup-20261104-020248/app.js#L348)
- [engineProblem](../../components/gaming-desk/storylens-integration/backup-20261104-020248/app.js#L419)
- [poll](../../components/gaming-desk/storylens-integration/backup-20261104-020248/app.js#L436)
- [open](../../components/gaming-desk/storylens-integration/backup-20261104-020248/app.js#L460)

### storylens-integration/backup-20261104-020248/feature-tools.js

[Open source](../../components/gaming-desk/storylens-integration/backup-20261104-020248/feature-tools.js)

- [badge](../../components/gaming-desk/storylens-integration/backup-20261104-020248/feature-tools.js#L11)

### storylens-integration/backup-20261104-020248/icons.js

[Open source](../../components/gaming-desk/storylens-integration/backup-20261104-020248/icons.js)

