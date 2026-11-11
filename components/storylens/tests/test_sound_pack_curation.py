import json
import tempfile
import unittest
import wave
from pathlib import Path

from hinglish_sound.library import decode, scan
from tools.sound_pack_categories import classify


class SoundPackCurationTests(unittest.TestCase):
    def test_pack_labels_use_cue_type_inside_transition_and_cinematic_folders(self):
        cases = {
            'TRANSITION SOUND EFFECTS/SBCT - TRANSITION SFX/transition-sfx-impact-01.wav': 'impact',
            'TRANSITION SOUND EFFECTS/SBCT - TRANSITION SFX/transition-sfx-glitch-01.wav': 'glitch',
            'TRANSITION SOUND EFFECTS/SBCT - TRANSITION SFX/transition-sfx-speed-ramp-01.wav': 'riser',
            'W. A. Production What About Cinematic FX/Foley FX/WACFX_Short_FX_01_Tuba.wav': 'impact',
            'W. A. Production What About Cinematic FX/Vocal FX/WACFX_Vocal_FX_01_One_Shot.wav': 'impact',
            'W. A. Production What About Cinematic FX/White Noise FX/WACFX_White_Noise_11_Line_Strings.wav': 'suspense',
        }
        for path, expected in cases.items():
            with self.subTest(path=path):
                self.assertEqual(classify(path), ('sfx', expected))

    def test_owner_wav_with_non_utf8_metadata_decodes(self):
        path = (Path(__file__).resolve().parents[1] /
                'library/owner-sound-packs/sfx/whoosh/'
                'd6a5304791b2-transition-sfx-bass-movement-01.wav')
        if not path.is_file():
            self.skipTest('Owner sound pack is not installed')
        audio = decode(path, 16000, mono=True, limit=1)
        self.assertGreater(audio.shape[1], 1000)

    def test_curated_family_updates_a_cached_recording_without_moving_it(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            path = root / 'general' / 'Designed Sweep.wav'
            path.parent.mkdir()
            with wave.open(str(path), 'wb') as wav:
                wav.setnchannels(1)
                wav.setsampwidth(2)
                wav.setframerate(16000)
                wav.writeframes(b'\0\0' * 3200)
            first = scan(root, 'sfx', root / 'cache', progress=lambda _: None)
            self.assertEqual(first[0].category, 'general')
            sidecar = Path(str(path) + '.json')
            sidecar.write_text(json.dumps({'name': 'Designed Sweep', 'category': 'whoosh',
                                           'tags': ['cinematic sweep']}), encoding='utf-8')
            second = scan(root, 'sfx', root / 'cache', progress=lambda _: None)
            self.assertEqual(second[0].category, 'whoosh')
            self.assertIn('cinematic sweep', second[0].text)
            self.assertEqual(second[0].path, str(path))

    def test_invalid_sidecar_category_does_not_enter_sound_family(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            path = root / 'impact' / 'Hit.wav'
            path.parent.mkdir()
            with wave.open(str(path), 'wb') as wav:
                wav.setnchannels(1)
                wav.setsampwidth(2)
                wav.setframerate(16000)
                wav.writeframes(b'\0\0' * 3200)
            Path(str(path) + '.json').write_text(json.dumps({'category': 'other'}), encoding='utf-8')
            self.assertEqual(scan(root, 'sfx', root / 'cache', progress=lambda _: None)[0].category,
                             'impact')

    def test_alternate_format_remains_on_disk_but_is_not_offered_twice(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for label, excluded in (('48k', False), ('96k', True)):
                path = root / 'whoosh' / f'sweep-{label}.wav'
                path.parent.mkdir(exist_ok=True)
                with wave.open(str(path), 'wb') as wav:
                    wav.setnchannels(1)
                    wav.setsampwidth(2)
                    wav.setframerate(16000)
                    wav.writeframes(b'\0\0' * 3200)
                Path(str(path) + '.json').write_text(
                    json.dumps({'exclude_from_selection': excluded}), encoding='utf-8')
            result = scan(root, 'sfx', root / 'cache', progress=lambda _: None)
            self.assertEqual([Path(asset.path).name for asset in result], ['sweep-48k.wav'])
            self.assertTrue((root / 'whoosh/sweep-96k.wav').is_file())


if __name__ == '__main__':
    unittest.main()
