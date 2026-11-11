import copy
import unittest
from unittest.mock import Mock,patch
from PIL import Image

from hinglish_broll.subjects import anchored_object,cached_scene_matches
from hinglish_broll.keywords import physical_keyword,discover
from hinglish_broll.verify import Checker,CheckUnavailable


class ExactSubjectTests(unittest.TestCase):
    def test_shared_search_clients_receive_a_fresh_bounded_budget_for_every_keyword(self):
        from types import SimpleNamespace
        from hinglish_broll.pipeline import gather_candidates
        from hinglish_visuals.websearch import WebSearch
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as temp:
            web=WebSearch(Path(temp),progress=lambda _:None)
            calls=[]
            class Client:
                name='web'
                def search(self,*args):
                    calls.append(web.subject_calls)
                    web.subject_calls=8
                    return []
            client=Client();client.web=web
            timeline=SimpleNamespace(width=720,height=1280)
            for subject in ('bed','wardrobe','water heater'):
                slot=SimpleNamespace(duration=1,moment=SimpleNamespace(queries=[subject],subject='',visual=subject))
                gather_candidates(slot,None,None,[client],'portrait',timeline,6,None,lambda _:None)
            self.assertEqual(calls,[0,0,0])

    def test_recent_failed_web_source_does_not_start_another_downloader(self):
        import tempfile,time,hashlib,json
        from pathlib import Path
        from hinglish_broll.web_download import download
        from hinglish_broll.stock import Candidate
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);item=Candidate('web','one','Video',10,720,1280,download_url='https://example.org/video')
            file=root/'cache/broll/unavailable'/(hashlib.sha256(item.download_url.encode()).hexdigest()+'.json')
            file.parent.mkdir(parents=True);file.write_text(json.dumps({'time':time.time()}))
            with patch('multiprocessing.get_context') as processes:
                with self.assertRaisesRegex(ValueError,'recently failed'):download(root,item,1)
                processes.assert_not_called()

    def test_spoken_object_cannot_be_broadened_to_a_room_or_another_object(self):
        self.assertEqual(physical_keyword({'keyword':'kitchen appliances','queries':['kitchen']},'no fridge')[0],'refrigerator')
        self.assertEqual(physical_keyword({'keyword':'furniture','queries':['furniture']},'bed sofa')[0],'sofa')
        self.assertEqual(anchored_object('washing machine'),'washing machine')
        self.assertEqual(anchored_object('fridge washing'),'')
        self.assertEqual(physical_keyword({'keyword':'flat search frustration','queries':['flat availability problem']})[0],'apartment interior')

    def test_discovery_grounds_fridge_to_its_actual_word_time(self):
        from hinglish_cut.model import Word
        from hinglish_broll.phrases import Phrase
        model=Mock();model.json.return_value={'keywords':[{'word_index':1,'keyword':'kitchen appliances','queries':['kitchen appliances'],'identity':''}]}
        slots=discover(model,[Phrase(0,1,2,'no fridge')],[Word('no',1,1.2),Word('fridge',1.3,2)],{},progress=lambda _:None)
        self.assertEqual(slots[0].moment.visual,'refrigerator');self.assertEqual(slots[0].start,1.3)
        self.assertEqual(model.json.call_count,1)

    def test_old_bank_cannot_seed_unrelated_keyword_checks(self):
        self.assertFalse(cached_scene_matches('A woman with an umbrella in the rain','refrigerator'))
        self.assertFalse(cached_scene_matches('The Taj Mahal and gardens','bed'))
        self.assertFalse(cached_scene_matches('A stove inside a kitchen','refrigerator'))
        self.assertTrue(cached_scene_matches('An open fridge with shelves','refrigerator'))
        self.assertTrue(cached_scene_matches('A small room with simple furniture','apartment interior'))

    def test_transliterated_household_nouns_and_geyser_sense_use_physical_english(self):
        self.assertEqual(physical_keyword({'keyword':'almaari','queries':['almaari','wardrobe']},'almaari')[0],'wardrobe')
        self.assertEqual(physical_keyword({'keyword':'geyser','queries':['geyser']},'geyser','flat mein bed aur geyser')[0],'water heater')
        self.assertEqual(physical_keyword({'keyword':'geyser','queries':['geyser']},'geyser','Yellowstone geothermal hot spring')[0],'geyser')
        self.assertEqual(physical_keyword({'keyword':'chaar divaaren','queries':['four walls']})[0],'empty room')

    def test_compound_object_starts_at_its_first_spoken_word(self):
        from hinglish_cut.model import Word
        from hinglish_broll.phrases import Phrase
        model=Mock();model.json.return_value={'keywords':[{'word_index':1,'keyword':'washing machine','queries':['washing machine'],'identity':'','meaning':'A household clothes washer'}]}
        slots=discover(model,[Phrase(0,1,2,'washing machine')],[Word('washing',1,1.4),Word('machine',1.4,2)],{},progress=lambda _:None)
        self.assertEqual(slots[0].start,1)
        self.assertEqual(slots[0].moment.meaning,'A household clothes washer')

    def test_high_generic_similarity_is_not_a_strong_subject_match(self):
        from hinglish_broll.stock import Candidate
        from hinglish_broll.ranker import acceptable
        c=Candidate('pixabay','one','interior',10,720,1280,score=.34,specific=-.1)
        self.assertFalse(acceptable(c));c.specific=.02;self.assertTrue(acceptable(c))


class ActualFrameTests(unittest.TestCase):
    def good(self):
        return {'seen':'A real refrigerator with open doors and shelves','related':True,'context_compatible':True,'real_clear_footage':True,
            'no_intrusive_text':True,'identity_compatible':True,'reason':'The requested object is clearly visible',
            'frame_checks':[dict(subject_visible=True,real_clear_footage=True,no_dominant_presenter=True,no_intrusive_overlay=True) for _ in range(3)]}

    def check(self,answer,slot=None):
        checker=Checker.__new__(Checker);checker.model=Mock();checker.model.name='local vision';checker.model.look.return_value=answer
        with patch('hinglish_broll.library.read_frames',return_value=[(t,Image.new('RGB',(100,100))) for t in (.15,.5,.85)]):
            return checker.check('source.mp4',0,1,slot or {'review_options':True,'visual':'refrigerator','text':'fridge'},'video')

    def test_visible_stove_cannot_pass_as_fridge_even_if_a_boolean_says_related(self):
        answer=self.good();answer['seen']='A gas stove and a kettle inside a kitchen'
        self.assertFalse(self.check(answer)['passed'])
        self.assertTrue(self.check(self.good())['passed'])

    def test_one_presenter_overlay_animation_or_unrelated_frame_vetoes_the_window(self):
        for field in ('subject_visible','real_clear_footage','no_dominant_presenter','no_intrusive_overlay'):
            answer=self.good();answer['frame_checks'][0][field]=False
            self.assertFalse(self.check(answer)['passed'],field)

    def test_partial_frame_answer_cannot_approve_video(self):
        answer=self.good();answer['frame_checks']=answer['frame_checks'][:2]
        self.assertFalse(self.check(answer)['passed'])

    def test_literal_match_cannot_override_a_failed_context_sense(self):
        answer=self.good();answer.update(seen='A natural geyser with steam rising',context_compatible=False)
        result=self.check(answer,{'review_options':True,'visual':'geyser','meaning':'A bathroom hot water heater'})
        self.assertFalse(result['passed']);self.assertFalse(result['fits_spoken_meaning'])

    def test_unambiguous_object_meaning_is_derived_from_all_frame_evidence(self):
        answer=self.good();answer['context_compatible']=False
        self.assertTrue(self.check(answer)['passed'])
        answer['no_intrusive_text']=False
        self.assertFalse(self.check(answer)['passed'])

    def test_model_outage_is_a_task_failure_not_fifteen_bad_candidate_checks(self):
        checker=Checker.__new__(Checker);checker.model=Mock();checker.model.look.side_effect=ConnectionError('local engine disconnected')
        with self.assertRaises(CheckUnavailable) as error:checker._look([], 'inspect', {})
        self.assertIn('disconnected',error.exception.stderr);self.assertEqual(checker.model.look.call_count,1)


if __name__=='__main__':unittest.main()
