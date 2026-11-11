import tempfile
import unittest
from pathlib import Path

import av
import numpy as np
from PIL import Image, ImageDraw

from hinglish_visuals.presentation import motion, overlay_frame
from hinglish_visuals.behind import occlude
from hinglish_visuals.gather import matches_event
from hinglish_visuals.planner import VisualMoment, fits_kind, resolve_entity
from hinglish_visuals.web import Entity, Media


class PresentationTests(unittest.TestCase):
    def test_visual_duration_matches_placed_frame_boundaries(self):
        from fractions import Fraction
        from types import SimpleNamespace
        from unittest.mock import patch
        from hinglish_visuals.pipeline import render_slot
        from hinglish_broll.xml_export import build_track
        with tempfile.TemporaryDirectory() as folder:
            folder=Path(folder);picture=folder/'photo.png'
            Image.new('RGB',(160,240),'green').save(picture)
            timeline=SimpleNamespace(width=160,height=240,fps=Fraction(30))
            # The live trophy slot rounded to 54 placed frames but only 53 source frames.
            slot={'index':0,'start':7.62,'end':9.4,'display':'fullscreen','label':'Trophy'}
            media=Media('image','web','trophy','Trophy','https://example.com/photo.png',path=str(picture))
            clip,_=render_slot(folder,folder,timeline,slot,media,None,'cpu')
            with av.open(str(clip)) as video:frames=sum(1 for _ in video.decode(video=0))
            expected=round(slot['end']*timeline.fps)-round(slot['start']*timeline.fps)
            self.assertEqual(frames,expected)
            track=build_track([{'path':str(clip),'start':slot['start'],'end':slot['end'],
                'source_duration':float(Fraction(frames,30))}],timeline.fps,160,240)
            self.assertEqual(int(track.find('clipitem/out').text),expected)

    def test_single_search_hit_still_needs_contextual_identity_check(self):
        self.assertFalse(fits_kind({'description': 'Indian businessperson (born 1982)'}, 'place'))
        class Web:
            def search_entities(self, name):
                return [{'id': 'Q1', 'label': 'Night Life', 'description': 'song by Foreigner'}]
            def entity(self, *args):
                raise AssertionError('A rejected song must not become a city-nightlife subject')
        class Brain:
            def json(self, system, data, schema, **kwargs):
                return {'id': ''}
        self.assertIsNone(resolve_entity(Brain(), Web(),
            {'key': 'nightlife', 'name': 'Night Life', 'kind': 'thing', 'about': 'City activity after dark'},
            {'topic': 'The city has no nightlife'}))

    def test_every_overlay_keeps_moving_and_has_transparent_endpoints(self):
        art = Image.new('RGBA', (80, 100))
        ImageDraw.Draw(art).ellipse((10, 4, 70, 96), fill='white')
        for rise in (False, True):
            frames = [np.asarray(overlay_frame(art, (20, 140), (180, 320), t, 3, rise))
                      for t in (0, .8, 1.4, 2, 3)]
            self.assertEqual(frames[0][..., 3].max(), 0)
            self.assertEqual(frames[-1][..., 3].max(), 0)
            self.assertGreater(np.abs(frames[1].astype(float) - frames[2]).sum(), 0)
            self.assertGreater(np.abs(frames[2].astype(float) - frames[3]).sum(), 0)
        values = np.array([motion(t, 3)[:2] for t in np.linspace(0, 3, 3001)])
        self.assertLess(np.abs(np.diff(values, axis=0)).max(), .008)

    def test_foreground_hides_only_the_visual_and_preserves_soft_edges(self):
        art = Image.new('RGBA', (3, 1), (255, 0, 0, 200))
        mask = Image.fromarray(np.array([[0, 128, 255]], dtype=np.uint8))
        result = np.asarray(occlude(art, mask))
        self.assertEqual(result[0, :, 3].tolist(), [200, 100, 0])
        self.assertEqual(result[0, :, 0].tolist(), [255, 255, 255])

    def test_event_year_and_final_cannot_be_substituted(self):
        entity = Entity('match', 'World Cup Final 2020', 'event')
        moment = VisualMoment(0, 'World Cup Final 2020', ['World Cup Final 2020'], 3, 'final', '', 'match')
        def candidate(title):
            return Media('image', 'web', title, title, 'https://example.com/p.jpg', official=True)
        self.assertFalse(matches_event(candidate('World Cup Final 2019'), moment, entity))
        self.assertFalse(matches_event(candidate('World Cup semi-final 2020'), moment, entity))
        self.assertFalse(matches_event(candidate('World Cup trophy'), moment, entity))
        # Metadata matching is necessary, but does not on its own verify an event exists.
        self.assertTrue(matches_event(candidate('World Cup Final 2020'), moment, entity))

    def test_audio_black_contains_no_original_picture_and_keeps_audio(self):
        from tests.test_visuals import write_video
        from hinglish_cut.model import Cut, Media as Source
        from hinglish_cut.xml_export import export_xml
        from hinglish_broll.timeline import parse_xmeml
        from hinglish_visuals.diagnostic import black_timeline
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = write_video(root / 'talk.mp4', 1, 144, 256)
            info = Source('source', str(source), 1, '30', 144, 256, 1, 48000)
            export_xml(root / 'source.xml', [Cut('source', 0, 30, 0)], {'source': info}, None)
            result = black_timeline(parse_xmeml(root / 'source.xml'), root, lambda _: None)
            with av.open(result.clips[0].path) as inp:
                frames = [f.to_ndarray(format='rgb24') for f in inp.decode(video=0)]
                self.assertEqual(len(frames), 30)
                self.assertLessEqual(max(f.max() for f in frames), 1)
            with av.open(result.clips[0].path) as inp:
                sound = np.concatenate([f.to_ndarray().reshape(-1) for f in inp.decode(audio=0)])
                self.assertGreater(np.std(sound), .02)
            self.assertTrue(source.is_file())


if __name__ == '__main__':
    unittest.main()
