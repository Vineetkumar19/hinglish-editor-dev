"""Auditable local-only documentary trial. Existing planner, saved rules and stock templates."""
import dataclasses, hashlib, html, json, math, os, subprocess, sys, time, traceback
from pathlib import Path
from fractions import Fraction
ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))
OUT=ROOT/'output/reference-analysis/local-documentary-trial'
OUT.mkdir(parents=True,exist_ok=True)

def save(name,value):
    (OUT/name).write_text(json.dumps(value,indent=2,ensure_ascii=False),encoding='utf-8')

def main():
    import numpy as np, requests, av
    from PIL import Image,ImageDraw
    from imageio_ffmpeg import get_ffmpeg_exe
    from hinglish_motion import plan
    from hinglish_motion.settings import MotionSettings
    from hinglish_motion.style import look,choices
    from hinglish_motion.pipeline import set_durations,_scene_payload,standalone_segments
    from hinglish_motion.render import SceneRenderer
    from hinglish_shorts.render import _Video
    from hinglish_niche.profiles import Profiles,use,inject
    from hinglish_niche.documentary import reference
    from hinglish_niche.style_memory import search
    from hinglish_aigen.plan import speech_lines
    from hinglish_cut.model import Word
    from hinglish_eval import guard
    replay_first = '--render-first-answer' in sys.argv
    budget_file=OUT/'budget-start.json'
    start_unix=json.loads(budget_file.read_text(encoding='utf-8'))['started_unix'] if budget_file.exists() else time.time()
    if not budget_file.exists():save('budget-start.json',{'started_unix':start_unix})
    began=time.monotonic()-(time.time()-start_unix);deadline=began+1800
    receipt={'status':'running','started_unix':start_unix,'budget_seconds':1800,'model':'qwen3:8b',
             'cloud_inference_calls':0,'cloud_creative_revision':False,'pipeline':'existing hinglish_motion planner and SceneRenderer',
             'source_seconds':[0,60],'reference_sets':['beneath-documentary-edit','crick-edit-editing-style'],
             'scope':'Local LLM planning and local rendering, not diffusion AI-video generation',
             'harness_changes':['Capture fresh model requests/responses, bypass answer cache',
                                'Provide both existing saved style memories and retrieval examples',
                                'Add local_asset_id to asset schema so the model selects existing local files',
                                'Use 720p/30fps and a 30-minute watchdog; no new animation templates or creative prompt rules']}
    save('receipt.json',receipt)
    if replay_first:
        receipt['deadline_fallback'] = 'Render the completed first local answer through existing autofill/repair; skip further slow model retries to reserve export time. No creative replacement.'
        guard.ATTEMPTS = 1
    def elapsed():return time.monotonic()-began
    def progress(s):
        print(f'[{elapsed():.1f}s] {s}',flush=True)
        receipt['stage']=s;receipt['elapsed_seconds']=elapsed();save('receipt.json',receipt)
    def remaining():
        left=deadline-time.monotonic()
        if left<=0:raise TimeoutError('30-minute run limit reached')
        return left
    inventory=json.loads((ROOT/'output/reference-analysis/crick-edit-editing-style/inventory.json').read_text(encoding='utf-8'))
    source=next(r['path'] for r in inventory if r['slug']=='reference-08')
    receipt['source']=source
    analysed=ROOT/'output/reference-analysis/crick-edit-editing-style/reference-08'
    word_data=[r for r in json.loads((analysed/'words.json').read_text(encoding='utf-8')) if r['start']<60]
    words=[Word(r['text'],r['start'],min(60,r['end'])) for r in word_data]
    lines=speech_lines(words)
    save('input-lines.json',[dataclasses.asdict(l) for l in lines])
    raw_segments=[r for r in json.loads((analysed/'transcript.json').read_text(encoding='utf-8')) if r['start']<60]
    save('source-transcript.json',raw_segments)
    asset_root=ROOT/'output/reference-analysis/crick-edit-editing-style/demo/assets'
    assets={
        'steyn-cutout':{'file':str(asset_root/'steyn-cutout.png'),'kind':'person','description':'Dale Steyn bowling pose, transparent cut-out; extracted from the supplied reference at 35.3 seconds','cutout':True},
        'bowling-photo':{'file':str(asset_root/'bowler.jpg'),'kind':'photo','description':'Dale Steyn in a green/yellow South Africa kit, bowling pose; reference at 35.3 seconds'},
        'celebration-photo':{'file':str(asset_root/'team.jpg'),'kind':'photo','description':'South Africa players celebrating together; reference at 234.5 seconds'},
        'steyn-portrait':{'file':str(asset_root/'portrait.jpg'),'kind':'photo','description':'Dale Steyn tossing a cricket ball; reference at 739.57 seconds'},
        'bowling-footage':{'file':str(OUT/'assets/bowling-footage.mp4'),'kind':'clip','description':'Seven seconds of cricket bowling footage from reference at 90.2 seconds'},
        'reaction-footage':{'file':str(OUT/'assets/reaction-footage.mp4'),'kind':'clip','description':'Five seconds of South Africa celebration footage from reference at 234.3 seconds'}}
    (OUT/'assets').mkdir(exist_ok=True)
    for key,start,length in [('bowling-footage',90.2,7),('reaction-footage',234.3,5)]:
        if replay_first and Path(assets[key]['file']).exists():continue
        subprocess.run([get_ffmpeg_exe(),'-hide_banner','-loglevel','error','-nostdin','-y','-ss',str(start),'-i',source,'-t',str(length),'-an','-vf','scale=960:540,fps=30','-c:v','libx264','-preset','veryfast','-crf','20','-threads','2',assets[key]['file']],check=True,timeout=remaining())
    save('asset-catalogue.json',assets)
    context=Profiles(ROOT).context('cricket')
    context['documentary_style']='crick-edit-editing-style'
    # Both complete saved rule sets are supplied below. Do not repeat Crick's rules
    # a second time inside the profile, which wastes local context memory.
    context.pop('documentary_reference',None)
    memories=[];examples=[]
    for key in receipt['reference_sets']:
        memory=reference(ROOT,key)
        memories.append({k:memory[k] for k in ('name','documentary_set','learning_method','rules','animation_settings') if k in memory})
        progress('Retrieving saved examples: '+key)
        query=' '.join(l.text for l in lines)[:1800]
        results=[] if replay_first else search(ROOT,key,query,4)
        examples.extend({'style':key,'source':r['source'],'start':r['start'],'end':r['end'],'reference':r['text']} for r in results)
    if replay_first:
        remembered=json.loads((OUT/'supplied-style-memory.json').read_text(encoding='utf-8'))
        memories,examples=remembered['memories'],remembered['examples']
    else:save('supplied-style-memory.json',{'memories':memories,'examples':examples})
    session=requests.Session();session.trust_env=False
    installed=session.get('http://127.0.0.1:11434/api/tags',timeout=10).json()
    model=next(m for m in installed['models'] if m['name']=='qwen3:8b')
    receipt['model_digest']=model['digest'];receipt['model_details']=model['details'];save('receipt.json',receipt)
    calls=[]
    class Brain:
        name='Ollama qwen3:8b (local-only, fresh answers)'
        # Retrieval already contains the same four examples per style below;
        # omit the optional .root hook so the planner does not duplicate them.
        def json(self,system,data,schema,max_tokens=2400,think=False):
            if replay_first:
                recorded=json.loads((OUT/'model-response-01.json').read_text(encoding='utf-8'))
                receipt['model_calls']=[recorded['metrics']]
                progress('Using the completed first local answer; existing rule repair only, no further model generation')
                return recorded['answer']
            payload={**data,'saved_documentary_styles':memories,'saved_documentary_examples':examples,
                     'source_reference':{'file':Path(source).name,'raw_asr_segments':raw_segments},
                     'available_local_assets':[{**v,'id':k} for k,v in assets.items()]}
            system,payload=inject(system,payload)
            body={'model':'qwen3:8b','stream':True,'think':think,'format':schema,
                  'options':{'temperature':.2,'seed':7,'num_ctx':10240,'num_predict':max_tokens+(3000 if think else 0)},
                  'messages':[{'role':'system','content':system},{'role':'user','content':json.dumps(payload,ensure_ascii=False)}]}
            index=len(calls)+1;save(f'model-request-{index:02}.json',body)
            progress(f'Local model request {index}: planning (max {max_tokens} tokens)')
            start=time.monotonic();content='';thinking='';final={};last_log=start
            with session.post('http://127.0.0.1:11434/api/chat',json=body,stream=True,timeout=(10,min(remaining(),900))) as response:
                response.raise_for_status()
                for line in response.iter_lines():
                    remaining()
                    if not line:continue
                    item=json.loads(line)
                    if 'error' in item:raise RuntimeError(item['error'])
                    msg=item.get('message',{});content+=msg.get('content','');thinking+=msg.get('thinking','')
                    if time.monotonic()-last_log>=30:
                        save(f'model-partial-{index:02}.json',{'content':content,'thinking':thinking,'elapsed_seconds':time.monotonic()-start,'complete':False})
                        progress(f'Local model request {index}: {len(content)} response characters generated');last_log=time.monotonic()
                    if item.get('done'):final=item
            answer=json.loads(content or '{}')
            save(f'model-partial-{index:02}.json',{'content':content,'thinking':thinking,'elapsed_seconds':time.monotonic()-start,'complete':True})
            info={k:v for k,v in final.items() if k not in ('message','context')}
            info.update(elapsed_seconds=time.monotonic()-start,model='qwen3:8b',request_sha256=hashlib.sha256(json.dumps(body,sort_keys=True).encode()).hexdigest())
            if info.get('eval_duration'):info['tokens_per_second']=info.get('eval_count',0)/(info['eval_duration']/1e9)
            save(f'model-response-{index:02}.json',{'answer':answer,'thinking':thinking,'metrics':info})
            calls.append(info);receipt['model_calls']=calls;save('receipt.json',receipt)
            progress(f'Local model request {index} finished: {info.get("eval_count",0)} tokens in {info["elapsed_seconds"]:.1f}s')
            return answer
    original_schema=plan.plan_schema
    def schema(count):
        result=original_schema(count)
        spec=result['properties']['moments']['items']['properties']['assets']['items']
        spec['properties']['local_asset_id']={'type':'string','enum':list(assets)}
        spec['required'].append('local_asset_id')
        return result
    plan.plan_schema=schema
    settings=MotionSettings(count='6',style='card:card_crick_edit_reference',mode='full',coverage='full',fps=30,brain='ollama',assets='web',check=False)
    progress('Local model planning started; existing planner and rule checks')
    with use(context):
        try:planned=plan.plan_scenes(Brain(),lines,settings,progress,full=True)
        finally:plan.plan_schema=original_schema
    guard.save(OUT)
    scenes=[p.to_dict() for p in planned]
    save('local-planned-scenes.json',scenes)
    if not scenes:raise ValueError('The local model produced no usable scenes')
    for s in scenes:
        s['mode']='full'
        for a in s['assets']:
            key=a.get('local_asset_id')
            if not key:
                # The existing field sanitiser keeps only kind/query/name. Restore file-binding
                # metadata from the model's recorded choice, never choose a replacement ourselves.
                matches=[]
                for path in sorted(OUT.glob('model-response-*.json')):
                    raw=json.loads(path.read_text(encoding='utf-8'))['answer']
                    for moment in raw.get('moments',[]):
                        if moment.get('line')!=s['line']:continue
                        for original in moment.get('assets',[]):
                            if plan.clean_query(original.get('query',''))==a.get('query'):
                                matches.append(original.get('local_asset_id'))
                if matches:key=matches[-1]
            if key not in assets:raise ValueError('Local model did not choose an available asset ID')
            selected=assets[key];a.update(file=os.path.relpath(selected['file'],OUT),cutout=selected.get('cutout',False),source='supplied reference',selected_local_asset_id=key)
    set_durations(scenes,lines,60,full=True)
    theme,speed,name=look(ROOT,settings.style)
    project={'version':2,'tool':'Local-only documentary trial','settings':dataclasses.asdict(settings),'style':settings.style,
             'style_name':name,'theme':theme,'speed':speed,'width':1280,'height':720,'fps':'30','seconds':60,
             'scenes':scenes,'full':True,'lines':[dataclasses.asdict(l) for l in lines],'timeline':None,'style_choices':choices(ROOT),'creator_profile':'cricket'}
    save('motion-project.json',project)
    session.post('http://127.0.0.1:11434/api/generate',json={'model':'qwen3:8b','keep_alive':0},timeout=min(30,remaining())).raise_for_status()
    receipt['model_unloaded_before_render']=True
    # Preserve source audio verbatim; this isolates the visual planning test from a second sound-design experiment.
    raw=subprocess.run([get_ffmpeg_exe(),'-hide_banner','-loglevel','error','-nostdin','-i',source,'-t','60','-vn','-ar','48000','-ac','2','-f','f32le','pipe:1'],check=True,capture_output=True,timeout=remaining()).stdout
    audio=np.frombuffer(raw,dtype='<f4').reshape(-1,2).T.copy()
    receipt['audio']='Original first-minute source audio retained unchanged; local sound director not tested'
    progress(f'Rendering {len(scenes)} local-model scenes at 720p/30fps')
    renderer=SceneRenderer(1280,720);writer=_Video(OUT/'LOCAL_MODEL_60S.mp4',1280,720,Fraction(30),'libx264',audio=True);writer.stream.thread_count=2
    try:
        for s,count in standalone_segments(scenes,60,Fraction(30)):
            remaining();payload=_scene_payload(OUT,s,project)
            s['layout']=renderer.check(payload)
            renderer.still(payload,min(max(.5,s['duration']*.6),s['duration']-.05),OUT/f'scene-{s["index"]:02}.jpg')
            s['still']=f'scene-{s["index"]:02}.jpg'
            renderer.load(payload)
            progress(f'Rendering scene {s["index"]}/{len(scenes)}: {s["template"]}, {s["duration"]:.2f}s')
            for n in range(count):
                remaining();writer.write(renderer.frame(n/30))
                if n and n%300==0:progress(f'Rendering scene {s["index"]}: {n/30:.0f}s rendered')
        need=60*48000;mix=np.zeros((2,need),np.float32);mix[:,:min(need,audio.shape[1])]=audio[:,:need]
        writer.write_audio(mix);writer.finish()
    except BaseException:writer.abort();raise
    finally:renderer.close()
    save('motion-project.json',project)
    progress('Verifying the exported video')
    count=0;sampled=[];points=list(range(1,60,3));i=0
    with av.open(str(OUT/'LOCAL_MODEL_60S.mp4')) as container:
        stream=container.streams.video[0];duration=float(stream.duration*stream.time_base)
        for f in container.decode(video=0):
            count+=1;t=float(f.pts*f.time_base)
            if i<len(points) and t>=points[i]:sampled.append((t,f.to_image().resize((320,180))));i+=1
    board=Image.new('RGB',(1280,math.ceil(len(sampled)/4)*204),'#101318');draw=ImageDraw.Draw(board)
    for i,(t,im) in enumerate(sampled):
        x=i%4*320;y=i//4*204;board.paste(im,(x,y));draw.text((x+8,y+185),f'{t:.2f}s',fill='white')
    board.save(OUT/'export-review.jpg',quality=92)
    assert count==1800 and abs(duration-60)<.001,(count,duration)
    receipt.update(status='complete',elapsed_seconds=elapsed(),decoded_frames=count,video_seconds=duration,scene_count=len(scenes),
                   templates=[s['template'] for s in scenes],layout_warnings=[{'scene':s['index'],'warnings':s['layout']} for s in scenes if s.get('layout')],
                   video='LOCAL_MODEL_60S.mp4',creative_plan_edited_by_cloud=False)
    save('receipt.json',receipt)
    figures=''.join(f'<figure><img src="{s["still"]}"><figcaption><b>{s["start"]:.2f}–{s["start"]+s["duration"]:.2f}s · {html.escape(s["template"])}</b><br>{html.escape(s["why"])}<br><small>{html.escape("; ".join(s.get("layout",[])))}</small></figcaption></figure>' for s in scenes)
    runtime=elapsed()/60
    page=f'''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Local Qwen3 documentary test</title><style>body{{background:#101318;color:#e8e4da;font:17px/1.65 system-ui;max-width:1200px;margin:auto;padding:30px}}h1{{font:42px Georgia;color:#e8d8b9}}video,img{{width:100%;border-radius:8px}}a{{color:#d2c087}}main{{display:grid;grid-template-columns:1fr 1fr;gap:24px}}figure{{margin:0}}figcaption{{padding:8px 0;font-size:15px}}small{{color:#adada7}}@media(max-width:700px){{main{{grid-template-columns:1fr}}}}</style><h1>Your local model’s edit.</h1><p>Qwen3:8B · 60 seconds · 720p/30fps · completed in {runtime:.1f} minutes. Existing local planner, saved vineet documentry edit and cricAddict instructions and stock animation templates. No cloud creative planning or revisions.</p><video controls playsinline preload="metadata" src="LOCAL_MODEL_60S.mp4"></video><p>The original first-minute reference audio is retained unchanged. This tests local visual planning and template execution; it does not test newly generated narration, music or sound design. Assets come from the reference you supplied. Automatic schema/rule checks may repair or trim model fields; all requests and raw answers are saved.</p><p><a href="receipt.json">Model and runtime receipt</a> · <a href="local-planned-scenes.json">Local plan</a> · <a href="supplied-style-memory.json">Saved instructions supplied</a> · <a href="model-checks.json">Automatic rule checks</a> · <a href="export-review.jpg">Encoded-frame review</a></p><main>{figures}</main></html>'''
    (OUT/'report.html').write_text(page,encoding='utf-8')
    progress('COMPLETE: '+str(OUT/'LOCAL_MODEL_60S.mp4'))

if __name__=='__main__':
    try:main()
    except BaseException as error:
        traceback.print_exc()
        previous=json.loads((OUT/'receipt.json').read_text(encoding='utf-8')) if (OUT/'receipt.json').exists() else {}
        previous.update(status='failed',error=str(error));save('receipt.json',previous)
        sys.exit(1)
