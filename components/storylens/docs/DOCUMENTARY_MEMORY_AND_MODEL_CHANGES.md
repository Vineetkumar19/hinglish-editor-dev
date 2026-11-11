# Your documentary memory and future local models

Your two reference libraries remain separate: **vineet documentry edit** and
**cricAddict**. They contain 16 videos totalling 13,004.85 seconds (3 hours,
36 minutes, 44.85 seconds). The original videos are read in place, one at a time.

## What is saved

| Area | Saved evidence |
|---|---|
| Cuts and transitions | Native-frame changes, source timestamps, scene candidates and nearby audio events |
| Camera and image movement | Adjacent-frame feature tracking, pan/zoom/rotation estimates, 3×3 local image-flow regions, measurable motion and weak-motion periods |
| Motion graphics | Source-linked scene/layout candidates and measured movement throughout each shot |
| Typography | Local CLIP style-family candidates on one source frame every second; exact font names are not claimed |
| Overlays and textures | Paper, halftone, film, photographic-background and light-treatment candidates |
| Zoom and parallax | Image-space scale changes and local-flow disagreement; a possible layered-motion cue, not a recovered physical 3D camera |
| Colour and pace | Native-frame brightness, contrast, saturation, edge detail and scene lengths |
| Voice | Full-track local voice activity and fallible source-timed transcription |
| Music and ambience | Existing offline CLAP interpretations covering the mixed track in 10-second windows |
| Effects, impacts, risers, whooshes | Full-track 20ms energy/spectral/onset measurements and locally classified onset candidates; overlapping audio is not represented as isolated stems |
| Beat timing | Candidate rhythmic grids and onset/cut offsets, retaining their uncertainty |

Video only contains its recorded frames, typically spaced 16.7–33.4ms apart.
The system measures every available native frame. It does not invent extra
information between frames or claim a human semantic review of every frame.

The complete **motion-graphics-editor-brain** and
**motion-graphics-animator-brain** are copied into the project. Their sections
are indexed for both styles. A compact core of those techniques and your own
requirements is supplied on every connected local-model documentary request.
Your documentary format and explicit preferences override generic vertical,
flat-grey, beat-driven or plugin-specific skill defaults.

## Continuous movement is a permanent requirement

The entrance of a photograph is only the start of a shot. Camera travel,
photographic-layer movement, depth, light and focus must continue through the
shot in a purposeful way. A readable evidence hold does not require a frozen
image. Grain moving over a frozen photograph does not satisfy this requirement.

Personal cricket motion renders now save a continuity review. Low measured
camera movement is flagged on the review page alongside layout warnings.
This is a conservative diagnostic, not a guarantee that every animation is
aesthetically good. Real footage, subject motion, optical-flow ambiguity and
readability still require judgement. General and Gaming retain their defaults.

## Changing the model

The knowledge lives in project files and a SQLite/vector database, independently
of Ollama. It is **persistent retrieval memory**, not language-model weight
fine-tuning. Replacing a language model does not delete this knowledge.

The shared local-model adapters load the same saved preferences, both motion
brains and relevant style examples. The memory revision is part of their input,
so changes invalidate old response caches. Motion settings have a `brain_model`
field; Sound Design already has `think_model`. Set these to the exact name of
your installed model. The motion command accepts `--brain-model`. The prepared sample worker also accepts the
`HINGLISH_DOCUMENTARY_MODEL` environment variable.

Keep the **multilingual E5 small embedding encoder** unchanged when changing
the language model. Its vectors are a different component. Vectors from a
different encoder are never compared merely because their dimensions match.
If the encoder is unavailable, keyword search still reads the saved records.

Each request receives relevant examples and core rules, rather than all three
hours of evidence at once. A smaller model may follow the same memory less
well than a larger model; storage does not make their reasoning ability equal.

## Moving to another laptop

The portable archive includes a consistent SQLite backup, vectors, style
settings, both complete brains, preferences, source-linked measurement curves,
per-second records, reference frames, transcripts and analysis receipts. It also
preserves the original 20ms audio feature arrays and native-frame colour/cut
measurements, so the backup retains detailed evidence beyond the summaries.
It excludes the large
original videos and model weights. Extract it into the project root and restore
the local E5 model for vector retrieval. Keep the original reference videos
separately if you also want to reopen their footage.

Restart an already running editor after code changes so its model adapters load
the new memory wiring. The saved knowledge remains available between restarts.
