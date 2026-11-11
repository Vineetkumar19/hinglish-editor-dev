import copy
import gzip
import json
import tempfile
import unittest
from fractions import Fraction
from pathlib import Path
from unittest.mock import patch
import xml.etree.ElementTree as ET

from hinglish_broll.pipeline import _apply_edits, render_choice
from hinglish_broll.ranker import choose
from hinglish_broll.placement import Moment, Slot
from hinglish_broll.stock import Candidate
from hinglish_broll.internet import exact_subject_match
from hinglish_broll.xml_export import export_broll_xml
from hinglish_broll.timeline import parse_xmeml
from hinglish_cut.xml_export import export_xml
from hinglish_cut.model import Media, Cut


class EditableBrollTests(unittest.TestCase):
    def test_cached_internet_search_bank_requires_pixel_approval_and_excludes_creator_takes(self):
        from hinglish_broll.pipeline import verified_internet_sources
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);folder=root/'output/broll/run/001-source';folder.mkdir(parents=True)
            footage=root/'stock.mp4';footage.write_bytes(b'cached footage')
            base=Candidate('pixabay','pixabay:1','bar counter',12,1280,720,path=str(footage)).to_dict()
            slots=[{'chosen':base,'checks':[{'id':'pixabay:1','passed':True}]},
                   {'chosen':dict(base,id='pixabay:2'),'checks':[]},
                   {'chosen':dict(base,id='library:take',source='library'),
                    'checks':[{'id':'library:take','passed':True}]}]
            (folder/'broll-project.json').write_text(json.dumps({'slots':slots}))
            self.assertEqual([c.id for c in verified_internet_sources(root)],['pixabay:1'])

    def test_generic_venue_labels_are_not_treated_as_named_identities(self):
        from hinglish_broll.subjects import specific_subject
        for label in ('Late-night cafe','Empty nightclub interior','club, launch, cafe',
                      'Night highway with closed shops','Indian city street at night',
                      'person asleep in bed','real people enjoying/celebrating'):
            self.assertEqual(specific_subject(label),'',label)
        self.assertEqual(specific_subject('Meenakshi temple'),'Meenakshi temple')
        self.assertEqual(specific_subject('Rohit Sharma'),'Rohit Sharma')

    def test_illustrative_venue_check_uses_the_mentioned_subject_not_an_empty_hint(self):
        from PIL import Image
        from unittest.mock import MagicMock
        from hinglish_broll.verify import Checker
        check=Checker.__new__(Checker);check.model=MagicMock();check.model.name='local judge'
        check.model.look.return_value={'seen':'a real nightclub dancefloor with dancers',
            'depicts_mentioned_subject':True,'useful_illustration':True,'identity_compatible':True,
            'real_clear_footage':True,'no_intrusive_text':True,'reason':'Illustrates the mentioned club'}
        with patch('hinglish_broll.library.read_frames',return_value=[(1,Image.new('RGB',(128,128)))]):
            result=check.check('club.mp4',0,2,{'text':'koi club nahin','context':'koi club nahin, late night cafe bhool jao',
                'visual':'Empty nightclub with no people','direction':'Show the mentioned venues as illustrative stock.'},'video')
        self.assertTrue(result['passed'])
        self.assertNotIn('Empty nightclub with no people',check.model.look.call_args.args[1])
        self.assertIn('depicts_mentioned_subject',check.model.look.call_args.args[2]['properties'])
        self.assertIn('coverage list applies across the edit',check.model.look.call_args.args[1])

    def test_venue_search_backups_reach_pixel_review_despite_weak_thumbnails(self):
        from hinglish_broll.internet import stock_keyword
        from hinglish_broll.ranker import venue_backups
        self.assertEqual(stock_keyword('bar interior India'),'bar')
        self.assertEqual(stock_keyword('lounge in India'),'bar')
        self.assertEqual(stock_keyword('cricket club practice'),'cricket')
        cafe=Candidate('pixabay','c','cafe, restaurant, people sitting chatting',20,1280,720,score=.2)
        street=Candidate('pixabay','s','daytime street market',20,1280,720,score=.5)
        lesson=Candidate('pixabay','l','cafe vocabulary lesson',20,1280,720,score=.5)
        self.assertEqual(venue_backups(['cafe at night India'],[street,lesson,cafe]),[cafe])

    def test_requested_count_preserves_distinct_venues_over_repeated_streets(self):
        from hinglish_broll.placement import cap_diverse_slots,scene_family
        slots=[Slot(Moment(i,'quiet city street',['street night'],3),i*4,i*4+2,'street') for i in range(4)]
        slots += [Slot(Moment(4,'nightclub interior',['nightclub'],2),20,22,'club'),
                  Slot(Moment(5,'cafe seating',['cafe'],2),26,28,'cafe')]
        kept=cap_diverse_slots(slots,5)
        self.assertEqual(len(kept),5)
        self.assertIn('cafe',[scene_family(s) for s in kept])
        self.assertIn('club',[scene_family(s) for s in kept])

    def test_candidate_picture_cache_reuses_vectors_but_not_a_different_encoder(self):
        from types import SimpleNamespace
        from unittest.mock import Mock
        from PIL import Image
        import numpy as np
        from hinglish_broll.ranker import score_stock
        with tempfile.TemporaryDirectory() as temp:
            folder=Path(temp);thumb=folder/'thumb.jpg';Image.new('RGB',(64,64),'gray').save(thumb)
            vision=SimpleNamespace(vector_cache=folder,vector_signature='encoder-v1',
                                   images=Mock(return_value=np.array([[1.,0.]],dtype=np.float32)))
            first=Candidate('pixabay','one','cafe',10,640,360,thumb=str(thumb))
            score_stock(vision,np.array([.8,.2]),[first])
            second=Candidate('pixabay','two','cafe',10,640,360,thumb=str(thumb))
            score_stock(vision,np.array([.3,.7]),[second])
            self.assertEqual(vision.images.call_count,1)
            self.assertAlmostEqual(second.score,.3)
            vision.vector_signature='encoder-v2'
            score_stock(vision,np.array([.3,.7]),[second])
            self.assertEqual(vision.images.call_count,2)

    def test_dark_opening_tries_a_readable_window_before_semantic_verification(self):
        from PIL import Image
        from hinglish_broll.verify import readable_window
        with patch('hinglish_broll.library.read_frames',side_effect=[
            [(2,Image.new('RGB',(270,480),(2,2,2)))],
            [(6,Image.new('RGB',(270,480),(80,80,80))),
             (12,Image.new('RGB',(270,480),(4,4,4)))]]):
            self.assertEqual(readable_window('source',25,2,1,270,480),5)
        with patch('hinglish_broll.library.read_frames',return_value=[(2,Image.new('RGB',(270,480),(2,2,2)))]):
            with self.assertRaisesRegex(ValueError,'too dark'):
                readable_window('source',25,2,1,270,480)

    def test_editorial_review_can_drop_filler_without_replacing_source_quotes(self):
        from hinglish_broll.planner import review_moments
        from unittest.mock import Mock
        physical={'id':4,'quote':'dukaanen band','meaning':'shops are shut','visual':'closed shop shutters',
                  'queries':['closed shops','shop shutters','shops night'],'priority':3,'subject':''}
        filler={**physical,'id':10,'quote':'main camera khol ke'}
        llm=Mock();llm.json.return_value={'reviews':[
            {**physical,'visual':'Valid. Looks appropriate.','queries':['nightlife definition'],
             'subject':'A person asking a question on a street','keep':True,'reason':'Direct visible detail'},
            {**filler,'keep':False,'reason':'The original presenter is already filming'},
            {**physical,'id':999,'keep':True,'reason':'Invented id'}]}
        result=review_moments(llm,{'phrases':[]},{'moments':[physical,filler]},3)
        self.assertEqual(result['moments'],[physical])

    def test_stock_animation_is_not_offered_as_filmed_broll(self):
        from hinglish_broll.stock import PixabayClient
        with tempfile.TemporaryDirectory() as temp:
            client=PixabayClient('test-key',temp)
            sizes={'small':{'url':'https://example.org/clip.mp4','width':640,'height':360}}
            from unittest.mock import Mock
            client._get=Mock(return_value={'hits':[
                {'id':1,'type':'animation','tags':'cafe loop','duration':10,'videos':sizes},
                {'id':2,'type':'film','tags':'closed shop','duration':10,'videos':sizes}]})
            clips=client.search('closed shop','portrait',270,480)
            self.assertEqual([c.id for c in clips],['pixabay:2'])
            self.assertEqual(client._get.call_args.args[1]['video_type'],'film')

    def test_planner_is_allowed_to_skip_nonvisual_reactions(self):
        from types import SimpleNamespace
        from hinglish_eval.model_rules import broll_moments
        phrases=[SimpleNamespace(id=0,text='aur kya hi karoon')]
        self.assertEqual(broll_moments(phrases,5)({'moments':[]}),[])

    def test_public_stock_page_keeps_advertised_media_and_attribution(self):
        from hinglish_broll.stock_pages import parse_page
        markup='''<script type="application/ld+json">{"@type":"VideoObject","name":"Empty street",
          "contentUrl":"https://cdn.example.org/street.mp4","thumbnailUrl":["/poster.jpg"],
          "duration":"PT12S","author":{"name":"Asha"},"width":1280,"height":720}</script>'''
        item=parse_page('https://example.org/street',markup)[0]
        self.assertEqual(item.duration,12)
        self.assertEqual(item.thumb,'https://example.org/poster.jpg')
        self.assertEqual(item.author,'Asha')
        self.assertEqual(parse_page('https://example.org/street','<script>fetch("private")</script>'),[])

    def test_pixel_checker_rejects_a_shared_topic_without_the_requested_scene(self):
        from PIL import Image
        from unittest.mock import MagicMock
        from hinglish_broll.verify import Checker
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'sky.jpg';Image.new('RGB',(100,100),'black').save(path)
            check=Checker.__new__(Checker);check.model=MagicMock();check.model.name='local visual judge'
            check.model.look.return_value={'seen':'a starry sky','matches_scene':False,'matches_action':False,
                'fits_spoken_meaning':False,'real_clear_footage':True,'no_intrusive_text':True,'reason':'No street visible'}
            with patch('hinglish_broll.library.read_frames',return_value=[(1,Image.new('RGB',(100,100)))]):
                verdict=check.check(path,0,2,{'text':'The streets are empty','visual':'empty city street at night',
                    'context':'After ten at night, there is no nightlife here.'},'video')
            self.assertFalse(verdict['passed'])
            self.assertIn('empty city street',check.model.look.call_args.args[1])
            self.assertIn('no nightlife here',check.model.look.call_args.args[1])

    def test_generic_description_contradiction_gets_one_local_recheck_but_named_identity_stays_strict(self):
        from PIL import Image
        from unittest.mock import MagicMock
        from hinglish_broll.verify import Checker
        for identity in ('','RCB'):
            with self.subTest(identity=identity):
                check=Checker.__new__(Checker);check.model=MagicMock();check.model.name='local judge'
                first={'seen':'A cricket stadium with stands and a green field','related':False,'context_compatible':True,
                       'identity_compatible':False,'real_clear_footage':True,'no_intrusive_text':True,
                       'reason':'A fixed camera shows a cricket stadium',
                       'frame_checks':[dict(subject_visible=True,real_clear_footage=True,no_dominant_presenter=True,no_intrusive_overlay=True) for _ in range(3)]}
                repaired={**first,'related':True,'identity_compatible':True,'reason':'It depicts the generic stadium subject'}
                check.model.look.side_effect=[first,repaired]
                with patch('hinglish_broll.library.read_frames',return_value=[(t,Image.new('RGB',(100,100))) for t in (.3,1,1.7)]):
                    verdict=check.check('clip.mp4',0,2,{'review_options':True,'visual':'cricket stadium','subject':identity},'video')
                self.assertEqual(check.model.look.call_count,1 if identity else 2)
                self.assertEqual(verdict['passed'],not bool(identity))

    def test_generic_recheck_cannot_automatically_approve_an_unrelated_video(self):
        from PIL import Image
        from unittest.mock import MagicMock
        from hinglish_broll.verify import Checker
        check=Checker.__new__(Checker);check.model=MagicMock();check.model.name='local judge'
        check.model.look.return_value={'seen':'A woman holding a camera','related':False,
            'identity_compatible':False,'real_clear_footage':True,'no_intrusive_text':True,'reason':'No cricket'}
        with patch('hinglish_broll.library.read_frames',return_value=[(t,Image.new('RGB',(100,100))) for t in (.3,1,1.7)]):
            verdict=check.check('clip.mp4',0,2,{'review_options':True,'visual':'cricket stadium','subject':''},'video')
        self.assertEqual(check.model.look.call_count,1)
        self.assertFalse(verdict['passed'])

    def project(self):
        return {'timeline':{'duration':12},'slots':[
            {'index':0,'start':2.,'end':4.,'source_in':2.,'source_duration':8.,'clip':'a.mp4'},
            {'index':1,'start':8.,'end':10.,'source_in':1.,'source_duration':6.,'clip':'b.mp4'}]}

    def test_trim_can_extend_within_handles_and_rejects_overlap_and_missing_footage(self):
        p=self.project();_apply_edits(p,{'0':{'start':1.5,'end':6.,'source_in':1.}})
        self.assertEqual(p['slots'][0]['end'],6.)
        for edit in ({'0':{'end':9.}}, {'0':{'source_in':7.}}, {'0':{'end':float('nan')}}, {'-1':{'start':0.}}):
            with self.assertRaises(ValueError):_apply_edits(copy.deepcopy(self.project()),edit)

    def test_fractional_word_endpoints_use_the_exported_frame_span(self):
        p={'timeline':{'duration':33.33,'fps':'30'},'slots':[
            {'index':0,'start':17.04,'end':17.32,'source_in':3.,
             'source_duration':98/30,'clip':'cafe.mp4'}]}
        _apply_edits(p,{})
        self.assertAlmostEqual(p['slots'][0]['source_in'],89/30)
        _apply_edits(p,{})
        self.assertAlmostEqual(p['slots'][0]['source_in'],89/30)

    def test_short_unused_choice_does_not_prevent_extending_the_selected_clip(self):
        p=self.project()
        p['slots'][0]['options']=[{'source_in':1.,'source_duration':2.,'clip':'unused.mp4'}]
        _apply_edits(p,{'0':{'end':6.}})
        self.assertEqual(p['slots'][0]['end'],6.)

    def test_acceptable_video_beats_a_higher_scoring_still(self):
        from hinglish_broll.planner import specific_subject
        self.assertEqual(specific_subject('closed Indian cafe'),'')
        self.assertEqual(specific_subject('Meenakshi temple'),'Meenakshi temple')
        slot=Slot(Moment(1,'the Taj Mahal',['Taj Mahal'],subject='Taj Mahal'),2,4,'Taj Mahal')
        video=Candidate('commons','v','Taj Mahal',10,1280,720,score=.3)
        image=Candidate('commons','i','Taj Mahal',0,1280,720,score=.6,kind='image')
        self.assertIs(choose([(slot,[image,video])],'landscape',.22)[0][0],video)
        self.assertIsNone(choose([(slot,[image])],'landscape',.22)[0][0])
        self.assertEqual(choose([(slot,[image])],'landscape',.22)[0][1],[])
        self.assertTrue(exact_subject_match(image,'Taj Mahal'))
        self.assertFalse(exact_subject_match(image,'Meenakshi temple'))

    def test_stale_settings_and_direct_render_cannot_enable_images(self):
        from hinglish_broll.settings import BrollSettings
        from hinglish_broll.internet import acquire
        self.assertFalse(BrollSettings(image_fallback=True).image_fallback)
        still=Candidate('commons','i','Taj Mahal',60,1280,720,kind='image')
        with patch('hinglish_broll.internet.acquire') as fetch:
            with self.assertRaisesRegex(ValueError,'videos only'):
                render_choice('.', '.', None,0,{'start':0,'end':2},still,'cpu')
            fetch.assert_not_called()
        with self.assertRaisesRegex(ValueError,'videos only'):acquire('.',still,2)

    def test_offline_saved_library_does_not_block_unrelated_setting_changes(self):
        from hinglish_broll.settings import save_user_settings,LOCAL_SETTINGS
        with tempfile.TemporaryDirectory() as temp:
            file=Path(temp)/LOCAL_SETTINGS
            old_folder=str(Path(temp)/'disconnected-drive')
            file.write_text(json.dumps({'library_folders':[old_folder],'image_fallback':True}))
            saved=save_user_settings(temp,{'library_folders':[old_folder],'use_web':True,'image_fallback':True})
            self.assertEqual(saved['library_folders'],[old_folder])
            self.assertFalse(saved['image_fallback'])
            with self.assertRaisesRegex(ValueError,'footage folder not found'):
                save_user_settings(temp,{'library_folders':[str(Path(temp)/'new-missing-folder')]})
            self.assertEqual(json.loads(file.read_text())['library_folders'],[old_folder])

    def test_context_keeps_adjacent_negation_and_original_timestamps(self):
        from hinglish_broll.pipeline import speech_context
        text=speech_context([{'start':0,'end':2,'text':'Yahaan nightlife nahin hai'},
            {'start':2,'end':5,'text':'koi cafe koi club nahin'},
            {'start':50,'end':52,'text':'unrelated later words'}],2,5)
        self.assertIn('nightlife nahin hai',text)
        self.assertIn('2.00-5.00s',text)
        self.assertNotIn('unrelated',text)

    def test_xml_and_native_project_keep_broll_timing_source_handles_and_base_audio(self):
        with tempfile.TemporaryDirectory() as temp:
            folder=Path(temp)
            media=Media('base',str(folder/'speech.mp4'),12,'30',270,480,2,48000)
            xml=folder/'source-timeline.xml';export_xml(xml,[Cut('base',0,360,0)],{'base':media})
            timeline=parse_xmeml(xml)
            placements=[{'path':str(folder/'cutaway.mp4'),'start':2,'end':4,'source_in':3,'source_duration':8}]
            edited=export_broll_xml(timeline,placements,folder/'BROLL_SEQUENCE.xml')
            item=ET.parse(edited).find('.//sequence/media/video/track[2]/clipitem')
            self.assertEqual([item.findtext(k) for k in ('start','end','in','out')],['60','120','90','150'])
            self.assertEqual(item.findtext('file/duration'),'240')
            p={'timeline':{'xml_path':str(xml)},'slots':[{'index':0,**placements[0],
                'clip':'cutaway.mp4','chosen':{'title':'Taj Mahal'}}]}
            project=folder/'broll-project.json';project.write_text(json.dumps(p))
            from hinglish_broll.premiere import export
            native=export(project,folder/'broll.prproj')
            tree=ET.fromstring(gzip.decompress(Path(native).read_bytes()))
            ticks=254016000000
            group=next(n for n in tree if n.get('ObjectID')=='164').find('TrackGroup/Tracks')
            self.assertEqual(len(group),2)
            lane=next(n for n in tree if n.get('ObjectUID')==group[1].get('ObjectURef'))
            ref=lane.find('ClipTrack/ClipItems/TrackItems/TrackItem').get('ObjectRef')
            item=next(n for n in tree if n.get('ObjectID')==ref)
            self.assertEqual(int(item.findtext('ClipTrackItem/TrackItem/Start')),2*ticks)
            sub_ref=item.find('ClipTrackItem/SubClip').get('ObjectRef')
            sub=next(n for n in tree if n.get('ObjectID')==sub_ref)
            clip=next(n for n in tree if n.get('ObjectID')==sub.find('Clip').get('ObjectRef'))
            self.assertEqual(int(clip.findtext('Clip/InPoint')),3*ticks)
            self.assertEqual(int(clip.findtext('Clip/OutPoint')),5*ticks)
            self.assertTrue(any(n.tag=='AudioClipTrackItem' for n in tree))

    def test_conform_retains_leading_and_trailing_handles(self):
        from types import SimpleNamespace
        with tempfile.TemporaryDirectory() as temp:
            slot={'start':4.,'end':6.}
            candidate=Candidate('library','v','video',12,270,480,path='source.mp4',offset=5.)
            with patch('hinglish_broll.internet.acquire',return_value=('source.mp4',12.,5.)), \
                 patch('hinglish_broll.pipeline.make_clip') as conform:
                render_choice(temp,temp,SimpleNamespace(width=270,height=480,fps=Fraction(30)),0,slot,candidate,'cpu')
            self.assertEqual(conform.call_args.args[1:3],(2.,8.))
            self.assertEqual(slot['source_in'],3.)
            self.assertEqual(slot['source_duration'],8.)


if __name__=='__main__':unittest.main()
