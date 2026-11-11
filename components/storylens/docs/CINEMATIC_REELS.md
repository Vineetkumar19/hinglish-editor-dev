# Cinematic Reels — music, performance shots, then effects

This is a separate travel / performance / action workflow. It does not use the
documentary style database, reference footage, voice-led scene timing or web
asset fetching. Your music and your chosen performance clips are the inputs.

## The three steps

1. **Music & rhythm.** Choose a local song, optionally set its in/out range, and
   detect beat points. Light / Medium / Strong control how many attacks are kept.
   The output sequence starts at zero with the selected music excerpt.
2. **Performance shots → assembled reel.** Add your source clips or a local
   folder. The editor groups beat points into usable shot lengths, compares
   sections of each clip, assigns a section to each interval, and renders the
   clean assembly. For a three-second interval, it searches for a suitable
   three-second section of a longer clip instead of always taking its start.
   Appropriate supported retiming can change the amount of source time used.
3. **Your effects, on the beats.** Review the clean reel, select effects, then
   click Apply separately. This renders another version from the clean assembly.
   It never overwrites the clean version and never stacks a previous effects
   pass into the next one.

## Timing and source selection

- Internal visual cuts are selected **detected beat points**. Dense drum hits
  are grouped according to Cinematic / Balanced / Action pace, clip availability
  and maximum shot length. Opening and closing are music-range endpoints.
- Every output shot has an exact integer number of video frames. Fractional
  timeline rates are supported by the renderer and XML writer.
- The soundtrack plays continuously. By default its XML clips are split at the
  visual cut points, retaining contiguous source in/out ranges and both stereo
  channels. No notes are discarded or rearranged. Uncheck Split music for one
  continuous audio item per channel.
- Shot quality uses measured exposure, usable brightness range, sharpness,
  contrast and movement, sampled every quarter second. The score also considers
  movement relative to the music interval and the location of motion peaks.
- This is **local computer vision**, not a claim that a language model understands
  the story, the meaning of an action, or your personal favourite performance.
  The result lists each chosen source range and speed so you can review it.
- Native-rate playback is preferred unless a different speed scores better or
  is needed to fit. Slow-motion candidates require sufficient source FPS: a
  60 fps source can play at 0.5× on a 30 fps output; a 30 fps source is not silently
  slowed to 0.5×. Speed-up candidates extend to 2×. This is constant-speed
  retiming, not optical-flow interpolation or an animated speed ramp.
- Sources are used once by default. Reuse is optional and only takes different,
  non-overlapping portions. If footage cannot cover the selected music under
  these rules, the job fails with an explanation instead of silently looping,
  freezing long sections or truncating the soundtrack.
- Longer intervals reserve suitable footage before short intervals. This helps
  avoid spending the only long clip on an easy short interval.

## Controls

| Control | Purpose |
| --- | --- |
| Music in/out | Select the excerpt; up to ten minutes per assembly |
| Beat density | More or fewer detected attack points; not a volume adjustment |
| Pace | Cinematic: at least about 1.8 s between cuts; Balanced: 1 s; Action: 0.5 s |
| Maximum shots | Cap the number of placed video shots; default is available clips |
| Maximum shot length | Default 6 s; raise for longer takes |
| Slow motion / speed-up | Permit supported retiming or require native speed |
| Reuse | Permit different unused portions of a source file |
| Framing | Fit preserves the whole image with bars; Fill performs a centre crop |
| Aspect ratio | Vertical 9:16, landscape 16:9, or square |
| Resolution | 720 for faster previews, 1080 for full quality |
| Effects | Punch zoom, Soft flash, Micro shake; select one or combine them |
| Effect strength | 1–20; default 8 |

Source audio from the performance shots is muted in this workflow. The selected
music is the soundtrack. Dialogue/ambience mixing remains a separate editor task.

Unusable or accidental very short files are skipped and listed in the reel's
warnings. Missing paths and unsupported file types are rejected. Completed reels
can be reopened with **Open latest completed reel** after restarting the editor.

## Outputs and editor integration

Each run writes a new folder under `output/cinematic-reels/<job-id>/`:

- `CINEMATIC_REEL.mp4`: the rendered reel with music.
- `CINEMATIC_REEL.xml`: a portable Final Cut Pro 7 XML sequence for Premiere and
  Resolve, with beat markers, editable video cuts and a separate soundtrack.
- `shot-001.mp4`, etc.: selected, normalized shot copies.
- `soundtrack.wav`: the selected music excerpt at 48 kHz stereo.
- `reel-plan.json`: original source ranges, selection scores, speeds, frame
  intervals, output choices, and effects.
- `completed-reel.json`: saved completion record for reopening the reel after
  restarting the local editor.
- `ffmpeg.log`: render diagnostics.

Retiming, framing and effects are **baked into the generated shot copies**. They
are not arbitrary native effect-pack controls or native speed-ramp curves. The
original videos remain untouched and the plan retains their ranges. Reassemble
to change selection/retiming; the imported sequence can still be trimmed and
rearranged within the generated media's available duration.

The Premiere CEP/UXP panels and the Resolve Studio window provide **Open Cinematic
Reels** and **Import latest cinematic reel**. The latter imports the latest
completed assembly/effects version as a new sequence, after a saved project
checkpoint. Desktop also offers Import new timeline to Resolve. Restart the local
bridge and reload updated host panels before using the new API. UXP asks for
permission when opening the local workspace in a browser, as required by Adobe.

External preset/effect packs have not been imported or learned. The built-in
effects are available without a pack. Proprietary pack integration will need the
actual files, supported host adapters and any required installed plugins.

## Resource and privacy behaviour

The workflow uses the CPU with bounded FFmpeg threads, one reel job at a time,
sharing the existing editing queue. No cloud model, GPU model, web footage or
publishing worker is invoked. Browser-selected files are copied to local output
storage; a supplied folder is read directly. Cancel stops a queued/running reel
and its current render process. Original files are never edited in place.

Limits: 100 performance clips, ten minutes per clip, one hour of source footage,
ten minutes of selected music, and 200 placed shots. These are resource guardrails,
not a promise of a particular render speed. Actual timing depends on footage,
resolution, effects and laptop hardware. Busy/syncopated music and subjective
shot quality still need viewing and listening review.

## Validation

Tests use actual generated MP4 footage with deliberately poor opening seconds
and better later sections, plus a synthesized soundtrack. They check that the
later usable sections win, slow motion respects FPS, cuts cover the exact music
duration without gaps, stereo source ranges stay contiguous, effect passes keep
the clean assembly intact, originals stay byte-for-byte unchanged, authentication
is required, range playback works and cancellation terminates jobs.

These generated fixtures prove the plumbing and measured selection behaviour.
They are not an aesthetic review of your travel/action footage. Native import,
saved-project readback and visual acceptance in the installed Premiere/Resolve
versions remain separate checks.
