from base64 import b64encode
from collections import OrderedDict
from pathlib import Path
from unittest import TestCase, main
from unittest.mock import Mock, patch
from hinglish_app import support_call_speech as speech


class VoiceCacheTests(TestCase):
    def setUp(self):
        self.cache = patch.object(speech, '_voice_cache', OrderedDict())
        self.cache.start()
        self.size = patch.object(speech, '_voice_cache_bytes', 0)
        self.size.start()
        self.addCleanup(self.cache.stop)
        self.addCleanup(self.size.stop)

    def test_exact_repeat_avoids_worker_but_new_text_is_synthesized(self):
        worker = Mock()
        worker.poll.return_value = None
        replies = Mock()
        replies.get.return_value = '{"audio":"' + b64encode(b'wave audio').decode() + '"}'
        with patch.object(speech, '_worker', worker), patch.object(speech, '_responses', replies):
            self.assertEqual(speech.synthesize(Path.cwd(), 'Opened B-roll.', 'en'), b'wave audio')
            self.assertEqual(speech.synthesize(Path.cwd(), 'Opened B-roll.', 'en'), b'wave audio')
            self.assertEqual(replies.get.call_count, 1)
            speech.synthesize(Path.cwd(), 'Opened Auto Captions.', 'en')
            self.assertEqual(replies.get.call_count, 2)

    def test_cache_is_bounded_and_evicts_oldest(self):
        with patch.object(speech, '_VOICE_CACHE_LIMIT', 8), patch.object(speech, '_VOICE_CACHE_ENTRIES', 2):
            speech._cache_voice(('en', 'a'), b'1234')
            speech._cache_voice(('hi', 'b'), b'5678')
            speech._cache_voice(('en', 'c'), b'1234')
            self.assertEqual(list(speech._voice_cache), [('hi', 'b'), ('en', 'c')])
            self.assertEqual(speech._voice_cache_bytes, 8)
            speech._cache_voice(('en', 'c'), b'1')
            self.assertEqual(speech._voice_cache_bytes, 5)
            speech._cache_voice(('en', 'too long'), b'123456789')
            self.assertNotIn(('en', 'too long'), speech._voice_cache)

    def test_release_discards_private_cached_audio(self):
        speech._cache_voice(('en', 'private'), b'voice')
        with patch.object(speech, '_model', None), patch.object(speech, '_stop_worker'):
            speech.release()
        self.assertFalse(speech._voice_cache)
        self.assertEqual(speech._voice_cache_bytes, 0)


if __name__ == '__main__':
    main()
