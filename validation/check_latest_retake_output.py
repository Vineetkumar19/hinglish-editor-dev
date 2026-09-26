"""Validate the real PG batch regression that previously kept both takes."""
from pathlib import Path
from urllib.parse import unquote, urlparse
import json
import sys
import xml.etree.ElementTree as ET
import wave

import av


def fail(message):
    raise SystemExit(f"FAIL: {message}")


root = Path(sys.argv[1] if len(sys.argv) > 1 else "output/phase2/20260919-220928-459231")
report = json.loads((root / "report.json").read_text(encoding="utf-8"))
decisions = json.loads((root / "edit-decisions.json").read_text(encoding="utf-8"))
rows = report["rows"]
cuts = decisions["cuts"]

if report["placed_sentences"] != report["sentence_count"]:
    fail("not every script sentence was placed")
if report["cut_count"] != len(cuts):
    fail("report and edit-decision cut counts differ")

retake = next(row for row in rows if "basic cheezein" in row["idea"])
chosen = retake["selected"]
if chosen["span"]["start"] < 15 or chosen["span"]["end"] > 18.2:
    fail("the corrected final take was not selected")
retake_media = chosen["span"]["media_id"]
if any(c["media_id"] == retake_media and c["start_frame"] < 100 for c in cuts):
    fail("the earlier duplicate take is still present in the timeline")

table = next(row for row in rows if row["idea"].startswith("Table itna"))
if "VID20260802142110" not in table["selected"]["source_name"]:
    fail("the newer Table take was not selected")
if any("VID20260802141614" in media["path"] and any(c["media_id"] == media_id for c in cuts)
       for media_id, media in decisions["media"].items()):
    fail("the superseded Table take is still present")

timeline_frames = sum(c["end_frame"] - c["start_frame"] for c in cuts)
if abs(timeline_frames / 30 - report["duration_seconds"]) > 1 / 30:
    fail("timeline duration does not equal its source cuts")

used = {}
for cut in cuts:
    bounds = used.setdefault(cut["media_id"], [])
    if any(max(cut["start_frame"], start) < min(cut["end_frame"], end)
           for start, end in bounds):
        fail("the timeline reuses overlapping source frames")
    bounds.append((cut["start_frame"], cut["end_frame"]))

xml_root = ET.parse(root / "EDITED_SEQUENCE.xml").getroot()
video_items = xml_root.findall(".//sequence/media/video/track/clipitem")
if len(video_items) != len(cuts):
    fail("XML video clip count does not equal the edit decisions")
for path_node in xml_root.findall(".//pathurl"):
    parsed = urlparse(path_node.text)
    path = Path(unquote(parsed.path.lstrip("/")).replace("/", "\\"))
    if not path.exists():
        fail(f"XML media is missing: {path}")

with av.open(str(root / "preview.mp4")) as preview:
    preview_frames = sum(1 for _ in preview.decode(video=0))
if preview_frames != timeline_frames:
    fail("preview frame count does not equal the XML timeline")
with wave.open(str(root / "full-timeline.wav")) as audio:
    audio_duration = audio.getnframes() / audio.getframerate()
if abs(audio_duration - timeline_frames / 30) > .001:
    fail("preview audio duration does not equal the XML timeline")

print("PASS: all script sections placed")
print("PASS: only the final corrected take (15.628s-17.948s) is used")
print("PASS: the earlier duplicate take is absent")
print("PASS: the newer Table take is used and the old one is absent")
print(f"PASS: XML, video, and audio contain {len(video_items)} cuts; duration {report['duration_seconds']:.2f}s")
