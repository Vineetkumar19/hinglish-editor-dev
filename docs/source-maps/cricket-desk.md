# cricket-desk source map

Use this map to jump from a module to its definitions. Links refer to this source snapshot. Static imports and definitions show where code lives. Runtime acceptance is recorded separately.

## app.py

[Open source](../../components/cricket-desk/app.py)

Imports pathlib, sqlite3, json, hashlib, time, threading, datetime, re, html, urllib.parse, xml.etree.ElementTree, secrets, sys, os, zipfile, io, html.parser, contextlib, requests, research.

- [now](../../components/cricket-desk/app.py#L14) — function
- [db](../../components/cricket-desk/app.py#L16) — function
- [init](../../components/cricket-desk/app.py#L23) — function
- [get](../../components/cricket-desk/app.py#L27) — function
- [put](../../components/cricket-desk/app.py#L30) — function
- [platform](../../components/cricket-desk/app.py#L32) — function
- [canonical](../../components/cricket-desk/app.py#L45) — function
- [ingest](../../components/cricket-desk/app.py#L53) — function
- [Extract](../../components/cricket-desk/app.py#L68) — class
- [fetch](../../components/cricket-desk/app.py#L75) — function
- [rss_rows](../../components/cricket-desk/app.py#L79) — function
- [reddit_rows](../../components/cricket-desk/app.py#L85) — function
- [media_allowed](../../components/cricket-desk/app.py#L93) — function
- [collect](../../components/cricket-desk/app.py#L97) — function
- [download](../../components/cricket-desk/app.py#L121) — function
- [export](../../components/cricket-desk/app.py#L136) — function
- [protect](../../components/cricket-desk/app.py#L146) — function
- [index](../../components/cricket-desk/app.py#L150) — function
- [state](../../components/cricket-desk/app.py#L152) — function
- [selected](../../components/cricket-desk/app.py#L156) — function
- [prepare_selected](../../components/cricket-desk/app.py#L158) — function
- [health](../../components/cricket-desk/app.py#L162) — function
- [config](../../components/cricket-desk/app.py#L164) — function
- [scan](../../components/cricket-desk/app.py#L172) — function
- [browser_connect](../../components/cricket-desk/app.py#L174) — function
- [browser_finish](../../components/cricket-desk/app.py#L178) — function
- [social_scan](../../components/cricket-desk/app.py#L182) — function
- [add](../../components/cricket-desk/app.py#L197) — function
- [gpt](../../components/cricket-desk/app.py#L202) — function
- [review](../../components/cricket-desk/app.py#L206) — function
- [media](../../components/cricket-desk/app.py#L212) — function
- [exports](../../components/cricket-desk/app.py#L216) — function
- [mediafile](../../components/cricket-desk/app.py#L218) — function
- [worker](../../components/cricket-desk/app.py#L219) — function
- [__init__](../../components/cricket-desk/app.py#L69) — function
- [handle_starttag](../../components/cricket-desk/app.py#L70) — function
- [handle_data](../../components/cricket-desk/app.py#L74) — function
- [run](../../components/cricket-desk/app.py#L183) — function

## clean_ui.py

[Open source](../../components/cricket-desk/clean_ui.py)

Imports pathlib, re, shutil.


## integrate-storylens.py

[Open source](../../components/cricket-desk/integrate-storylens.py)

Imports pathlib, datetime, hashlib, json, shutil.

- [replace](../../components/cricket-desk/integrate-storylens.py#L13) — function

## probe_sources.py

[Open source](../../components/cricket-desk/probe_sources.py)

Imports requests, json, pathlib.


## record-ui-update.py

[Open source](../../components/cricket-desk/record-ui-update.py)

Imports pathlib, datetime, json, shutil, sys, urllib.request.


## research.py

[Open source](../../components/cricket-desk/research.py)

Imports pathlib, datetime, json, subprocess, threading, shutil, re, urllib.parse, os.

- [localnow](../../components/cricket-desk/research.py#L5) — function
- [minute](../../components/cricket-desk/research.py#L6) — function
- [validate](../../components/cricket-desk/research.py#L8) — function
- [slot](../../components/cricket-desk/research.py#L25) — function
- [cancel](../../components/cricket-desk/research.py#L37) — function
- [run](../../components/cricket-desk/research.py#L39) — function

## selected_assets.py

[Open source](../../components/cricket-desk/selected_assets.py)

Imports datetime, hashlib, json, pathlib, shutil, uuid.

- [rows](../../components/cricket-desk/selected_assets.py#L9) — function
- [manifest](../../components/cricket-desk/selected_assets.py#L24) — function
- [sync](../../components/cricket-desk/selected_assets.py#L31) — function
- [prepare](../../components/cricket-desk/selected_assets.py#L38) — function

## social.py

[Open source](../../components/cricket-desk/social.py)

Imports pathlib, datetime, re, urllib.parse, json, time, threading, contextlib, msvcrt, requests, playwright.sync_api.

- [browser_state](../../components/cricket-desk/social.py#L19) — function
- [save_browser_state](../../components/cricket-desk/social.py#L23) — function
- [browser_lock](../../components/cricket-desk/social.py#L29) — function
- [connect_browser](../../components/cricket-desk/social.py#L40) — function
- [direct_url](../../components/cricket-desk/social.py#L67) — function
- [is_search_redirect](../../components/cricket-desk/social.py#L85) — function
- [resolve_result](../../components/cricket-desk/social.py#L91) — function
- [publication](../../components/cricket-desk/social.py#L112) — function — Search-result age is approximate evidence, never a precise post timestamp.
- [collect](../../components/cricket-desk/social.py#L141) — function

## storylens-integration/save-result.py

[Open source](../../components/cricket-desk/storylens-integration/save-result.py)

Imports pathlib, datetime, hashlib, json, sys, urllib.request.


## test_inbox.py

[Open source](../../components/cricket-desk/test_inbox.py)

Imports unittest, tempfile, json, datetime, uuid, pathlib, app, research.

- [Contracts](../../components/cricket-desk/test_inbox.py#L4) — class
- [setUp](../../components/cricket-desk/test_inbox.py#L5) — function
- [tearDown](../../components/cricket-desk/test_inbox.py#L7) — function
- [test_off_never_invokes_model](../../components/cricket-desk/test_inbox.py#L8) — function
- [test_csrf](../../components/cricket-desk/test_inbox.py#L12) — function
- [test_dedupe_and_review_preservation](../../components/cricket-desk/test_inbox.py#L13) — function
- [test_window_and_dates](../../components/cricket-desk/test_inbox.py#L19) — function
- [test_validation_and_ssrf](../../components/cricket-desk/test_inbox.py#L23) — function
- [forbidden](../../components/cricket-desk/test_inbox.py#L9) — function

## validate_live.py

[Open source](../../components/cricket-desk/validate_live.py)

Imports pathlib, requests, re, json.

## Frontend and native source files

### storylens-integration/app-before-direct-frame.js

[Open source](../../components/cricket-desk/storylens-integration/app-before-direct-frame.js)

- [updateCaptionReference](../../components/cricket-desk/storylens-integration/app-before-direct-frame.js#L12)
- [api](../../components/cricket-desk/storylens-integration/app-before-direct-frame.js#L28)
- [setMode](../../components/cricket-desk/storylens-integration/app-before-direct-frame.js#L35)
- [uploadOne](../../components/cricket-desk/storylens-integration/app-before-direct-frame.js#L113)
- [addVideos](../../components/cricket-desk/storylens-integration/app-before-direct-frame.js#L131)
- [countWords](../../components/cricket-desk/storylens-integration/app-before-direct-frame.js#L173)
- [renderLibrary](../../components/cricket-desk/storylens-integration/app-before-direct-frame.js#L183)
- [showSettings](../../components/cricket-desk/storylens-integration/app-before-direct-frame.js#L190)
- [loadBrollSettings](../../components/cricket-desk/storylens-integration/app-before-direct-frame.js#L200)
- [syncResultBar](../../components/cricket-desk/storylens-integration/app-before-direct-frame.js#L212)
- [showQuality](../../components/cricket-desk/storylens-integration/app-before-direct-frame.js#L228)
- [loadEyeStatus](../../components/cricket-desk/storylens-integration/app-before-direct-frame.js#L270)
- [loadSoundSettings](../../components/cricket-desk/storylens-integration/app-before-direct-frame.js#L278)
- [changeSoundFolder](../../components/cricket-desk/storylens-integration/app-before-direct-frame.js#L280)
- [aiPayload](../../components/cricket-desk/storylens-integration/app-before-direct-frame.js#L285)
- [videoStudioPayload](../../components/cricket-desk/storylens-integration/app-before-direct-frame.js#L288)
- [updateVideoMethod](../../components/cricket-desk/storylens-integration/app-before-direct-frame.js#L289)
- [showStyles](../../components/cricket-desk/storylens-integration/app-before-direct-frame.js#L300)
- [loadAigen](../../components/cricket-desk/storylens-integration/app-before-direct-frame.js#L304)
- [showMotion](../../components/cricket-desk/storylens-integration/app-before-direct-frame.js#L321)
- [loadMotionStyles](../../components/cricket-desk/storylens-integration/app-before-direct-frame.js#L341)
- [updateMotionEngine](../../components/cricket-desk/storylens-integration/app-before-direct-frame.js#L344)
- [learnMotion](../../components/cricket-desk/storylens-integration/app-before-direct-frame.js#L348)
- [engineProblem](../../components/cricket-desk/storylens-integration/app-before-direct-frame.js#L419)
- [poll](../../components/cricket-desk/storylens-integration/app-before-direct-frame.js#L436)
- [open](../../components/cricket-desk/storylens-integration/app-before-direct-frame.js#L460)

### storylens-integration/backup-20261104-013730/app.js

[Open source](../../components/cricket-desk/storylens-integration/backup-20261104-013730/app.js)

- [updateCaptionReference](../../components/cricket-desk/storylens-integration/backup-20261104-013730/app.js#L12)
- [api](../../components/cricket-desk/storylens-integration/backup-20261104-013730/app.js#L28)
- [setMode](../../components/cricket-desk/storylens-integration/backup-20261104-013730/app.js#L35)
- [uploadOne](../../components/cricket-desk/storylens-integration/backup-20261104-013730/app.js#L112)
- [addVideos](../../components/cricket-desk/storylens-integration/backup-20261104-013730/app.js#L130)
- [countWords](../../components/cricket-desk/storylens-integration/backup-20261104-013730/app.js#L172)
- [renderLibrary](../../components/cricket-desk/storylens-integration/backup-20261104-013730/app.js#L182)
- [showSettings](../../components/cricket-desk/storylens-integration/backup-20261104-013730/app.js#L189)
- [loadBrollSettings](../../components/cricket-desk/storylens-integration/backup-20261104-013730/app.js#L199)
- [syncResultBar](../../components/cricket-desk/storylens-integration/backup-20261104-013730/app.js#L211)
- [showQuality](../../components/cricket-desk/storylens-integration/backup-20261104-013730/app.js#L227)
- [loadEyeStatus](../../components/cricket-desk/storylens-integration/backup-20261104-013730/app.js#L269)
- [loadSoundSettings](../../components/cricket-desk/storylens-integration/backup-20261104-013730/app.js#L277)
- [changeSoundFolder](../../components/cricket-desk/storylens-integration/backup-20261104-013730/app.js#L279)
- [aiPayload](../../components/cricket-desk/storylens-integration/backup-20261104-013730/app.js#L284)
- [videoStudioPayload](../../components/cricket-desk/storylens-integration/backup-20261104-013730/app.js#L287)
- [updateVideoMethod](../../components/cricket-desk/storylens-integration/backup-20261104-013730/app.js#L288)
- [showStyles](../../components/cricket-desk/storylens-integration/backup-20261104-013730/app.js#L299)
- [loadAigen](../../components/cricket-desk/storylens-integration/backup-20261104-013730/app.js#L303)
- [showMotion](../../components/cricket-desk/storylens-integration/backup-20261104-013730/app.js#L320)
- [loadMotionStyles](../../components/cricket-desk/storylens-integration/backup-20261104-013730/app.js#L340)
- [updateMotionEngine](../../components/cricket-desk/storylens-integration/backup-20261104-013730/app.js#L343)
- [learnMotion](../../components/cricket-desk/storylens-integration/backup-20261104-013730/app.js#L347)
- [engineProblem](../../components/cricket-desk/storylens-integration/backup-20261104-013730/app.js#L418)
- [poll](../../components/cricket-desk/storylens-integration/backup-20261104-013730/app.js#L435)
- [open](../../components/cricket-desk/storylens-integration/backup-20261104-013730/app.js#L459)

### storylens-integration/backup-20261104-013730/icons.js

[Open source](../../components/cricket-desk/storylens-integration/backup-20261104-013730/icons.js)


### storylens-integration/backup-20261104-013933/feature-tools.js

[Open source](../../components/cricket-desk/storylens-integration/backup-20261104-013933/feature-tools.js)

- [badge](../../components/cricket-desk/storylens-integration/backup-20261104-013933/feature-tools.js#L11)
