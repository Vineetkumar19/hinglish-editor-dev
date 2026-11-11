"""Fresh sequential ASR for the first reference, without the old batch gaps."""
import json,os,subprocess,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
OUT=ROOT/'output/reference-analysis/cricAddict-by-video/reference-01'

def main():
    from imageio_ffmpeg import get_ffmpeg_exe
    from tools.analyze_documentary_reference import facts,write_json
    OUT.mkdir(parents=True,exist_ok=True)
    source=json.loads((ROOT/'output/reference-analysis/crick-edit-editing-style/inventory.json').read_text(encoding='utf8'))[0]
    audio=OUT/'speech-audio.wav'
    if not audio.exists():
        subprocess.run([get_ffmpeg_exe(),'-v','error','-nostdin','-threads','2','-i',source['path'],'-vn','-ar','16000','-ac','1','-c:a','pcm_s16le',str(audio)],check=True)
    if (OUT/'fresh-transcript.json').exists():return
    runtime=ROOT/'tools/cuda-reference-runtime/bin'
    dll=os.add_dll_directory(str(runtime));os.environ['PATH']=str(runtime)+os.pathsep+os.environ['PATH']
    from faster_whisper import WhisperModel
    manifest=json.loads((ROOT/'models/meaning-upgrade.json').read_text(encoding='utf8'))
    began=time.time();words=[];lines=[]
    model=WhisperModel(manifest['speech_path'],device='cuda',compute_type='int8_float16',cpu_threads=2,num_workers=1,local_files_only=True)
    segments,info=model.transcribe(str(audio),language='hi',beam_size=3,temperature=0,word_timestamps=True,
        condition_on_previous_text=False,vad_filter=True,vad_parameters={'min_silence_duration_ms':250})
    with (OUT/'fresh-speech-checkpoint.jsonl').open('w',encoding='utf8') as saved:
        for segment in segments:
            line={'start':segment.start,'end':segment.end,'text':segment.text.strip(),
                'avg_logprob':segment.avg_logprob,'no_speech_probability':segment.no_speech_prob}
            row=[]
            for word in segment.words or []:
                row.append({'start':word.start,'end':word.end,'text':word.word.strip(),'probability':word.probability,
                    'aligned':False,'timestamp_source':'Sequential local Whisper large-v3-turbo word estimate'})
            words.extend(row);lines.append(line)
            saved.write(json.dumps({'line':line,'words':row},ensure_ascii=False)+'\n');saved.flush()
            if len(lines)%10==0:print(f'Speech {segment.end:.1f}/{source["seconds"]:.1f}s',flush=True)
    write_json(OUT/'fresh-transcript.json',lines);write_json(OUT/'fresh-words.json',words)
    write_json(OUT/'speech-receipt.json',{'source':facts(Path(source['path'])),'model':'faster-whisper-large-v3-turbo',
        'device':'cuda','beam_size':3,'batched':False,'segments':len(lines),'words':len(words),'elapsed_seconds':time.time()-began,
        'scope':'Whole reference audio transcribed sequentially. ASR remains fallible; these are word estimates, not certified forced alignment.',
        'cloud_inference':False,'other_videos_started':False})
    print('COMPLETE fresh sequential speech:',len(words),'words',flush=True)

if __name__=='__main__':main()
