"""Regressions from the owner's actual saved-Shorts requests; no publishing."""
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import threading
import unittest
from unittest.mock import patch

from hinglish_app.assistant_saved_reels import requested,clip_count,library,supplied_locations,followup
from hinglish_app.assistant_edit_workflow import destination_profile
from hinglish_app.assistant_publishing_context import intent_text
from hinglish_publish.features import instagram_text_mode
from hinglish_publish.store import fingerprint


class SavedReelRequests(unittest.TestCase):
    def test_youtube_only_declines_instagram_only_route_before_quantity_binding(self):
        text=('Cricket profile: Choose one existing finished Short from my saved library. '
              'Upload that same one video now to my Cricket YouTube channel Fantasy Legends '
              'and keep the same one video on that YouTube channel. '
              'Exactly one video per platform.')
        self.assertTrue(requested(text))
        with self.temporary_workspace() as tmp:
            assistant=SimpleNamespace(root=Path(tmp))
            with patch('hinglish_app.assistant_saved_reels.library') as scan:
                self.assertFalse(followup(assistant,'paired-test',text,lambda _:None))
                scan.assert_not_called()

    def test_paired_saved_video_uses_bounded_model_selection_and_one_identical_clip(self):
        from hinglish_app.server import AppState
        from hinglish_app.assistant_distribution import WORKFLOW
        from unittest.mock import Mock
        text=('Cricket profile: Choose one existing finished Short from my saved library. '
              'Upload that same one video now to Cricket YouTube and Cricket Instagram. '
              'Exactly one video per platform. I authorize these two uploads now.')
        with self.temporary_workspace() as tmp:
            root=Path(tmp);state=AppState(root);assistant=state.assistant;session=assistant.create()['id']
            assistant._update(session,profile='cricket',active_request_message_id='one-test')
            state.local_browser.bind('cricket','fantasy_legends91')
            source=root/'finished.mp4';source.write_bytes(b'finished-portrait-fixture')
            meta={'title':'Temporary local test','description':'Temporary local test. #Cricket #Shorts #Test',
                  'tags':['Cricket','Shorts','Test'],'instagram_caption':'Temporary local test. #Cricket #Shorts #Test'}
            candidate={'id':'fixture-one','source':'Cricket final','video':str(source),'fingerprint':fingerprint(source),
                       'duration':14,'metadata':meta,'title':'Cricket final','content_excerpt':'Cricket match reaction','campaign_id':''}
            old_source=root/'already-uploaded.mp4';old_source.write_bytes(b'old-uploaded-portrait')
            old={**candidate,'id':'cancelled-with-receipt','video':str(old_source),'fingerprint':fingerprint(old_source)}
            old_id=state.publisher.store.add_batch([{**old,'profile':'cricket','platform':'youtube','kind':'short'}])[0]
            state.publisher.store.change(old_id,status='cancelled',remote={'id':'existing-owner-video'})
            brain=Mock(name='local-fixture');brain.name='Local model fixture'
            brain.json.return_value={'clip_ids':['fixture-one'],'profiles':['cricket']}
            account={'connected':True,'name':'Fantasy Legends','id':'UC'+'c'*22}
            with patch.object(state.publisher,'accounts',return_value={'youtube':account}), \
                 patch('hinglish_app.assistant_saved_reels.library',return_value=[old,candidate]), \
                 patch('hinglish_visuals.brain.open_brain',return_value=brain), \
                 patch('hinglish_app.assistant_distribution.prepare_copy',return_value=(meta,'Local copy fixture')), \
                 patch('hinglish_app.assistant_pipeline.prepared') as prepared:
                self.assertTrue(followup(assistant,session,text,lambda _:None))
            review=assistant.snapshot(session)['publishing_review']
            self.assertEqual(len(review['rows']),1);self.assertEqual(len(review['instagram_rows']),1)
            y,ig=review['rows'][0],review['instagram_rows'][0]
            self.assertEqual(y['fingerprint'],ig['fingerprint']);self.assertEqual(y['profile'],'cricket')
            self.assertEqual(ig['account'],'fantasy_legends91');self.assertTrue(y['immediate']);self.assertTrue(ig['immediate'])
            self.assertTrue(assistant.snapshot(session)['pipeline']['automatic'])
            self.assertEqual(brain.json.call_count,1);prepared.assert_called_once()
            self.assertEqual([c['id'] for c in brain.json.call_args.args[1]['candidates']],['fixture-one'])
            self.assertEqual(state.publisher.store.get(old_id)['remote'],{'id':'existing-owner-video'})
            self.assertFalse(state.local_browser.data['jobs'])
            receipt=Path(assistant.snapshot(session)['campaign'])/'decision-001.json'
            self.assertTrue(receipt.is_file())

    def temporary_workspace(self):
        folder=Path(__file__).resolve().parents[1]/'tmp'
        folder.mkdir(exist_ok=True)
        return TemporaryDirectory(dir=folder)

    def test_owner_wording_selects_two_saved_shorts_and_keeps_hashtags(self):
        text='upload any 2 shorts(which u have in memory) to my cricket insta channel with title and hastags that should be seo friendly'
        self.assertTrue(requested(text))
        self.assertEqual(clip_count(text),2)
        self.assertEqual(destination_profile(text),'cricket')
        self.assertEqual(instagram_text_mode(Path('.'),text),'title_hashtags')
        self.assertIn('hashtags',intent_text(text))

    def test_saved_references_do_not_require_library_password_words(self):
        for text,count in [
            ('Upload any 2 shorts on my cricket insta page with title and hashtags',2),
            ('Post three old reels to Instagram',3),
            ('Queue 7 existing Shorts on Instagram',7),
            ('Upload 2 shorts you have in memory with titles and hashtags',2),
            ('Use 6 existing finished Reels from saved outputs and alternate cricket and gaming Instagram accounts; post them in 60 seconds',6),
            ('Upload any 2 shorts from this folder with a title',2),
        ]:
            with self.subTest(text=text):
                self.assertTrue(requested(text));self.assertEqual(clip_count(text),count)

    def test_new_extraction_editing_and_questions_keep_their_routes(self):
        for text in [
            'Extract 2 Shorts from Dc.mp4 and upload on Instagram',
            'Make 2 new shorts from the old video and post on Instagram',
            'Trim the existing shorts and upload them',
            'Add subtitles to my existing reels and upload them',
            'Where are my old Shorts saved?',
            'How can I upload 2 saved Shorts?',
            'Do not upload my old reels',
        ]:
            with self.subTest(text=text):self.assertFalse(requested(text))

    def test_extract_outputs_are_available_without_campaign_and_unsafe_media_stays_excluded(self):
        with self.temporary_workspace() as tmp:
            root=Path(tmp);batch=root/'output/shorts/run/batch';batch.mkdir(parents=True)
            assets=batch/'assets';assets.mkdir()
            one=batch/'01 - First.mp4';one.write_bytes(b'first')
            duplicate=batch/'02 - Duplicate.mp4';duplicate.write_bytes(b'first')
            two=batch/'03 - Second.mp4';two.write_bytes(b'second')
            landscape=batch/'landscape.mp4';landscape.write_bytes(b'landscape')
            (assets/'background.mp4').write_bytes(b'background')
            bridge=SimpleNamespace(lock=threading.RLock(),data={'jobs':[{
                'action':'reel','video':str(two.resolve()),'status':'needs_review',
                'submission_started':True,'stop':False}]})
            assistant=SimpleNamespace(root=root,state=SimpleNamespace(local_browser=bridge,
                publisher=SimpleNamespace(store=SimpleNamespace(list=lambda:[]))))
            def facts(path):return SimpleNamespace(width=1920 if path==landscape else 1080,height=1920,duration=35)
            with patch('hinglish_shorts.source.open_video',side_effect=facts):
                clips=library(assistant,False)
            self.assertEqual(len(clips),1)
            self.assertEqual(clips[0]['fingerprint'],fingerprint(one))
            self.assertEqual(bridge.data['jobs'][0]['status'],'needs_review')
            self.assertFalse((root/'output/campaigns').exists())

    def test_literal_folder_is_preserved_as_a_folder_not_one_guessed_file(self):
        with self.temporary_workspace() as tmp:
            folder=Path(tmp)/'saved shorts';folder.mkdir()
            (folder/'one.mp4').write_bytes(b'one');(folder/'two.mp4').write_bytes(b'two')
            text=f'{folder}\nupload any 2 shorts from this folder to my cricket insta channel'
            self.assertEqual(supplied_locations(text),[folder.resolve()])

    def test_folder_upload_accepts_videos_and_does_not_treat_path_words_as_edits(self):
        from hinglish_app.assistant_artifacts import editing_requested
        with self.temporary_workspace() as tmp:
            folder=Path(tmp)/'remove silence'/'All Shorts';folder.mkdir(parents=True)
            for noun in ('videos','video','shorts','reels'):
                text=f'{folder}\nupload 2 {noun} on my cricket insta page and add title and hastags'
                self.assertTrue(requested(text),text)
                self.assertEqual(clip_count(text),2)
            self.assertFalse(editing_requested(f'{folder}\nupload 2 videos on my cricket page'))
            self.assertTrue(editing_requested(f'{folder}\nextract 2 shorts from a long video'))
            self.assertFalse(requested(f'{folder}\nextract 2 shorts and upload them'))


if __name__=='__main__':unittest.main()
