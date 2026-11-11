"""AI Images and AI Video (two tools, one shared engine), with a fake GPU worker, fake AI and fake vision check."""
import json
import re
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import numpy as np
from PIL import Image

from hinglish_aigen import pipeline
from hinglish_aigen.judge import Verdict, decide
from hinglish_aigen.plan import _names, names_in, plan_repair, plan_rules, script_lines
from hinglish_aigen.settings import GenSettings, all_styles, save_styles, style_prompt

SCRIPT = ('Mumbai Indians ki kahani 2008 se shuru hoti hai. Rohit Sharma captain bane aur sab badal gaya. '
          'Stadium mein hazaaron log chilla rahe the. Raat ko Marine Drive par jashn manaya gaya. '
          'Sabko laga tha ki yeh team kabhi nahi jeetegi. Lekin mehnat ne sab kuch badal diya. '
          'Aaj yeh team paanch baar champion hai. Yeh sirf cricket nahi, ek emotion hai.')
LONG = ' '.join(['detail'] * 20)
READY = {'ready': True, 'cuda': True, 'gpu': 'Fake RTX', 'vram_gb': 12, 'mode': 'offload',
         'image_model': True, 'video_model': True}


class FakeBrain:
    name = 'fake'

    def json(self, system, data, schema, max_tokens=0, think=False):
        if 'people' in json.dumps(schema):
            return {'people': ['Rohit Sharma'], 'brands': ['Mumbai Indians'], 'places': ['Marine Drive']}
        ids = [int(i) for i in re.findall(r'^\[(\d+)\]', data['script_part'], re.M)]
        return {'moments': [
            {'line': ids[2], 'why': 'crowd', 'importance': 9, 'motion': 'slow push in',
             'prompt': 'A packed cricket stadium at night, thousands of fans in blue waving flags, ' + LONG},
            {'line': ids[4], 'why': 'party', 'importance': 7, 'motion': 'pan',
             'prompt': 'Fireworks over a seaside promenade at night with a happy crowd celebrating, ' + LONG},
            {'line': ids[6], 'why': 'captain', 'importance': 8, 'motion': 'push',
             'prompt': 'Rohit Sharma holding the trophy in a blue jersey under stadium lights, ' + LONG}]}

    def close(self):
        pass


def fake_generate(root, items, jobs_file, progress=print, mode='auto'):
    import av
    results = {}
    for item in items:
        Path(item['out']).parent.mkdir(parents=True, exist_ok=True)
        if item['kind'] == 'image':
            Image.new('RGB', (item['width'] // 8, item['height'] // 8), (40, 90, 160)).save(item['out'])
        else:
            with av.open(item['out'], 'w') as out:
                s = out.add_stream('libx264', rate=24)
                s.width, s.height, s.pix_fmt = 320, 176, 'yuv420p'
                for i in range(120):
                    frame = av.VideoFrame.from_ndarray(np.full((176, 320, 3), i * 2, np.uint8), format='rgb24')
                    frame.pts = i
                    for p in s.encode(frame):
                        out.mux(p)
                for p in s.encode():
                    out.mux(p)
        results[item['id']] = {'event': 'done', 'id': item['id'], 'out': item['out'], 'seconds': 1.0}
    return results


class FakeJudge:
    name = 'fake judge'

    def __init__(self):
        self.calls = 0

    def image(self, path, prompt):          # every second picture fails
        self.calls += 1
        return Verdict(self.calls % 2 == 0, 7.0, [] if self.calls % 2 == 0 else ['does not show what was asked'])

    def video(self, path, prompt):
        return Verdict(True, 8.0)

    def close(self):
        pass


def patched(judge=None, generate=fake_generate):
    return [mock.patch.object(pipeline.engine, 'doctor', return_value=READY),
            mock.patch.object(pipeline.engine, 'generate', side_effect=generate),
            mock.patch.object(pipeline, 'open_judge', return_value=judge),
            mock.patch('hinglish_visuals.brain.open_brain', return_value=FakeBrain())]


class RuleTests(unittest.TestCase):
    def test_script_lines_are_timed_sentences(self):
        lines = script_lines(SCRIPT)
        self.assertEqual(len(lines), 8)
        self.assertTrue(all(b.start >= a.end for a, b in zip(lines, lines[1:])))

    def test_real_names_are_caught_in_prompts(self):
        names = _names({'people': ['Rohit Sharma'], 'brands': ['Zomato']})
        self.assertEqual(names_in('Rohit holds a cup', names), ['rohit'])
        self.assertEqual(names_in('a zomato delivery bag', names), ['zomato'])
        self.assertEqual(names_in('a captain in a blue jersey', names), [])

    def test_rules_and_repair_for_pictures_and_clips(self):
        lines = script_lines(SCRIPT)
        names = _names({'people': ['Rohit Sharma'], 'brands': []})
        answer = {'moments': [
            {'line': 1, 'prompt': 'Rohit Sharma smiling ' + LONG, 'importance': 9, 'why': ''},
            {'line': 3, 'prompt': 'a stadium ' + LONG, 'importance': 5, 'why': ''},
            {'line': 99, 'prompt': 'x ' + LONG, 'importance': 1, 'why': ''}]}
        self.assertEqual({p.rule for p in plan_rules(lines, names, 'image', 3)(answer) if p.hard},
                         {'aigen.no_real_names', 'aigen.line'})
        self.assertIn('aigen.motion', {p.rule for p in plan_rules(lines, names, 'video', 3)(answer) if p.hard})
        fixed, notes = plan_repair(lines, names, 'video', 3)(answer)
        self.assertEqual([m['line'] for m in fixed['moments']], [3])
        self.assertEqual(fixed['moments'][0]['motion'], 'slow cinematic camera push-in')
        self.assertFalse([p for p in plan_rules(lines, names, 'video', 3)(fixed) if p.hard])

    def test_judge_decision(self):
        good = decide({'shows_request': True, 'broken': False, 'bad_text': False, 'real_logo_or_celebrity': False,
                       'score': 8, 'problem': ''})
        bad = decide({'shows_request': True, 'broken': True, 'bad_text': False, 'real_logo_or_celebrity': False,
                      'score': 6, 'problem': 'six fingers'})
        self.assertTrue(good.passed)
        self.assertFalse(bad.passed)

    def test_settings_and_own_styles(self):
        self.assertEqual(GenSettings(kind='image').target(600), 30)
        self.assertEqual(GenSettings(kind='video').target(600), 5)
        self.assertEqual(GenSettings(kind='video', count='2').target(600), 2)
        with self.assertRaises(ValueError):
            GenSettings(kind='both')
        with tempfile.TemporaryDirectory() as root:
            styles = save_styles(root, [{'name': 'My neon', 'prompt': 'neon cyberpunk glow'}, {'name': '', 'prompt': 'x'}])
            self.assertEqual([s['name'] for s in styles if s['own']], ['My neon'])
            self.assertEqual(style_prompt(root, 'my:My neon'), 'neon cyberpunk glow')
            self.assertEqual(style_prompt(root, 'cinematic', 'my own words'), 'my own words')
            self.assertEqual(len(all_styles(root)), 6)


class ImageToolTests(unittest.TestCase):
    def test_pictures_checked_chosen_folder_and_rebuild(self):
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            (root / 'output').mkdir()
            patches = patched(FakeJudge())
            for p in patches:
                p.start()
            try:
                page = pipeline.run(root, None, SCRIPT, GenSettings(kind='image', count='3', options=2), progress=lambda m: None)
                folder = page.parent
                self.assertEqual(folder.parent.parent.name, 'aiimage')             # its own output folder
                project = json.loads((folder / 'aiimage-project.json').read_text(encoding='utf-8'))
                moments = project['moments']
                self.assertEqual(len(moments), 2)                                   # the Rohit Sharma prompt was dropped
                self.assertTrue(all(m['kind'] == 'image' and not m.get('video') for m in moments))
                for m in moments:
                    chosen = next(o for o in m['options'] if o['id'] == m['chosen'])
                    self.assertTrue(chosen['verdict']['passed'])
                self.assertEqual(len(list((folder / 'chosen').glob('*.png'))), 2)
                self.assertIn('Rohit Sharma', (folder / 'report.html').read_text(encoding='utf-8'))
                result = pipeline.rebuild_project(folder / 'aiimage-project.json',
                                                  {'choices': {str(moments[1]['index']): ''},
                                                   'regenerate': {str(moments[0]['index']): 'An empty stadium at dawn, ' + LONG}},
                                                  progress=lambda m: None)
                self.assertEqual(result['remade'], 1)
                self.assertEqual(result['with_visual'], 1)
                self.assertEqual(len(list((folder / 'chosen').iterdir())), 1)
            finally:
                for p in patches:
                    p.stop()


class VideoToolTests(unittest.TestCase):
    def test_clips_from_first_frames_and_a_new_frame_reanimates(self):
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            (root / 'output').mkdir()
            calls = []

            def counting(root_, items, jobs_file, progress=print, mode='auto'):
                calls.append([i['kind'] for i in items])
                return fake_generate(root_, items, jobs_file, progress, mode)
            patches = patched(FakeJudge(), counting)
            for p in patches:
                p.start()
            try:
                page = pipeline.run(root, None, SCRIPT, GenSettings(kind='video', count='2', options=2), progress=lambda m: None)
                folder = page.parent
                self.assertEqual(folder.parent.parent.name, 'aivideo')
                project = json.loads((folder / 'aivideo-project.json').read_text(encoding='utf-8'))
                moments = project['moments']
                self.assertEqual(len(moments), 2)
                self.assertTrue(all(m['kind'] == 'video' and m['motion'] for m in moments))
                self.assertTrue(all(m['video']['file'] and not m['video']['error'] for m in moments))
                self.assertTrue(all(m['video']['from'] == m['chosen'] for m in moments))      # animated from the chosen frame
                self.assertEqual(len(list((folder / 'chosen').glob('*.mp4'))), 2)
                self.assertIn(['video', 'video'], calls)
                other = next(o['id'] for o in moments[0]['options'] if o['id'] != moments[0]['chosen'])
                calls.clear()
                result = pipeline.rebuild_project(folder / 'aivideo-project.json', {'choices': {str(moments[0]['index']): other}},
                                                  progress=lambda m: None)
                self.assertEqual(calls, [['video']])                                # only that clip is made again
                self.assertEqual(result['remade'], 1)
                project = json.loads((folder / 'aivideo-project.json').read_text(encoding='utf-8'))
                self.assertEqual(project['moments'][0]['video']['from'], other)
            finally:
                for p in patches:
                    p.stop()

    def test_video_input_places_clips_on_a_timeline(self):
        import sys
        import xml.etree.ElementTree as ET
        sys.path.insert(0, str(Path(__file__).parent))
        from test_shorts import make_video, speech
        from hinglish_broll.timeline import parse_xmeml, path_key
        from hinglish_eval.specs import check_xml
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            (root / 'output').mkdir()
            video = root / 'talk.mp4'
            make_video(video, seconds=24, size=(640, 360))
            words = speech([s for s in SCRIPT.split('. ') if s], gap=.4, word=.3)
            patches = patched(None) + [mock.patch('hinglish_broll.pipeline.transcripts_for',
                                                  side_effect=lambda r, sources, d, p: ({path_key(s): words for s in sources}, []))]
            for p in patches:
                p.start()
            try:
                page = pipeline.run(root, video, '', GenSettings(kind='video', count='2', options=1, check=False),
                                    progress=lambda m: None)
            finally:
                for p in patches:
                    p.stop()
            folder = page.parent
            project = json.loads((folder / 'aivideo-project.json').read_text(encoding='utf-8'))
            xml = folder / project['xml']
            self.assertEqual(xml.name, 'AI_VIDEO_SEQUENCE.xml')
            self.assertTrue(all(c.passed for c in check_xml(xml)))
            tracks = ET.parse(xml).getroot().findall('.//sequence/media/video/track')
            clips = tracks[1].findall('clipitem')                                 # V2, right above the talking head
            self.assertEqual(len(clips), 2)
            fps = float(parse_xmeml(xml).fps)
            self.assertTrue(all(2.4 <= (int(c.findtext('end')) - int(c.findtext('start'))) / fps <= 5.01 for c in clips))


if __name__ == '__main__':
    unittest.main()
