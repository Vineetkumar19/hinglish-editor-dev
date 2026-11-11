import tempfile,unittest,wave
from pathlib import Path
import numpy as np
from hinglish_sound.cues import Cue
from hinglish_sound.mix import mix,write_wav,db

def read(path):
    with wave.open(str(path),'rb') as w:
        return np.frombuffer(w.readframes(w.getnframes()),'<i2').reshape(-1,w.getnchannels()).T.astype(np.float32)/32767

def sum_stems(stems):
    out=read(stems['voice'])
    if stems.get('music'):out+=read(stems['music'])
    for row in stems['effects']:
        audio=read(row['path']);start=round(row['start']*48000)
        out[:,start:start+audio.shape[1]]+=audio
    return out

class SoundEditorMasterTests(unittest.TestCase):
    def test_hot_overlapping_editor_stems_reconstruct_the_preview_without_clipping(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);t=np.arange(96000)/48000
            voice=(.7*np.sin(t*400*2*np.pi)).astype(np.float32)
            source=write_wav(p/'hit.wav',voice[:24000])
            cues=[Cue(.25,.25,str(source),'poke',.5,0,-15,'overlap',group_id='strong',role=role)
                  for role in ('contact','detail','tail')]
            result=mix(voice,[],cues,p,layered=True,composed=True)
            raw=sum_stems(result['stems']['analysis']);native=sum_stems(result['stems'])
            self.assertGreater(float(np.max(np.abs(raw))),1.05) # reproduces the old export failure
            self.assertLess(float(np.max(np.abs(native))),float(db(-2))+.0002)
            self.assertLess(float(np.max(np.abs(native-read(result['preview_mix'])))),.0003)
            self.assertTrue(result['stems']['mastering']['shared_master_gain'])
