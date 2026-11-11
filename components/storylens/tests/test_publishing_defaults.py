"""Default post copy remains enabled when on-video subtitles are disabled."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch,Mock

from hinglish_publish.features import features,instagram_text_mode,title_hashtags
from hinglish_publish.metadata import generate_instagram
from hinglish_app.assistant_distribution import prepare_copy
from hinglish_app.assistant_saved_reels import export_context


class PublishingDefaultsTests(unittest.TestCase):
    def test_saved_youtube_declarations_apply_without_repeated_fields_or_implicit_authorization(self):
        from hinglish_publish.service import Publisher
        (self.root/'config.workflow.local.json').write_text(json.dumps({'publishing_defaults':{'made_for_kids':False,'synthetic_media':False}}),'utf-8')
        publisher=Publisher(self.root)
        item={'video':str(self.root/'short.mp4'),'fingerprint':'test-reel','platform':'youtube','profile':'cricket',
              'kind':'short','metadata':self.meta.copy(),'thumbnail':'','visibility':'private'}
        job_id=publisher.store.add_batch([item])[0]
        with self.assertRaises(ValueError):publisher.authorize({'ids':[job_id]})
        self.assertEqual(publisher.store.get(job_id)['status'],'draft')
        with patch.object(publisher,'accounts',return_value={'youtube':{'connected':True,'id':'verified-channel'}}):
            publisher.authorize({'ids':[job_id],'authorize':True})
        job=publisher.store.get(job_id)
        self.assertFalse(job['made_for_kids']);self.assertFalse(job['synthetic_media'])
        self.assertEqual(job['status'],'ready')

    def setUp(self):
        folder=Path(__file__).resolve().parents[1]/'tmp';folder.mkdir(exist_ok=True)
        self.temp=TemporaryDirectory(dir=folder);self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.meta={'title':'A PUBG gameplay challenge','description':'A player tackles a PUBG challenge.\n\n#PUBG #Gameplay #Gaming',
                   'tags':['PUBG','Gameplay','Gaming'],'instagram_caption':''}

    def test_basic_commands_get_title_and_hashtags_without_burned_subtitles(self):
        self.assertFalse(features(self.root)['burn_in_captions'])
        for request in ('upload 2 reels on my gaming instagram page','post one Short on cricket Instagram',
                        'no captions needed, just upload this video','add title on Instagram'):
            self.assertEqual(instagram_text_mode(self.root,request),'title_hashtags',request)

    def test_instagram_writer_returns_short_post_text_instead_of_empty_caption(self):
        writer=Mock(name='local writer');writer.name='local fixture'
        writer.json.side_effect=[{'title':self.meta['title'],'tags':self.meta['tags'],'sentence_ids':[0]},
                                 {'approved':True,'issues':[]}]
        with patch('hinglish_visuals.brain.open_brain',return_value=writer), \
             patch('hinglish_publish.metadata.generate_youtube',side_effect=AssertionError('Instagram must not generate a YouTube description')):
            result,_=generate_instagram(self.root,self.root/'Shorts 28.mp4',transcript='PUBG gameplay challenge.',
                notes='upload on my gaming instagram page')
        self.assertEqual(writer.json.call_count,2)
        self.assertEqual(result['instagram_caption'],title_hashtags(self.meta))
        self.assertNotIn('Shorts 28',result['instagram_caption'])
        self.assertEqual(writer.json.call_args_list[0].args[2]['required'],['title','tags','sentence_ids'])

    def test_instagram_only_uses_its_own_writer_and_keeps_youtube_deferred(self):
        meta={**self.meta,'copy_scope':'instagram_title_hashtags'}
        with patch('hinglish_app.assistant_publish.transcripts'), \
             patch('hinglish_publish.metadata.generate_instagram',return_value=(meta,'local writer')) as instagram, \
             patch('hinglish_publish.metadata.generate_youtube',side_effect=AssertionError('No YouTube work for Reel upload')):
            result,_=prepare_copy(self.root,self.root/'video.mp4','cricket','upload 2 reels',lambda _:None,youtube=False)
        self.assertEqual(result,meta);instagram.assert_called_once()

    def test_noisy_unused_statistics_are_not_in_the_title_grounding_request(self):
        writer=Mock();writer.name='local fixture'
        writer.json.side_effect=[{'title':'Mumbai Indians Teamwork','tags':['MumbaiIndians','Cricket','Teamwork'],'sentence_ids':[0]},
                                 {'approved':True,'issues':[]}]
        speech='Mumbai ke har player batting bowling mein contribute kar raha tha. kumra 27 trend gold 25 football cricket.'
        with patch('hinglish_visuals.brain.open_brain',return_value=writer):
            result,_=generate_instagram(self.root,self.root/'Shorts 28.mp4',transcript=speech,progress=lambda _:None)
        audit=writer.json.call_args_list[1].args[1]
        self.assertNotIn('27',audit['speech']);self.assertNotIn('football',audit['speech'])
        self.assertNotIn('description',audit['draft'])
        self.assertIn('MumbaiIndians',result['instagram_caption'])

    def test_uncertain_claim_is_simplified_by_the_local_writer_before_acceptance(self):
        writer=Mock();writer.name='local fixture'
        writer.json.side_effect=[
            {'title':'Football Players Become Cricketers','tags':['Cricket','Football','PlayerTransitions'],'sentence_ids':[1]},
            {'approved':False,'issues':['Draft wording Football Players Become Cricketers reinterprets a garbled fragment.']},
            {'title':'Mumbai Indians Teamwork','tags':['MumbaiIndians','Cricket','Teamwork'],'sentence_ids':[0]},
            {'approved':True,'issues':[]}]
        with patch('hinglish_visuals.brain.open_brain',return_value=writer):
            result,_=generate_instagram(self.root,self.root/'Shorts 28.mp4',transcript='Mumbai team batting bowling contribute. trend volt football cricket.',progress=lambda _:None)
        self.assertNotIn('Football',result['instagram_caption'])
        self.assertIn('Simplify',writer.json.call_args_list[2].args[1]['correction'])

    def test_later_youtube_request_generates_its_own_description(self):
        from hinglish_app.assistant_distribution import ensure_youtube_copy
        assistant=Mock(root=self.root)
        import threading
        assistant.state.work_lock=threading.RLock()
        clip={'video':str(self.root/'short.mp4'),'metadata':{**self.meta,'instagram_caption':'An existing Reel title #PUBG #Gaming #Gameplay','copy_scope':'instagram_title_hashtags'}}
        campaign={'clips':[clip]}
        with patch('hinglish_app.assistant_distribution.prepare_copy',return_value=(self.meta.copy(),'local writer')) as copy:
            ensure_youtube_copy(assistant,'test',clip,'gaming',self.root,campaign,'post on YouTube')
        self.assertTrue(copy.call_args.kwargs['youtube']);self.assertFalse(copy.call_args.kwargs['instagram'])
        self.assertNotIn('copy_scope',clip['metadata'])
        self.assertEqual(clip['metadata']['instagram_caption'],'An existing Reel title #PUBG #Gaming #Gameplay')

    def test_both_platforms_use_local_copy_writer_without_seo_keyword(self):
        with patch('hinglish_app.assistant_publish.transcripts') as speech, \
             patch('hinglish_publish.metadata.generate_youtube',return_value=(self.meta.copy(),'local writer')) as writer:
            result,_=prepare_copy(self.root,self.root/'video.mp4','gaming','upload this video',lambda _:None)
        speech.assert_called_once();writer.assert_called_once()
        self.assertTrue(result['description']);self.assertEqual(result['instagram_caption'].count('#'),3)

    def test_numbered_library_keeps_verified_original_topic_and_spoken_context(self):
        video=self.root/'Shorts 28.mp4'
        video.with_suffix('.txt').write_text('PUBG gameplay challenge.','utf-8')
        (self.root/'library.json').write_text(json.dumps({'shorts':[{
            'file':video.name,'sha256':'verified-digest','title':'A PUBG gameplay challenge'}]}),'utf-8')
        title,excerpt=export_context(video,'verified-digest')
        self.assertEqual(title,'A PUBG gameplay challenge');self.assertIn('PUBG',excerpt)
        self.assertEqual(export_context(video,'changed-digest')[0],video.stem)


if __name__=='__main__':unittest.main()
