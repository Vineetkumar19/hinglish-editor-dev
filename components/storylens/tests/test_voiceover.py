"""Behavior contracts written before the Voiceover implementation."""
import io
import json
import tempfile
import unittest
import wave
from pathlib import Path
from unittest.mock import patch


def recording(seconds=4):
    import math, struct
    stream = io.BytesIO()
    with wave.open(stream, 'wb') as wav:
        wav.setparams((1, 2, 16000, 0, 'NONE', 'not compressed'))
        wav.writeframes(b''.join(struct.pack('<h', int(10000*math.sin(i*.12))) for i in range(seconds*16000)))
    return stream.getvalue()


class VoiceoverTests(unittest.TestCase):
    def setUp(self):
        from hinglish_voice.service import VoiceService
        Path('work/voiceover-tests').mkdir(parents=True, exist_ok=True)
        self.tmp = tempfile.TemporaryDirectory(dir='work/voiceover-tests')
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.service = VoiceService(self.root)

    def voice(self):
        upload = self.service.upload('mine.wav', recording())
        return self.service.create_voice(dict(upload_id=upload['id'], name='My voice', transcript='This is my sample.', consent=True))

    def test_save_reload_voice_and_exact_transcript(self):
        from hinglish_voice.service import VoiceService
        voice = self.voice()
        again = VoiceService(self.root).voices()[0]
        self.assertEqual(voice, again)
        self.assertEqual(again['transcript'], 'This is my sample.')
        self.assertGreater(again['duration'], 3)

    def test_invalid_audio_and_short_sample_are_rejected(self):
        for data in (b'not audio', recording(1), recording(21)):
            with self.assertRaises(ValueError): self.service.upload('x.wav', data)

    def test_cannot_read_arbitrary_local_paths_or_traversal(self):
        for key in ('../secret', 'a'*31, 'C:/private.wav'):
            with self.assertRaises(ValueError): self.service.voice(key)
        with self.assertRaises(ValueError):
            self.service.create_voice(dict(upload_id='../x', name='Mine', transcript='x', consent=True))

    def test_requires_sample_transcript_and_owner_confirmation(self):
        upload = self.service.upload('mine.wav', recording())
        for extra in (dict(consent=False, transcript='words'), dict(consent=True, transcript='')):
            with self.assertRaises(ValueError):
                self.service.create_voice(dict(upload_id=upload['id'], name='Mine', **extra))

    def test_generation_preserves_hinglish_numbers_and_punctuation(self):
        voice = self.voice()
        script = 'Namaste! Aaj 28 October hai.\nScore 123/4 — let’s begin.'
        with patch.object(self.service, '_launch') as launch:
            job = self.service.start(dict(voice_id=voice['id'], script=script, language='auto', speed=1, request_id='a'*32))
        self.assertEqual(job['script'], script)
        self.assertEqual(job['status'], 'queued')
        launch.assert_called_once()

    def test_retry_same_request_returns_same_job_without_second_generation(self):
        voice = self.voice()
        data = dict(voice_id=voice['id'], script='Hello world.', request_id='b'*32)
        with patch.object(self.service, '_launch') as launch:
            first = self.service.start(data)
            second = self.service.start(data)
        self.assertEqual(first['id'], second['id'])
        self.assertEqual(launch.call_count, 1)
        with self.assertRaises(ValueError): self.service.start(dict(data, script='Changed.'))

    def test_generation_input_validation(self):
        voice = self.voice()
        for change in (dict(script=' '), dict(script='x'*20001), dict(speed=float('nan')), dict(speed=3), dict(language='arbitrary')):
            with self.assertRaises(ValueError):
                self.service.start(dict(dict(voice_id=voice['id'], script='Hello.'), **change))

    def test_job_uses_saved_voice_and_exports_real_mp3_wav(self):
        import numpy as np
        voice = self.voice()
        with patch.object(self.service, '_launch'):
            job = self.service.start(dict(voice_id=voice['id'], script='Hello world.'))
        def synth(request, destination, log):
            import soundfile as sf
            sf.write(destination, np.sin(np.arange(24000)*.05).astype('float32')*.2, 24000)
        with patch('hinglish_voice.service.synthesize', side_effect=synth), patch('hinglish_voice.service.gpu_lock') as lock:
            lock.return_value.__enter__.return_value = None
            self.service.run(job['id'])
        saved = self.service.job(job['id'])
        self.assertEqual(saved['status'], 'complete')
        self.assertEqual(saved['script'], 'Hello world.')
        for kind in ('mp3', 'wav'):
            path = self.service.file(job['id'], kind)
            self.assertGreater(path.stat().st_size, 100)
        self.assertEqual(saved['engine'], 'VoiceStudio · OmniVoice')

    def test_failure_preserves_script_and_plain_language_with_details(self):
        voice = self.voice()
        with patch.object(self.service, '_launch'):
            job = self.service.start(dict(voice_id=voice['id'], script='Keep these words.'))
        with patch('hinglish_voice.service.synthesize', side_effect=RuntimeError('unusual backend crash')), patch('hinglish_voice.service.gpu_lock'):
            self.service.run(job['id'])
        saved = self.service.job(job['id'])
        self.assertEqual(saved['status'], 'failed')
        self.assertEqual(saved['script'], 'Keep these words.')
        self.assertNotIn('Traceback', saved['error'])
        self.assertIn('unusual backend crash', saved['error_details'])
        with self.assertRaises(ValueError): self.service.file(job['id'], 'mp3')

    def test_restart_marks_unfinished_work_interrupted_and_keeps_progress(self):
        from hinglish_voice.service import VoiceService
        voice = self.voice()
        with patch.object(self.service, '_launch'):
            job = self.service.start(dict(voice_id=voice['id'], script='Saved draft.'))
        self.service._update(job['id'], owner_pid=999999999)
        saved = VoiceService(self.root).job(job['id'])
        self.assertEqual(saved['status'], 'interrupted')
        self.assertEqual(saved['script'], 'Saved draft.')

    def test_second_instance_does_not_interrupt_a_live_generation(self):
        from hinglish_voice.service import VoiceService
        voice = self.voice()
        with patch.object(self.service, '_launch'):
            job = self.service.start(dict(voice_id=voice['id'], script='Still running.'))
        self.assertEqual(VoiceService(self.root).job(job['id'])['status'], 'queued')


if __name__ == '__main__': unittest.main()
