# Hinglish Editor – New Features (September 2026)

This file explains the four new tools added to the Hinglish Editor, and how to set up, use and check each one.

**Main folder:** `E:\Hinglish Editor DEV`
**Your original app in `E:\remove silence` was not changed.**

| # | Tool | In one line | App button |
|---|------|-------------|-----------|
| 1 | **Long to Shorts** | Your long video becomes finished vertical Shorts/Reels of its best hook moments | 9 |
| 2 | **AI Images** | Your script gets AI-made pictures for the moments that need one, made on your GPU | 10 |
| 3 | **AI Video** | The few moments that need movement get 5-second AI video clips, made on your GPU | 11 |
| 4 | **Motion Graphics** | Your story told with animated scenes built from real people, logos, objects, photos and clips | 12 |

All four tools:
- **run locally.** Your videos and scripts never leave your PC. The only exception is searching the web and stock sites for pictures.
- **appear in the app, in the Premiere Pro panels (CEP and UXP) and in DaVinci Resolve Studio.**
- **never touch your original sequence.** They always create a new, editable XML timeline.
- **run under the Quality Evaluator.** Rules check every AI answer and every result, and a `quality-check.html` report is written next to the output.
- **give you a review page** (`report.html`) where you can change things and press **Save & rebuild**.

---

## Before you start (one time, on the RTX 5070 Ti laptop)

1. **Run Hinglish Editor.bat** starts the app, as before.
2. **Ollama.** The local AI "brain" used by all the new tools. Install Ollama, then in a terminal:
   ```
   ollama pull qwen3:8b        (plans shorts, pictures, clips and scenes)
   ollama pull qwen2.5vl:7b    (the vision model that checks pictures)
   ```
3. **AI Images / AI Video only:**
   - Double-click **`Setup AI Images (RTX).bat`** (about 21 GB) and/or **`Setup AI Video (RTX).bat`** (about 24 GB).
   - They install their own Python and models, and never touch the editor's Python.
   - To keep the models off drive E:, run the setup with `-Target D:\HinglishEditorModels` (this laptop already uses that folder).
4. **Motion Graphics only:**
   - Microsoft Edge (already on Windows) renders the animations.
   - The background-removal models download themselves on the first run into `models\rembg` (about 180 MB + 220 MB).
5. **Pexels / Pixabay keys (optional).** Used by B-roll and Motion Graphics for photos and clips. Paste them once in the app under **Add B-roll → B-roll settings**.

> **Speed note.** The new tools use several AI models. On this GTX 1650 (4 GB) laptop they are very slow (a Motion Graphics run took about 1 hour, and one AI Video clip took 7 hours) and are for testing only. On the RTX 5070 Ti (12 GB) they should be many times faster (for example, roughly 5–10 minutes for a Motion Graphics run of a short video). These RTX timings are estimates until tested on that laptop.

---

## 1. Long to Shorts (button 9)

**What it does:** give it your finished long YouTube video (for example 15 minutes). The local AI finds the moments that work on their own as Shorts: a strong **hook** at the start and a **payoff** at the end. It then makes each one ready to post. The idea is like FireCut's "Create highlights", done locally.

### How it chooses
1. **Speech to text.** Your speech is turned into text with the exact time of every word. Saved transcripts are reused.
2. **The AI reads the video.** It reads the whole video first, then each 5-minute part.
3. **For every short it picks:**
   - the hook line to start on
   - the payoff line to end on
   - up to **3 pieces** of the same story, joined
   - a **title**, true to what you said
   - a reason ("why")
4. **Rules check every answer.** The AI is asked again with the exact problems, and the rules fix what's left:
   - never starts on "aur / toh / so / but / lekin"
   - the right length
   - no like / subscribe / sponsor parts
   - pieces in time order
   - ends on a finished thought
   - every cut falls **between words**, never inside one
   - no two shorts about the same moment

### Choices in the app
| Setting | Options |
|---|---|
| How many | Low (about 1 per 4 min), Medium (about 1 per 2 min), High (about 1 per 75 s), or an exact number (1–40) |
| Look | **My template:** the full 16:9 video framed in the middle, a blurred background, the title with a red bar, and "WATCH FULL VIDEO ON ▶ @channel" below. Nothing is cropped. Or **Face crop 9:16:** fills the phone screen and follows your face. |
| Pieces | Up to 3, 2 or 1 per short |
| Length | Min / max seconds (default 30–60) |
| From / To | Only look inside part of the video |
| Title, channel, call to action | Your own text for the template (remembered on this PC) |
| Captions | Optional, in any of the 19 caption styles |

### What you get (`output\shorts\...`)
- **`SHORT_01_….mp4`:** a finished 1080×1920 MP4 at 30 fps with your sound, one per short.
- **`SHORT_01_….xml`:** an editable sequence per short for Premiere or Resolve, at your video's own frame rate.
  - **Template look:** V1 blurred background, V2 your video pieces, V3 title/frame layer, V4 captions.
  - **Face look:** V1 your video, V2 captions.
- **`report.html` (review page):**
  - edit titles
  - move cut points by ±0.5 s
  - remove a short, or add your own from times
  - switch the look, captions, title or channel
  - **Save & rebuild**

**In Premiere:** select the long video in the Project panel → Hinglish Editor → **Long to Shorts**. Each short is imported as its own sequence.

**Quality check:**
- length, cuts between words, no overlaps
- starts on a hook, finished ending, titles present
- no calls to action
- MP4 is 1080×1920 with sound
- every sequence is valid

**Tested:** on your 12.5-minute "mi final.mp4" (4K, 60 fps). It made 6 shorts and scored 100/100, and you approved the output.

---

## 2. AI Images (button 10)

**What it does:** paste your script, or choose your video / timeline. The local AI picks the moments where a picture helps:
- an idea or a feeling
- the look of a place
- history or the future
- a metaphor or a process

It writes one detailed prompt per moment in your chosen style, and your GPU makes the pictures with **Z-Image Turbo**. That model is free for commercial use (Apache 2.0) and fits 12 GB.

### Rules
- **Real people and brands are never AI-drawn.** The AI first lists every real name in your script, and a prompt that names one is dropped. Use **Smart Visuals** for real people and logos.
- Prompts must be 20–70 words.
- Never two pictures on neighbouring lines.
- About as many pictures as you asked for.

### Vision check
The vision model looks at every picture. It fails a picture that:
- doesn't show what was asked
- has deformed faces or hands
- has garbled text
- shows a real logo or a famous face

A failed moment is made again once, and the best passing option is chosen.

### Choices
| Setting | Options |
|---|---|
| Style | Cinematic realistic, Documentary archive, 3D animated, 2D illustration, Anime, **your own saved styles**, or a one-off style prompt |
| How many | Low / Medium / High (about 1.5 / 3 / 5 per minute) or an exact number |
| Format | Same as the video, 16:9, 9:16 or 1:1 |
| Pictures per moment | 1–4 (you pick the best on the review page) |
| Evaluator | The vision check, on or off |

### What you get (`output\aiimage\...`)
- **`chosen` folder:** the pictures in story order.
- **`AI_IMAGES_SEQUENCE.xml`:** the pictures on V2 above your video, with a gentle push-in, 2.5–6 s each (when you gave a video).
- **`report.html`:**
  - pick another option
  - edit a prompt and make it again
  - remove a picture

**Memory modes (automatic):**
- **Offload** on the 12 GB RTX: about 5–15 s per picture.
- **Low mode** on small cards: slow, for testing only.

**Tested:** end to end on this laptop in low mode. The pictures passed the vision check (100/100).

---

## 3. AI Video (button 11) – a separate tool from AI Images

**What it does:** picks only the **few** moments that need movement:
- a journey
- a crowd reacting
- weather or time passing
- a transformation or a reveal

For each one it writes the first frame and one simple movement. Your GPU then:
1. makes a sharp **first frame** with Z-Image Turbo (checked by the vision model)
2. animates it into a **5-second 720p clip at 24 fps** with **Wan 2.2 TI2V 5B** (Apache 2.0)

You can also choose **"Animate from the text only"**, which is faster, less sharp and doesn't need the picture model.

### Choices
The same as AI Images: style (including your own), how many (Low / Medium / High ≈ 0.25 / 0.5 / 1 per minute), format, first frames per clip, evaluator.

### What you get (`output\aivideo\...`)
- **`chosen` folder:** the clips.
- **`AI_VIDEO_SEQUENCE.xml`:** the clips on V2.
- **`report.html`:** pick another first frame, and **only that clip is animated again**.

**Rules:** the same "no real people or brands" rule. Every clip has a motion sentence, and 3 frames of each clip are checked by the vision model.

**Tested:** a real clip was made on this laptop's 4 GB GPU, an empty PG room with the camera gliding across. In low mode it is 2 s at 832×480 and took 7 hours. On the RTX 5070 Ti it makes the full 5 s at 1280×704 in a few minutes per clip (an estimate until tested there).

---

## 4. Motion Graphics (button 12)

Brought in from your project `local-motion-graphics-generator`. Its design, its Madurai `motion.mp4` and the four reference videos in its style memory were studied. The project itself was only read and was not changed.

**What it does:** turns your script or video into **motion graphics: pictures that move, not captions.** For every beat the local AI plans a scene and names **what it is built from**:

| Asset | Where it comes from |
|---|---|
| A real **person, brand/logo or place** you talk about | Wikipedia and web image search, **checked by the vision model** (is it really them? is it clean?) |
| An **object** that stands for the idea (a watch, money, a bike, a trophy…) | Made by **AI Images on your RTX**, or a transparent picture from the web |
| A **photo** of a situation | Web |
| A **video clip** of an action or place | Pexels / Pixabay (your keys) |

The background of every asset is removed **on your PC** (BiRefNet for people, ISNet for objects) so each one becomes a clean cut-out. Then each scene animates it.

### The scenes
| Scene | What it looks like |
|---|---|
| **Cut-out + big word** | The person or object cut out, a huge word **behind** them, a handwritten circled note |
| **Photo card** | A real photo taped on the page, a handwritten note with an arrow |
| **Spotlight** | The subject pops out of a big colour circle, with a 2-line title |
| **Object drop** | An object drops in and lands with a real shadow; the number next to it (only if you said it) |
| **Collage** | 2–4 things, each a picture with its name |
| **Versus** | Two things side by side with "VS" and a number under each |
| **Clip window** | A real video clip playing inside a window |
| **Silhouette** | The person as a glowing silhouette with one huge word |
| **Map route** | A line from one place to another, with photos of both places |
| Also | Phone app screen, phone call, chat, stamp (CANCELLED…), big number, timeline, end card |

### Rules (checked on every AI answer)
- A real person, brand or place is used **only if you actually say it.** No invented celebrities. Hinglish spellings are understood, for example "dilli" = Delhi and "tamilnaadu" = Tamil Nadu.
- **A number is shown only if you say it.**
- Each scene gets the right number of pictures.
- Short words only, and never written text inside a picture.
- Most scenes must carry a picture.
- A variety of scene types: the same type at most 3 times.
- Missing words are filled in from what you said.
- If a picture can't be found, the scene changes to one that still works. It is never left empty.

### Looks (styles)
- **From your reference videos:**
  - **Archive paper:** the Edison look. Grey paper, black-and-white photos.
  - **Teal pop:** cut-outs on white.
  - **Desk grid:** a white grid with window light.
  - **Cinematic dark.**
- **Also:** Street tech (your Madurai design), Documentary gold, Newsroom, Midnight neon.
- **Style memory:**
  1. In the app, under **Style memory**, press **Learn from pictures / videos** (or a folder).
  2. It measures colours, texture, black-and-white photos and speed, and saves a **style card**.
  3. Press **Approve** to use the card (you can also rename or delete it). Only approved cards can be used.

### Choices
| Setting | Options |
|---|---|
| Style | A theme or one of your approved style cards |
| What to make | **Full motion-graphics video** (every line; the default for a script or a video up to 3 min), or **Key moments on my timeline** (for longer videos) |
| Show them as | AI decides, all full screen, or over your video where it fits |
| Pictures from | Web + Pexels/Pixabay + AI Images (default), web only, or AI Images for objects |
| How many (key moments) | Low / Medium / High (about 2 / 4 / 6 per minute) or an exact number |
| Format (script only) | 16:9, 9:16 or 1:1 |

### What you get (`output\motion\...`)
- **`MOTION_GRAPHICS.mp4`:** the whole story as scenes, **with your voice**. No gaps, no captions.
- **`scenes\` folder:** every scene as its own file. Full-screen scenes are MP4. Scenes over your video are a transparent .mov.
- **`MOTION_GRAPHICS_SEQUENCE.xml`:** a copy of your timeline with full-screen scenes on **V2** and transparent scenes on **V3**.
- **`report.html`:**
  - each scene with its still, its words and **its pictures**
  - type new search words to **find another picture**
  - change the words, the scene type or the style
  - remove a scene
  - **Save & rebuild** re-renders only what changed

**How it renders:** each scene is an HTML/CSS animation played in Microsoft Edge and captured frame by frame, the same way as your own project's HyperFrames. It uses neither Three.js nor Remotion.

**Quality check:**
- at least half the scenes are built from pictures, and every picture file exists
- all text fits
- no invented numbers
- no overlapping scenes
- the full video covers the whole length with sound
- a valid timeline

**Tested on your `madurai_1.mp4` (48 s), with honest results:**
- **Worked:** the real run produced 14 scenes. The Madurai temple was cut out with MADURAI behind it, and the Zomato logo, the delivery bag and the graduation gown ("fresh") all came out well.
- **Went wrong:**
  - Some pictures were wrong because this laptop's vision check failed on the small GPU (an eye chart for "Swiggy", no-smoking signs for "no one").
  - "Rapido bike" became a bicycle.
  - 3 scenes fell back to text.
- **Fixed since:** failed checks now reject a picture, logos come from Wikipedia first, AI objects must be single physical things with no text, and scene variety is enforced.
- **Not yet done:** a fresh run with these fixes was stopped on purpose to free this laptop. Run it on the RTX laptop.

**Not built yet:** 3D objects (Poly Haven models) and tracked callouts that follow an object (YOLO).

---

## Shared improvements

- **Numbers in speech no longer break timing.** A spoken number ("10 saal", "2013") used to make a whole 25-second part lose its word timings. Now the number gets the time between its neighbours, and old saved transcripts with this problem are re-timed automatically. This helps every feature (captions, shorts, B-roll, zoom…).
- **The AI brain retries** when Ollama crashes on the GPU (seen on the 4 GB card).
- **Transcripts** are reused by all the tools, so a video is only transcribed once.
- **Quality Evaluator:** it now has rules for Long to Shorts, AI Images, AI Video and Motion Graphics.

---

## Where everything is

| Folder / file | What it is |
|---|---|
| `hinglish_shorts\` | Long to Shorts |
| `hinglish_aiimage\`, `hinglish_aivideo\` | AI Images and AI Video (two separate tools) |
| `hinglish_aigen\`, `tools\aigen\` | Their shared engine: GPU worker, vision check, styles, setup script |
| `hinglish_motion\` | Motion Graphics (`web\scene.html` = the animated scenes) |
| `hinglish_app\` | The app window (buttons 9–12) |
| `editor_plugins\premiere-cep`, `premiere-uxp` | The Premiere Pro panels |
| `hinglish_eval\` | The Quality Evaluator |
| `library\motion-styles\` | Your Motion Graphics style cards |
| `output\shorts`, `output\aiimage`, `output\aivideo`, `output\motion` | Results |
| `config.aigen.local.json` | Where the AI models are installed, plus your own AI styles (this PC only) |
| `models\rembg\` | Background-removal models |
| `D:\HinglishEditorModels\` | The large AI Images / AI Video models and their own Python |
| `DEV NOTES\07`–`10` and `FEATURE LOG.md` | Detailed notes for each feature |
| `tests\test_shorts.py`, `test_aigen.py`, `test_motion.py` | Automatic tests (all 267 tests pass) |

## Running from a terminal (optional)

```
.venv\Scripts\python.exe -m hinglish_shorts  --root . --input "D:\videos\long.mp4" --count medium --look template
.venv\Scripts\python.exe -m hinglish_aiimage --root . --script script.txt --style cinematic --count medium
.venv\Scripts\python.exe -m hinglish_aivideo --root . --script script.txt --count low
.venv\Scripts\python.exe -m hinglish_motion  --root . --input "D:\videos\reel.mp4" --style theme:archive
.venv\Scripts\python.exe -m hinglish_motion  --root . --learn-style "D:\references" --name "My look"
.venv\Scripts\python.exe -m hinglish_aiimage --root . --doctor     (is the GPU / model ready?)
```

## Good to know

- **Copyright of web pictures.** Smart Visuals and Motion Graphics can use pictures from websites. Check that you're allowed to use them before posting, and keep the credits the review page shows. Stock (Pexels/Pixabay) and AI-made pictures are safe.
- **Privacy.** Only web searches go out. Your videos, scripts and API keys stay on your PC, and the keys are never shown again.
- **Git.** None of this is committed yet. It will go to a new branch only when you ask, and `main` stays untouched until you say "merge to main".
