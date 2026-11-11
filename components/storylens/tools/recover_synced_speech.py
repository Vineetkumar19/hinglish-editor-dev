"""Short-window local ASR prevents long mixed-language gaps from hiding cues."""
import gc,json,os,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))
OUT=ROOT/'output/reference-analysis/local-documentary-synced'
os.environ['HF_HUB_OFFLINE']='1'
os.environ['TRANSFORMERS_OFFLINE']='1'
def save(name,data):
    (OUT/name).write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf8')
def main():
    import numpy as np
    from imageio_ffmpeg import get_ffmpeg_exe
    from faster_whisper import WhisperModel
    source=json.loads((OUT/'source.json').read_text())['path']
    audio=np.frombuffer(subprocess.check_output([get_ffmpeg_exe(),'-v','error','-nostdin','-threads','2','-i',source,'-t','60','-vn','-ac','1','-ar','16000','-f','f32le','-']),dtype='<f4').copy()
    if not (OUT/'windowed-words.json').exists():
        model=WhisperModel(json.loads((ROOT/'models/meaning-upgrade.json').read_text())['speech_path'],device='cpu',compute_type='int8',cpu_threads=2,num_workers=1,local_files_only=True)
        words=[];lines=[]
        for start in range(0,60,10):
            lo=max(0,start-.6);hi=min(60,start+10.6)
            segments,info=model.transcribe(audio[round(lo*16000):round(hi*16000)],beam_size=3,temperature=0,
                word_timestamps=True,condition_on_previous_text=False,vad_filter=False,
                initial_prompt='Cricket documentary. Dale Steyn. Sachin Tendulkar. Rohit Sharma. डेल स्टेन। सचिन तेंदुलकर। रोहित शर्मा।',
                hallucination_silence_threshold=1)
            for seg in segments:
                selected=[{'text':w.word.strip(),'start':lo+w.start,'end':lo+w.end,'probability':w.probability} for w in seg.words or [] if start <= (lo+(w.start+w.end)/2) < start+10]
                if selected:
                    lines.append({'start':selected[0]['start'],'end':selected[-1]['end'],'text':' '.join(w['text'] for w in selected),'language':info.language})
                    words.extend(selected)
            print(f'Short-window local ASR {start}–{min(60,start+10)}s ({info.language})',flush=True)
            save('windowed-words.partial.json',words)
        words.sort(key=lambda w:w['start'])
        save('windowed-words.json',words);save('windowed-segments.json',lines)
        del model;gc.collect()
    if not (OUT/'timed-words.json').exists():
        from hinglish_cut.backends import LocalSpeech
        from hinglish_cut.model import Settings
        backend=LocalSpeech(Settings(device='cpu',cpu_threads=2,offline=True),ROOT/'models')
        words=json.loads((OUT/'windowed-words.json').read_text(encoding='utf8'));result=[];issues=[]
        for line in json.loads((OUT/'windowed-segments.json').read_text(encoding='utf8')):
            selected=[w for w in words if line['start']-.001<=w['start']<line['end']-.001]
            lo=max(0,line['start']-.12);hi=min(60,line['end']+.12)
            try:
                aligned=backend.align(audio[round(lo*16000):round(hi*16000)],' '.join(w['text'] for w in selected))
                for original,word in zip(selected,aligned):
                    good=word.score>=.08 and not any(c.isdigit() for c in original['text']) and abs(lo+word.start-original['start'])<.65
                    result.append({**original,'asr_start':original['start'],'asr_end':original['end'],
                        'start':lo+word.start if good else original['start'],'end':lo+word.end if good else original['end'],
                        'score':word.score,'timing_source':'local MMS forced alignment' if good else 'local Whisper acoustic timestamp',
                        'alignment_disagreement_seconds':round(lo+word.start-original['start'],3)})
            except ValueError as error:
                issues.append({'start':lo,'error':str(error)});result.extend({**w,'timing_source':'local Whisper acoustic timestamp','score':0} for w in selected)
            print(f'Short-window CTC alignment through {hi:.2f}s',flush=True)
        for i,w in enumerate(result):w['id']=f'w{i:03}'
        save('timed-words.json',result)
        save('timing-receipt.json',{'local_only':True,'method':'10-second overlapping local Whisper automatic-language windows + separate MMS acoustic alignment',
            'words':len(result),'issues':issues,'limit':'Machine estimates. Numeric and low-confidence tokens retain Whisper timing; no claim of human-certified phonetic boundaries.'})
        backend.close()
    print('TIMING COMPLETE',flush=True)
if __name__=='__main__':main()
