"""Run one bounded real inference check for a staged C-drive replacement."""
import argparse
import base64
import gc
import io
import json
import os
from pathlib import Path
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
STORE=Path(r'C:\Ai Models')
sys.path.insert(0,str(ROOT))


def run(name):
    import numpy as np
    from PIL import Image,ImageDraw
    from hinglish_cut.model_storage import configure,role
    from hinglish_cut.model_preferences import release_ollama
    configure(ROOT)
    release_ollama(ROOT)
    assert role(ROOT,name), 'A staged model selection is required'
    if name in ('planner','meaning'):
        import requests
        session=requests.Session();session.trust_env=False
        tag=role(ROOT,name)['ollama_model']
        def chat(messages,schema,images=None):
            if images: messages[-1]['images']=images
            response=session.post('http://127.0.0.1:11434/api/chat',json={
                'model':tag,'messages':messages,'format':schema,'stream':False,
                'think':False,'keep_alive':'30s','options':{'temperature':0,
                'seed':0,'num_ctx':8192,'num_predict':384}},timeout=900)
            response.raise_for_status()
            result=response.json()
            assert result.get('done_reason')=='stop','The control answer was truncated'
            return json.loads(result['message']['content'])
        try:
            if name=='meaning':
                # Each validation must perform inference, even if previous
                # application-level semantic responses are already cached.
                control_context='Runtime validation '+str(time.time_ns())
                from hinglish_semantic.models import Verifier
                from hinglish_semantic.core import SemanticSettings
                engine=Verifier(SemanticSettings(device='cuda',offline=True),ROOT)
                answers=[]
                memory={}
                try:
                    for a,b,expected in [
                        ('Maine 40 rupaye diye.','Maine 60 rupaye diye.',False),
                        ('Mujhe editing seekhni hai.','Main video edit karna seekhna chahta hoon.',True),
                        ('Rahul ne Aman ko phone kiya.','Aman ne Rahul ko phone kiya.',False),
                        ('Kal hum Mumbai nahi jayenge.','Kal hum Mumbai jayenge.',False)]:
                        answer=engine.check('match',expected=a,spoken=b,context=control_context)
                        assert answer['equivalent'] is expected,str(answer)
                        if not expected: assert not answer['safe_to_remove']
                        answers.append(answer)
                        memory=session.get('http://127.0.0.1:11434/api/ps',timeout=10).json()
                finally: engine.close()
                from hinglish_semantic.local_judge import MeaningJudge
                classifier=MeaningJudge(SemanticSettings(device='cuda',offline=True,matching_backend='meaning'),ROOT)
                try:
                    result=classifier.compare('Maine 40 rupaye diye.',
                        ['Maine 60 rupaye diye.','Maine chalis rupaye diye.'],context=control_context)
                    assert result[0]['status']!='complete' and result[1]['status']=='complete',str(result)
                    answers.append({'candidate_classifier':result})
                    memory=session.get('http://127.0.0.1:11434/api/ps',timeout=10).json()
                finally: classifier.close()
            else:
                schema={'type':'object','properties':{k:{'type':'string'} for k in ('text','left','right')},
                        'required':['text','left','right']}
                image=Image.open(ROOT/'output/validation/new-laptop/vision-control.png').convert('RGB')
                buffer=io.BytesIO();image.save(buffer,'PNG')
                answer=chat([{'role':'user','content':'Read the word at the top and describe the color and shape on the left and right.'}],
                    schema,[base64.b64encode(buffer.getvalue()).decode()])
                assert 'STORYLENS' in answer['text'].upper(),str(answer)
                assert 'red' in answer['left'].lower() and 'circle' in answer['left'].lower(),str(answer)
                assert 'blue' in answer['right'].lower() and ('square' in answer['right'].lower() or 'rectangle' in answer['right'].lower()),str(answer)
                answers=[answer]
                from hinglish_sound.brain import Brain
                brain=Brain(ROOT,model=tag,embed_model=role(ROOT,'embedding')['ollama_model'])
                try:
                    result=brain.ask('Choose exactly one supplied asset ID matching the requested mood. Return JSON.',
                        {'mood':'quiet reflective piano','assets':[{'id':'soft','description':'quiet piano'},
                        {'id':'loud','description':'loud explosion'}]},
                        {'type':'object','properties':{'id':{'type':'string','enum':['soft','loud']}},
                         'required':['id']},think=True,max_tokens=1600,label='Upgrade planning check')
                    assert result['id']=='soft',str(result)
                    answers.append({'id':result['id']})
                finally: brain.session.close()
            if name=='planner':
                memory=session.get('http://127.0.0.1:11434/api/ps',timeout=10).json()
            loaded=[row for row in memory.get('models',[]) if row.get('name')==tag]
            assert loaded and loaded[0].get('size_vram',0)>2**30,'The selected model did not run on the GPU'
            for row in loaded:
                if row.get('name')==tag and row.get('size_vram',0)>10.3*2**30:
                    raise ValueError('The configured model exceeds the planned GPU budget; reduce GPU layers/context before activation')
            return {'answers':answers,'loaded_models':memory}
        finally:
            session.post('http://127.0.0.1:11434/api/generate',json={'model':tag,'keep_alive':0},timeout=60)
            session.close()
    if name=='embedding':
        from hinglish_cut.ollama_embeddings import OllamaEmbeddings
        engine=OllamaEmbeddings(ROOT,role(ROOT,name)['ollama_model'])
        try:
            documents=engine.encode(['A quiet reflective melody played on a piano.',
                                     'A huge explosion and shattering glass.'],manage_residency=False)
            query=engine.encode(['soft sad piano music'],query=True,manage_residency=False)
            memory=engine.session.get(engine.url+'/api/ps',timeout=15).json()
            loaded=[row for row in memory.get('models',[]) if row.get('name')==engine.model]
            assert loaded and 2**30<loaded[0].get('size_vram',0)<=10.3*2**30,'Embedding GPU budget check failed'
            assert documents.shape==(2,4096) and query.shape==(1,4096)
            scores=(documents@query[0]).tolist()
            assert scores[0]>scores[1]+.03,str(scores)
            from hinglish_niche.style_memory import StyleEmbedder
            style=StyleEmbedder(ROOT)
            assert style.model_name==role(ROOT,name)['ollama_model']
            vectors=style.encode(['A bowler releases a cricket ball.'])
            assert vectors.shape==(1,4096)
            style.ollama.close()
            return {'dimensions':4096,'retrieval_scores':scores,'loaded_models':memory}
        finally: engine.close()
    # Ollama owns its CUDA context. Importing PyTorch for those checks creates
    # an unnecessary second context on a laptop with only 16 GB system RAM.
    if name in ('asr','independent_asr','broll_vision'):
        import torch
        torch.set_num_threads(8)
        torch.cuda.reset_peak_memory_stats()
    if name in ('asr','independent_asr'):
        from hinglish_cut.media import read_audio
        audio=read_audio(ROOT/'output/validation/new-laptop/speech-control.wav',0,6)
        from hinglish_cut.backends import LocalSpeech
        from hinglish_cut.model import Settings
        if name=='asr':
            engine=LocalSpeech(Settings(device='cuda',offline=True,cpu_threads=8),ROOT/'models')
        else:
            from hinglish_semantic.speech import TurboSpeech
            from hinglish_semantic.core import SemanticSettings
            engine=TurboSpeech(SemanticSettings(device='cuda',offline=True,cpu_threads=8),ROOT)
        try:
            transcript=engine.recognize(audio)
            assert len(transcript.split())>=3,'Empty or unusably short speech control'
            if name=='asr':
                if role(ROOT,name)['repo'].startswith('Qwen/'):
                    assert getattr(engine,'qwen_asr',False),'The selected Qwen speech model was not loaded'
                else:
                    assert Path(engine.asr.config._name_or_path).resolve()==Path(role(ROOT,name)['path']).resolve(), 'A different speech model was loaded'
                assert not engine.detect(np.zeros(16000,np.float32))
                words=engine.align(audio,transcript)
                assert words and all(0<=w.start<=w.end<=6.3 for w in words)
            free,total=torch.cuda.mem_get_info()
            return {'transcript':transcript,'torch_peak_allocated_GiB':torch.cuda.max_memory_allocated()/2**30,
                    'gpu_device_used_GiB':(total-free)/2**30,
                    'memory_note':'Device-wide snapshot includes other driver allocations; PyTorch peak excludes CTranslate2.'}
        finally: engine.close()
    if name=='broll_vision':
        from hinglish_broll.vision import Vision
        engine=Vision('openai/clip-vit-base-patch32',ROOT,device='cuda',threads=8)
        try:
            assert engine.multimodal,'The legacy CLIP model was selected'
            images=[]
            for color,shape in [('red','circle'),('blue','square')]:
                image=Image.new('RGB',(256,256),'white');draw=ImageDraw.Draw(image)
                if shape=='circle': draw.ellipse((40,40,216,216),fill=color)
                else: draw.rectangle((40,40,216,216),fill=color)
                images.append(image)
            visual=engine.images(images)
            text=engine.texts(['A red circle on a white background.','A blue square on a white background.'])
            assert visual.shape==text.shape==(2,2048),(visual.shape,text.shape)
            assert np.isfinite(visual).all() and np.isfinite(text).all()
            scores=text@visual.T
            assert scores[0,0]>scores[0,1]+.02 and scores[1,1]>scores[1,0]+.02,str(scores)
            free,total=torch.cuda.mem_get_info()
            return {'shape':list(visual.shape),'retrieval_scores':scores.tolist(),
                    'torch_peak_allocated_GiB':torch.cuda.max_memory_allocated()/2**30,
                    'gpu_device_used_GiB':(total-free)/2**30}
        finally: engine.close()
    if name=='cutout':
        from hinglish_motion.assets import Remover
        # Actual first-frame pixels, not a model-produced fixture.
        from hinglish_broll.library import read_frames
        source=next((ROOT/'input/phase1').rglob('*.mp4'))
        image=read_frames(source,[.5],size=512)[0][1]
        remover=Remover(ROOT)
        output=remover(image,'person')
        assert output.mode=='RGBA' and output.size==image.size
        alpha=np.asarray(output.getchannel('A'))
        assert alpha.max()>128 and alpha.min()<128,'The cutout mask contains no foreground/background separation'
        output.save(STORE/'logs/upgraded-cutout-control.png')
        return {'size':list(output.size),'foreground_share':float((alpha>128).mean()),
                'providers':remover.last_providers}
    raise ValueError('Unknown check '+name)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--check',required=True)
    parser.add_argument('--output',type=Path)
    args=parser.parse_args();start=time.monotonic()
    target=args.output or STORE/'logs'/('upgrade-validation-'+args.check+'.json')
    from hinglish_cut.model_storage import role
    selected=role(ROOT,args.check)
    try:
        result=run(args.check)
        proof={'passed':True,'result':result,'seconds':round(time.monotonic()-start,2),
               'model_revision':selected.get('revision'), 'model_path':selected.get('path')}
    except Exception as error:
        proof={'passed':False,'error':f'{type(error).__name__}: {error}','seconds':round(time.monotonic()-start,2)}
        target.write_text(json.dumps(proof,indent=2),encoding='utf-8')
        raise
    target.write_text(json.dumps(proof,indent=2,ensure_ascii=False),encoding='utf-8')
    print(args.check+': REAL_INFERENCE_PASSED',flush=True)


if __name__=='__main__':
    from hinglish_cut.gpu_lock import gpu_lock
    with gpu_lock(ROOT):main()
