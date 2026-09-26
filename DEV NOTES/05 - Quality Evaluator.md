# 05 – Quality Evaluator (rules for every feature, auto-redo)

**Status:** ✅ Built and running for every feature, in the app and the plugins.   **Date:** 27 Sep 2026

## What it does (3 layers)
1. **Model guard: the AI must follow its rules.**
   - Every AI answer is checked the moment it arrives: B-roll summary and moments, zoom sections, sound story/moments, sound file choices.
   - If it breaks a hard rule, the model is asked again, with its previous answer and the exact list of problems. It gets up to 3 tries, and the best try is kept.
   - If the model still can't fix it, the rules repair the answer themselves by dropping or trimming the bad items. They never invent anything.
   - Everything is recorded in `model-checks.json`.
2. **Output spec: the finished result must meet the feature's spec.**
   - Measured from the real files: timeline XML, audio stems, video, captions, plan files.
   - Hard rules = FAIL, advice = NOTE. Score 0–100 (hard rules count 3x).
3. **Auto-redo.**
   - If a hard rule fails and a correction exists, the feature runs again with the corrections, and the AI is told what went wrong.
   - Up to 3 attempts; the best one wins. Engine crashes are never looped.
   - The report `quality-check.html` sits next to the result. The app shows e.g. "Quality check passed · 96/100 · redone 1x" plus a **Quality report** button.

## How it runs
- App and plugins: automatic. The server runs every job as `python -m hinglish_eval run --attempts 3 -- -m <feature> …`.
- Check any old result: `python -m hinglish_eval check <result folder>`.
- Corrections reach the features through `HINGLISH_EVAL_TUNE` (a small JSON per attempt). Without it, the features behave exactly as before.

| Correction | Used by | Effect |
|---|---|---|
| `sound.effect_gain_db` | mixer | makes all effects louder by the measured shortfall |
| `sound.music_trim_db` | music bed | brings the music back into the 7–17 dB-under-voice window |
| `sound.count_scale` | sound director | asks for more sound moments |
| `zoom.count_scale` | zoom planner | fewer zooms if too much is zoomed, more if too few |
| `broll.count_scale` | B-roll planner | more (or fewer) B-roll moments |
| `feedback` | the feature's AI | plain-English "last time …" findings added to its prompt |

## The rules (spec per feature)
**AI answers (model guard)**
- **B-roll moments:**
  - the id must exist
  - the quote must be copied from *that* line
  - no brand/app names in search phrases
  - no text, logos or captions in the visual
  - no invented numbers
  - meaning in English
  - no duplicates
- **B-roll summary:**
  - topic and visual world are required
  - places must be spoken; Hindi names count ("Dilli" = Delhi)
- **Zoom sections:**
  - the ids must exist
  - to_id within 3 phrases
  - the stressed word must be really in that phrase, and not a filler word
  - sections never overlap
  - at most 60% zoomed; not far more sections than asked for
- **Sound story:**
  - every line gets an emotion
  - music covers the video with no gaps or overlaps, using library moods; at most 2 sections in a Reel
  - every moment's word is in its line
  - valid effect types; pull-back at most 2
  - enough moments (at least 60% of the target); variety
- **Sound file choices:** every pick must be a real candidate number.

**Outputs**
- **Smart Clean:**
  - no speech cut
  - order kept, cuts inside the video
  - audio and video the same length (within 1 frame)
  - length matches the edit
  - advice: at most 45% removed, no tiny cuts
- **Auto Captions:**
  - captions never overlap
  - inside the video
  - at most 4 words / 28 letters (portrait; 6 / 46 landscape)
  - at most about 3 s on screen, never under 0.2 s
  - words timed inside their caption, no empty captions
  - at least 95% of spoken words captioned; .srt complete
  - advice: at most 22 letters per second
- **B-roll:**
  - enough clips (at least 1 per 12 s in Reels, 1 per 60 s long-form)
  - no more than the profile's coverage
  - clip length = its line (within the profile's min/max)
  - face time between clips; face shown at the start and the end
  - stock clips must meet the match score (0.26)
  - clips long enough and present on disk
  - no brands, filmable visuals, footage from the right country
  - advice: no clip used twice
- **Smart Zoom:**
  - never past the chosen strength
  - at most 50% of the video zoomed
  - no scale jumps (except on a cut)
  - no in-and-out pulses under 1 s
  - eased over at least 0.3 s
  - holds for the whole point (2–8 s in Reels)
  - wide gap between zooms
  - the word is really said there
  - face found in at least 80% of zoomed frames
  - advice: sensible count
- **Sound Design:**
  - every effect audible (phone-weighted loudness within 3 dB of its level)
  - no clicks under 60 ms
  - plenty of sounds (at least 60% of one every 2.5 s)
  - never two speech sounds within 0.8 s
  - hits, whooshes and risers peak on their word or cut (within 50 ms)
  - every B-roll cut has a whoosh
  - music covers the whole video, at most 2 sections in a Reel, 7–17 dB under the voice
  - master at or below −2 dB; pull-back at most 2
  - advice: master loudness about −14, variety, no cartoon sounds in serious stories
- **Eye Contact:**
  - copies exist, same length, same audio tracks, same size
  - NVIDIA fixed every frame
  - the timeline is relinked
  - advice: flags simulated runs
- **Every timeline XML:** valid, positive-length clips, no overlaps on a track, all media files exist.

## What it found and fixed on the first day (madurai_1)
- **Captions:**
  - **Problem:** 14 captions overlapped the next one by up to 80 ms, so two captions showed at once.
  - **Fix:** the hold after the last word now stops where the next caption starts.
- **Sound, hits a frame late:** the library stores a sound's peak rounded down to 50 ms, so hits landed 20–35 ms after the word. The exact peak is now measured when placing the sound.
- **Sound, risers peaked early:** the per-sound limiter flattened risers' climaxes, so their loudest part arrived about 300 ms before the word. Risers, whooshes, tension and vanish sounds are no longer squashed, and hits use a fast 30 ms release.
- **Smart Zoom:**
  - **Problem:** the small Qwen3-4B model returned overlapping sections, fixed only some after two retries, and wrong words on phrases.
  - **Fix:** after the retries, the rules drop the weaker overlapping sections. Result: 100/100.
- My own rule bugs, found by testing on the real results and fixed:
  - wrong constant name
  - country compared with a capital letter
  - the "plenty of sounds" count ignored the whooshes and booms on edits
