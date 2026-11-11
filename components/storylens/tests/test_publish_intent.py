"""Owner's missing-source prompt and platform vocabulary; no publishing side effects."""
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import Mock
from hinglish_app.assistant_publish_intent import preflight,platforms,execution_text
from hinglish_app.assistant_edit_workflow import constraints
from hinglish_app.assistant_distribution import WORKFLOW


class PublishIntentTests(TestCase):
    def setUp(self):
        self.assistant=Mock(root=Path(__file__).resolve().parents[1])
        self.snapshot={'id':'test','messages':[],'attachments':[]}

    def test_exact_reported_request_asks_only_for_source_before_planning(self):
        result=preflight(self.assistant,'test','upload 2 reel on cricket channel',self.snapshot,[])
        self.assertIsNone(result)
        question=self.assistant._message.call_args.args[2]
        self.assertIn('2 Instagram Reels',question)
        self.assertIn('@fantasy_legends91',question)
        self.assertIn('full folder path',question)
        self.assertNotIn('Which account',question)
        self.assertNotIn('context',question)
        self.assistant.state.create_job.assert_not_called()
        self.assistant.state.local_browser.create.assert_not_called()

    def test_truly_missing_account_and_source_asks_for_both(self):
        self.assertIsNone(preflight(self.assistant,'test','upload two reels',self.snapshot,[]))
        question=self.assistant._message.call_args.args[2]
        self.assertIn('full folder path',question)
        self.assertIn('cricket or gaming',question)

    def test_platform_terms_and_explicit_override(self):
        for text,expected in [
            ('upload 2 reel on cricket channel',['instagram']),
            ('upload 2 shorts on gaming channel',['youtube']),
            ('post a video to cricket',['youtube']),
            ('upload my 10-15 minute short-form video',['youtube']),
            ('upload saved Shorts on Instagram',['instagram']),
            ('upload 2 reels on YouTube',['youtube']),
            ('post shorts to YouTube and Instagram',['youtube','instagram']),
        ]:
            with self.subTest(text=text):self.assertEqual(platforms(text),expected)
        self.assertEqual(execution_text('extract 2 reels'),'extract 2 reels')
        self.assertEqual(execution_text('do not upload two reels'),'do not upload two reels')

    def test_folder_reply_retains_count_account_and_platform_without_changing_raw_request(self):
        with TemporaryDirectory(dir=self.assistant.root/'tmp') as tmp:
            folder=Path(tmp)/'All Shorts';folder.mkdir()
            preflight(self.assistant,'test','upload 2 reel on cricket channel',self.snapshot,[])
            pending=self.assistant._update.call_args.kwargs['publishing_inputs_pending']
            self.snapshot['publishing_inputs_pending']=pending
            resolved=preflight(self.assistant,'test',str(folder),self.snapshot,[])
            self.assertIn('upload 2 reel on cricket channel',resolved)
            self.assertIn('Instagram only',resolved)
            self.assertNotIn('YouTube',resolved)
            self.assertIsNone(self.assistant._update.call_args.kwargs['publishing_inputs_pending'])
            self.assertEqual(platforms(str(folder)+'\nupload 2 reels on cricket channel'),['instagram'])

    def test_unknown_new_request_does_not_inherit_pending_publishing_permission(self):
        self.snapshot['publishing_inputs_pending']={'request':'upload 2 reels on cricket channel'}
        self.assertEqual(preflight(self.assistant,'test','add subtitles to this video',self.snapshot,[]),'add subtitles to this video')
        self.assistant._update.assert_called_with('test',publishing_inputs_pending=None)

    def test_destination_only_reply_keeps_selected_source(self):
        with TemporaryDirectory(dir=self.assistant.root/'tmp') as tmp:
            self.snapshot['publishing_inputs_pending']={'request':str(Path(tmp))+'\nupload 2 reels'}
            resolved=preflight(self.assistant,'test','cricket',self.snapshot,[])
            self.assertIn(str(Path(tmp)),resolved)
            self.assertIn('upload 2 reels',resolved)
            self.assertIn('Instagram only',resolved)

    def test_questions_edits_and_receipt_continuations_keep_their_routes(self):
        for text in ('How do I upload 2 reels?', 'extract 2 reels and upload them',
                     'retry', 'post now', 'where are my videos?'):
            with self.subTest(text=text):
                self.assertEqual(preflight(self.assistant,'test',text,self.snapshot,[]),text)

    def test_new_edit_pipeline_obeys_noun_scope_over_old_paired_default(self):
        workflow={**WORKFLOW,'default_short_platforms':'paired'}
        for noun,expected in [('reels','instagram'),('Shorts','youtube')]:
            facts=constraints(f'extract 2 {noun} and upload to cricket channel',[],workflow)
            self.assertEqual(facts['platforms'],expected)
            self.assertEqual(facts['capacity'],2)
        self.assertEqual(constraints('extract 2 Shorts and post to Instagram',[],workflow)['platforms'],'instagram')

    def test_long_video_is_not_classified_as_short(self):
        from hinglish_app.assistant_publish import request
        parsed=request(execution_text('upload any short-form video to cricket channel privately'))
        self.assertEqual(parsed['kinds'],['long'])
