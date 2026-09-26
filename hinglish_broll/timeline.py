"""Read an FCP 7 XML sequence (Premiere / Resolve export or our own) and map speech to it."""
from dataclasses import dataclass, field
from fractions import Fraction
from pathlib import Path
from urllib.parse import unquote, urlparse
import os
import xml.etree.ElementTree as ET

from hinglish_cut.model import Word


@dataclass
class TimelineClip:
    path: str
    start: float        # seconds on the sequence
    end: float
    source_in: float    # seconds inside the source file
    source_out: float
    track: int


@dataclass
class Timeline:
    name: str
    fps: Fraction
    width: int
    height: int
    duration: float
    clips: list[TimelineClip]
    xml_path: str | None = None
    warnings: list[str] = field(default_factory=list)

    @property
    def orientation(self):
        if self.height > self.width: return 'portrait'
        if self.width > self.height: return 'landscape'
        return 'square'

    def sources(self):
        seen = {}
        for clip in self.clips:
            seen.setdefault(path_key(clip.path), clip.path)
        return list(seen.values())


def path_key(path):
    return os.path.normcase(str(Path(path).resolve()))


def path_from_pathurl(url):
    """file://localhost/E:/a%20b.mp4, file:///E:/..., or a plain path -> local path."""
    url = (url or '').strip()
    if not url.lower().startswith('file:'):
        return unquote(url)
    parsed = urlparse(url)
    path = unquote(parsed.path)
    if parsed.netloc and parsed.netloc.lower() != 'localhost':
        return '//' + parsed.netloc + path       # UNC share
    if len(path) > 2 and path[0] == '/' and path[2] == ':':
        path = path[1:]                          # /E:/... -> E:/...
    return str(Path(path))


def read_rate(node, fallback=None):
    rate = node.find('rate') if node is not None else None
    if rate is None or rate.findtext('timebase') is None:
        if fallback is None: raise ValueError('The XML has no frame rate')
        return fallback
    base = int(float(rate.findtext('timebase')))
    ntsc = (rate.findtext('ntsc') or 'FALSE').strip().upper() == 'TRUE'
    return Fraction(base * 1000, 1001) if ntsc else Fraction(base)


def _int(node, tag, default=0):
    text = node.findtext(tag)
    try: return int(float(text))
    except (TypeError, ValueError): return default


def parse_xmeml(path):
    path = Path(path)
    root = ET.parse(path).getroot()
    sequence = root if root.tag == 'sequence' else root.find('.//sequence')
    if sequence is None:
        raise ValueError('This XML has no sequence. Export a Final Cut Pro 7 XML timeline.')
    fps = read_rate(sequence)
    files = {}
    for f in root.iter('file'):
        url = f.findtext('pathurl')
        if f.get('id') and url:
            files[f.get('id')] = path_from_pathurl(url)
    fmt = sequence.find('./media/video/format/samplecharacteristics')
    width = _int(fmt, 'width', 1920) if fmt is not None else 1920
    height = _int(fmt, 'height', 1080) if fmt is not None else 1080
    warnings = []

    def clips_on(kind):
        found = []
        for index, track in enumerate(sequence.findall(f'./media/{kind}/track'), 1):
            if (track.findtext('enabled') or 'TRUE').upper() == 'FALSE':
                continue
            for item in track.findall('clipitem'):
                if (item.findtext('enabled') or 'TRUE').upper() == 'FALSE':
                    continue
                if item.find('sequence') is not None:
                    warnings.append('Nested sequences are skipped for speech; B-roll may miss that part')
                    continue
                file = item.find('file')
                source = files.get(file.get('id')) if file is not None else None
                if not source:
                    continue
                if any((e.findtext('effectid') or '').lower() == 'timeremap' for e in item.iter('effect')):
                    warnings.append(f'Speed change on {Path(source).name}; its B-roll timing may be approximate')
                clip_rate = read_rate(item, fps)
                start, end = _int(item, 'start', -1), _int(item, 'end', -1)
                src_in, src_out = _int(item, 'in'), _int(item, 'out')
                length_seq = (src_out - src_in) / clip_rate * fps
                if start < 0 and end >= 0: start = round(end - length_seq)
                if end < 0 and start >= 0: end = round(start + length_seq)
                if start < 0 or end <= start:
                    continue
                found.append(TimelineClip(source, float(start / fps), float(end / fps),
                                          float(src_in / clip_rate), float(src_out / clip_rate), index))
        return found

    audio = [c for c in clips_on('audio') if c.track == 1]
    speech = audio or [c for c in clips_on('video') if c.track == 1]
    duration_frames = _int(sequence, 'duration', 0)
    duration = float(duration_frames / fps) if duration_frames else 0.0
    duration = max([duration] + [c.end for c in speech])
    name = sequence.findtext('name') or path.stem
    if not speech:
        raise ValueError('No video or audio clips were found on the first track of this sequence')
    return Timeline(name, fps, width, height, duration, sorted(speech, key=lambda c: c.start),
                    str(path.resolve()), sorted(set(warnings)))


def timeline_words(timeline, transcripts):
    """transcripts: {path_key(source): [Word(source seconds)]} -> words in sequence seconds."""
    placed = []
    for clip in timeline.clips:
        words = transcripts.get(path_key(clip.path), [])
        for w in words:
            middle = (w.start + w.end) / 2
            if not clip.source_in <= middle < clip.source_out:
                continue
            shift = clip.start - clip.source_in
            start = max(clip.start, w.start + shift)
            end = min(clip.end, w.end + shift)
            if end > start:
                placed.append(Word(w.text, start, end, w.score, w.aligned))
    return sorted(placed, key=lambda w: w.start)
