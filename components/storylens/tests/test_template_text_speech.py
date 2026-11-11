import gc
import unittest
import weakref
from types import SimpleNamespace
from hinglish_app.template_text_speech import transcribe_words


class SpeechLifetimeTests(unittest.TestCase):
    def run_speech(self, cancel=False):
        events=[]; refs=[]
        class Model:
            def __init__(self, *a, **kw): refs.append(weakref.ref(self))
            def transcribe(self, *a, **kw):
                def stream():
                    try:
                        yield SimpleNamespace(end=1, words=[SimpleNamespace(word='Mumbai won', start=0, end=1, probability=.9)])
                        yield SimpleNamespace(end=2, words=[])
                    finally: events.append('closed')
                return stream(), None
        def progress(*args):
            if cancel: raise RuntimeError('cancelled')
        if cancel:
            with self.assertRaisesRegex(RuntimeError, 'cancelled'):
                transcribe_words(Model, 'local-model', 'cuda', 'audio.wav', 'Mumbai won', 2, lambda:None, progress)
        else:
            words=transcribe_words(Model, 'local-model', 'cuda', 'audio.wav', 'Mumbai won', 2, lambda:None, progress)
            self.assertEqual([w['text'] for w in words], ['Mumbai','won'])
        gc.collect()
        self.assertEqual(events, ['closed'])
        self.assertIsNone(refs[0](), 'Speech model must be released before heading model loads')
    def test_releases_speech_before_next_model(self): self.run_speech()
    def test_cancel_closes_generator_and_releases_model(self): self.run_speech(True)

if __name__=='__main__': unittest.main()
