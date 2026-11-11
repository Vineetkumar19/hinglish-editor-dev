# Local assistant workflow

Give the execution request in Storylens. Codex is not required to operate the
editor or trigger the daily Instagram uploads.

Example:

> From `A:\Editing\documentry edit\final videos\final videos`, use `mi final.mp4`.
> Extract up to 7 worthwhile Shorts with captions. Write English YouTube titles,
> descriptions and relevant hashtags, plus separate Instagram captions and
> hashtags. Post to my gaming accounts on YouTube and Instagram, one matching
> clip per day starting tomorrow at 7 p.m. IST.

The installed local model selects moments and writes the copy. The workflow code
resolves actual files, validates its plan, renders outputs, stores per-clip
preparation checkpoints, uploads the YouTube videos privately, applies their daily
release dates, and verifies the exact channel/video/time. Instagram uses the same
exports and matching times in a disk-backed local queue.

The owner has saved permanent YouTube defaults: **Not made for kids** and
**No realistic altered or synthetic media**. Storylens applies these without
asking each time. An explicit later change takes precedence. “Draft” or
“review first” keeps the review step. New Shorts workflows default to both matching
accounts; “YouTube only” or “Instagram only” limits the platforms.

For finished clips, an Instagram follow-up such as “Post these Shorts on my
gaming Instagram, one video now and the second tomorrow at 7 p.m.” reuses the
current batch, generates missing Instagram copy locally, and queues those exact
clips. The first is immediately eligible; the second waits for its future slot.
It does not repeat the YouTube upload. Saved declarations do not turn a new
platform or date request into confirmation of an older review.

For a real Instagram run while YouTube uploads are unavailable, explicitly say
**“YouTube check only.”** Storylens checks the live channel identity, local
exports and metadata, then keeps YouTube drafts unsubmitted. This does not
prove that YouTube's upload limit has reset. The independently authorized
Instagram queue can still run.

Caption review includes a persistent cricket spelling reference at
`hinglish_captions/cricket_vocabulary.json`, with official-source links. It covers
common players, current and historical IPL team names, and cricket terminology;
it is not an exhaustive player registry or a source of match scores. The local
model also proposes names from the actual speech. Whole-name corrections may
merge syllables split by ASR, but cannot delete surrounding Hindi words or
change a valid singular term into its plural. Numerical corrections remain
bound to speech evidence. Likely misspellings in headings are sent back to
the local model for correction or a neutral title.

“Repair these saved Shorts' captions and headings, then resume the original
publishing workflow” runs a local-model review and rebuilds only changed
Shorts. A repair command without an explicit continuation remains a local edit.
Each repair records its model decisions and proposed corrections beside the
editable Shorts project.

## Persistence and recovery

- Each new edit-and-publish request gets a saved workflow record in its chat.
- Preparation identifies its batch from the actual exports and destinations.
  Each completed description is checkpointed; retries reuse that batch.
- After approval, transient failures receive up to three automatic recovery
  attempts (30, 120, 300 seconds). Restart recovery uses finished outputs and
  recorded upload IDs. A pending retry can be paused in the chat.
- A prepared, authorized workflow waits for Chrome to reconnect and continues
  without another prompt. It retains the requested dates; expired dates still
  need a new schedule.
- An uncertain upload/Share outcome is not repeated. Login/account problems,
  expired dates, missing files and invalid content need attention.
- A schedule failure for one video does not skip the other reviewed videos,
  provided no live browser action still owns the executor.
- A plain scheduling resume keeps the exact selected subset.
- Already armed Instagram slots remain independent of a YouTube retry.
- Legacy tasks are not automatically executed by installing this update.

The queue survives closing the app. Posting at the due time still requires the
laptop awake, Storylens running, Chrome connected, Internet and a signed-in
Instagram account. A missed slot more than 15 minutes late pauses; it does not
dump several late posts at once. A queued slot is not a published Reel.

Recovery does not automatically restart a renderer with an unknown outcome.
The completed Shorts handoff and publishing boundaries have durable recovery;
login challenges and changes to platform controls can still require attention.

## Verification

`tests/test_pipeline_end_to_end.py` exercises the real chat, stores and pipeline
with simulated model, media and platform boundaries: one request, seven clips,
a copy-generation timeout, recovery, seven YouTube receipts and seven separate
Instagram release days with queue restarts.

Other regression tests cover changed dates, selected subsets, partial scheduling
failure, uncertain submission, account binding and Windows file locks.
`validation/check_pipeline_planner.py` requests plans from the installed local
model only; it cannot create edits or publish.

Fixture success is not a claim that a new live publishing run has completed.
