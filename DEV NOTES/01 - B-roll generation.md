# 01 – B-roll generation (one click)

**Status:** ✅ Built and tested with your own footage library · ⏳ Stock footage waits on your API keys · ⏳ Needs a real Premiere/Resolve test   **Started:** 26 Sep 2026
**Inspired by:** FireCut "Find B-roll". FireCut uses paid Storyblocks footage. Ours uses **your own footage library + free Pexels/Pixabay stock**.

## What it does
Click **Add B-roll**. The app reads what you are saying (Hindi, English or Hinglish), decides where B-roll helps and what it should show, finds the best clip and places it on your timeline.
You get a **new sequence**: your timeline plus B-roll on a new video track (V2). Your original timeline is never changed.

## How it works (the pipeline)
1. **Timeline in:**
   - Premiere: exports the open sequence as XML.
   - Resolve Studio: exports the current timeline.
   - Standalone app: a video file, or an XML from Smart Clean / Script Edit.
2. **Transcript:** reuses your existing Hinglish transcripts from the cache, then maps each word to its time on the timeline.
3. **Understanding** (local Qwen AI, runs on this computer):
   - Pass A: summary of the whole video (topic, places, people, mood).
   - Pass B: goes through the speech phrase by phrase. It picks B-roll moments and writes what to show, plus 3 English search phrases for each.
4. **Placement rules:** Reel vs YouTube timing, density (Low/Medium/High), and no B-roll over the opening hook.
5. **Finding clips:** your own footage library first, then Pexels and Pixabay. A visual AI (CLIP) scores every candidate against what is being said. It keeps the best clip plus alternatives and never repeats a clip.
6. **Preparing clips:** cuts the best part of each clip, crops it to fill 9:16 or 16:9, matches the frame rate and mutes it. Uses the NVIDIA encoder when an RTX card is present.
7. **Output:** `BROLL_SEQUENCE.xml` (imports automatically), `report.html` review page (swap or remove clips, then Save & rebuild), and the prepared clips in `media\`.

## Default amount of B-roll
| | Instagram Reel | YouTube long form |
|---|---|---|
| How often | every ~4–6 s | every ~20–40 s |
| Clip length | 1.5–3 s | 3–6 s |
| Screen covered | ~40 % | ~20 % |
| Protected opening | first 2 s | first 5 s |

## One-time setup
- Paste your **Pexels** and **Pixabay** API keys into **Settings → B-roll**.
- Add your footage folders under **Settings → My footage library**. They are indexed once, and the index is reused after that.

## Files (new package `hinglish_broll\`)
| File | Job |
|---|---|
| `settings.py` | density rules, API keys and library folders (stored locally, never uploaded) |
| `timeline.py` | reads the Premiere/Resolve XML and maps speech to timeline time |
| `phrases.py` | splits speech into short phrases |
| `llm.py` / `planner.py` | local Qwen: summary + B-roll moments |
| `placement.py` | timing rules (density, gaps, hook protection) |
| `stock.py` | Pexels + Pixabay search and download (cached) |
| `vision.py` / `library.py` | CLIP visual matching and the index of your own footage |
| `ranker.py` | picks the best clip per moment, no repeats |
| `conform.py` | cuts, crops and encodes the B-roll clips |
| `xml_export.py` | adds the B-roll track to the sequence |
| `project.py` / `report.py` | review page and Save & rebuild |
| `pipeline.py` / `__main__.py` | runs everything |

## Later upgrade (when the RTX 5070 Ti arrives)
- A bigger CLIP model (ViT-L/14) for better visual matching.
- A vision-language model that "watches" each candidate clip before it is picked.
- Optional local AI video generation for moments where no stock or library clip fits.

## How to try it in Premiere / Resolve (DEV copy)
Run `Install Editor Plugins.bat` **from this DEV folder**. Premiere and Resolve then use the DEV copy, which has the new **Add B-roll** button.
To switch back to your original, run `Install Editor Plugins.bat` from `E:\remove silence`.

## Test log (26 Sep 2026, current laptop: Ryzen 5 4600H, GTX 1650, CPU mode)
| Test | Result |
|---|---|
| Automated tests | **146 / 146 pass** (116 original + 30 new B-roll tests) |
| Local AI understanding (sample Madurai Hinglish text) | Topic, places and foods found correctly. "paise bachana mushkil" became "young man counting rupee notes, worried". About 75 s on CPU. |
| Single Reel clip (22.8 s) | 2 moments. Clips from the footage library chosen. Output is 1080×1920, 30 fps, muted, exact frame counts. |
| Multi-clip edited sequence (6 clips, 46 s) | V1 untouched (6 clips), B-roll on V2, audio intact. Moments picked: "PG le liya", "basic chizen", the "…nahin, …nahin, AC" list, "table itna chhota… laptop". |
| Save & rebuild (review page → app server) | Swapping one clip and removing another took 3.9 s. XML rewritten correctly. |
| App UI | Add B-roll mode, density selector and B-roll settings (keys + footage folders) all work. |

### Fixed during testing
- The AI invented a price ("500 extra"). The prompt now forbids made-up numbers, text and signs.
- The AI skipped named landmarks. The prompt now always prioritises places, foods and objects.
- Filler phrases ("Haan ji") got B-roll. Fillers are now skipped, and short fragments are merged with a neighbour.
- Early weak moments blocked better ones. Placement now picks the best-scoring combination (optimal DP).
- Clips were always the 1.5 s minimum. Ideal length is now 2.2 s (Reels) and 4.5 s (YouTube).
- The same library file was used twice. A different file is now preferred when nearly as good.
- CLIP model files and thumbnail names for library paths were fixed.

### Known limits / next ideas
- **Speech-recognition mistakes.** "pushing machine" (washing machine) was not corrected by the small 4B model. On the RTX 5070 Ti a bigger model (Qwen3-14B) should fix most of these.
- **Talking-head takes in the library.** Clips of you talking to camera in a footage folder can be picked as B-roll. Keep talking-head takes out of the library folders, or we can add face/speech detection later.
- **Long list phrases.** A list like "no fan, no washing machine, no fridge, no AC" gets one cutaway. Several quick cuts (one per item) would be better.
- **Stock footage** (Pexels + Pixabay) is covered by automated tests but not yet run live. It needs your keys in Settings.
