"""Real delayed-transient excerpts must survive placement, mixing and PCM export."""
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
import wave

import numpy as np

from hinglish_sound.cues import place_cue
from hinglish_sound.library import decode, exact_peak_time
from hinglish_sound.mix import effect, write_wav


class SoundExcerptTests(unittest.TestCase):
    def setUp(self):
        self.folder=tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.root=Path(self.folder.name)
        t=np.arange(48000)/48000
        # Long silence, one clear transient and a decaying tail.
        envelope=np.exp(-((t-.65)/.027)**2)
        self.source=.2*np.sin(t*440*2*np.pi)*envelope
        self.path=write_wav(self.root/'delayed-hit.wav',self.source)
        self.asset=SimpleNamespace(path=str(self.path),duration=1.,peak_time=.65,loudness=-20.)

    def render(self,cue):
        start,audio=effect(cue,-18.,-6.,np.zeros(192000,np.float32),192000,
                           words_full=-20.,duck_db=-2.)
        out=write_wav(self.root/'effect.wav',audio)
        with wave.open(str(out)) as media:
            encoded=np.frombuffer(media.readframes(media.getnframes()),'<i2')/32767.
        return start,audio,encoded

    def test_short_peak_aligned_excerpt_uses_audible_region_and_preserves_landing(self):
        for category in ('impact','poke'):
            with self.subTest(category=category):
                cue=place_cue(self.asset,2.,category,'reveal',requested_length=.12)
                start,audio,encoded=self.render(cue)
                self.assertGreater(cue.source_offset,.5)
                self.assertLessEqual(cue.length,.12)
                self.assertGreater(float(np.max(np.abs(encoded))),.01)
                local=exact_peak_time(str(self.root/'effect.wav'),cue.length)
                self.assertLess(abs(start/48000+local-cue.target),.025)

    def test_short_start_aligned_awkward_excerpt_is_audible_at_the_requested_start(self):
        cue=place_cue(self.asset,2.,'awkward','record scratch',requested_length=.12)
        start,audio,encoded=self.render(cue)
        self.assertEqual(start,96000)
        self.assertEqual(cue.time,2.)
        self.assertGreater(cue.source_offset,.5)
        self.assertGreater(float(np.max(np.abs(encoded))),.01)
        self.assertGreater(float(np.max(np.abs(audio[:,:1920]))),.005)

    def test_negative_start_adds_source_trim_once_and_keeps_original_excerpt_end(self):
        normal=place_cue(self.asset,2.,'impact','reveal',requested_length=.12)
        cue=place_cue(self.asset,.02,'impact','opening reveal',requested_length=.12)
        self.assertEqual(cue.time,0.)
        self.assertGreater(cue.source_offset,normal.source_offset)
        self.assertAlmostEqual(cue.source_offset+cue.length,
                               normal.source_offset+normal.length,places=5)
        start,audio,encoded=self.render(cue)
        self.assertGreater(float(np.max(np.abs(encoded))),.01)
        peak=exact_peak_time(str(self.root/'effect.wav'),cue.length)
        self.assertLess(abs(start/48000+peak-cue.target),.025)

    def test_invalid_requested_lengths_are_rejected_and_real_bounds_are_kept(self):
        for bad in (0,-1,float('nan'),float('inf'),True,'0.2'):
            with self.subTest(bad=bad),self.assertRaises(ValueError):
                place_cue(self.asset,2.,'impact','reveal',requested_length=bad)
        cue=place_cue(self.asset,2.,'poke','tap',requested_length=8.)
        self.assertLessEqual(cue.length,self.asset.duration)
        self.assertLessEqual(cue.source_offset+cue.length,self.asset.duration+.000001)

    def test_legacy_placement_and_peak_helper_default_are_unchanged(self):
        cue=place_cue(self.asset,2.,'impact','reveal')
        self.assertEqual(cue.source_offset,0.)
        self.assertEqual(cue.length,1.)
        self.assertAlmostEqual(cue.time+exact_peak_time(self.asset.path,1.05),2.,places=3)
        offset=.55
        local=exact_peak_time(self.asset.path,.2,source_offset=offset)
        self.assertAlmostEqual(local+offset,.65,places=2)


if __name__=='__main__':unittest.main()
