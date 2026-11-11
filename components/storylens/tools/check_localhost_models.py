"""Exercise the running editor with real local models and a six-second clip."""
import base64
import argparse
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import uuid

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--resume',type=Path)
    parser.add_argument('--upgrades',action='store_true',help='Verify the activated replacements without regenerating unchanged image/video models')
    args=parser.parse_args()
    if args.upgrades and args.resume:
        parser.error('Upgrade verification needs a fresh receipt, not checks from the previous models')
    import requests
    from PIL import Image
    from hinglish_cut.model_storage import configure
    from hinglish_cut.model_preferences import preferences,release_ollama
    configure(ROOT)
    session=requests.Session();session.trust_env=False
    base='http://127.0.0.1:8765'
    bridge=json.loads((ROOT/'cache/app/bridge.json').read_text(encoding='utf-8'))
    session.headers['X-Hinglish-Token']=bridge['token']
    folder=args.resume or ROOT/'output/validation/new-laptop'/('localhost-control-'+uuid.uuid4().hex[:10])
    folder.mkdir(parents=True,exist_ok=True)
    proof=folder/'live-model-checks.json'
    receipt=json.loads(proof.read_text(encoding='utf-8')) if args.resume and proof.exists() else {'url':base,'checks':{},'folder':str(folder)}
    recheck=folder/'caption-recheck.json'
    if args.resume and recheck.exists():
        verified=json.loads(recheck.read_text(encoding='utf-8'))
        if verified.get('passed') and all(Path(p).is_file() for p in verified['result']['previews']):
            receipt['checks']['live_caption_job_cuda_speech_render']={
                'passed':True,'result':verified['result'],'decoded_frames':verified['frames'],
                'validation_note':'The caption export is XML plus a transparent overlay. The exported timeline was rendered separately and the MP4 decoded successfully.'}
    generation_proof=ROOT/'output/validation/new-laptop/generation-inference.json'
    if args.resume and generation_proof.exists():
        verified=json.loads(generation_proof.read_text(encoding='utf-8'))
        if verified.get('passed') and all(Path(verified.get(key,'')).is_file() for key in ('image','video','image_to_video')):
            old=receipt['checks'].get('real_image_text_video_and_image_video')
            if old and not old.get('passed'):
                receipt.setdefault('previous_failures',[]).append({'check':'generation','error':old.get('error'),
                    'resolution':'Retested in isolated image/video worker processes, matching the editor.'})
            receipt['checks']['real_image_text_video_and_image_video']={
                'passed':True,'result':verified,'seconds':verified['seconds']}
    def save():proof.write_text(json.dumps(receipt,indent=2,ensure_ascii=False),encoding='utf-8')
    def check(name,fn):
        if receipt['checks'].get(name,{}).get('passed'):
            return
        start=time.monotonic();print('Checking '+name,flush=True)
        try:
            receipt['checks'][name]={'passed':True,'result':fn(),'seconds':round(time.monotonic()-start,2)}
        except Exception as error:
            receipt['checks'][name]={'passed':False,'error':f'{type(error).__name__}: {error}',
                                     'seconds':round(time.monotonic()-start,2)}
            print(name+': '+str(error),flush=True)
        save()

    def captions():
        from imageio_ffmpeg import get_ffmpeg_exe
        if receipt.get('caption_job_id'):
            job={'id':receipt['caption_job_id']}
        else:
            core=json.loads((ROOT/'output/validation/new-laptop/core-inference.json').read_text())
            source=core['hinglish_speech_vad_and_alignment']['result']['source']
            clip=folder/'six-second-input.mp4'
            subprocess.run([get_ffmpeg_exe(),'-nostdin','-v','error','-y','-i',source,'-t','6',
                '-vf','scale=360:-2','-r','30','-c:v','libx264','-preset','veryfast','-threads','2',
                '-c:a','aac',str(clip)],check=True)
            response=session.post(base+'/api/jobs',json={'mode':'captions','source_paths':[str(clip)],
                'device':'cuda','caption_style':'flash_cut','quality_check':True},timeout=30)
            response.raise_for_status();job=response.json()
            receipt['caption_job_id']=job['id'];save()
        deadline=time.monotonic()+900
        previous=''
        while time.monotonic()<deadline:
            response=session.get(base+'/api/jobs/'+job['id'],timeout=20)
            response.raise_for_status();job=response.json()
            if job['stage']!=previous:
                print('  '+job['stage'],flush=True);previous=job['stage']
            if job['status'] in ('complete','failed'):break
            time.sleep(3)
        assert job['status']=='complete',json.dumps(job,ensure_ascii=False)
        output=job['result']
        assert output['xml_files'] and all(Path(p).is_file() for p in output['xml_files'])
        if not output['previews']:
            from hinglish_app.assistant_media import render_xml
            output['previews']=[render_xml(output['xml_files'][0],folder/'captioned-preview.mp4')]
        assert output['previews'] and all(Path(p).is_file() for p in output['previews'])
        import av
        with av.open(output['previews'][0]) as media:
            assert media.streams.video and media.streams.audio
            assert sum(1 for _ in media.decode(video=0))>0
        return output

    def meaning():
        release_ollama(ROOT)
        from hinglish_semantic.local_judge import MeaningJudge
        from hinglish_semantic.core import SemanticSettings
        model=MeaningJudge(SemanticSettings(device='cuda',offline=True,matching_backend='meaning'),ROOT)
        try:
            answers=model.compare('Maine 40 rupaye diye.',[
                'Maine 60 rupaye diye.','Maine chalis rupaye diye.'])
            assert answers[0]['status']!='complete' and answers[1]['status']=='complete',str(answers)
            return {'model':model.manifest.get('ollama_model'),'answers':answers}
        finally:model.close()

    def vision():
        release_ollama(ROOT)
        tag=preferences(ROOT)['vision_model']
        image=Image.open(ROOT/'output/validation/new-laptop/vision-control.png')
        buffer=io.BytesIO();image.save(buffer,'PNG')
        schema={'type':'object','properties':{k:{'type':'string'} for k in ('text','left','right')},
                'required':['text','left','right']}
        try:
            response=session.post('http://127.0.0.1:11434/api/chat',json={
                'model':tag,'stream':False,'think':False,'format':schema,'keep_alive':'30s',
                'options':{'num_ctx':8192,'num_predict':256,'temperature':0},
                'messages':[{'role':'user','content':'Read the word at the top, then describe the color and shape on the left and right.',
                             'images':[base64.b64encode(buffer.getvalue()).decode()]}]},timeout=600)
            response.raise_for_status();payload=response.json()
            assert payload.get('done_reason')=='stop','Truncated image answer'
            answer=json.loads(payload['message']['content'])
            assert 'STORYLENS' in answer['text'].upper(),str(answer)
            assert 'red' in answer['left'].lower() and 'blue' in answer['right'].lower(),str(answer)
            loaded=session.get('http://127.0.0.1:11434/api/ps',timeout=10).json()
            return {'model':tag,'answer':answer,'loaded_models':loaded}
        finally:
            session.post('http://127.0.0.1:11434/api/generate',json={'model':tag,'keep_alive':0},timeout=60)

    def generation():
        release_ollama(ROOT)
        result=subprocess.run([sys.executable,'-E','-X','utf8',str(ROOT/'tools/validate_laptop_generation.py')],
            cwd=ROOT,check=True,timeout=1200)
        data=json.loads((ROOT/'output/validation/new-laptop/generation-inference.json').read_text())
        assert data['passed'],str(data)
        return data

    def specialists():
        subprocess.run([sys.executable,'-E','-X','utf8',str(ROOT/'tools/validate_laptop_models.py'),
                        '--phase','core'],cwd=ROOT,check=True,timeout=1200)
        data=json.loads((ROOT/'output/validation/new-laptop/core-inference.json').read_text())
        assert data and all(row['passed'] for row in data.values())
        return data

    if args.upgrades:
        from hinglish_cut.model_storage import configuration
        data=configuration(ROOT)
        completion=json.loads((Path(data['root'])/'logs/model-upgrade-completion.json').read_text())
        assert data.get('active') and completion['status']=='complete','Finish activation and retirement first'
        verified={}
        for name in ('planner','meaning','embedding','asr','independent_asr','broll_vision','cutout'):
            selected=data['roles'][name]
            result=json.loads((Path(data['root'])/'logs'/('upgrade-validation-'+name+'.json')).read_text())
            assert result['passed'] and result['model_path']==selected['path']
            assert result.get('model_revision')==selected.get('revision')
            verified[name]={'path':selected['path'],'revision':selected.get('revision')}
        edit=json.loads((ROOT/'output/validation/new-laptop/edit-pipeline-upgrade-inference.json').read_text())
        assert edit['passed'] and edit['asr_path']==data['roles']['asr']['path']
        assert edit['asr_revision']==data['roles']['asr']['revision']
        receipt.update(selected_replacements=verified,storage_root=data['root'],
                       scope='Fresh localhost caption/audio/video export and activated vision/meaning checks, backed by matching inference receipts for all seven replacements.')

    check('live_caption_job_cuda_speech_render',captions)
    from hinglish_cut.gpu_lock import gpu_lock
    with gpu_lock(ROOT):
        check('live_vision_model_real_pixels',vision)
        check('real_meaning_control',meaning)
        if not args.upgrades:
            check('real_image_text_video_and_image_video',generation)
            check('remaining_installed_specialist_models',specialists)
    receipt['passed']=all(row['passed'] for row in receipt['checks'].values())
    save()
    summary='localhost-upgrade-checks.json' if args.upgrades else 'localhost-model-checks.json'
    (ROOT/'output/validation/new-laptop'/summary).write_text(proof.read_text(encoding='utf-8'),encoding='utf-8')
    print(json.dumps({'passed':receipt['passed'],'receipt':str(proof)},indent=2),flush=True)
    return 0 if receipt['passed'] else 1


if __name__=='__main__':raise SystemExit(main())
