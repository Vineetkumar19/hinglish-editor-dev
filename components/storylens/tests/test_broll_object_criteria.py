"""Fresh request criteria, with raw negative verdicts remaining negative."""
import copy
import unittest
from pathlib import Path
from unittest.mock import patch,Mock
from PIL import Image
from tests import test_broll_residential_verdict_replay as replay


class ObjectCriteriaTests(unittest.TestCase):
    def test_capture_context_is_wider_but_cannot_excuse_bad_active_frames(self):
        from hinglish_broll.verify import Checker
        f=replay.ResidentialVerdictReplayTests();f.setUp()
        slot=copy.deepcopy(f.observed['slot']);slot.update(visual='refrigerator',subject='')
        raw=copy.deepcopy(f.raw);raw['capture_type']='live_action'
        checker=Checker.__new__(Checker);checker.model=Mock(name='test-only')
        checker.model.name='test-only';checker.model.look.return_value=raw
        def frames(path,times,size):return [(t,Image.new('RGB',(24,40),'black')) for t in times]
        with patch('hinglish_broll.library.read_frames',side_effect=frames),patch('hinglish_broll.library.probe_video',return_value=(8.,1080,1920)):
            result=checker.check(Path('synthetic-not-read.mp4'),1.,.4,slot,'video')
        images,prompt,schema=checker.model.look.call_args.args
        self.assertEqual(len(images),5)
        self.assertIn('first THREE',prompt);self.assertIn('capture context only',prompt)
        self.assertEqual(schema['properties']['frame_checks']['maxItems'],3)
        self.assertFalse(result['passed'])
        self.assertEqual(result['capture_context_times'],[0.,2.4])

    def test_object_request_defines_aggregate_flags_without_approving_a_negative(self):
        f=replay.ResidentialVerdictReplayTests();f.setUp()
        slot=copy.deepcopy(f.observed['slot']);slot.update(visual='refrigerator',subject='')
        raw=copy.deepcopy(f.raw)
        raw.update(related=False,seen='A refrigerator interior with milk.',identity_compatible=True,
                   real_clear_footage=True,no_intrusive_text=True)
        raw['frame_checks']=[dict(subject_visible=True,real_clear_footage=True,
                                 no_dominant_presenter=True,no_intrusive_overlay=True) for _ in range(3)]
        checker,result=f.replay(slot=slot,answer=raw)
        prompt=checker.model.look.call_args.args[1]
        self.assertIn('related:',prompt)
        self.assertIn('identity_compatible:',prompt)
        self.assertIn('subject_visible:',prompt)
        self.assertFalse(result['passed'])
        self.assertFalse(result['related'])
        self.assertEqual(checker.model.look.call_count,1)

    def test_explicit_talking_presenter_flag_maps_without_losing_a_negative(self):
        f=replay.ResidentialVerdictReplayTests();f.setUp()
        slot=copy.deepcopy(f.observed['slot']);slot.update(visual='refrigerator',subject='')
        raw=copy.deepcopy(f.raw)
        raw.update(related=True,seen='A refrigerator interior with milk.',identity_compatible=True,
                   real_clear_footage=True,no_intrusive_text=True,capture_type='live_action')
        raw['frame_checks']=[dict(subject_visible=True,real_clear_footage=True,
             no_unrelated_talking_presenter=True,no_intrusive_overlay=True) for _ in range(3)]
        checker,result=f.replay(slot=slot,answer=raw)
        schema=checker.model.look.call_args.args[2]
        self.assertIn('no_unrelated_talking_presenter',schema['properties']['frame_checks']['items']['required'])
        self.assertTrue(result['passed'])
        self.assertEqual(result['raw_frame_checks'],raw['frame_checks'])
        raw['frame_checks'][1]['no_unrelated_talking_presenter']=False
        _,negative=f.replay(slot=slot,answer=raw)
        self.assertFalse(negative['passed'])

    def test_object_approval_requires_explicit_filmed_capture_not_rendered_design(self):
        f=replay.ResidentialVerdictReplayTests();f.setUp()
        slot=copy.deepcopy(f.observed['slot']);slot.update(visual='wardrobe',subject='')
        raw=copy.deepcopy(f.raw)
        raw.update(related=True,seen='A wardrobe design.',identity_compatible=True,
                   real_clear_footage=True,no_intrusive_text=True)
        raw['frame_checks']=[dict(subject_visible=True,real_clear_footage=True,
             no_unrelated_talking_presenter=True,no_intrusive_overlay=True) for _ in range(3)]
        for capture in (None,'cgi_or_animation','still_image_or_slideshow','uncertain'):
            with self.subTest(capture=capture):
                answer=copy.deepcopy(raw)
                if capture:answer['capture_type']=capture
                checker,result=f.replay(slot=slot,answer=answer)
                self.assertFalse(result['passed'])
                schema=checker.model.look.call_args.args[2]
                self.assertIn('capture_type',schema['required'])
                self.assertIn('cgi_or_animation',schema['properties']['capture_type']['enum'])
                self.assertEqual(checker.model.look.call_count,1)


if __name__=='__main__':unittest.main()
