import json
from pathlib import Path
import tempfile
import unittest

import av

from hinglish_captions.demo import DURATION, SCRIPT, ensure_demo_projects, sample_cues
from hinglish_captions.editing import apply_timings
from hinglish_captions.project import cues_to_data
from hinglish_captions.styles import SELECTABLE_TEMPLATES


class CaptionDemoTests(unittest.TestCase):
    def test_sample_can_be_saved_by_the_normal_editor(self):
        cues = sample_cues()
        self.assertEqual(' '.join(cue.text for cue in cues), SCRIPT)
        self.assertEqual(cues[0].start, 0)
        self.assertEqual(cues[-1].end, DURATION)
        self.assertTrue(all(len(cue.words) <= 5 for cue in cues))
        # Use the actual validator used by Save & export, including word edits.
        timings = [{'start': row['start'], 'end': row['end'], 'words': row['words']}
                   for row in cues_to_data(cues)]
        self.assertEqual(apply_timings(cues, timings, DURATION), cues)

    def test_projects_use_real_black_media_and_preserve_saved_edits(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / 'hinglish_app/static').mkdir(parents=True)
            manifest = ensure_demo_projects(root)
            self.assertEqual(set(manifest['templates']), set(SELECTABLE_TEMPLATES))
            base = root / 'output/captions/template-demos'
            with av.open(str(base / 'black-background.mp4')) as movie:
                self.assertAlmostEqual(movie.duration / av.time_base, DURATION, places=1)
                frame = next(movie.decode(video=0)).to_ndarray(format='rgb24')
                self.assertEqual(frame.max(), 0)
            narrated=json.loads((base/'caption_1/caption-project.json').read_text('utf-8'))
            self.assertEqual(narrated['media']['fps'],'60')
            self.assertEqual(narrated['demo_narration']['sample'],'Taj Mahal')
            self.assertEqual(' '.join(w['text'] for c in narrated['cues'] for w in c['words']),SCRIPT)
            with av.open(str(base/'caption_1'/narrated['source_relative'])) as movie:
                import numpy as np
                audio=[]
                for i,frame in enumerate(movie.decode(audio=0)):
                    audio.append(frame.to_ndarray().reshape(-1))
                    if i>=20:break
                self.assertGreater(float(np.sqrt(np.mean(np.concatenate(audio)**2))),.01)
            path = base / 'typography_1/caption-project.json'
            saved = json.loads(path.read_text(encoding='utf-8'))
            self.assertEqual(saved['output_format'], 'source')
            self.assertEqual((saved['width'], saved['height']), (720, 1280))
            reference=base/'kinetic_documentary_reference16/caption-project.json'
            data=json.loads(reference.read_text(encoding='utf-8'))
            self.assertEqual(data['size'],1)
            self.assertEqual((data['width'],data['height']),(1080,1920))
            self.assertAlmostEqual(data['position'],1651.5/1920)
            self.assertIn('kinetic_documentary_reference16',manifest['templates']['kinetic_documentary']['url'])
            saved['cues'][0]['words'][0]['text'] = 'Welcome'
            path.write_text(json.dumps(saved), encoding='utf-8')
            before = path.read_bytes()
            ensure_demo_projects(root)
            self.assertEqual(path.read_bytes(), before)
            report = (path.parent / 'report.html').read_text(encoding='utf-8')
            self.assertIn('Welcome', report)
            self.assertIn('/caption-demo-editor.js', report)
            self.assertIn('/feedback.js', report)
            self.assertIn('caption-project.json', report)


if __name__ == '__main__':
    unittest.main()
