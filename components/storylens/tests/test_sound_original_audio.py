import tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import numpy as np
from hinglish_sound.mix import mix
from test_sound_editor_master import read


class OriginalAudioTests(unittest.TestCase):
    def test_keep_source_preserves_stereo_and_bass_without_doubling(self):
        with tempfile.TemporaryDirectory() as temp:
            rate=48000;t=np.arange(rate)/rate
            original=np.stack([.15*np.sin(2*np.pi*30*t),.08*np.sin(2*np.pi*700*t)]).astype(np.float32)
            result=mix(original.mean(axis=0),[],[],Path(temp),source_audio=original)
            raw=read(result['stems']['analysis']['voice'])
            self.assertLess(float(np.max(np.abs(raw-original))),.00004)
            self.assertGreater(float(np.max(np.abs(raw[0]-raw[1]))),.1)
            self.assertEqual(result['stems']['voice_label'],'Original audio (voice + existing music)')
            self.assertIsNone(result['stems']['music'])

    def test_preserved_source_requires_exact_stereo_timing(self):
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaises(ValueError):
                mix(np.zeros(48000),[],[],Path(temp),source_audio=np.zeros((2,47000)))

    def test_timeline_source_audio_uses_original_stereo_excerpt_and_position(self):
        from hinglish_sound.source_audio import original_mix
        samples=np.stack([np.arange(96000)/1e6,-np.arange(96000)/1e6]).astype(np.float32)
        clip=SimpleNamespace(path='source.wav',source_in=.5,source_out=1.5,start=.2)
        with patch('hinglish_sound.source_audio.parse_xmeml',return_value=SimpleNamespace(clips=[clip])),patch('hinglish_sound.source_audio.decode',return_value=samples):
            out=original_mix('timeline.xml',2)
        self.assertEqual(out.shape,(2,96000))
        np.testing.assert_array_equal(out[:,9600:57600],samples[:,24000:72000])
        self.assertEqual(float(np.max(np.abs(out[:,:9600]))),0)


if __name__=='__main__':unittest.main()
