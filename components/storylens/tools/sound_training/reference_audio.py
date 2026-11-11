"""Local CLAP evidence, explicitly probabilistic; not isolated-stem listening."""
from pathlib import Path
import sys,json
import numpy as np
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from hinglish_sound.listen import Listener
import soundfile as sf
OUT=ROOT/'output/sound-training/20261030-revision2/references'
LABELS=['A woman speaking over music','A woman speaking without music','Music with a rhythmic drum beat',
 'Music with piano and atmospheric pads','A digital whoosh transition under speech',
 'Short pop sound effects under speech','Computer keyboard typing under speech',
 'A sharp camera shutter click under speech','A rising electronic transition under speech',
 'A bass impact under speech','A bell or sparkle chime under speech','Birds chirping under speech',
 'A comedic cartoon boing under speech','A sustained engine under speech','Running water under speech',
 'A quiet room with speech','A crowd with speech','A glitch sound under speech']
def main():
    listener=Listener(ROOT,device='cpu',threads=2);texts=listener.text_vectors(LABELS)
    for n in (1,2,3):
        folder=OUT/f'ref{n}';a,sr=sf.read(folder/'audio.wav',dtype='float32');rows=[]
        for start in np.arange(0,len(a)/sr,2):
            segment=a[int(start*sr):int((start+2)*sr)]
            if len(segment)<2400:continue
            vector=listener.audio([segment])[0];scores=texts@vector
            order=np.argsort(scores)[::-1][:5]
            rows.append(dict(start=float(start),end=min(float(start+2),len(a)/sr),hypotheses=[dict(label=LABELS[i],similarity=float(scores[i])) for i in order]))
        (folder/'audio-hypotheses.json').write_text(json.dumps(dict(method='CLAP mixed-audio similarity, not a calibrated probability or proof of an individual sound',windows=rows),indent=2),encoding='utf-8')
        print(f'ref{n}: {len(rows)} mixed-audio windows analyzed',flush=True)
if __name__=='__main__':main()
