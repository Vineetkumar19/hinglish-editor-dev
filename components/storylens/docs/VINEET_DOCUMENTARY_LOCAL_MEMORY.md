# vineet documentry edit — local reference memory

The reference folder is `A:\after effects\documentry edit\final videos\final videos`.
The originals stay there. The analysis reads one video at a time and stores small
images, measurements, transcripts and local-model candidates in the project.

## What is saved

- Every native decoded frame: change, colour, texture, and image shift measurements.
- Scene candidates: source timestamps, one in-scene keyframe, layout, typography
  and texture suggestions, plus sampled pan, scale, rotation and residual motion.
- Earlier reviewed chapter notes: photo arrangements, entrances, masks, page and
  reel treatments, evidence holds, narrator bridges and colour treatment.
- Complete mixed audio: 20ms measurements, voice activity, music/ambience
  suggestions, distributed short onset clips, and rhythm/beat candidates.
- Automatic narration transcripts and shot/chapter pacing statistics.
- Source-linked records and real 384-dimensional semantic vectors in
  `library\creator-profiles\editing-dna.sqlite3`.

The offline tools use FFmpeg/NVDEC, OpenCV, Silero VAD, the installed Whisper
transcripts, CLIP ViT-B/32, CLAP HTSAT and multilingual E5 small. None of the
analysis stages calls a cloud model. No ChatGPT subscription is needed to run
the saved pipeline once the project environment and local weights are available.

## How the editor uses it

Choose **Cricket → vineet documentry edit**. The motion planner retrieves visual
examples from this style. The sound planner retrieves audio examples. Retrieved
examples retain reference filenames, timestamps and uncertainty notes.

The five approved executable animations remain Road Timeline, Aligned Film Reel,
Centred Photo Reveal, Hinged Glass Panels and Turning Photo Album. More reference
knowledge does not automatically create additional animation rigs. The
`cricAddict` database records and General/Gaming defaults stay separate.

## Review and resume

Open `output\reference-analysis\cricket-documentaries\dna-report.html` to inspect
each video's scene and audio evidence. `dna-coverage.json` records the coverage,
vector counts and retrieval checks. `style-memory.md` is the readable guide.

To resume the full analysis locally from the project folder:

```powershell
.venv\Scripts\python.exe tools\learn_vineet_documentary.py
```

Completed stages are reused. The run requires the existing offline model weights
and the original reference drive. To continue after source measurements have
completed:

```powershell
.venv\Scripts\python.exe tools\learn_vineet_documentary.py --interpret-and-index
```

New files in the same folder are discovered on the next full run. New files have
automatic candidates until their chapter observations are reviewed.

## What “learned” means

This is persistent reference memory and semantic retrieval, not fine-tuning of
LLM weights. Every native frame has measurements; one representative per scene
has local semantic suggestions. Exact fonts, physical cameras, hidden 3D layers,
isolated sound stems and original project keyframes cannot be recovered exactly
from flattened videos. Sound labels and beat estimates are candidates. Cricket
names, statistics, player identity and archival dates need separate verification.
