# Feature log

## Already built (before this copy)

1. Silence removal: Smart Clean / Phase 1
2. Script-based semantic arrangement: Script Edit / Phase 2
3. Filler word removal
4. Retake removal (keeps the latest complete take)
5. Auto Captions: Roman Hinglish, 15 animated styles, Caption Studio
6. Standalone app plus Premiere Pro 2024 / DaVinci Resolve plugins

## New features (DEV copy)

| # | Feature | Status | Note |
|---|---|---|---|
| 00 | Baseline copy created, 116/116 tests pass | ✅ Done | [00 - START HERE](00%20-%20START%20HERE.md) |
| 01 | One-click B-roll (local AI + your footage + Pexels/Pixabay), Premiere/Resolve/app | ✅ Built · ⏳ live stock + editor test | [01 - B-roll generation](01%20-%20B-roll%20generation.md) |
| 02 | Smart Zoom: AI key moments, stressed word, face-aware smooth/punch/impact/reveal/push zooms, jump-cut framing | ✅ Built · ⏳ editor import test | [02 - Smart Zoom](02%20-%20Smart%20Zoom.md) |
| 03 | Fixes from the first real run (madurai_1) — see below | ✅ Done, 169/169 tests | this file |
| 07 | Sound Design: AI music mood + sound effects on exact words, B-roll whooshes, ducked mix, own audio tracks. v4: CLAP listens to every file, a trigger + evidence for every sound, tone rules, fewer sounds, evaluator + mix check, learns your taste (Save & remix) | ✅ v4 built · ⏳ your listening test | [03 - Sound Design](03%20-%20Sound%20Design.md) |
| 08 | Eye Contact: NVIDIA Maxine redraws your eyes into the lens while you read; RTX only; app + Premiere + Resolve | ✅ Built, pipeline tested here (simulated) · ⏳ RTX 5070 Ti setup + real test | [04 - Eye Contact](04%20-%20Eye%20Contact.md) |
| 09 | Smart Visuals: AI agent with story memory finds the REAL person / brand logo / place / event you talk about. v2 searches the whole web (image search on any site, YouTube + 1000 video sites via yt-dlp) plus Wikipedia/Commons/Pexels/Pixabay, proves each file is about it, v3 Evaluator (qwen2.5vl looks at every picture/video: TYPE, IDENTITY, QUALITY rules, fails wrong ones), pop-ups on the name word + full-screen footage; app + Premiere + Resolve | ✅ v2 built · ⏳ first real laptop run (cloud has no internet) | [05 - Smart Visuals](05%20-%20Smart%20Visuals.md) |

### 03 – Fixes from the first real run (26 Sep)
- **"Failed to fetch"**: the DEV app now uses port **8766**, so it can't clash with the original app on 8765 (the old Premiere plugin keeps restarting that one). The page also reconnects for about 60 s and shows plain instructions.
- **Captions crash** ("list index out of range"): Typography 1 crashed on one-word captions. It now uses the boxed-keyword layout for them. A regression test was added.
- **Bad API key** no longer stops B-roll: that site is skipped and the others are used. Output text is now UTF-8-safe.
- **B-roll quality**:
  - Wide Pixabay clips are allowed and centre-cropped for 9:16.
  - A specificity check makes a clip fit *this* moment rather than just "a young man".
  - Brand names are banned from search terms.
  - Library clips that are **raw takes of the same video** are skipped automatically.
- **Zoom preview** now also shows the B-roll track (the real finished look).
- Final demo video: `output\final\madurai_1_FINAL.mp4` (Smart Clean → Captions → B-roll → Smart Zoom).

### 04 – More B-roll, smoother zooms (26 Sep, after your feedback)
- **B-roll went from 2 clips to 7 of 8 moments** on madurai_1 (Pixabay only; Pexels key still rejected).
  - All 3 search phrases are now searched, with 12 results each.
  - The "too generic" check now only rejects talking-head-like shots, not real street/food/phone B-roll.
  - Library clips with ≥ 30 % look-alike frames are skipped as raw takes of the same video.
- **Smoother zooms:**
  - **Smooth** is the default style (every zoom eases in and out; punch is still available).
  - Ramps are ~0.8 s in / ~0.7 s out.
  - The value rounding is 100× finer, so frames never freeze at the start or end of an ease.
  - The preview uses an antialiased resize (no texture shimmer).
  - Verified: 100 → 115 % over 25 frames, 0 frozen frames.
- Test video: `output\final\madurai_1_BROLL_ZOOM.mp4` (B-roll + Smart Zoom only). 169/169 tests pass.

### 05 – Zoom redone the editor way, B-roll context fixed (26 Sep, after "pathetic" feedback)
- **Root cause of the bad zooms:** the face was measured **once for the whole video**, but madurai_1 has 7 shots with the face in very different places. The zooms went to empty areas.
- **New zoom rules**, following common talking-head editing practice:
  - The face is found **during each zoom**; no clear, steady face means no zoom.
  - Shot changes inside the file are detected, and a zoom never crosses one.
  - Zooms go into the face and pull it toward the centre.
  - Used sparingly (about 1 per 6.5 s max on Reels), gentle 112 %, smooth ease in and out.
  - "Hide jump cuts" is now off by default.
- **Root cause of the wrong B-roll:**
  - Pixabay returned foreign footage (Colombia, New York, Seoul, a China map) and it was accepted.
  - The small AI sometimes attached an idea to the neighbouring line.
- **B-roll fixes:**
  - The AI states the video's country, and searches add it.
  - Clips tagged with another country are rejected.
  - A stricter match score.
  - The AI must quote words from the exact line; the quote, not the line number, decides placement.
  - Maps are suggested when a place is introduced.
- Result: B-roll now follows the words ("school geography" → India map, "Rapido" → taxi traffic, "night" → Indian night street). 178/178 tests pass.
- **Pexels:** still 401 (key rejected). The key must be pasted with the copy button, not read from a screenshot.

### 06 – Zoom sections + line-exact B-roll timing (26 Sep, after the second round of feedback)
- **Zoom = sections, not pulses.**
  - The video stays WIDE by default.
  - The local AI marks each important point: where it starts, the stressed word, where it ends, and a written reason.
  - The zoom eases in on the word, **stays in for the whole point** (2–8 s Reels / 3–15 s YouTube), then eases back to wide, with at least 2 s of wide framing between sections.
  - A section that crosses a shot change continues zoomed in the next shot, re-centred on the face there (two-camera style).
  - This follows the punch-in guidance (PremiumBeat, Jupitrr).
- **"Thinking" step:** before choosing, the planners must write their reasoning:
  - B-roll: the English meaning of the exact line.
  - Zoom: why the point matters.
  - The whole-video summary is given as context (the AI's "memory").
- **B-roll timing = the spoken line.** Each clip starts with its line and ends when the line ends (1–4 s), never running into the next line. A very short line may extend into silence only.
- A zoom word that isn't in the named line is only looked for in the 2 neighbouring lines (never borrowed from far away).
- Editing templates (green screen, chroma key, mock-ups, overlays) are never used as B-roll.
- madurai_1 v4: 5 B-roll clips timed to their lines, 3 zoom sections. 182/182 tests pass.
