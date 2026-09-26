# 03 – Sound Design (music + sound effects), v4

## v4 – the AI can now HEAR, needs a reason for every sound, and learns your taste (after "it adds random music and sounds")
**Why v3 sounded random:**
1. The AI never heard a sound. It chose files by their names and tags ("impact_03.wav"), which say nothing about the sound.
2. Too many sounds: one every 2.5 s, plus a whoosh on every B-roll, a boom on every zoom and a whoosh on every hit.
3. Music was picked by folder name: nothing checked for singing or matched the energy.
4. Nothing checked the result or learned from your changes.

**What changed:**
| | Now |
|---|---|
| **Ears (CLAP, local)** | `laion/larger_clap_general` listens to every effect and music file once (cached), so search and the AI's choice go by what a file SOUNDS like. Each file gets "sounds like: boom, bass drop" and "cartoonish or clean"; music also gets "HAS SINGING or instrumental", energy and BPM. Search fuses name match + sound match (sound counts double). |
| **A reason for every sound** | The director works like a pro "spotting session": each sound needs a trigger (punchline, reveal, list item, app name, number, new place, failure, win, worry…) AND the exact words that prove it. No trigger in the words = no sound. |
| **Tone rules in code** | The trigger decides the allowed types (a reveal gets a hit, never a coin). No playful sound (pop, ding, game, buzzer, glitch) on a sad, serious or vulnerable line unless the video is comedic. Singing tracks are never speech beds. |
| **Fewer, better sounds** | Budget includes B-roll/zoom sounds. Reel medium: about 1 sound per 4 s, at least 1.5 s apart. Low 1 per 6 s, high 1 per 3 s. Edit sounds may use at most half; the layered whoosh only on the biggest hits; pull-back-and-punch once per Reel. |
| **Evaluator** | Every picked effect is listened to: SOUNDS LIKE the wanted type (a voice, laughter, a music loop or the wrong kind fails) and TONE (no cartoon in serious/emotional/informational). Music fails when it has singing; energy mismatch warns. A failed file → next candidate. |
| **Mix check** | Measured on the final audio: each effect's loudness vs your words, music under speech (≤ −8 dB), master ≈ −14, no clipping, number of sounds within budget, spacing. |
| **Learns your taste** | report.html: untick sounds you don't like → **Save & remix**. Files you removed twice are never used again; your recent keeps/removals are given to the AI as examples next time (`cache\learning\sound-preferences.json`, delete to reset). |

- **First run:** the listening model downloads once (~0.8 GB, into `models\`) and listens to all ~1,400 files (a few minutes on CPU, cached after that).
- Settings (`config.sound.local.json`): `listen`, `listen_model`, `evaluate`.
- **Tested in the cloud (no torch/Ollama/models there):**
  - 12 new tests: the rules, the listening index (with a stand-in model), the evaluator, the mix check, taste learning and the report
  - the pipeline was linted and import-checked
  - ⏳ your listening test on the laptop

**How to improve further (in order of value):**
1. Use Save & remix on 5–10 videos: your taste becomes the AI's examples.
2. Add better sounds: a pro library is the biggest quality lever (Mixkit pack already added). Put packs into the effects folder; they are listened to automatically.
3. On the RTX 5070 Ti, set `think_model` to `qwen3:14b` for better story reading.
4. Later, reference matching: give it 3–5 Reels you love; it measures their sound density and levels, and targets them.


## v3 (after "I can't hear any sound effects")
- **Extended library:** a professional pack of **757 Mixkit sounds** was downloaded to `library\sfx-pro\` (167 MB):
  - whoosh 134, impact 127, poke 176 (pops/clicks/notifications/typing/camera/money), cute 80 (dings/chimes/sparkles)
  - awkward 71 (fail/error/scratch), retro 72, suspense 45 (heartbeat/clock), riser 23, glitch 29
  - Licence: Mixkit Sound Effects Free License, free in commercial videos with no attribution; the files must not be redistributed as a library, so the folder is kept out of git.
  - The pack is preferred when a match is about as good. Your own library is still searched.
  - Re-fetch or update with `python -m hinglish_sound.fetch_pack .`
- **Audible levels (fixed again after measuring):**
  - **Why they were quiet:** effects were matched by their *peak*. Your voice is compressed (dense body), while a whoosh or pop is a thin spike, so they came out 15–22 dB quieter than you. That is why you couldn't hear them.
  - **How they are set now:** by how loud they *sound on a phone*, meaning their loudest 150 ms, K-weighted so deep bass doesn't count. This is compared with how loud your *words* sound (90th percentile of 150 ms windows).
  - **Levels:** hits 2 dB under your words; pops and buzzers 3 dB; whooshes, dings, coins and glitches 4 dB; risers and vanishes 5 dB; the layer whoosh 7 dB; heartbeat and tension 8 dB.
  - **SFX bus compressor:** each sound's sharpest spike is trimmed 4–10 dB so its body can come up. No effect peak goes more than 3 dB over your voice peak, and the master limiter holds −2 dB.
  - **Tiny clicks skipped:** any sound audible for less than 60 ms is skipped when choosing files. One "message pop" was a 15 ms click, and no level can make that audible.
- **Reel density:** about one designed speech sound every 2.5 s (never two within 0.8 s), plus a whoosh on every B-roll cut and a boom on every zoom landing.
- **Layering:** every hit of strength 2–3 gets a whoosh whose peak arrives exactly on the hit.
- **Director rules:** a clear vocabulary of which moment gets which sound (whoosh / impact / riser / poke / ding / money / fail / tension / glitch / vanish), a target number of moments, and variety (never the same type 3 times in a row).

---

# v2 "thinking" version

**Status:** 🔁 Rebuilt after your feedback. v1 had no context, the music was too quiet and the effects were random. · ⏳ Your listening test   **Date:** 26 Sep 2026

## What changed from v1 (and why)
| v1 problem | v2 fix |
|---|---|
| No idea of the story or the emotion | A **thinking local model** (Ollama `qwen3:8b`) reads every line with the whole context. It writes the story, and for each line: emotion (sad / frustrated / lonely / sarcastic / hopeful…), intensity and story role. |
| Only read the words, not the tone | **Voice evidence** for every line: louder or quieter, higher or lower pitch, expressive or flat, fast or slow, relative to your own average. |
| Random files | **RAG:** a **vector index** (Ollama `qwen3-embedding:0.6b`) of all 563 effects and all music, each described by type, genre, length and shape (hits at once / builds up / swells). Each moment retrieves its best **real candidates**, and the model **picks** one with a reason (or none). |
| Cartoon sounds in a serious story | The model picks a **palette** (serious / emotional / comedic / energetic / informational). Cartoon/"funny" files are excluded unless the palette is comedic. |
| Music inaudible | Brain numbers (see below): music in pauses sits **8 dB under** the voice and **ducks 9 dB** while you speak. |
| No brain rules | The **sound-design brain** rules are in the model's instructions: felt not noticed, contrast not loudness, pull back and punch, effect by moment, density, never on every line. |

## How it works
1. Speech lines + voice evidence + edit events (B-roll cutaways, zoom landings) go to the thinking model, which returns the story, palette, emotion map, music sections (mood per emotional section) and the few moments that deserve a sound (exact word, type, intent, strength, pull-back).
2. For each moment and each music section, the vector index returns the top real files, and the model chooses the exact file.
3. **Placement:** the file's peak lands on the exact word. Density is about one designed sound per 5 s in Reels, never two within 1.5 s, strongest first.
4. **Edit sounds (brain §7):** a subtle swoosh or low thud on each B-roll cut, and a felt low hit where a zoom lands, in the video's palette.
5. **Mix (brain numbers):**
   - voice high-pass at 80 Hz
   - music EQ dip −3 dB at 1–3 kHz, 8 dB under the voice in pauses, −9 dB duck under speech (80 ms attack / 900 ms release)
   - **pull back and punch:** −10 dB vacuum 0.45 s before the one or two biggest reveals
   - effects set by peak: hits 8–10 dB under the voice peak, UI pops 14 dB under, 150 Hz high-pass on UI sounds
   - master −14 LUFS, **−2 dB ceiling limiter**
6. **Output:**
   - `SOUND_SEQUENCE.xml`: music and each effect on their own tracks
   - `preview.mp4`
   - `report.html`: story, emotion map, music and every sound with its reason, plus the model's own thinking

## Needs
The Ollama app must be running with `qwen3:8b` and `qwen3-embedding:0.6b` (both already on this laptop).
On this CPU the thinking takes a few minutes per video. On the RTX 5070 Ti it will take seconds, and a bigger model (e.g. `qwen3:14b`) can be set in `config.sound.local.json` → `think_model`.
