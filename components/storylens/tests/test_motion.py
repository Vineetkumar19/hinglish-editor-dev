"""Motion Graphics: the rules on the AI's answer (assets named, no invented people / numbers), timing of the scenes and
of the full video, the fallback when pictures are missing, and a real render (Microsoft Edge / Chrome) with a fake
AI and a fake picture finder."""
import json
import re
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import numpy as np
from PIL import Image

from hinglish_broll.phrases import Phrase
from hinglish_motion import pipeline
from hinglish_motion.assets import cutout_ok, has_alpha, trim
from hinglish_motion.plan import has_number, name_said, plan_repair, plan_rules
from hinglish_motion.settings import MotionSettings

SCRIPT = ('Thomas Edison school se nikaala gaya tha. Teacher ne kaha yeh bachcha slow hai. '
          'Usne bulb banane ki 1000 koshish ki. Har baar fail hua. '
          'Phir ek raat bulb jal utha. Aaj duniya roshan hai.')


def lines_of(texts, seconds=3.0):
    return [Phrase(i, i * seconds, (i + 1) * seconds, t) for i, t in enumerate(texts)]


class FakeBrain:
    name = 'fake'

    def json(self, system, data, schema, max_tokens=0, think=False):
        ids = [int(i) for i in re.findall(r'^\[(\d+)\]', data['script_part'], re.M)]
        return {'moments': [
            {'line': ids[0], 'why': 'who', 'template': 'cutout_hero', 'mode': 'full', 'word': 'Edison', 'label': 'nikaala gaya',
             'assets': [{'kind': 'person', 'query': 'thomas edison portrait', 'name': 'Thomas Edison'}]},
            {'line': ids[2], 'why': 'tries', 'template': 'object_drop', 'mode': 'full', 'title': 'Koshish', 'value': '1000',
             'assets': [{'kind': 'object', 'query': 'old light bulb', 'name': ''}]},
            {'line': ids[3], 'why': 'made up', 'template': 'spotlight', 'mode': 'full', 'title': 'Genius',
             'assets': [{'kind': 'person', 'query': 'elon musk', 'name': 'Elon Musk'}]},           # never said: dropped
            {'line': ids[4], 'why': 'light', 'template': 'collage', 'mode': 'full', 'title': 'Roshni', 'items': ['Bulb', 'Ghar'],
             'assets': [{'kind': 'object', 'query': 'glowing bulb', 'name': ''}, {'kind': 'photo', 'query': 'house night', 'name': ''}]}]}

    def close(self):
        pass


class FakeFinder:
    """Makes a cut-out (a disc on transparency) or a photo locally instead of searching the web."""
    def __init__(self, root, progress=print, use_ai='auto', check=True):
        pass

    def describe(self):
        return 'fake pictures'

    def find(self, asset, folder, stem, want_cut, seconds=5, orientation='portrait', size=(1080, 1920)):
        if 'house' in asset.query:
            asset.error = 'no fitting picture found'            # one picture is missing -> the scene adapts
            return asset
        image = Image.new('RGBA', (400, 500), (0, 0, 0, 0) if want_cut else (90, 120, 160, 255))
        if want_cut:
            yy, xx = np.mgrid[:500, :400]
            a = np.asarray(image).copy()
            a[((xx - 200) ** 2 + (yy - 250) ** 2) < 150 ** 2] = (200, 170, 90, 255)
            image = Image.fromarray(a)
        target = folder / 'assets' / f'{stem}.png'
        target.parent.mkdir(parents=True, exist_ok=True)
        image.save(target)
        asset.file, asset.cutout, asset.source = f'assets/{target.name}', want_cut, 'fake'
        return asset

    def make_ai(self, progress):
        pass

    def close(self):
        pass


def edge_ready():
    try:
        from hinglish_motion.render import SceneRenderer
        SceneRenderer(1080, 1080).close()
        return True
    except Exception:
        return False


class PlanRulesTest(unittest.TestCase):
    def test_numbers_must_be_said_and_scenes_need_their_assets(self):
        part = lines_of(['Price 60 rupees tha', 'Phir sab badal gaya', 'Aur kuch nahi hua', 'Yeh end hai'])
        check = plan_rules(part, {3})
        rules = [p.rule for p in check({'moments': [{'line': 1, 'template': 'big_number', 'mode': 'full', 'value': '40',
                                                     'label': 'x', 'assets': []}]})]
        self.assertIn('motion.no_invented_numbers', rules)
        rules = [p.rule for p in check({'moments': [{'line': 0, 'template': 'cutout_hero', 'mode': 'full', 'word': 'Price',
                                                     'assets': []}]})]
        self.assertIn('motion.assets', rules)                     # a cut-out scene without a picture is not allowed
        self.assertFalse([p for p in check({'moments': [{'line': 0, 'template': 'object_drop', 'mode': 'full', 'title': 'Price',
                          'value': '60', 'assets': [{'kind': 'object', 'query': 'rupee notes', 'name': ''}]}]}) if p.hard])
        self.assertTrue(has_number('paanch baar champion'))
        self.assertFalse(has_number('sab badal gaya'))

    def test_people_only_when_talked_about(self):
        self.assertTrue(name_said('Thomas Edison', 'phir edison ne bulb banaya'))
        self.assertFalse(name_said('Elon Musk', 'phir edison ne bulb banaya'))
        part = lines_of(['Edison ne bulb banaya', 'Sab log hanse', 'Phir roshni hui'])
        rules = [p.rule for p in plan_rules(part, {2})({'moments': [{'line': 1, 'template': 'spotlight', 'mode': 'full',
                 'title': 'X', 'assets': [{'kind': 'person', 'query': 'elon musk', 'name': 'Elon Musk'}]}]})]
        self.assertIn('motion.no_invented_people', rules)

    def test_repair_drops_invented_people_and_fixes_counts(self):
        part = lines_of(['Edison ka pehla din', 'Doosri line 5 baar', 'Teesri line', 'Aakhri line'])
        answer, fixes = plan_repair(part, {3}, 4)({'moments': [
            {'line': 0, 'template': 'spotlight', 'mode': 'full', 'title': 'A very long title that will not fit',
             'assets': [{'kind': 'person', 'query': 'edison portrait', 'name': 'Thomas Edison'}]},
            {'line': 1, 'template': 'collage', 'mode': 'full', 'items': ['A', 'B', 'C'],
             'assets': [{'kind': 'object', 'query': 'bulb', 'name': ''}]},                  # 1 picture: becomes a cut-out
            {'line': 2, 'template': 'cutout_hero', 'mode': 'full', 'word': 'Musk',
             'assets': [{'kind': 'person', 'query': 'elon musk', 'name': 'Elon Musk'}]},    # not said: no picture -> dropped
            {'line': 3, 'template': 'end_card', 'mode': 'x', 'title': 'Bye', 'assets': []}]})
        kept = {m['line']: m for m in answer['moments']}
        self.assertEqual(sorted(kept), [0, 1, 3])
        self.assertLessEqual(len(kept[0]['title']), 22)
        self.assertEqual(kept[1]['template'], 'cutout_hero')
        self.assertEqual(kept[3]['mode'], 'full')
        self.assertTrue(any('line 2' in f for f in fixes))


class TimingTest(unittest.TestCase):
    def test_modes(self):
        self.assertEqual(pipeline.scene_mode('collage', 'overlay', 'auto', True), 'full')      # does not work over video
        self.assertEqual(pipeline.scene_mode('object_drop', 'overlay', 'auto', True), 'overlay')
        self.assertEqual(pipeline.scene_mode('stamp', 'overlay', 'auto', False), 'full')      # no video to put it on

    def test_key_moments_never_overlap_and_the_full_video_is_all_scenes(self):
        lines = lines_of(['one two three four', 'five six seven', 'eight nine ten', 'eleven twelve', 'thirteen'], 2.0)
        scenes = [{'index': 1, 'line': 1, 'start': 2.0, 'template': 'cutout_hero', 'mode': 'full', 'data': {}},
                  {'index': 2, 'line': 2, 'start': 4.5, 'template': 'stamp', 'mode': 'overlay', 'data': {}},
                  {'index': 3, 'line': 4, 'start': 8.0, 'template': 'quote', 'mode': 'full', 'data': {}, 'removed': True}]
        pipeline.set_durations(scenes, lines, 10.6)
        self.assertLessEqual(scenes[0]['start'] + scenes[0]['duration'], scenes[1]['start'])
        pipeline.set_durations(scenes, lines, 10.6, full=True)
        self.assertEqual(scenes[0]['start'], 0.0)                                      # the video opens on a scene
        self.assertAlmostEqual(scenes[0]['duration'], 4.5)
        self.assertAlmostEqual(scenes[1]['start'] + scenes[1]['duration'], 10.6)
        for fps in (30, 25, 29.97):
            segments = pipeline.standalone_segments(scenes, 10.6, fps)
            self.assertEqual(sum(f for _, f in segments), round(10.6 * fps))
            self.assertEqual([s['index'] for s, _ in segments], [1, 2])                # no captions, no removed scene

    def test_missing_pictures_change_the_scene_not_leave_it_empty(self):
        s = {'template': 'collage', 'data': {'title': 'Roshni', 'items': ['Bulb', 'Ghar']},
             'assets': [{'file': 'a.png', 'cutout': True}, {'file': ''}], 'assets_all': [{'file': 'a.png'}, {'file': ''}]}
        self.assertEqual(pipeline.fallback(s)['template'], 'cutout_hero')
        s = {'template': 'spotlight', 'data': {'title': 'Genius'}, 'assets': [{'file': ''}], 'assets_all': [{'file': ''}]}
        self.assertEqual(pipeline.fallback(s)['template'], 'headline')

    def test_cutout_helpers(self):
        image = Image.new('RGBA', (100, 100), (0, 0, 0, 0))
        image.paste((255, 0, 0, 255), (30, 30, 70, 70))
        self.assertTrue(has_alpha(image) and cutout_ok(image))
        self.assertLess(trim(image).size[0], 60)
        self.assertFalse(cutout_ok(Image.new('RGBA', (50, 50), (1, 2, 3, 255))))


@unittest.skipUnless(edge_ready(), 'Microsoft Edge / Chrome is needed to render')
class RenderTest(unittest.TestCase):
    def test_script_run_builds_scenes_from_pictures_and_rebuilds(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with mock.patch('hinglish_visuals.brain.open_brain', lambda *a, **k: FakeBrain()), \
                    mock.patch('hinglish_motion.assets.AssetFinder', FakeFinder):
                page = pipeline.run(root, None, SCRIPT, MotionSettings(aspect='1:1'), lambda m: None)
            folder = page.parent
            project = json.loads((folder / 'motion-project.json').read_text(encoding='utf-8'))
            self.assertTrue(project['full'])
            templates = [s['template'] for s in project['scenes']]
            self.assertEqual(templates, ['cutout_hero', 'object_drop', 'cutout_hero'])   # Musk dropped; collage adapted
            self.assertTrue(all(s['assets'] and (folder / s['assets'][0]['file']).is_file() for s in project['scenes']))
            self.assertTrue((folder / 'MOTION_GRAPHICS.mp4').is_file())
            from hinglish_eval.specs import evaluate
            checks = {c.rule: c for e in evaluate(folder) for c in e.checks}
            self.assertTrue(all(c.passed for c in checks.values() if c.hard), [c for c in checks.values() if not c.passed])
            old = {s['index']: s['file'] for s in project['scenes']}
            with mock.patch.object(pipeline, 'render_standalone') as full:
                result = pipeline.rebuild_project(folder / 'motion-project.json',
                                                  {'scenes': {'1': {'data': {'word': 'Genius'}}}}, lambda m: None)
            full.assert_called_once()
            project = json.loads((folder / 'motion-project.json').read_text(encoding='utf-8'))
            files = {s['index']: s['file'] for s in project['scenes']}
            self.assertEqual(result['rendered'], 1)
            self.assertNotEqual(files[1], old[1])
            self.assertEqual(files[2], old[2])                                      # untouched scenes are kept
            self.assertIn('Genius', (folder / 'report.html').read_text(encoding='utf-8'))


if __name__ == '__main__':
    unittest.main()
