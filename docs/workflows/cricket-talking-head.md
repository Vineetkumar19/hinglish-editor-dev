---
name: cricket-talking-head
description: Prefer ChatGPT/OpenAI; local fallback only when the required capability is unavailable. Process the owner's unscripted cricket talking-head video and matched screenshots with Storylens Smart Clean/Edit, reference zooms/photo motion/effects/SFX and important-word-only glowing captions with UI sounds. Show the complete captioned edit PLUS FIVE long-form daily packaging sets (each thumbnail preview, title, description, hashtags), then STOP for owner approval before Premiere speech enhancement, Resolve grading and Vineet_4K NVIDIA export on D:. Upload the long form to cricket YouTube PRIVATE with an English SEO title, description, hashtags and thumbnail. Extract FIVE Shorts using the existing Storylens tool, give each YouTube title/description/hashtags and Instagram caption/hashtags, and schedule one per day on BOTH platforms. Refresh the long-form title, description, hashtags and thumbnail every 24 hours for FIVE days. Use for Cricket Talking Head, not documentaries or gaming.
---

# Cricket Talking Head

Invocation with a video path and evidence assets starts the saved procedure. Make
routine editing and import/export choices autonomously. The sole required creative
approval is the visual-edit checkpoint below; do not ask for permission at each
application handoff. Respect narrower instructions, missing dependencies and
actual tool permissions. Never equate skill instructions with a verified pipeline.

```text
$cricket-talking-head
Video: D:\Cricket\Cricket Talking Head\My Videos\Video 1 | Screenshots: D:\Cricket\Cricket Talking Head\Screenshots\Screenshot 1
```

Read `C:/Users/Vineet Kumar/.codex/references/talking-head-workflow-20261103/REFERENCE-GUIDE.txt`
for current policy (workspace mirror `D:/Workflow_Automation/talking-head-workflow/REFERENCE-GUIDE.txt`).
Use the GPT-led executor rules in `C:/Users/Vineet Kumar/.codex/skills/storylens-workflows/SKILL.md`.
Read only relevant stage guides/source/receipts, not the entire project history.

## Inputs, persistence and disk

- Root `D:/Cricket/Cricket Talking Head`: numbered `My Videos/Video N` pairs with
  `Screenshots/Screenshot N`; resolve supplied exact paths first. References are
  in `Refrence Videos`. Do not guess a different source/account from filename order.
- All exports/projects/previews/intermediates/caption assets/managed caches go
  under `Talking Head Premiere`, `Talking Head DaVinci`, `Talking Head Topaz` in
  this root, each with video/revision subfolders. This overrides the general
  `D:/Topaz Videos` destination for this workflow. Preserve originals/manual edits.
- Save source hashes, raw and edited clocks, transcript/cut map, asset/effect cues,
  native project/preview hashes, exact approval, stage results, output hashes,
  platform/account/remote IDs and daily campaign receipts. Resume matching completed
  stages and remote uploads rather than blindly repeating them. Explicitly cancelled
  work stays cancelled. Cached decisions are not fresh inference or new approval.
- **ChatGPT FIRST.** Use this GPT assistant/OpenAI models for reasoning, planning,
  visual interpretation, creative selection and writing. Local models are permitted
  ONLY as a worst-case fallback when the required ChatGPT capability is genuinely
  unavailable, not for lower cost, speed, convenience or token savings. An absent
  adapter is not a reason to outsource a decision this assistant can make directly.
  Check actual authorized tool availability; use executor-only/GPT-authored plans.
  Record any real cloud-unavailability reason, affected stage and exact local model,
  and disclose fallback to the owner. Never label local/cached output as GPT. Failed
  fallback quality is a failure, not an accepted deliverable. Do not rewire standalone
  model settings, create paid API access or start unrelated workers to save this rule.

## Phase 1 — complete the captioned edit and five packaging sets, then stop

1. **No script required.** Transcribe ALL spontaneous speech. Prefer an available,
   authorized ChatGPT/OpenAI speech route with usable timing; verify actual access,
   do not assume this text chat can decode MP4 audio without a tool. If that cloud
   capability is genuinely unavailable, use installed Whisper large-v3/NVIDIA ONLY
   as the recorded/disclosed worst-case ASR fallback. No silent small-model downgrade.
   GPT checks meaning, names, dates, quantities and audible timing when available;
   any fallback decisions keep their true provenance and all quality checks. Optional
   scripts assist spelling, never manufacture speech. Reuse verified timing/cut maps.
2. **Clean/edit.** Use existing Smart Clean, Smart Edit as needed. Keep the second/
   later COMPLETE retake, meaningful quiet words and unique speech; distinguish
   intentional repetition. Preserve natural pacing rather than forcing10–15minutes.
3. **Build the actual visual/SFX edit.** Read the matching source patterns from
   `C:/Users/Vineet Kumar/.codex/references/cricket-update-style-20261103/REFERENCE-GUIDE.md`
   and `C:/Users/Vineet Kumar/.codex/references/cricket-ipl-style-20261103/REFERENCE-GUIDE.md`.
   The four newer Bhuvi/Hardik/Rohit/CSK studies are indexed at
   `C:/Users/Vineet Kumar/.codex/references/cricket-reference-library-20261103/REFERENCE-GUIDE.md`;
   retrieve the matching per-video patterns and cue map, preserving source identity.
   Preserve source identities, measured zoom/evidence-card/report-panel/label/meme
   patterns and entrance/hold/exit details; exact fonts/native easing remain unresolved.
   Prefer **native editable Premiere Pro zoom-in/out keyframes**, with suitable
   Ease In/Out or Bezier interpolation, stable framing and smooth cut concealment.
   This is the owner's 3 November correction shared with Cricket Documentary.
   Choose Hyperframes OR Remotion only for graphics/motion that benefit; minimize
   avoidable full-video exports using native handoffs, overlays or section renders.
   Do not add an extra baked master just to animate zooms. Preserve this skill's
   complete-captioned-edit approval gate and later enhancement/color/Topaz order.
   Animate supplied photos, highlights, transitions and reframing at the actual
   matching spoken moment. Hide stubborn jump cuts with the asset relevant to the
   NEXT line, from the cut's onset. Vertical screenshots stay readable and undistorted.
   Use the saved preferred real-SFX palette and UE movement/event mapping via the
   Storylens skill; preserve the original song once/stereo and editable source clips.
4. **Important words only — BEFORE owner review.** Highlight supported names, dates, scores, overs, wickets,
   IPL teams and key facts, not every spoken word. Examples: `50 ALL OUT`, `5 OVERS`,
   `7 WICKETS`, `ROHIT SHARMA`. Match text onsets, asset cues and real UI-sound
   transients to final edited speech/word IDs, not the raw clock or delayed guesses.
   Use the existing Storylens feature implemented in
   `D:/Full Drive/remove silence/hinglish_captions/important_words.py`, with the
   authenticated `/important-captions.html` page linked in Auto Captions.
   Its LOCAL `transcribe` command is a fallback-only large-v3 route; first check
   authorized ChatGPT/OpenAI speech capability. The `build` executor also accepts
   compatible source-bound timed transcripts from an authorized cloud route. GPT creates
   a source/transcript-hash-bound selective plan; `build` exports separate glowing
   transparent clips, real UI WAVs, editable cue JSON/SRT and Premiere/Resolve XML.
   Read [references/important-words.txt](references/important-words.txt) at this stage.
   NO After Effects. Check actual available native glow or use this plugin-free
   rendered glow; do not claim editable native glow nodes from a baked overlay.
5. **Prepare FIVE long-form packaging sets.** Show five actual thumbnail design
   previews, numbered Day1–5. EACH set contains its thumbnail, English title, FULL
   publication-ready description and relevant hashtags. These are the five daily
   changes for the SAME long-form video, NOT the five Shorts/Reels. Use actual
   video facts and saved SEO/thumbnail procedures; make all five sets reviewable
   together, not placeholders or a promise to create them later.
6. **MANDATORY REVIEW GATE.** Present the complete PLAYABLE edit with all images,
   animations/effects, zooms/transitions, important-word auto captions, general SFX
   AND synchronized UI sounds, plus the FIVE long-form thumbnail/title/description/
   hashtag sets. STOP and wait for explicit owner approval of this exact video
   revision and these packaging sets. Do NOT start Premiere speech enhancement,
   Resolve color correction, Topaz, uploads/schedules or daily refresh activation
   before approval. A plan or still sheet is not the requested edited-video review.
   Bind approval to preview/project/cut-map hashes AND each packaging set's text
   and thumbnail hash. Revise rejected items and present them again. Do not silently
   change approved copy/design during the later rollout. Save owner corrections
   for future videos, without claiming model-weight training.

## Phase 2 — finish autonomously after approval

1. **Premiere speech enhancement and export.** Find the owner's actual enhancement preset from saved
   screenshot/preset inputs and apply once to presenter dialogue, not music.
   Its exact identity remains pending: search before asking once; never invent it.
   Check actual dialogue clarity, sync and stereo output.
2. **Resolve color correction and export.** Read the approved guide/hash-verified DRX at
   `C:/Users/Vineet Kumar/.codex/references/resolve-color-grading-20261101/REFERENCE-GUIDE.txt`.
   Keep the exact native CAM-DWG -> BAL/EXP -> CONTRAST -> SAT -> parallel
   TEMP/HDR/WARPER/CURVES -> mixer -> TRIM -> parallel PW1/PW2/PW3 -> mixer ->
   Texture -> SPARE -> DWG-709 graph. Kodak/Cineon OFF, spare reserved. Grade ONE
   representative shot and copy editable graphs across the consistent setup;
   sample start/middle/end and correct only actual differences. Adapt source CST,
   avoid double transforms and exclude graphics from presenter grading. Verify
   cut/effect/audio-preserving round-trip; do not promise unsupported Dynamic Link.
3. **Topaz 4x finishing export.** Read `D:/Workflow_Automation/Topaz-workflow.md`. Use **Vineet_4K**,
   **NVIDIA** encoder, saved controls/H264/MP4/audio-copy, aspect ratio and version
   rules. This supersedes 2K/undecided choice. Vineet_4K is relative4x, not inherently
   fixed3840×2160: verify/report actual output dimensions. Export under this project's
   `Talking Head Topaz`; no separate Shorts enhancement. Verify actual completed output.

## Private long form, daily public Shorts and five-day refresh

- Prepare the FIVE long-form packaging sets with saved `yt-package`/`yt-seo`
  BEFORE the gate; after approval use those exact approved sets, not newly invented
  replacements. Include >=10 relevant hashtags subject to platform limits. No
  guaranteed virality/score. Verify exact cricket account/source and native saves.
- Upload LONG FORM to cricket YouTube **PRIVATE**, with thumbnail, title,
  description and hashtags. The owner makes it Public after checking. Never
  automatically change its release state while editing packaging. Apply available
  monetisation/mid-roll controls and accurate ad ratings; old MI copyright acceptance
  is not universal permission to ignore future claims/restrictions.
- EXTRACT **FIVE** Shorts using the EXISTING Storylens Long to Shorts tool on the
  finished long form (`hinglish_shorts`; consult `shorts-review.md` in the maintained
  Storylens knowledge directory). No manual/new-generator substitute. Verify real
  self-contained exports, narration sync and9:16 relayout; fixed face crops can
  hide evidence. Report a true shortfall rather than pad/repeat unsuitable moments.
- EACH Short needs its own **YouTube title, description, hashtags** and **Instagram
  caption, hashtags**. English, truthful, excerpt-specific. Instagram prose <=10
  English words unless changed, with hashtags separate. Schedule **ONE per day for
  FIVE days on BOTH cricket YouTube and Instagram** for PUBLIC release. These are
  not permanent Private/draft Shorts. Use owner-selected RANDOM times between
  17:00 and20:00 IST for each day/platform, starting the day AFTER the approved
  final video is ready unless a date is supplied. Persist choices once using
  `scripts/shorts_schedule.py`; retries reuse them. This is a preference, not a
  proven safety advantage over fixed times. Record IST/UTC instants,
  verify remote publishAt/local queue state separately and recover existing IDs.
- For THIS talking-head/news long form, refresh **title, description, hashtags and
  thumbnail every24 HOURS for FIVE days** using the five OWNER-APPROVED long-form
  sets, Day1–5 (first set at upload, then the next four at24h intervals). Stop after
  Day5; never confuse these sets with Shorts metadata or generate replacements silently. This category overrides earlier weekly/
  four-day cadence. Keep facts current/truthful and preserve visibility/manual release.
- After the review gate and actual source/account/remote-ID binding, create/recover
  the finite daily campaign using available scheduling tools. Discover
  `automation_update`; use a source-bound local heartbeat by default for packaging
  updates, quiet while unchanged, actionable failures only, self-stop after five
  sets. Do not write raw automation directives or invent an enabled schedule from
  this skill file. A fresh invocation should arrange the whole five-day work without
  daily re-prompting. Never activate production posts/campaigns during skill editing.

## Verify, learn, report

Routine app handoffs/exports need no extra approval beyond the saved job scope.
Preserve the mandatory visual gate. Ask only for genuine missing inputs/settings,
continue independent work and report precise blockers. No production run or five-day
platform acceptance follows from source/media/unit/UI checks. Report actual output
paths, Private long-form ID, five Shorts' per-platform schedule receipts, daily refresh
state/end and remaining limitations. Maintain source-bound correction examples and
reuse approved knowledge/checkpoints to reduce repeated work and token use.

## Owner-invocable reference skills — twelve-video expansion

For taught editing patterns, load `C:/Users/Vineet Kumar/.codex/skills/cricket-talking-head-editing-style/SKILL.md` (display name **Cricket Talking Head Editing Style**).
For taught thumbnail composition with the owner's portrait, load `C:/Users/Vineet Kumar/.codex/skills/cricket-thumbnail/SKILL.md` (display name **Cricket Thumbnail**).
Current twelve-source coverage and limits are recorded at `C:/Users/Vineet Kumar/.codex/references/cricket-twelve-references-20261103/INDEX.md`; inspect actual per-source coverage rather than assuming installation means every aspect is verified. These extend the earlier six actual source studies. Follow the strict reference-only correction: generic text/effect defaults are not permission to introduce an untaught visual treatment. Existing production order, approval gates and platform authorization are unchanged.
