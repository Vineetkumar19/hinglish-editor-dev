import json
import tempfile
import unittest
import wave
from pathlib import Path

import numpy as np

from hinglish_broll.phrases import Phrase
from hinglish_sound import learning
from hinglish_sound.cues import Cue
from hinglish_sound.director import TRIGGERS, validate_moments
from hinglish_sound.evaluator import check_effect, check_music, mix_qa
from hinglish_sound.library import Asset
from hinglish_sound.listen import SFX_VOCAB, Listener, music_features
from hinglish_sound.vectors import SoundIndex, document

FAMILIES = sorted({t for types in TRIGGERS.values() for t in types})


def write_wav(path, samples, rate=48000):
    pcm = (np.clip(samples, -1, 1) * 32767).astype('<i2')
    with wave.open(str(path), 'wb') as out:
        out.setnchannels(1); out.setsampwidth(2); out.setframerate(rate); out.writeframes(pcm.tobytes())
    return Path(path)


class FakeClap:
    """Stands in for CLAP: a text/audio 'sounds like X' space where each file's audio is tagged by its path."""
    words = list(SFX_VOCAB) + ['singing', 'instrumental', 'calm', 'busy']

    def _vec(self, text):
        v = np.array([1.0 if w.split()[0] in text.casefold() else 0.0 for w in self.words], np.float32)
        if 'cartoon' in text.casefold() or 'boing' in text.casefold(): v[self.words.index('cartoon')] = 1
        if 'song' in text.casefold() or 'vocals' in text.casefold() or 'singing' in text.casefold():
            v[self.words.index('singing')] = 1 if 'without' not in text.casefold() else 0
        if 'instrumental' in text.casefold(): v[self.words.index('instrumental')] = 1
        v += .01
        return v / np.linalg.norm(v)

    def texts(self, texts):
        return np.stack([self._vec(t) for t in texts])

    def audio(self, clips):   # the "audio" is a tone whose frequency encodes a label index
        out = []
        for c in clips:
            spectrum = np.abs(np.fft.rfft(c[:48000]))
            label = int(round(np.argmax(spectrum[1:]) + 1) / 100) - 1
            v = np.full(len(self.words), .01, np.float32)
            v[min(max(label, 0), len(self.words) - 1)] = 1
            out.append(v / np.linalg.norm(v))
        return np.stack(out)


def tone_for(label, seconds=1.0):
    """A sine whose frequency tells FakeClap which vocabulary label the file 'sounds like'."""
    freq = (FakeClap.words.index(label) + 1) * 100
    t = np.arange(int(seconds * 48000)) / 48000
    return .3 * np.sin(2 * np.pi * freq * t)


class FakeBrain:
    def embed(self, texts):   # text embeddings only know file names/tags
        vocab = ['impact', 'boom', 'whoosh', 'pop', 'music', 'funny', 'cartoon', 'calm', 'piano', 'song']
        rows = [np.array([1.0 if w in t.casefold() else 0.0 for w in vocab] + [.01], np.float32) for t in texts]
        return np.stack([r / np.linalg.norm(r) for r in rows])


def asset(path, kind='sfx', category='impact', name=None):
    return Asset(str(path), kind, category, name or Path(path).stem, name or Path(path).stem, 1.0, -20.0, .05)


class ListeningTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.dir = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def test_search_finds_what_a_file_sounds_like_not_what_it_is_called(self):
        boom = write_wav(self.dir / 'impact_03.wav', tone_for('boom'))           # a boom with a useless name
        boing = write_wav(self.dir / 'boom_epic.wav', tone_for('cartoon'))       # named boom, sounds cartoon
        listener = Listener(self.dir, backend=FakeClap())
        index = SoundIndex([asset(boom), asset(boing)], FakeBrain(), listener, progress=lambda m: None)
        self.assertIn('sounds like: boom', index.docs[0])
        self.assertEqual(index.genres[1], 'funny')                                # heard as a cartoon
        hits = index.search('a deep cinematic boom impact with bass', top=2, exclude_genres=('funny',),
                            min_audible=0)
        self.assertEqual([Path(a.path).name for a, _, _ in hits], ['impact_03.wav'])
        self.assertTrue(list((self.dir / 'cache' / 'sound' / 'clap').glob('*.npy')))   # listened once, cached

    def test_songs_with_singing_are_kept_out_of_speech_beds(self):
        song = write_wav(self.dir / 'calm piano.wav', tone_for('singing', 8))
        bed = write_wav(self.dir / 'bed.wav', tone_for('instrumental', 8))
        listener = Listener(self.dir, backend=FakeClap())
        index = SoundIndex([asset(song, 'music', 'reflective'), asset(bed, 'music', 'reflective')], FakeBrain(),
                           listener, progress=lambda m: None)
        self.assertTrue(index.facts[0]['vocals'])
        self.assertIn('HAS SINGING', index.docs[0])
        hits = index.search('calm piano bed', top=2, instrumental_only=True, min_audible=0)
        self.assertEqual([Path(a.path).name for a, _, _ in hits], ['bed.wav'])

    def test_music_tempo_is_measured_from_the_audio(self):
        t = np.arange(20 * 16000) / 16000
        clicks = np.zeros_like(t)
        for beat in np.arange(0, 20, .5):                                        # 120 BPM
            i = int(beat * 16000); clicks[i:i + 400] = .8
        path = write_wav(self.dir / 'beat.wav', clicks + .01 * np.sin(2 * np.pi * 220 * t), 16000)
        facts = music_features(path)
        self.assertLess(abs(facts['bpm'] - 120), 8)
        self.assertGreater(facts['energy'], .2)


class DirectorRuleTests(unittest.TestCase):
    lines = [Phrase(0, 0, 2, 'Aur phir maine Zomato khola.'), Phrase(1, 2, 4, 'Main bahut akela feel kar raha tha.'),
             Phrase(2, 4, 6, 'Aur result? Zero.')]

    def analysis(self, *moments):
        return {'lines': [{'id': 0, 'emotion': 'casual'}, {'id': 1, 'emotion': 'sad, lonely'},
                          {'id': 2, 'emotion': 'shocked'}], 'moments': list(moments)}

    def moment(self, id, trigger, evidence, type, word='x'):
        return {'id': id, 'trigger': trigger, 'evidence': evidence, 'word': word, 'type': type, 'intent': '',
                'strength': 2, 'pull_back': False, 'why': ''}

    def test_every_sound_needs_its_trigger_in_the_words(self):
        kept, dropped = validate_moments(self.analysis(
            self.moment(0, 'app_or_device', 'Zomato khola', 'poke'),
            self.moment(0, 'money', '500 rupaye', 'retro')), self.lines, FAMILIES, 'informational')
        self.assertEqual([m['trigger'] for m in kept], ['app_or_device'])
        self.assertIn('no trigger', dropped[0][1])

    def test_sound_type_must_suit_the_trigger(self):
        kept, _ = validate_moments(self.analysis(self.moment(2, 'reveal', 'result Zero', 'retro')),
                                   self.lines, FAMILIES, 'serious')
        self.assertEqual(kept[0]['type'], 'impact')                             # a reveal is a hit, not a coin

    def test_no_playful_sound_on_a_sad_line_unless_the_video_is_comedic(self):
        sad = self.moment(1, 'realisation', 'akela feel', 'cute')
        kept, dropped = validate_moments(self.analysis(sad), self.lines, FAMILIES, 'emotional')
        self.assertEqual(kept, [])
        self.assertIn('does not fit a sad, lonely line', dropped[0][1])
        kept, _ = validate_moments(self.analysis(sad), self.lines, FAMILIES, 'comedic')
        self.assertEqual(len(kept), 1)


class EvaluatorTests(unittest.TestCase):
    def setUp(self):
        self.listener = Listener(tempfile.mkdtemp(), backend=FakeClap())

    def vector(self, label):
        return FakeClap().audio([tone_for(label)])[0]

    def test_a_boom_passes_as_an_impact_and_a_voice_or_cartoon_fails(self):
        ok = check_effect(self.listener, self.vector('boom'), {}, 'impact', 'deep cinematic boom', 'serious')
        self.assertTrue(ok.passed)
        self.assertIn('boom', ok.heard)
        talk = check_effect(self.listener, self.vector('voice'), {}, 'impact', 'deep cinematic boom', 'serious')
        self.assertFalse(talk.passed)
        self.assertIn('a person talking', talk.reasons[0])
        cartoon = check_effect(self.listener, self.vector('boom'), {'cartoonish': True}, 'impact', 'boom', 'emotional')
        self.assertFalse(cartoon.passed)
        self.assertIn('TONE', cartoon.reasons[0])

    def test_a_whoosh_is_not_accepted_as_a_notification(self):
        verdict = check_effect(self.listener, self.vector('whoosh'), {}, 'poke', 'phone notification ping', 'informational')
        self.assertFalse(verdict.passed)

    def test_music_with_singing_fails(self):
        self.assertFalse(check_music({'vocals': True, 'sounds_like': ['upbeat pop']}, 2, 'upbeat').passed)
        calm = check_music({'vocals': False, 'energy': .9, 'sounds_like': ['electronic']}, 1, 'reflective')
        self.assertTrue(calm.passed)
        self.assertTrue(calm.warnings)

    def test_mix_check_measures_levels_density_and_clipping(self):
        rate = 48000
        voice = np.zeros(rate * 6, np.float32)
        voice[rate:rate * 3] = .2 * np.sin(np.arange(rate * 2) * 2 * np.pi * 200 / rate)
        speech = np.abs(voice) > 0
        bed = np.stack([.2 * np.ones(rate * 6, np.float32)] * 2)                 # music as loud as the voice
        quiet_hit = np.stack([.0005 * np.ones(4800, np.float32)] * 2)            # inaudible effect
        master = np.stack([voice, voice]) * .5
        cues = [Cue(1.0, 1.0, 'a', 'impact', .1, -2, -20, '', source='ai'),
                Cue(1.3, 1.3, 'b', 'poke', .1, -3, -20, '', source='ai')]
        rows = {r['check'].split(' at ')[0].split(' (')[0]: r for r in
                mix_qa(voice, bed, [(rate, quiet_hit, cues[0])], master, speech, cues, 1, 1.5)}
        self.assertFalse(rows['Effect']['passed'])
        self.assertFalse(rows['Music under your speech']['passed'])
        self.assertFalse(rows['Number of sounds']['passed'])
        self.assertFalse(rows['Spacing']['passed'])
        self.assertTrue(rows['No clipping']['passed'])


class TasteTests(unittest.TestCase):
    def test_removed_twice_is_banned_and_taste_reaches_the_director(self):
        with tempfile.TemporaryDirectory() as root:
            cues = [{'path': 'boing.wav', 'category': 'awkward', 'source': 'ai', 'line': 'Main fail ho gaya',
                     'word': 'fail', 'trigger': 'failure_or_rejection', 'sound': 'cartoon boing', 'emotion': 'sad'},
                    {'path': 'boom.wav', 'category': 'impact', 'source': 'ai', 'line': 'Result? Zero.',
                     'word': 'Zero', 'trigger': 'reveal', 'sound': 'deep boom', 'emotion': 'shocked'}]
            learning.record(root, cues, [1], video='reel-1')
            learning.record(root, cues, [1], video='reel-1')        # saving the same video again: still one vote
            self.assertEqual(learning.banned(learning.load(root)), set())
            data = learning.record(root, cues, [1], video='reel-2')  # removed in a second video: banned
            self.assertEqual(learning.banned(data), {'boing.wav'})
            self.assertEqual(sum(e['word'] == 'fail' for e in data['examples']), 2)   # one example per video
            text = learning.taste(data)
            self.assertIn('KEPT', text)
            self.assertIn('REMOVED', text)
            self.assertIn('cartoon boing', text)


class ReportTests(unittest.TestCase):
    def test_report_shows_why_each_sound_is_there_and_can_remix(self):
        from hinglish_sound.report import write_report
        cue = Cue(1.0, 1.1, 'C:/lib/boom.wav', 'impact', 1.0, -2, -20, 'reveal needs weight', 'Zero',
                  'deep cinematic boom', trigger='reveal', evaluation={'passed': True, 'heard': 'sounds like boom, hit',
                  'warnings': [], 'rejected': [{'file': 'boing.wav', 'reasons': ['TONE: a cartoon sound']}]})
        plan = {'lines': [], 'music': [], 'cues': [cue.to_dict()], 'voice_db': -20, 'story': 's', 'palette': 'serious',
                'dropped': [{'word': 'akela', 'type': 'cute', 'why': 'a playful cute sound does not fit a sad line'}],
                'mix_qa': [{'check': 'Master loudness', 'passed': True, 'value': '-14.2 dB'}], 'budget': 8}
        with tempfile.TemporaryDirectory() as folder:
            page = Path(folder) / 'report.html'
            write_report(page, 'madurai', plan)
            text = page.read_text(encoding='utf-8')
        for expected in ('Save &amp; remix', 'reveal', '✓ PASS', 'threw out boing.wav', 'does not fit a sad line',
                         'Mix check (1/1 passed)', '/api/sound/rebuild'):
            self.assertIn(expected, text)


if __name__ == '__main__':
    unittest.main()
