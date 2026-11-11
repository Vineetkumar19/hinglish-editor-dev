import unittest
import xml.etree.ElementTree as ET
from pathlib import Path
from PIL import ImageChops
from hinglish_captions.caption_two import motion_state
from hinglish_captions.caption_three import decorations_only
from hinglish_captions.core import CaptionCue, CaptionWord
from hinglish_captions.renderer import draw_editor_caption
from hinglish_app.premiere_decorations import attach


class CaptionFadeFramesTests(unittest.TestCase):
    def test_saved_caption_two_report_receives_fade_engine(self):
        from hinglish_app.presentation import caption_html
        html=b'<head></head><body><script>// Caption 2 keeps the measured row roles\nOLD_SLIDE_ENGINE</script></body>'
        updated=caption_html(html,Path('sample'),'test-token').decode('utf8')
        self.assertNotIn('OLD_SLIDE_ENGINE',updated)
        self.assertIn('"main_entrance": "rise_pop_settle"',updated)
        self.assertNotIn('main&&slide?m.main_slide',updated)

    def test_every_row_has_the_same_rise_pop_and_settle_without_lateral_slide(self):
        times=(0,.06,.12,.18,.24,.5)
        frames=[motion_state(t,main=True,slide=True) for t in times]
        self.assertEqual(frames,[motion_state(t,main=False) for t in times])
        self.assertTrue(all(f[1]==0 for f in frames))
        self.assertEqual(frames[0][2],16)
        self.assertLess(motion_state(.26,main=True)[2],0)
        self.assertEqual(frames[-1][2:],(0,0))
        from hinglish_captions.caption_two import word_scale
        self.assertGreater(word_scale(0),1)
        self.assertEqual(word_scale(.5),1)
        self.assertEqual(frames[0][0],0)
        self.assertEqual(frames[-1][0],1)
        self.assertTrue(all(a[0]<b[0] for a,b in zip(frames[:4],frames[1:5])))

    def test_frame_layer_has_no_words_and_uses_saved_placement(self):
        cue=CaptionCue(tuple(CaptionWord(w,i*.2,i*.2+.2) for i,w in enumerate('The Taj Mahal stands beside'.split())),0,3)
        def draw(layout):return draw_editor_caption(360,640,cue,1.5,'caption_3','template',layout,'phrase')
        layout={'x':.5,'y':.42,'size':1}
        original=draw(layout)
        with decorations_only():
            frame=draw(layout)
            moved=draw(dict(layout,x=.6))
        # The owner-selected serif reference has no dotted selection frame.
        # A plain recipe must not silently retain its superseded decoration.
        self.assertIsNone(frame.getbbox())
        self.assertIsNone(moved.getbbox())
        self.assertIsNone(ImageChops.difference(original,draw(layout)).getbbox())

    def test_premiere_frame_track_is_separate_transparent_media(self):
        tree=ET.parse('hinglish_app/templates/premiere-caption-1.xml').getroot()
        attach(tree,{'width':720,'height':1280,'media':{'duration':10,'fps':60}},Path('D:/sample-frames.mov'),254016000000)
        tracks=next(n for n in tree if n.get('ObjectID')=='164').find('TrackGroup/Tracks')
        self.assertEqual([int(t.get('Index')) for t in tracks],[0,1,2])
        media=next(n for n in tree if n.tag=='Media' and n.findtext('Title')=='Caption 3 reference text annotations')
        self.assertIsNone(media.find('AudioStream'))
        stream=next(n for n in tree if n.get('ObjectID')==media.find('VideoStream').get('ObjectRef'))
        self.assertEqual(stream.findtext('IgnoreAlpha'),'false')
        self.assertEqual(stream.findtext('Duration'),'2540160000000')
        self.assertTrue(all(n.get('ObjectRef') in {x.get('ObjectID') for x in tree.iter()} for n in tree.iter() if n.get('ObjectRef')))
