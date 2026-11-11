# One video at a time: cricAddict

The active source is `Gautam Gambhir is an Attention Seeker_.mp4` in the user-provided cricAddict reference folder. Its duration is 752.885 seconds. Reference 2 must wait for the user's review of reference 1; workers never advance automatically.

The source is unchanged. Its native cadence is 30000/1001 fps: approximately one recorded frame every 33.37 milliseconds. The workflow does not invent images between those frames or describe automated measurements as human-certified analysis.

## Evidence and local decisions

1. An offline CLIP ViT-B/32 encoder interprets every decoded native frame at a reduced measurement resolution: a 256x144 thumbnail followed by CLIP's standard 224px centre crop. Full-frame every-second panels complement this reduced view; small letters and faces cannot be certified. All 22,564 normalized visual vectors are saved in a separate 512-dimensional array, with ordered timestamps and layout/typography/texture candidate labels. These visual vectors are not mixed with the E5 text embeddings.
2. The earlier fingerprint-matched native optical-flow evidence, cut candidates, scene evidence and full 20-millisecond mixed-audio measurements are retained. Motion in image space does not prove a physical camera, separated 3D layers or the original After Effects settings.
3. Fresh sequential local Whisper large-v3-turbo transcribes the whole reference with word-time estimates. These are not certified forced-alignment onsets. The saved original mixed audio contains narration, music and existing sound effects; it is not a set of isolated stems.
4. Local Qwen2.5-VL sees a timestamped original image for every source second, grouped into panels. Only complete validated English observations are eligible for memory. Failed, repetitive and truncated responses remain diagnostic evidence, not lessons. CPU inference avoids the installed GTX 1650 CUDA vision crash.
5. Local Qwen3:8B infers source-grounded lessons and selects a contiguous 60-second window. It chooses the scene sequence, available approved rigs, short English copy, photo word cues, note word cues and optional local sound cues. No assistant-authored storyboard replaces the local decisions.
   The sample director uses focused calls: first it chooses real word IDs for the scene clock, then an existing rig and its bounded parameters for each scene. Sorting those locally chosen IDs is mechanical; no new boundaries are inserted. Validated scene checkpoints allow a failed asset choice to be repaired by the same local model without discarding its other decisions. Language-only repairs are also performed locally and retain valid observations.
6. Local Qwen2.5-VL resolves actual source photo regions, one image per request. Existing offline IS-Net weights isolate appropriate subjects. If a photo is unsuitable, the local director receives the issue and revises its choices. No unrelated earlier demo assets or generated player identity substitutes are used.
7. A mechanical adapter binds those choices to existing cricAddict rigs. The local director selects a 1–3 multiplier for existing continuous camera/subject movement; the adapter preserves the approved rigs' paths, layouts, entrances and masks. Word IDs control reveals; source playback follows the original narration time. Geometry checks exclude grain, fading alpha and changing JPEG filenames from photo motion. The adapter verifies the original rig hash, 1,800 encoded frames, a 60-second export and audio synchronization. Cutout hashes must match the current source image and local crop, preventing stale subjects after a repaired cue.
8. Source-specific seconds, local observations and lessons are encoded with the existing fixed multilingual E5 encoder and saved in `library/creator-profiles/editing-dna.sqlite3`. Explicit user preferences and approved styles are not overwritten by inferred lessons. The model-independent memory and consistent database snapshot are exportable without original videos or model weights.

## Outputs

All first-reference outputs live in `output/reference-analysis/cricAddict-by-video/reference-01`.

- `progress.html`: live progress, clearly distinguished from a finished sample.
- `report.html`: completed source-specific lessons, the one-minute sample, every-second evidence and links to coverage receipts.
- `CRICADDICT_REFERENCE_01_LOCAL_60S.mp4`: locally directed 720p/30fps sample using a local-model-selected source passage.
- `native-visual-candidates.csv` and `native-clip-embeddings.npy`: every-native-frame local visual candidates and vectors.
- `fresh-transcript.json` and `fresh-words.json`: whole-source sequential local speech recognition.
- `local-visual-review.json`, `learned-lessons.json` and `local-plan.json`: recorded local interpretations and creative decisions.
- `sample-cue-audit.json`, `sample-continuity.json` and `sample-render-receipt.json`: scheduling, movement and export evidence.
- `CRICADDICT_VIDEO_01_MEMORY.zip`: portable first-video evidence and a consistent style-database snapshot.

This is retrieval-based reference memory, not fine-tuning new neural weights. A future language model can use the same stored memory through the project's existing memory adapters; keep the E5 embedding encoder fixed unless deliberately rebuilding the index.
