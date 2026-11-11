import json
from pathlib import Path
import subprocess
import tempfile
import unittest

import av
import numpy as np
from imageio_ffmpeg import get_ffmpeg_exe

from hinglish_cut.model import Media
from hinglish_captions.core import CaptionCue, CaptionWord
from hinglish_captions.project import write_project, rebuild_project


class CaptionDemoScreenTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.folder = Path(self.temporary.name)
        (self.folder / 'media').mkdir()
        self.source = self.folder / 'media/source.mp4'
        subprocess.run([get_ffmpeg_exe(), '-nostdin', '-v', 'error', '-y',
            '-f', 'lavfi', '-i', 'color=c=blue:s=160x284:r=60',
            '-f', 'lavfi', '-i', 'sine=frequency=440:sample_rate=48000',
            '-t', '1', '-c:v', 'libx264', '-preset', 'ultrafast',
            '-pix_fmt', 'yuv420p', '-c:a', 'aac', str(self.source)], check=True,
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        media = Media('demo-test', str(self.source), 1, '60', 160, 284, 1, 48000)
        cue = CaptionCue((CaptionWord('Taj', .1, .4), CaptionWord('Mahal', .42, .8)), .1, 1)
        self.project = self.folder / 'caption-project.json'
        self.data = write_project(self.project, media, [cue], 'caption_2', 'source', 'media/source.mp4')
        self.data['demo'] = True
        self.project.write_text(json.dumps(self.data), encoding='utf8')

    @staticmethod
    def audio_packets(path):
        with av.open(str(path)) as movie:
            return [bytes(packet) for packet in movie.demux(audio=0) if packet.size]

    def test_black_and_white_survive_real_export_with_unchanged_audio_and_sync(self):
        original_audio = self.audio_packets(self.source)
        for color, value in [('black', 0), ('white', 255)]:
            result = rebuild_project(self.project, {'demo_background': color, 'export_video': True}, lambda _: None)
            saved = json.loads(self.project.read_text('utf8'))
            self.assertEqual(saved['demo_background'], color)
            self.assertEqual(saved['cues'], self.data['cues'])
            self.assertTrue(saved['media']['path'].endswith('solid-' + color + '.mp4'))
            with av.open(result['video']) as movie:
                self.assertEqual(float(movie.streams.video[0].average_rate), 60)
                frame = next(movie.decode(video=0)).to_ndarray(format='rgb24')
                self.assertTrue(np.all(frame == value), color)  # Before first caption, no blue source leaks.
                frames = list(movie.decode(video=0))
                self.assertGreater(len(frames), 40)
                self.assertTrue(np.all(frames[30].to_ndarray(format='rgb24')[:12] == value), color)
            self.assertEqual(self.audio_packets(result['video']), original_audio)

    def test_invalid_background_does_not_change_saved_progress(self):
        before = self.project.read_bytes()
        with self.assertRaisesRegex(ValueError, 'black or white'):
            rebuild_project(self.project, {'demo_background': 'red'}, lambda _: None)
        self.assertEqual(self.project.read_bytes(), before)

    def test_uploaded_video_does_not_get_a_demo_background(self):
        self.data['demo'] = False
        self.project.write_text(json.dumps(self.data), encoding='utf8')
        with self.assertRaisesRegex(ValueError, 'demo project'):
            rebuild_project(self.project, {'demo_background': 'white'}, lambda _: None)


if __name__ == '__main__':
    unittest.main()
