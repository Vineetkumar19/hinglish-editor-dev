# Storylens

**Personal Android app:** native Ask the Editor with an owned encrypted connection
to the laptop; no browser or Tailscale is required by this path. Run
**Start StoryLens Android Connection.cmd** after opening StoryLens.
See [native app setup and verification limits](docs/PHONE_NATIVE.txt).
The earlier [private browser companion](docs/PHONE_REMOTE.txt) remains available
separately; neither connection exposes the full editor interface.

**Cinematic Reels:** a separate music-led workflow for travel, performance and
action footage. Detect beats, select suitable shot sections, assemble a synced
reel, then choose effects. See [Cinematic Reels](docs/CINEMATIC_REELS.md).

**Beat Studio:** local music-beat detection with Light / Medium / Strong density,
an optional marker cap, and a separate beat-effects action for Premiere Pro and
Resolve Studio. See [the Beat Studio guide](docs/BEAT_STUDIO.md) for setup,
supported effects and the live-editor validation boundary.

Storylens is the AI video editor built in this project. One ₹2,000 monthly or
₹20,000 annual subscription includes the Desktop application and Editor Plugins
on one registered computer.

The account service now supports MySQL, a private owner dashboard and moderated
customer ratings/reviews. Start **Start Storylens Website.cmd**, then follow
[the Storylens owner guide](docs/STORYLENS_OWNER_GUIDE.md). The public website is
https://storylens.magicpearl129.chatgpt.site . Public account hosting remains a
separate deployment step; the complete MySQL-backed service works locally.

Older Python package names and installation paths are retained for compatibility.

## Subscription website preparation

The separate website preview runs at `http://127.0.0.1:8788/` using
**Run Website Preview.bat**. It includes the product website, interactive demo,
accounts, Razorpay integration and a private rendering queue. Live payments
and public processing are disabled until configured. See the
[SaaS hosting and launch guide](docs/SAAS_HOSTING_AND_LAUNCH.md) for pricing,
tested protections, free hosting options and what remains before launch.
The existing local editor and personal creator profiles remain intact.

## Conversational editing

The editor now includes a right-side AI chat. Attach your clips, type or speak an editing request, and the assistant selects and runs the existing tools. Multi-step edits run in order and follow-up requests reuse the last completed video. **Show tools** reveals the detailed controls. See [the conversational editor guide](docs/CONVERSATIONAL_EDITOR_GUIDE.md) for examples, voice setup, hardware requirements and validation.


> **New (September 2026):** Long to Shorts, AI Images, AI Video and Motion Graphics are explained in
> **[NEW FEATURES - README.md](NEW%20FEATURES%20-%20README.md)**.

## Optional personal Cricket and Gaming profiles

General retains the existing editor defaults. Select **Cricket** or **Gaming** to add domain guidance, separate preferences, sourced cricket research, gaming highlights, thumbnail options and separate channel publishing routes. See [the creator profiles guide](docs/CREATOR_PROFILES_GUIDE.md) for setup, examples, account folders, hardware requirements and the tested limits. This upgrade uses persistent preferences and source retrieval; it does not train new model weights.

## New simple app and editor panels

- Double-click **Run Hinglish Editor.bat** for the standalone app.
- Choose **Smart Clean** to remove silence without a script.
- Choose **Script Edit** to arrange clips by meaning, keep the latest complete retake, and clean pauses/fillers.
- Choose **Auto Captions** to generate timed Roman Hinglish captions with fifteen premium animated styles, including the reference-inspired **Typography 1**.
- Double-click **Install Editor Plugins.bat** once for Premiere Pro 2024 and DaVinci Resolve Studio.
- In Premiere Pro 2024 open **Window > Extensions > Hinglish Editor**.
- In Resolve Studio open **Workspace > Scripts > Hinglish Editor**.
- Premiere Pro 25.6+ has the UXP build in `editor_plugins/premiere-uxp`; load it with Adobe UXP Developer Tool until the commercial plugin is signed.
- Resolve Free, old, or modified editors use the standalone app and import its XML manually.

The app never overwrites the original sequence. It creates a new editable XML timeline.

### Add B-roll (new)

One click adds cutaway footage that matches what you are saying (Hindi, English or Hinglish).

- **Premiere Pro:** open the edited sequence â†’ **Window > Extensions > Hinglish Editor** â†’ **Add B-roll**. A new sequence `<name>_BROLL` is imported with B-roll on V2 (your talking head stays on V1; any caption layer stays on top).
- **DaVinci Resolve Studio:** open the timeline â†’ **Workspace > Scripts > Hinglish Editor** â†’ **Add B-roll** â†’ keep *Use the timeline open in DaVinci Resolve* ticked â†’ **Import to Resolve** when finished.
- **Standalone app:** choose a video, or **Or choose a timeline XMLâ€¦** (e.g. `EDITED_SEQUENCE.xml` from Script Edit).

First time only: **Add B-roll â†’ B-roll settings** â€” paste your free **Pexels** and **Pixabay** API keys and/or add folders of your own footage. Keys stay in `config.broll.local.json` on this computer (never uploaded, never shown again).

How it decides: the local Qwen model summarises the video, then picks the phrases that benefit from a cutaway and writes what should be on screen plus English search terms. CLIP compares every candidate clip with that description; your own footage is preferred when equally good, and no clip is used twice. Reels (â‰¤ 3 min) get 1.5â€“3 s cutaways, long YouTube videos 3â€“6 s cutaways every ~20â€“40 s; the opening hook always stays on your face. Density: Low / Medium / High.

### Smart Visuals (new)

One click puts the REAL thing you talk about on screen: the actual person (Gandhi, Virat Kohli), the app or brand logo (Zomato, Swiggy, ChatGPT), the place or the historical event. It is not generic B-roll.

- A local AI agent (Ollama `qwen3:8b` when running, else the built-in Qwen) reads the whole speech with memory of the story, so a Gandhi story shows Gandhi only. It fixes speech-recognition spellings ("Jomato" â†’ Zomato) and finds the exact Wikidata item.
- The agent searches the whole web like you would ("Zomato logo png", "Meenakshi temple video"): images from any website, videos from YouTube and 1000+ sites (only the needed part is downloaded), plus Wikipedia/Wikimedia Commons and Pexels/Pixabay. No account or key needed. Every file must prove it is about that person or brand, and the AI checks the best one before it is used. Web files can be copyrighted: check before posting.
- **Evaluator:** a local vision model (Ollama `qwen2.5vl:7b`) looks at every picture and video before it is used and fails it if it is the wrong type (you said temple, it shows a dog), the wrong one (a random temple, a logo that doesn't read "Zomato") or poor quality (watermark, collage, screenshot). Results in `report.html` and `EVALUATION.json`; re-check any result with `python -m hinglish_visuals.evaluator --project <visuals-project.json>`.
- First time: `.venv\Scripts\python.exe -m pip install ddgs yt-dlp imageio-ffmpeg` and `ollama pull qwen2.5vl:7b`.
- Logos and faces pop up on the word that names them, never over your face. Stories, facts, places and footage go full screen for exactly the spoken line.
- Output `output\visuals\<date>\...\VISUALS_SEQUENCE.xml` (new sequence `<name>_VISUALS`: V2 full screen, V3 transparent pop-ups), `preview.mp4`, `report.html` (swap or remove, **Save & rebuild**) and **`CREDITS.txt`**. Paste the credits into your video description.
- Same button in the app, Premiere Pro (CEP and UXP) and DaVinci Resolve Studio. Details: `DEV NOTES\05 - Smart Visuals.md`.

### Smart Zoom (new)

One click adds zooms on the key moments: the local AI picks the important phrases **and the stressed word**, and the zoom lands on that word. Types: smooth zoom-in (sine ease), impact punch (settling overshoot), punch-in, zoom-out reveal, slow story push-in, plus alternate framing on every cut to hide jump cuts. Zooms go toward your face (OpenCV YuNet, local) without ever revealing frame edges. Settings: Style (Mixed/Smooth/Punch), Strength (108/115/125 %), How often (Low/Medium/High). Output `output\zoom\<date>\...\ZOOMED_SEQUENCE.xml` (new sequence `<name>_ZOOM`; audio never cut; ramps are written frame-by-frame so Premiere and Resolve match exactly), `preview.mp4` (timelines â‰¤ 5 min) and `report.html`. Works on any XML from the other features, including `_BROLL` sequences (zooms under B-roll are skipped).

Each B-roll run writes `output\broll\<date>\...\`: `BROLL_SEQUENCE.xml`, `report.html` (swap any clip for one of the alternatives or remove it, then **Save & rebuild**) and the prepared clips in `media\` (cropped to the sequence size and frame rate, muted).

### Auto Captions

Open **Auto Captions**, click **Choose videos** or **Choose folder**, select one of the fifteen templates and run it. **Typography 1** adds colored text strips, a condensed hero word, shadow, glow, blur transitions and camera push motion. An optional rough script can supply the preferred spelling of names and English words even when the spoken wording differs. Each video receives:

- `CAPTIONED_SEQUENCE.xml` with the original video/audio on V1/A1 and a transparent animated caption layer on V2.
- `captions.srt`, `captions.ass`, and `transcript.txt` for later text corrections.
- `report.html` with an on-video editor. Correct any word, switch templates or fonts, move and resize the captions, choose 9:16 / 1:1 / 16:9, then click **Save & rebuild** to update every export.

The speech stays in Roman Hinglish, for example `Aaj hum video editing seekhenge`; it is not translated to English or converted to Devanagari. The reference script acts as a spelling guide and does not replace genuinely different spoken sentences. Existing completed transcripts are reused on later style runs. The first transcription still depends on recording quality, so the final text remains manually editable before publishing.

**Current Phase 2 output:** import `EDITED_SEQUENCE.xml` and open the sequence
named **EDITED_SEQUENCE**. Play `preview.mp4` first. Paragraphs now assemble from
multiple source clips with nearby complete later takes preferred. See
**PHASE 2 AND CLEAN PLUS - START HERE.txt** for current instructions; old
`draft.xml` instructions below apply to the original cutter/older results.

**New: Phase 2 and Clean+.** **Run Phase 2.bat** arranges `input\phase2` clips against `input\phase2\script.txt` by meaning and source timing. **Run Clean Plus.bat** uses `input\phase1` recordings for conservative filler/retake cleanup without a script. Both provide review controls; **Apply Reviewed Choices.bat** applies saved selections into a fresh output. See **PHASE 2 AND CLEAN PLUS - START HERE.txt**. Meaning checks are fallible: review uncertain ideas and source sections left out of the arrangement.

**New: Phase 1 silence removal (no script).** Put recordings in `input\phase1\videos` and double-click **Run Phase 1.bat**. Use `input\phase1\instagram-vertical` or `input\phase1\youtube-horizontal` for a fixed canvas; fill only one Phase 1 folder per batch. Results go to `output\phase1`: a cleaned MP4, Premiere XML and before/after review page per video. See **PHASE 1 - START HERE.txt** for the short guide. Filler and retake handling are future Phase 1 milestones.

A local Python application that arranges raw talking-head takes according to your Hinglish script, trims pauses, checks the edited speech, and writes an editable **Final Cut Pro 7 XML** timeline for **Premiere Pro**. Includes CPU and NVIDIA RTX 5070 configurations. No editor scripting API or paid inference API is used.

## Start here

The project is in `E:\remove silence`. On this computer an isolated `.venv` environment has been created. On a new computer, install 64-bit Python 3.12 and run **Setup CPU.bat** first.

**Current setup status:** the CPU dependencies and Swift transcription weights are installed. Run **Download Models.bat** for the two main models. It does not download the huge optional meaning-check model. You can ignore **Download Optional Evaluator.bat** for now.

**Choose your frame before each run:** Put Reels/Shorts in `input\instagram-vertical` for a 1080x1920 vertical sequence, or put long YouTube videos in `input\youtube-horizontal` for a 1920x1080 horizontal sequence. Use one of these folders at a time. The app rotates phone footage upright and fits the whole video without automatic cropping. The old `input\videos` folder remains available for existing projects.

1. Put your 15â€“20 raw videos in `input\videos`. Subfolders are supported. Files are identified from their speech; filenames do not determine script order.
2. Open `input\script.txt` and paste your master script in **UTF-8**. Use one short sentence or intended edit unit per line. Use Roman Hinglish such as `Is process ke liye API ki zaroorat nahi hai.` An example is in `examples\script.txt`.
3. Double-click **Run CPU.bat**. It uses the already downloaded local models. If it says a model is missing, run **Download Models.bat** once and try again.
4. Open `report.html` in the new dated folder inside `output`. Listen to the audio for each line and inspect any warnings.
5. In **Premiere Pro**, use **File > Import** and select that folder's `draft.xml`. Keep the original videos in their original locations so Premiere can find them. If Premiere asks to locate media, point it at `input\videos`.
6. Continue editing and export in Premiere. For After Effects, use Premiere/After Effects project interchange or Adobe Dynamic Link when your installed versions support it. The XML is intended for Premiere, not direct After Effects import.

**Try it without footage:** double-click **Run Demo.bat**. It creates small real video files containing synthetic tones, arranged using known test transcripts, and a playable HTML report. The demo checks the editing/export machinery; it is not a speech-recognition benchmark.

## After you install the RTX 5070

1. Install a current NVIDIA driver compatible with your GPU and CUDA 12.8.
2. Run **Setup RTX 5070.bat**. This switches the project environment to matched PyTorch 2.9.1 / torchaudio 2.9.1 CUDA 12.8 packages. PyTorch's CUDA 12.8 builds support NVIDIA Blackwell. You do not need to install the full CUDA development toolkit just to run these wheels.
3. Run **Run RTX 5070.bat**. Recognition, forced alignment and the local language model run on the GPU. VAD, audio decoding and timeline construction remain on the CPU. Recognition uses float16 on CUDA and float32 on CPU. A real CUDA matrix operation is checked before processing.

The same CUDA environment can also run **Run CPU.bat**. To return to a CPU-only installation, run **Setup CPU.bat**. The GPU model files are the same as the CPU files. RTX performance cannot be measured until your card is installed; the application does not assume the GPU is currently present.

## What is automatic

| Stage | Implementation |
|---|---|
| Media inspection | PyAV inspects video/audio and verifies a constant frame rate. No separate FFmpeg executable is needed. |
| Speech detection | Silero VAD identifies speech regions; long recordings are processed in bounded windows. |
| Hinglish transcription | Oriserve Whisper-Hindi2Hinglish-Swift runs locally through Transformers. No master-script prompt is used to avoid encouraging the model to invent the desired words. |
| Word alignment | Multilingual romanized MMS CTC emissions plus a NumPy Viterbi aligner produce estimated word times. Hindi/English code-switching still needs evaluation on your recordings. |
| Clip arrangement | Token sequence matching and a bounded beam search choose nonoverlapping source word spans in script order. A later-recorded clip may appear first in the output. |
| Silence removal | Removes sufficiently long gaps unsupported by both VAD and aligned words. Keeps default 120 ms before and 160 ms after speech and rounds outward to whole video frames. |
| Evaluator | Reconstructs the actual edited audio, re-transcribes it, checks coverage/negations/numbers/important terms, and retries a conservative cut if those checks fail. A local Qwen model also checks intent and entities. |
| Output | FCP 7 `xmeml` version 5 XML with linked video/audio and absolute media URLs. Original footage is not re-encoded or modified. |

WhisperX was researched because your PDF proposes it. Its default Hindi aligner is designed around a Hindi character dictionary; arbitrary Roman Hinglish needs a compatible alignment vocabulary. This implementation uses the multilingual romanized MMS model instead, keeping the requested forced-alignment stage. The CTC decoder is implemented in NumPy to avoid a Windows C++ extension build requirement.

## Understanding the evaluator

Every script line remains in the report, including lines for which no source was found. The evaluator checks:

- How much of the intended line remains in the edited audio.
- Changes to negations such as `nahi`, `mat`, `not`, and `never`.
- Changes to numeric tokens and your configured important terms.
- Ambiguous retakes, uncertain alignment, missing script lines, and repeated source frames.
- Intent and entity preservation from a **local** instruction model.

### Local learning from your corrections

In a Phase 2 review page, choose the correct take, click **Save reviewed choices**, and drag the downloaded file onto **Apply Reviewed Choices.bat**. The app saves those approved and rejected take pairs locally in `cache/learning`. Future meaning checks give closely related corrections to the local Qwen judge as examples. Unrelated projects are not injected, and the system does not change model weights automatically.

The two configuration files enable `Qwen/Qwen2.5-1.5B-Instruct` as a small baseline semantic evaluator. It runs after the speech models are released from memory. Its Hinglish judgment is **not a guarantee**: a small language model can misunderstand a sentence, and re-transcribing with the same ASR model can repeat the same error. Listen to the supplied cut audio. For higher quality you can set `judge_model` to another compatible local Transformers instruction model after checking available RAM/VRAM and that model's language performance.

The conservative retry restores pauses inside the selected sentence span when the speech/text checks fail. It does not invent a missing recording or loop indefinitely. A failed semantic judgment is flagged for manual review. Malformed model JSON or failure to load the judge never becomes a pass.

Set `judge_model` to `null` if you want structural evaluation only. The report then explicitly says `semantic_not_checked`, and the output remains a draft.

### Outputs

Each run gets a fresh dated folder; previous runs are not overwritten.

| File | Purpose |
|---|---|
| `draft.xml` | Editable Premiere timeline. Can contain a partial assembly if some lines are missing; consult the report. |
| `timeline.xml` | Also written only when every required check passes and no source errors remain. Human review is still recommended. |
| `report.html` | Readable per-line review, audio players, alternatives and warnings. |
| `report.json` | Detailed checks, settings and selected spans. |
| `edit-decisions.json` | Exact source frame in/out points and media metadata. |
| `review-audio\line-XXXX.wav` | Mono audio of each selected and trimmed line. |
| `review-audio\full-timeline.wav` | Mono preview of the whole assembled timeline. Original channels remain linked in XML. |

`REVIEW_REQUIRED` is a completed draft requiring attention. Command exit code 2 means this review state; 1 means an execution/setup error, and 130 means interruption. If nothing matches, the report still lists every missing line, but no empty XML timeline is fabricated.

## Supported footage and current limits

- Intended for separately recorded talking-head takes, not automatic camera synchronization or visual best-angle selection.
- Each chosen script line must occur within a single source file. If one sentence is intentionally recorded across files, split it into separate lines in the master script.
- First release requires a uniform constant frame rate: 24, 25, 30, 48, 50, 60, 24000/1001, 30000/1001, or 60000/1001. Variable-frame-rate phone recordings and mixed rates must be conformed first. These are rejected instead of guessing time mappings.
- Embedded audio is required. Files with multiple independent audio streams are rejected until you choose the intended stream. Channels within the chosen stream are kept as linked mono tracks in the XML.
- Square-pixel, progressive, already oriented footage is the intended input. Bake phone rotation into conformed files if needed. Source resolutions can differ; the first selected clip sets the sequence dimensions, so inspect scaling in Premiere.
- Alignment is estimated, not exact to a millisecond. Video edits land on frame boundaries. Unknown symbols/numeric spellings or low-confidence alignment retain a coarse span and trigger review rather than inventing precise word times.
- Pacing is conservative. It deliberately retains short natural pauses and speech missed by one detector. It does not remove every breath or guarantee click-free hard audio edits; review and add fades in Premiere where needed.
- No B-roll, color grading, denoising, or final video rendering is added automatically. Auto Captions creates a transparent caption layer plus editable subtitle files.
- A 15â€“20-file or larger batch is supported, but throughput depends on total audio duration and CPU/GPU. No five-minute runtime promise is made.

## Settings

Edit `config.cpu.json` or `config.rtx5070.json`:

- `min_silence`: gaps must exceed this many seconds before removal; default `0.45`.
- `pre_padding` / `post_padding`: speech protection in seconds; defaults `0.12` / `0.16`.
- `match_threshold`: reject weak script matches below this score; default `0.72`.
- `coverage_threshold`: edited-speech coverage threshold; default `0.85`.
- `aliases`: map equivalent single-word spellings such as `"nahin": "nahi"`. Do not map negations to affirmative words.
- `important_terms`: names, product names or phrases whose disappearance must be flagged, e.g. `["Premiere Pro", "Mumbai"]`.
- `cpu_threads`: CPU inference thread count, default 4. Increase cautiously if your CPU benefits.
- `offline`: use only previously downloaded model files. Run the download launcher once before setting this to `true`.
- `asr_model`, `align_model`, `judge_model`: Hugging Face identifiers or compatible local model directories.

Downloaded models are stored in `models`; decoded audio and completed analysis are stored in `cache`. A full source-file digest and settings are included in cache keys, so changed footage/settings triggers fresh analysis. A first run needs several GB of model storage and internet for downloads. Inference itself is local. Model weights have their own licenses; see the linked model cards.

## Commands for troubleshooting

Run from this project directory:

```powershell
.\.venv\Scripts\python.exe -m hinglish_cut doctor
.\.venv\Scripts\python.exe -m hinglish_cut doctor --device cuda
.\.venv\Scripts\python.exe -m hinglish_cut prepare --config config.cpu.json
.\.venv\Scripts\python.exe -m hinglish_cut run --config config.cpu.json --offline
.\.venv\Scripts\python.exe -m hinglish_cut run --config config.rtx5070.json --offline
.\.venv\Scripts\python.exe -m hinglish_cut demo
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

## Research and implementation references

Read against the user's full nine-page PDF; the XML route explicitly overrides the PDF's direct editor-API workflow. Some PDF statements, including guaranteed accuracy, universal XML support and fixed processing speeds, are not assumed by this implementation.

- [Oriserve Whisper-Hindi2Hinglish repository](https://github.com/OriserveAI/Whisper-Hindi2Hinglish) and [Swift model card](https://huggingface.co/Oriserve/Whisper-Hindi2Hinglish-Swift).
- [WhisperX](https://github.com/m-bain/whisperX) and its [Hindi alignment configuration](https://github.com/m-bain/whisperX/blob/main/whisperx/alignment.py).
- [CTC forced aligner](https://github.com/MahmoudAshraf97/ctc-forced-aligner) and [multilingual MMS model](https://huggingface.co/MahmoudAshraf/mms-300m-1130-forced-aligner). Used as architecture/model references; no upstream C++ implementation is vendored.
- [Silero VAD](https://github.com/snakers4/silero-vad).
- [Sarvam intent/entity evaluation](https://github.com/sarvamai/llm_intent_entity), an evaluation reference; this project does not call Sarvam services.
- [Qwen local evaluator model](https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct).
- [Apple legacy Final Cut XML reference](https://developer.apple.com/library/archive/documentation/AppleApplications/Reference/FinalCutPro_XML/Elements/Elements.html).
- [PyTorch Blackwell support](https://pytorch.org/blog/pytorch-2-7/) and [matched PyTorch installations](https://pytorch.org/get-started/previous-versions/).
- [Adobe Premiere/After Effects Dynamic Link](https://helpx.adobe.com/uk/premiere/desktop/use-premiere-with-other-apps/working-with-other-adobe-applications/share-assets-between-after-effects-and-premiere-using-dynamic-link.html).

See `docs/design.md` and `docs/implementation-plan.md` for the implementation structure. See `docs/validation.md` for what has actually been exercised in this environment.
# Phase 2 update â€” September 15

For your current script/video workflow: see **PHASE 2 AND CLEAN PLUS - START HERE.txt**.
Phase 2 now assembles each paragraph from multiple sentence clips, prefers nearby
complete later takes, and produces **EDITED_SEQUENCE.xml** plus **preview.mp4**.
Open the imported **EDITED_SEQUENCE** sequence in Premiere. Older Phase 2
instructions mentioning `draft.xml` apply only to older saved projects.
Highly paraphrased speech and transcription errors still need listening review.
