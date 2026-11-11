"""Exercise official API request/receipt contracts without posting to an account."""
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from hinglish_publish.providers import Instagram, PreflightError, YouTube


class ProviderTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.video = self.root / 'export.mp4'
        self.video.write_bytes(b'provider contract fixture')
        self.job = {'video': str(self.video), 'thumbnail': '', 'account_id': 'channel',
                    'visibility': 'public', 'due': time.time(), 'made_for_kids': False,
                    'synthetic_media': True, 'remote': {}, 'status': 'processing',
                    'metadata': {'title': 'A spoken story', 'description': 'Actual content.',
                                 'tags': ['story'], 'instagram_caption': 'Actual content. #Story'}}
        self.client = MagicMock()
        self.client.videos.return_value.insert.return_value.next_chunk.return_value = (None, {'id': 'video123'})
        self.client.videos.return_value.list.return_value.execute.return_value = {
            'items': [{'status': {'privacyStatus': 'public', 'uploadStatus': 'processed'}}]}
        self.checkpoints = []

    def tearDown(self):
        self.temp.cleanup()

    def youtube(self, job=None):
        with patch('hinglish_publish.providers.youtube_client', return_value=(self.client, {'channel_id': 'channel'})), \
             patch('googleapiclient.http.MediaFileUpload'):
            return YouTube(self.root, {'youtube_public_api_ready': True}).publish(
                job or self.job, lambda value: self.checkpoints.append(dict(value)))

    def test_public_upload_and_declarations_are_verified(self):
        remote, status = self.youtube()
        self.assertEqual(status, 'published')
        self.assertEqual(remote['id'], 'video123')
        body = self.client.videos.return_value.insert.call_args.kwargs['body']
        self.assertFalse(body['status']['selfDeclaredMadeForKids'])
        self.assertTrue(body['status']['containsSyntheticMedia'])
        self.assertEqual(self.checkpoints[0]['id'], 'video123')

    def test_future_youtube_uses_native_private_publish_at(self):
        future = {**self.job, 'due': time.time() + 86400}
        self.client.videos.return_value.list.return_value.execute.return_value = {
            'items': [{'status': {'privacyStatus': 'private', 'uploadStatus': 'processed',
                                  'publishAt': '2026-10-06T13:30:00Z'}}]}
        self.assertEqual(self.youtube(future)[1], 'scheduled')
        body = self.client.videos.return_value.insert.call_args.kwargs['body']
        self.assertEqual(body['status']['privacyStatus'], 'private')
        self.assertIn('publishAt', body['status'])

    def test_private_is_not_reported_as_public(self):
        self.client.videos.return_value.list.return_value.execute.return_value = {
            'items': [{'status': {'privacyStatus': 'private', 'uploadStatus': 'processed'}}]}
        self.assertEqual(self.youtube({**self.job, 'visibility': 'private'})[1], 'uploaded_private')
        with self.assertRaises(RuntimeError):
            self.youtube()

    def test_unaudited_public_upload_is_blocked_before_api_call(self):
        with patch('hinglish_publish.providers.youtube_client') as client:
            with self.assertRaises(PreflightError):
                YouTube(self.root, {}).publish(self.job, lambda _: None)
            client.assert_not_called()

    def test_account_mismatch_never_uploads(self):
        with self.assertRaises(PreflightError):
            self.youtube({**self.job, 'account_id': 'different-channel'})
        self.client.videos.return_value.insert.assert_not_called()

    def test_thumbnail_failure_preserves_remote_receipt(self):
        self.client.thumbnails.return_value.set.return_value.execute.side_effect = TimeoutError()
        with self.assertRaises(TimeoutError):
            self.youtube({**self.job, 'thumbnail': str(self.root / 'thumbnail.jpg')})
        self.assertEqual(self.checkpoints[0]['id'], 'video123')

    def test_saved_video_receipt_is_not_inserted_again(self):
        self.youtube({**self.job, 'remote': {'id': 'already-uploaded'}})
        self.client.videos.return_value.insert.assert_not_called()

    def test_initial_rejection_keeps_safe_reason_without_leaking_request_url(self):
        from googleapiclient.errors import ResumableUploadError
        from httplib2 import Response
        from hinglish_publish.providers import YouTubeUploadRejected
        error=ResumableUploadError(Response({'status':'403'}),
            b'{"error":{"errors":[{"reason":"uploadLimitExceeded"}],"message":"private URL or token must not be echoed"}}',
            uri='https://upload.example.invalid/?token=secret')
        self.client.videos.return_value.insert.return_value.next_chunk.side_effect=error
        with self.assertRaises(YouTubeUploadRejected) as caught:self.youtube()
        failure=caught.exception
        self.assertEqual(failure.failure,{'phase':'initializing','safe_retry':True,'http_status':403,'reason':'uploadLimitExceeded'})
        self.assertIn('upload limit',str(failure));self.assertNotIn('secret',str(failure))
        self.assertNotIn('private URL',str(failure));self.assertFalse(self.checkpoints)

    def test_ambiguous_transfer_failure_is_not_labelled_safe_to_retry(self):
        self.client.videos.return_value.insert.return_value.next_chunk.side_effect=TimeoutError('transfer interrupted')
        with self.assertRaises(TimeoutError) as caught:self.youtube()
        self.assertFalse(getattr(caught.exception,'failure',{}))

    def instagram(self, responses, job=None):
        account = {'account_id': '123', 'token': 'not-a-real-token', 'version': 'v25.0'}
        chosen = {**self.job, 'account_id': '123', 'video_url': 'https://media.example.org/clip.mp4'}
        if job:
            chosen.update(job)
        with patch('hinglish_publish.providers.secrets.load', return_value=account), \
             patch('hinglish_publish.providers.requests.request') as request, \
             patch('hinglish_publish.providers.time.sleep'):
            request.side_effect = [MagicMock(ok=True, json=MagicMock(return_value=data)) for data in responses]
            result = Instagram(self.root, {}).publish(chosen, lambda value: self.checkpoints.append(dict(value)))
            return result, request.call_args_list

    def test_instagram_waits_for_processing_then_verifies_permalink(self):
        result, calls = self.instagram([{'id': 'container1'}, {'status_code': 'IN_PROGRESS'},
                                       {'status_code': 'FINISHED'}, {'id': 'media1'},
                                       {'id': 'media1', 'permalink': 'https://www.instagram.com/reel/example/'}])
        self.assertEqual(result[1], 'published')
        self.assertEqual(calls[0].kwargs['data']['media_type'], 'REELS')
        self.assertTrue(calls[3].args[1].endswith('/123/media_publish'))
        self.assertEqual(self.checkpoints[0]['container'], 'container1')
        self.assertEqual(self.checkpoints[1]['id'], 'media1')

    def test_saved_instagram_id_only_verifies_without_republishing(self):
        result, calls = self.instagram([{'id': 'media1', 'permalink': 'https://www.instagram.com/reel/example/'}],
                                      {'remote': {'container': 'container1', 'id': 'media1'}})
        self.assertEqual(result[1], 'published')
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0].args[0], 'GET')

    def test_instagram_bad_processing_stops_before_publish(self):
        with self.assertRaises(RuntimeError):
            self.instagram([{'id': 'container1'}, {'status_code': 'ERROR'}])
        self.assertEqual(self.checkpoints, [{'container': 'container1'}])

    def test_instagram_local_path_is_blocked_before_request(self):
        with patch('hinglish_publish.providers.requests.request') as request:
            with self.assertRaises(PreflightError):
                Instagram(self.root, {}).publish({**self.job, 'video_url': str(self.video)}, lambda _: None)
            request.assert_not_called()

