"""Repair the user's actual song with exact supplied lyrics and measured RTX use."""
import hashlib
import json
from pathlib import Path
import subprocess
import time

ROOT=Path(__file__).resolve().parents[1]
LYRICS='Haan tujhe dekhta raha\nKissi khwab ki tarah\nJo ab samne hai tu\nHo kaise yakeen bhala'


def read(path):return json.loads(path.read_text(encoding='utf-8-sig'))


def main():
    import av
    import requests
    source=ROOT/'cache/app/jobs/c5bb5a966d94/media/0000-6c06e15c-Rog Music.mp4'
    original=hashlib.sha256(source.read_bytes()).hexdigest()
    session=requests.Session();session.trust_env=False
    session.headers['X-Hinglish-Token']=read(ROOT/'cache/app/bridge.json')['token']
    base='http://127.0.0.1:8765'
    response=session.post(base+'/api/jobs',json={'mode':'captions','source_paths':[str(source)],
        'caption_content':'lyrics','caption_style':'typography_2','script':LYRICS,'device':'cpu','preview':True},timeout=30)
    response.raise_for_status();job=response.json()
    assert job['device']=='cuda','The RTX policy was not applied'
    print('CORRECTED_SONG_JOB '+job['id'],flush=True)
    deadline=time.monotonic()+1200;previous='';samples=[]
    while time.monotonic()<deadline:
        response=session.get(base+'/api/jobs/'+job['id'],timeout=20);response.raise_for_status();job=response.json()
        if job['stage']!=previous:print(job['stage'],flush=True);previous=job['stage']
        try:
            sample=subprocess.run(['nvidia-smi','--query-gpu=utilization.gpu,memory.used','--format=csv,noheader,nounits'],
                capture_output=True,text=True,timeout=5)
            values=[int(value.strip()) for value in sample.stdout.strip().split(',')]
            if len(values)==2:samples.append({'gpu_utilization_percent':values[0],'device_memory_MiB':values[1]})
        except (ValueError,subprocess.TimeoutExpired):pass
        if job['status'] in ('failed','complete'):break
        time.sleep(1)
    assert job['status']=='complete',json.dumps(job,ensure_ascii=False)
    folder=Path(job['result']['folder']);project_file=next(folder.rglob('caption-project.json'));project=read(project_file)
    assert [ ' '.join(word['text'] for word in cue['words']) for cue in project['cues']]==LYRICS.splitlines()
    assert project['transcription']['backend_device']=='cuda' and project['video_encoder']=='h264_nvenc'
    assert job['result']['previews'],'The editor did not return a playable video'
    video=Path(job['result']['previews'][0])
    with av.open(str(video)) as container:
        assert container.streams.audio and container.streams.video
        frames=sum(1 for _ in container.decode(video=0))
    assert frames>=460 and hashlib.sha256(source.read_bytes()).hexdigest()==original
    proof={'passed':True,'job_id':job['id'],'source':str(source),'source_unchanged':True,
        'video':str(video),'caption_project':str(project_file),'srt':str(project_file.parent/'captions.srt'),
        'lyrics':LYRICS,'cue_count':len(project['cues']),'frames':frames,'inference_device':'cuda',
        'video_encoder':project['video_encoder'],'transcription':project['transcription'],
        'peak_sampled_gpu_utilization_percent':max((sample['gpu_utilization_percent'] for sample in samples),default=None),
        'peak_sampled_device_memory_MiB':max((sample['device_memory_MiB'] for sample in samples),default=None),
        'gpu_samples':samples,'quality':job['result']['quality_summary']}
    (ROOT/'output/validation/song-captions/corrected-localhost-result.json').write_text(json.dumps(proof,indent=2,ensure_ascii=False),encoding='utf-8')
    print(json.dumps({key:value for key,value in proof.items() if key!='gpu_samples'},indent=2,ensure_ascii=False),flush=True)


if __name__=='__main__':main()
