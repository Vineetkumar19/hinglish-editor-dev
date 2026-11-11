"""Check the actual localhost Eye Contact job, including audio and frame count."""
import json
from pathlib import Path
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))


def main():
    import av
    import requests
    from imageio_ffmpeg import get_ffmpeg_exe
    folder=ROOT/'output/validation/new-laptop/eyecontact-open'
    video=folder/'frontal-with-audio.mp4'
    source=ROOT/'input/phase1/instagram-vertical/VID20260808003915.mp4'
    subprocess.run([get_ffmpeg_exe(),'-nostdin','-v','error','-y','-i',str(folder/'frontal-input.mp4'),
        '-ss','1','-i',str(source),'-map','0:v:0','-map','1:a:0','-t',str(115/30),
        '-c:v','copy','-c:a','aac',str(video)],check=True)
    session=requests.Session();session.trust_env=False
    bridge=json.loads((ROOT/'cache/app/bridge.json').read_text())
    session.headers['X-Hinglish-Token']=bridge['token']
    base='http://127.0.0.1:8765'
    response=session.get(base+'/api/eyecontact/status',timeout=20);response.raise_for_status()
    ready=response.json();assert ready['ready'],ready
    response=session.post(base+'/api/jobs',json=dict(mode='eyecontact',source_paths=[str(video)],
        eye_reach='near',eye_size='3',eye_look_away=False),timeout=30)
    response.raise_for_status();job=response.json()
    deadline=time.monotonic()+300
    while time.monotonic()<deadline:
        response=session.get(base+'/api/jobs/'+job['id'],timeout=20)
        response.raise_for_status();job=response.json()
        if job['status'] in ('complete','failed'):
            break
        time.sleep(2)
    assert job['status']=='complete',job
    plans=sorted((ROOT/'output/eyecontact').glob('*/eyecontact-plan.json'),key=lambda p:p.stat().st_mtime)
    plan=json.loads(plans[-1].read_text())
    assert plan['settings']['backend']=='hsu_onnx' and not plan['simulated']
    model_result=plan['files'][0];target=Path(model_result['target'])
    with av.open(str(target)) as c:
        tracks=len(c.streams.audio);frames=sum(1 for _ in c.decode(video=0))
    assert frames==115 and tracks==1,(frames,tracks)
    assert model_result['corrected_frames']>0,model_result
    proof=dict(passed=True,job_id=job['id'],engine=ready['engine'],result=job['result'],
        corrected_frames=model_result['corrected_frames'],frames=frames,audio_tracks=tracks,
        plan=str(plans[-1]),original_unchanged=video.is_file())
    (folder/'localhost-inference.json').write_text(json.dumps(proof,indent=2),encoding='utf-8')
    print(json.dumps(proof),flush=True)


if __name__=='__main__':main()
