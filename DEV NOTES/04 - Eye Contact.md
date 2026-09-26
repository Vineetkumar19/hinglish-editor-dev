# 04 – Eye Contact (NVIDIA Maxine, RTX only)

**Status:** ✅ Built. The whole pipeline was tested on this laptop with a stand-in for NVIDIA's engine. ⏳ Real run on the RTX 5070 Ti.   **Date:** 26 Sep 2026

There is **no CPU version** (your choice). On this GTX 1650 laptop the app says so clearly and does nothing.

## What it does
You read a script from a laptop, a phone or paper. NVIDIA Maxine's **Gaze Redirection** redraws your eyes so you look into the lens.
- **Natural glances** (on by default): tiny random look-aways, so it never looks like a fixed stare.
- **Real eyes are left alone:** eyes that look far away, such as a real look to the side or a head turn, are not changed. NVIDIA fades the effect out past the angle limits.

## How to use (on the RTX laptop)
1. Once: double-click **`Setup Eye Contact (RTX).bat`**. It:
   1. checks the GPU (RTX 5070 Ti → `-gpu 120`)
   2. offers to install Git, Git LFS, CMake and VS 2022 C++ Build Tools with winget
   3. opens NVIDIA's NGC page for the AR SDK (free NVIDIA account; you download and extract the zip into `tools\maxine\ARSDK`)
   4. asks for **your NGC API key**. You type it in that window; it is used there only and never saved.
   5. installs the 3 features: gaze redirection, landmarks, face box
   6. builds NVIDIA's `GazeRedirectionApp.exe`
   7. saves `config.eyecontact.local.json` and runs a test on NVIDIA's sample clip

   Run it again any time; finished steps are skipped.
2. Then use the **Eye Contact** button in the app, Premiere (CEP or UXP) or Resolve.
   - **Where was your script?** *Near the lens* (laptop or phone under the camera) or *Further away* (paper on the desk, screen to the side).
   - **Eye size sensitivity:** 2–6, default 3.
   - **Natural glances:** on or off.
3. Result:
   - `EYE_CONTACT_SEQUENCE.xml`: the same edit, relinked to the corrected copies (imported automatically in Premiere)
   - a before/after preview
   - corrected copies in `output\eyecontact\media\`

   Your originals are never changed.

## How it works (so quality and sync are exact)
NVIDIA's app reads through OpenCV: it ignores phone rotation, drops the audio and writes plain video. So we wrap it:
1. **Only camera clips:** from the timeline, only camera clips are processed. B-roll, stock and the sound library are skipped.
2. **Clean parts for NVIDIA:** each camera file is decoded once and turned upright, 8-bit, standard (TV) range. It is cut into parts of a few minutes, each under OpenCV's 4 GB file limit. Joins go where your edit doesn't use the footage when possible, and each part is written near-lossless with NVENC.
3. **NVIDIA runs on each part:**
   - offline mode, split-screen and debug drawings forced **off** (the sample turns them on by default)
   - `--temporal --landmarks_126 --use_cuda_graph`, MJPG output
   - live progress (frames, fps, time left)
4. **Final encode:** H.264 (NVENC, constant quality 17) using **your source's own frame timestamps**. Frame *i* is always frame *i* of the original, so length, timing and sync never change.
5. **Audio and timecode:** your **original audio is copied back bit-for-bit**, along with the timecode.
6. **Relinked XML:** a new XML with only the media links swapped. Every cut, effect and keyframe stays as it was.
7. **Reuse:** results are cached by file + settings, so running it again is instant.

## Tested here (simulated engine, 26 Sep)
- madurai_1 timeline (after B-roll + Zoom): 1460/1460 frames, **0.0 ms** timing difference, audio **byte-identical**, colour tags kept, picture 41–49 dB PSNR (visually identical), brightness difference 0.04.
- Split into 5 parts: rejoined frame-exact; the first join landed in an unused gap.
- Bug found and fixed:
  - **Problem:** PyAV does not convert full-range (JPEG) video to TV range; it only relabels it, which made the picture 7 levels darker.
  - **Fix:** the range is now converted explicitly, both for NVIDIA's MJPG output and for full-range phone footage.
- The doctor and setup stop cleanly on the GTX 1650. The app status line shows the reason, and a job fails with the same message.

## Verified facts (NVIDIA)
- **SDK layout:**
  - `<ARSDK>\bin\nvARPose.dll` and `<ARSDK>\bin\models`
  - features in `<ARSDK>\features\<feature>\bin`
  - `features\install_feature.ps1 -gpu <75|86|89|120> -features <name>`, with `NGC_CLI_API_KEY` set
- **Sample app:**
  - `github.com/NVIDIA-Maxine/AR-SDK-Samples` (needs Git LFS)
  - build: `cmake -S . -B build -DARSDK_ROOT=<ARSDK>` then `cmake --build build --config Release`
  - the build writes `run_gazeredirectionapp_offline.bat` with the DLL PATH and `--model_path`; we read it
- **Defaults in the app:**
  - on unless changed: split screen, debug drawing, temporal
  - thresholds: gaze 20/30°, head pitch 15/25°, yaw 25/30°
  - look-away: max 5°, every 3–11 s

## Files
- `hinglish_eyecontact/`
  - `settings.py`: options → NVIDIA flags
  - `maxine.py`: GPU check, finding the install, doctor, running NVIDIA with progress
  - `media.py`: parts, final encode, audio, preview
  - `timeline.py`: used clips + relinked XML
  - `pipeline.py`, `report.py`, `__main__.py` (`--doctor`; `--simulate` is a developer test)
- `tools/eyecontact/setup_eyecontact.ps1` and `Setup Eye Contact (RTX).bat`
- App: server mode `eyecontact` + `/api/eyecontact/status`, UI panel. Plugins: Premiere CEP + UXP buttons (Resolve uses the app page).
- git-ignored: `tools/maxine/` (NVIDIA SDK, not ours to share) and `config.eyecontact.local.json`.
