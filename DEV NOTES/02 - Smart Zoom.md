# 02 – Smart Zoom (one click)

**Status:** ✅ Built and tested on your footage (app + engine) · ⏳ Needs a real Premiere/Resolve import test   **Date:** 26 Sep 2026
**Inspired by:** FireCut "Add zooms": AI picks the important moments; settings for scale, face centre, sharp vs smooth, and frequency; zooms become clips in the sequence.

## What it does
Click **Smart Zoom**. The local AI finds the key moments in your Hinglish speech **and the exact stressed word**. The zoom lands on that word, goes into your face, then eases back out.
You get a new sequence `<name>_ZOOM`. Your original sequence is unchanged, the audio is never cut, and moments covered by B-roll are skipped.

## Zoom types
| Type | When (Mixed style) | Feel |
|---|---|---|
| Smooth zoom-in | important points | sine ease-in, reaches full zoom exactly on the word, eases out |
| Impact punch | strongest lines | instant punch 4.5 % past the target that settles in ~0.3 s |
| Punch-in | alternates with impact | sharp cut in, sharp cut out |
| Zoom-out reveal | a result, answer or twist is revealed | starts zoomed, eases back to wide |
| Slow push-in | calm storytelling | gentle build over the phrase |
| Jump-cut framing | every cut | alternates 100 % / ~109 % so jump cuts feel intentional |

Settings: **Style** (Mixed / Smooth / Punch), **Strength** (Subtle 108 % / Medium 115 % / Strong 125 %), **How often** (Low / Medium / High), **Zoom into my face**, **Hide jump cuts**.
Pacing: Reels (≤ 3 min) get a zoom every ~3.5 s. Long YouTube videos get calmer, longer zooms every ~10 s+.

## Why it is smooth and never jittery
- **Sine easing** peaks at only 1.57× the average speed (cubic easing is 3×). Stronger zooms also take a little longer.
- Tests confirm the peak speed stays **≤ 70 % scale/second for Reels and ≤ 50 %/s for YouTube**, at 24, 30 and 60 fps. Every zoom is one clean rise and one clean fall, with no wobble.
- Ramps are **baked frame by frame** as tiny clips with fixed scale. Premiere and Resolve reproduce them exactly, with no keyframe-import quirks (Resolve is known to drop XML keyframes).

## Face-aware framing
- OpenCV **YuNet** face detector runs locally and finds your face in each clip.
- Each zoom pulls the face toward the ideal spot (centred, 38 % from the top), but only as far as the zoomed image still fills the frame. Tests confirm that **no black edge ever shows** in 9:16 or 16:9.
- No face found → zoom into the frame centre. Clips you already repositioned keep the face fixed.

## Files (new package `hinglish_zoom\`)
| File | Job |
|---|---|
| `settings.py` | Reel vs YouTube pacing, style/strength/frequency |
| `planner.py` | local Qwen: key moments + stressed word + zoom kind |
| `events.py` | word timing, zoom types, optimal spacing, jump-cut framing |
| `curve.py` | eased per-frame zoom curve |
| `faces.py` | face position per clip (YuNet, cached) |
| `xml_apply.py` | splits V1 clips, writes scale + centre, keeps audio whole |
| `preview.py` | preview.mp4 with audio (timelines up to 5 min) |
| `report.py` / `pipeline.py` / `__main__.py` | results page, runs everything |

New dependency: `opencv-python-headless` (installed in the DEV `.venv` and added to `requirements.txt`). Face model: `models\opencv\face_detection_yunet_2023mar.onnx`.

## Test log (current laptop, CPU)
| Test | Result |
|---|---|
| Automated tests | **163 / 163 pass** (17 new zoom tests + server test) |
| Real 46 s, 6-clip Reel sequence | 5 zooms on "nahin" (opener), "AC" (end of the list), "jugaad", "yahaan **nahin** rahna"… Face found in 6/6 clips. Audio untouched (6 + 6 clips). |
| Visual check of preview frames | Smooth zoom tightens on the face with no edges. The impact punch is clearly visible on a wide shot and settles. Next clip at 109 % jump-cut framing. |
| App UI (Smooth / Strong / High) | Ran end to end: "1 editable XML timeline created", results page + preview OK. |

## Must check once in the real editors
The XML "centre" value is written as a fraction of the frame size (x right, y down). Apple's documentation does not state the exact units.
**First test:** import `ZOOMED_SEQUENCE.xml` in Premiere, open a zoomed clip and look at **Effect Controls → Motion**.
- Scale should read e.g. 115, and the zoom should go toward your face.
- If it zooms toward the wrong spot, turn off **Zoom into my face** for now and tell me. The fix is one line (`CENTER_X_UNIT` / `CENTER_Y_UNIT` in `xml_apply.py`).

## Known limits / next ideas
- The small 4B model sometimes stresses a weaker word (e.g. "Bhai" instead of "nahin"). A bigger model on the RTX 5070 Ti will choose better.
- The preview is skipped for timelines over 5 minutes (render time). The XML is still made.
- The face position is measured once per clip. If you move around a lot inside one long clip, the zoom follows the average position.
