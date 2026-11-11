import copy
import threading
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import Mock, patch

from hinglish_app.assistant_prepare_post import followup


class AskPreparePostTests(TestCase):
    def setUp(self):
        tmp = TemporaryDirectory(dir=Path(__file__).resolve().parents[1] / 'tmp')
        self.addCleanup(tmp.cleanup); self.root = Path(tmp.name)
        self.video = self.root / 'source.mp4'; self.video.write_bytes(b'source')
        self.thumb = self.root / 'thumbnail.jpg'; self.thumb.write_bytes(b'thumbnail')
        self.snapshot = {'profile': 'cricket', 'attachments': [],
                         'messages': [{'id': 'old', 'role': 'assistant', 'text': 'unrelated history ' * 20000}]}
        self.assistant = SimpleNamespace(root=self.root,
            state=SimpleNamespace(work_lock=threading.RLock()), _stopped=lambda _: False,
            _update=Mock(), _message=Mock())
        self.draft = {'id': 'a' * 32, 'profile': 'cricket', 'mode': 'shorts', 'status': 'prepared',
                      'count': 5, 'platforms': ['youtube', 'instagram'], 'errors': {}, 'stages': {}}
        self.engine = Mock(); self.engine.create.return_value = copy.deepcopy(self.draft)
        self.engine.get.return_value = copy.deepcopy(self.draft)
        self.engine.run.return_value = copy.deepcopy(self.draft)
        self.engine.post.return_value = {'jobs': [{'id': 'post1', 'status': 'ready'}]}
        self.service = patch('hinglish_app.prepare_post_http.service', return_value=self.engine).start()
        self.addCleanup(patch.stopall)

    def call(self, text, selected=(), snapshot=None):
        return followup(self.assistant, 'chat1', text, snapshot or self.snapshot,
                        list(selected), lambda _: None, 'message1')

    def test_preparation_uses_same_engine_and_never_passes_chat_history_or_posts(self):
        self.assertTrue(self.call('Prepare 5 Shorts for Cricket from this video.', [{'path': str(self.video)}]))
        payload = self.engine.create.call_args.args[0]
        self.assertEqual((payload['profile'], payload['mode'], payload['count']), ('cricket', 'shorts', 5))
        self.assertEqual(payload['video'], str(self.video.resolve()))
        self.assertNotIn('messages', payload); self.assertNotIn('history', payload)
        self.service.assert_called_once_with(self.assistant.state, recover_delivery=False)
        self.engine.run.assert_called_once(); self.engine.post.assert_not_called()

    def test_missing_thumbnail_asks_before_any_engine_or_planner_work(self):
        self.assertTrue(self.call('Prepare this long YouTube video.', [{'path': str(self.video)}]))
        self.engine.create.assert_not_called(); self.engine.run.assert_not_called()
        self.assertIn('thumbnail', self.assistant._message.call_args.args[2].lower())

    def test_help_and_unrelated_editing_do_not_start_publishing(self):
        for text in ['Can you explain how Prepare and Post works?', 'Add captions to this video.', 'Do not upload this video.',
                     'Create a thumbnail for this video.', 'Make 5 Shorts with captions.']:
            self.assertFalse(self.call(text))
        self.service.assert_not_called()

    def test_hindi_profile_name_does_not_silently_use_selected_cricket(self):
        self.assertTrue(self.call('Prepare 5 Shorts for गेमिंग from this video.', [{'path': str(self.video)}]))
        self.assertEqual(self.engine.create.call_args.args[0]['profile'], 'gaming')

    def test_missing_thumbnail_followup_keeps_previous_video_only(self):
        original = [{'id': 'video1', 'path': str(self.video)}]
        self.assertTrue(self.call('Prepare this long YouTube video.', original))
        pending = next(c.kwargs['prepare_post_inputs'] for c in self.assistant._update.call_args_list if 'prepare_post_inputs' in c.kwargs)
        self.assertTrue(self.call('Here is the thumbnail.', [{'id': 'image1', 'path': str(self.thumb)}],
            snapshot={**self.snapshot, 'prepare_post_inputs': pending, 'attachments': original}))
        self.engine.create.assert_called_once()
        payload = self.engine.create.call_args.args[0]
        self.assertEqual(payload['video'], str(self.video)); self.assertEqual(payload['thumbnail'], str(self.thumb))

    def saved(self, **changes):
        return {**self.snapshot, 'prepare_post_bridge': {'id': 'a' * 32, 'profile': 'cricket',
            'platforms': ['youtube', 'instagram'], 'request': 'Prepare five Shorts.'}, **changes}

    def test_resume_reuses_saved_id_and_never_creates_a_new_job(self):
        self.assertTrue(self.call('Resume preparation.', snapshot=self.saved()))
        self.engine.resume.assert_called_once_with('a' * 32, 'cricket')
        self.engine.run.assert_called_once(); self.engine.create.assert_not_called()
        self.engine.post.assert_not_called()

    def test_status_is_read_only_and_uses_saved_id(self):
        self.assertTrue(self.call('What is the preparation status?', snapshot=self.saved()))
        self.engine.get.assert_called_with('a' * 32, 'cricket')
        self.engine.run.assert_not_called(); self.engine.create.assert_not_called(); self.engine.post.assert_not_called()

    def test_explicit_followup_posts_only_requested_platform_with_saved_id(self):
        with patch('hinglish_app.assistant_preferences.declarations', return_value={'made_for_kids': False, 'synthetic_media': False}):
            self.assertTrue(self.call('Post these now to YouTube only.', snapshot=self.saved()))
        self.engine.post.assert_called_once_with('a' * 32, 'cricket', 'youtube',
            {'made_for_kids': False, 'synthetic_media': False}, 'post_now')
        self.engine.create.assert_not_called(); self.engine.run.assert_not_called()

    def test_changed_profile_cannot_retarget_saved_draft(self):
        self.assertTrue(self.call('Resume preparation.', snapshot=self.saved(profile='gaming')))
        self.service.assert_not_called()
        self.assertIn('cricket', self.assistant._message.call_args.args[2].lower())

    def test_named_new_channel_cannot_retarget_a_post_continuation(self):
        self.assertTrue(self.call('Post these now on Gaming YouTube.', snapshot=self.saved()))
        self.service.assert_not_called(); self.engine.post.assert_not_called()

    def test_wait_for_owner_approval_is_not_automatic_permission(self):
        with patch('hinglish_app.assistant_preferences.declarations', return_value={'made_for_kids': False, 'synthetic_media': False}):
            for text in ['Upload these to YouTube after I approve.', 'Upload these if I agree.']:
                self.assertTrue(self.call(text, snapshot=self.saved()))
        self.engine.post.assert_not_called()

    def test_same_long_followup_passes_parent_id_for_speech_reuse(self):
        self.engine.get.return_value.update(mode='long', source={'path': str(self.video)})
        self.assertTrue(self.call('Prepare 5 Shorts from the same video.', snapshot=self.saved()))
        spec = self.engine.create.call_args.args[0]
        self.assertEqual(spec['source_preparation'], 'a' * 32)
        self.assertEqual(spec['video'], str(self.video)); self.engine.post.assert_not_called()

    def test_finished_short_is_not_silently_reextracted(self):
        self.assertTrue(self.call('Upload this existing finished Short to YouTube and Instagram.', [{'path': str(self.video)}]))
        self.engine.create.assert_not_called(); self.engine.post.assert_not_called()
        self.assertIn('finished short', self.assistant._message.call_args.args[2].lower())

    def test_negated_post_does_not_turn_preparation_into_authorization(self):
        self.assertTrue(self.call('Prepare 5 Shorts from this video. Do not post them.', [{'path': str(self.video)}]))
        self.engine.run.assert_called_once(); self.engine.post.assert_not_called()

    def test_preparing_for_upload_does_not_authorize_upload(self):
        with patch('hinglish_app.assistant_preferences.declarations', return_value={'made_for_kids': False, 'synthetic_media': False}):
            self.assertTrue(self.call('Prepare 5 Shorts for upload to YouTube and Instagram.', [{'path': str(self.video)}]))
        self.engine.run.assert_called_once(); self.engine.post.assert_not_called()

    def test_question_about_posting_a_saved_draft_does_not_post(self):
        self.assertFalse(self.call('Can you explain how to post these?', snapshot=self.saved()))
        self.service.assert_not_called(); self.engine.post.assert_not_called()

    def test_literal_path_upload_reaches_prepare_engine_without_video_noun(self):
        self.draft.update(mode='long', count=1, platforms=['youtube'], visibility='private')
        self.engine.create.return_value = self.engine.run.return_value = copy.deepcopy(self.draft)
        with patch('hinglish_app.assistant_preferences.declarations', return_value={}):
            self.assertTrue(self.call('Upload "' + str(self.video) + '" to Cricket YouTube privately.', [{'path': str(self.thumb)}]))
        self.engine.create.assert_called_once(); self.engine.post.assert_not_called()

    def test_private_followup_cannot_post_a_public_draft(self):
        self.engine.get.return_value['visibility'] = 'public'
        with patch('hinglish_app.assistant_preferences.declarations', return_value={'made_for_kids': False, 'synthetic_media': False}):
            self.assertTrue(self.call('Upload these privately to YouTube.', snapshot=self.saved()))
        self.engine.post.assert_not_called()

    def test_normal_assistant_route_delegates_before_legacy_preflight(self):
        from hinglish_app.assistant import Assistant
        snapshot = {**self.snapshot, 'attachments': [{'id': 'video1', 'path': str(self.video), 'kind': 'video'}]}
        normal = Assistant.__new__(Assistant); normal.root = self.root; normal.state = self.assistant.state
        normal.snapshot = Mock(return_value=snapshot); normal._update_user_message = Mock()
        normal._progress = Mock(); normal._update = Mock(); normal._message = Mock(); normal._stopped = Mock(return_value=False)
        normal.lock = threading.RLock()
        with patch('hinglish_app.assistant_publish_intent.preflight', side_effect=AssertionError('Legacy preflight must not run')), \
             patch('hinglish_app.assistant_plan.plan', side_effect=AssertionError('Full chat planner must not run')):
            normal._respond('chat1', 'Prepare 5 Shorts from this video.', ['video1'], None, 'message1')
        self.engine.run.assert_called_once(); self.engine.post.assert_not_called()
