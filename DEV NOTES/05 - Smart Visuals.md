# 05 – Smart Visuals (real people, logos, places, facts from the internet)

**Status:** ✅ v2 built: the agent searches the WHOLE web · ⏳ First real run on the laptop (the cloud session has no internet access to image sites, YouTube or Wikipedia)   **Date:** 26 Sep 2026

## v3 – the Evaluator (after "check if it is really a Zomato PNG / really Meenakshi temple, not a dog")
Every picture and video is LOOKED AT before it goes on your timeline. The evaluator ignores titles and web
addresses (they can lie) and judges the pixels. Brain: Ollama **qwen2.5vl:7b** (vision model, already on the
laptop). It first writes what it really sees, then answers the rules. The PASS/FAIL decision is made by fixed
rules in code (`hinglish_visuals/evaluator.py`), not by the model's mood:

| Rule | Fails when | Example |
|---|---|---|
| 1. TYPE | it doesn't show the kind of thing that was said | you said temple → it is a dog, a person, a text page, a cartoon |
| 2. IDENTITY | it is a different one | a random temple instead of Meenakshi Amman; a logo that reads "SWIGGY" when you said Zomato (the letters in a logo must spell the brand) |
| 3. QUALITY | it isn't a clear real picture | big watermark, collage, website/search screenshot, meme text, blurry or tiny |
| 4. MOMENT | it doesn't fit the line | only a warning: lowers the score |

- **Videos:** 3 frames from the exact seconds that will be used are judged together.
- **Failed file:** thrown out; the next best file is checked (up to 5). If all fail, no visual (your face stays), never a wrong one.
- **Planner:** now also states the *category* per moment ("temple", "man", "logo", "train"), which rule 1 checks.
- **Without the vision model:** CLIP still checks rule 1 (is it more "temple" than dog / person / text / map / cartoon…).
- **Where you see it:**
  - `report.html`: every visual has a green **Evaluator PASS** box with what it saw, and the thrown-out files with the reason (✗ Rejected … : TYPE: not temple; it shows a dog).
  - `EVALUATION.json` in every result folder.
- **Re-check a finished result** (from the rendered files):
  `.venv\Scripts\python.exe -m hinglish_visuals.evaluator --project "output\visuals\<date>\001-<video>\visuals-project.json"`
  → PASS/FAIL per visual; exit code 2 if anything fails.
- App option: **Evaluator** (on). CLI: `--evaluator auto|vlm|clip|off`.
- **Needs:** the Ollama app running; `ollama pull qwen2.5vl:7b` (already done on the laptop). On the CPU laptop each check takes some time (roughly half a minute to a minute, not measured yet); on the RTX 5070 Ti, seconds.
- **Honest limit:** a vision model can still be wrong, especially on WHO a person is (it may say "unsure"; then the web proof decides). Brands are checked by reading the letters, places by their known look.

## v2 – whole-web agent (after "I want real images from any website, not just Wikipedia")
- **Images from any website**, the way you would search:
  - "Zomato logo png" (transparent images first), "Mahatma Gandhi photo", "Meenakshi Amman Temple"
  - web image search (DuckDuckGo / Bing / Yahoo through the `ddgs` package, no key), then download of the real full-size file
  - watermarked stock previews (Shutterstock, Getty, Alamy…) are skipped
- **Videos from YouTube and 1000+ sites**:
  - web video search + YouTube search, e.g. "Meenakshi Amman Temple Madurai drone", "Gandhi Salt March real footage"
  - downloaded with `yt-dlp`, video only, up to 1080p; for long videos only a ~50 s part is downloaded, then the best seconds are picked
  - `imageio-ffmpeg` brings its own ffmpeg, so nothing extra to install
- Wikipedia / Commons / Pexels / Pixabay are still searched too; every result competes. The same rules apply to every file:
  - its title or web address must name the person/brand/place (proof check)
  - CLIP ranks how well it matches the moment
  - the AI makes the final pick
- App option: **Search the whole web** (on by default). CLI: `--no-web` to switch it off.
- **Copyright:** web images and YouTube clips can be copyrighted and can get a Content ID claim. CREDITS.txt lists every source link: check before posting.
- **Install once on the laptop:** `.venv\Scripts\python.exe -m pip install ddgs yt-dlp imageio-ffmpeg`
  (or run Setup CPU.bat again). If YouTube downloads stop working one day, update yt-dlp with `.venv\Scripts\python.exe -m pip install -U yt-dlp`.

**About the first cloud test images:** the brown boxes and the "TEST TEMPLE PHOTO" in the first preview were placeholders drawn by me, because the cloud computer cannot reach the internet. They are not what the feature downloads. That frame sheet has been deleted.

## What it does
Click **Smart Visuals**. A local AI "agent" reads everything you say, like a researcher, and puts the REAL thing on screen:
- **Famous person** (Gandhi, Virat Kohli): their face pops up in a card with their name when you say the name. When you tell a story about them, real archival footage or photos of them go full screen.
- **App / brand / tool** (Zomato, Swiggy, ChatGPT, Premiere Pro): the real logo (PNG) pops up exactly on the word.
- **Place** (Madurai, Meenakshi temple, Taj Mahal): real footage or photo of that place, full screen.
- **Event / fact** (Salt March, 1983 World Cup): real footage or photo of that event.

Different from B-roll: B-roll finds *generic* footage for an idea ("worried man counting money"). Smart Visuals shows *the actual* person, brand, place or event. Both can be used on the same timeline; Smart Visuals skips lines already covered by B-roll.

## How the agent thinks
1. **Reads with memory.** Goes through the speech part by part (local AI). It keeps a running "story so far" and the list of people and brands already found. So in a Gandhi story, "unhone namak kanoon toda" (no name said) is still Gandhi → Salt March.
2. **Fixes speech-recognition spelling:** "Jomato" → Zomato, "Swigi" → Swiggy.
3. **Finds the exact item on Wikidata** ("Gandhi" in a freedom story = Mahatma Gandhi, not Indira Gandhi). If it cannot tell which person or brand you mean, it shows nothing (a wrong person is worse than none).
4. **Searches the internet** (no account or key needed):
   - Wikidata: the item's own logo, portrait, video and map
   - Wikipedia: the article's lead image
   - Wikimedia Commons: millions of free photos and archival videos (small 720p copies are downloaded)
   - Pexels / Pixabay (your B-roll keys): places and things only; stock sites don't have real people or brands
   - a company's own website icon (last resort for logos)
5. **Proof check:** every file must be linked from the item itself, or name it in its title, description or categories.
   - "Indira Gandhi" or "Gandhi Nagar station" never pass for Mahatma Gandhi. A bare surname is not proof.
   - Stock clips must be about the place themselves; our own search words don't count.
6. **Visual match** (CLIP, local) ranks the files against what the moment needs.
7. **Final check:** the AI looks at the top files (title, description, categories) and picks the one that shows *this* moment, or rejects them all.

**Which AI:** Auto = Ollama `qwen3:8b` with thinking when the Ollama app is running (knows far more people and brands). Otherwise the built-in Qwen that B-roll and Smart Zoom already use. You can pick either in the app.

## Timing and look
- **Full screen:** plays exactly while its line is spoken (B-roll rules). The first 2 s hook stays on your face.
  - Photos get a slow push-in.
  - Photos and old 4:3 footage that don't fit 9:16 are shown whole over a blurred copy, instead of being cut to a sliver.
  - Muted; your voice continues.
- **Pop-up:**
  - Lands on the word that names the person or brand, holds about 2 s, with a small pop in and fade out.
  - A face card ends just before that person's full-screen footage.
  - The same logo won't pop up again within 45 s.
- **Pop-ups never cover your face.** The face is found during each pop-up (Smart Zoom's detector) and the card takes the first free spot:
  - top centre → top corners → the same spots with a smaller card → the side at mid-height
  - always above the caption area
- Everything is rendered to clips, not keyframes, so Premiere and Resolve show the same thing.

## Output (`output\visuals\<date>\<video>\`)
- `VISUALS_SEQUENCE.xml` (new sequence `<name>_VISUALS`):
  - V1 your edit, untouched
  - V2 full-screen visuals
  - V3 pop-ups (transparent .mov, like the caption layer)
  - captions stay on top
- `preview.mp4` (timelines up to 5 min), `report.html` (swap any visual for an alternative or remove it → **Save & rebuild**)
- **`CREDITS.txt`**: author + licence of every file. **Paste it into the video description.**
  - Commons CC BY / CC BY-SA files need this credit.
  - Logos are trademarks, shown to identify the brand.

Works on any XML from the other features. Smart Zoom still zooms under pop-ups (they don't hide the face). Eye Contact skips the downloaded visuals.

## Where to click
- **App:** Run Hinglish Editor.bat → **Smart Visuals** → choose a video or a timeline XML
  - Options: How many visuals (Low/Medium/High), AI brain (Auto/Ollama/Built-in), Pop-up logo/face (on/off)
- **Premiere Pro (CEP 2024 + UXP):** open the sequence → Hinglish Editor panel → **Smart Visuals** → the new sequence is imported.
- **DaVinci Resolve Studio:** Workspace → Scripts → Hinglish Editor → **Smart Visuals** (keep "Use the timeline open in DaVinci Resolve" ticked) → **Import to Resolve**.
- Command line: `.venv\Scripts\python.exe -m hinglish_visuals --input <video or xml> [--density high] [--brain ollama] [--no-popups]`

## Files (new package `hinglish_visuals\`)
| File | Job |
|---|---|
| `brain.py` | Ollama qwen3 (thinking) or the built-in Qwen, JSON answers, cached |
| `planner.py` | the agent's steps: plan with story memory, pick the Wikidata item, judge candidates |
| `web.py` | Wikidata / Wikipedia / Commons clients (cached; transcoded videos; licences) |
| `evaluator.py` | the Evaluator: vision model looks at every picture/video, fixed PASS/FAIL rules, CLIP fallback, re-check command |
| `websearch.py` | the web agent: image search on the whole web, web + YouTube video search, browser-like image download, yt-dlp section download |
| `gather.py` | collects media per moment, proof check, ranking |
| `timing.py` | full-screen = spoken line; pop-up = on the name word, no repeats, before footage |
| `layout.py` | finds the face and a free spot for the card |
| `render.py` | photo push-in, 4:3 over blur, alpha pop-up cards (logo / face + name) |
| `report.py` | review page (Save & rebuild) + CREDITS.txt |
| `pipeline.py` / `__main__.py` / `settings.py` | runs everything; optional `config.visuals.local.json` (git-ignored) |

Other changes:
- `hinglish_broll/xml_export.py`: the track writer is shared (B-roll output unchanged)
- `hinglish_zoom`: pop-ups no longer block zooms
- `hinglish_eyecontact`: skips visuals media
- App server: `visuals` mode + `/api/visuals/rebuild`
- App UI, Premiere CEP + UXP panels: Smart Visuals button
- `requirements.txt`: `requests` + `regex` listed explicitly
- `pyproject.toml`: all packages included

## Test log (26 Sep, cloud: Linux, no GPU, no models, no internet to Wikimedia)
| Test | Result |
|---|---|
| Automated tests | 25 Smart Visuals tests (incl. the web agent, the Evaluator rules, and an end-to-end run where a wrong logo is thrown out) + 1 server test. All pass except 4 caption tests that need Windows fonts (missing in the cloud) |
| Timing/render check on `input\final-demo\madurai_1.mp4` (1080×1920, 48.7 s). Transcript, AI answers and images were PLACEHOLDERS (no internet in the cloud); only timing, layout and XML were checked | 4/4 visuals placed in 136 s on CPU: Meenakshi temple photo full screen 4.1–7.6 s; Zomato logo pop-up on "Jomato" 10.7 s; Gandhi face card on "Gandhi" 17.4 s, ending before his footage; Gandhi 4:3 footage full screen 20.2–24.2 s |
| Measured | Every clip file has exactly its timeline frame count (106/120 frames H.264, 66/77 frames alpha qtrle). V1 + both audio tracks untouched. Preview 1460/1460 frames |
| Fixed during testing | Face card was dropped when footage followed → now shortened. Pop-ups covered the head in a wide shot → face-aware spots. Pexels echoes the query as the title → it no longer counts as proof. A brand article's photo was taken as the logo → only files named as logos. Tiny website icons → rejected |

## First real test on the laptop
1. Keep the Ollama app running (optional but better): `ollama pull qwen3:8b` is already done.
2. Run Hinglish Editor.bat → **Smart Visuals** → pick a video where you name a famous person and an app.
3. Check in `report.html`:
   - right person and brand?
   - logo pops on the word?
   - footage about the right story?
   - `CREDITS.txt` filled?
4. Import `VISUALS_SEQUENCE.xml` in Premiere, and in Resolve.
   - V2 and V3 should line up with your words.
   - The pop-up .mov must be transparent.

If Wikimedia refuses downloads (HTTP 403), tell me: the fix is the identification line (`USER_AGENT` in `web.py`).

## Known limits / next ideas
- Web search results change and sites sometimes refuse downloads; the next best file is tried (up to 5).
- Brand logos that exist only on English Wikipedia are "non-free" (fair use). They are allowed for logo pop-ups and marked in CREDITS.txt. Your channel, your call.
- Next ideas:
  - background removal (cut-out person PNG instead of a card)
  - a bigger local model on the RTX 5070 Ti for better story reading
