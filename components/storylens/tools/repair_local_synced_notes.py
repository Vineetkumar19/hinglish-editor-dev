"""Ask the same offline director to repair a late statistics panel only.

The engineer supplies measured timing/layout errors. Qwen supplies all words,
facts and row anchors; the rest of its saved scene plan remains intact.
"""
import json,sys,time,copy
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import local_documentary_synced as d
from hinglish_motion.speech_clock import compile_plan,frame_at

def main():
    import requests
    files=sorted(d.OUT.glob('model-response-*.json'))
    previous=json.loads(files[-1].read_text(encoding='utf8'))['answer']
    words=d.load('timed-words.json')
    scenes=compile_plan({'scenes':[{**s,'notes':[],'photos':[],'sfx':'none'} for s in previous['scenes']]},words,d.EFFECTS)
    issues=[]
    for index,scene in enumerate(scenes):
        raw=previous['scenes'][index]
        if raw['effect']!='crick-evidence':continue
        first=min(next(w['start'] for w in words if w['id']==n['word']) for n in raw['notes'])
        if first-scene['start']>2.5:issues.append((index,scene,first-scene['start']))
    if not issues:
        print('No late evidence rows to repair.',flush=True);return
    session=requests.Session();session.trust_env=False
    for index,scene,gap in issues:
        tokens=[w for w in words if scene['start_frame']<=frame_at(w['start'])<scene['end_frame']]
        text=lambda n:{'type':'string','pattern':f'^[ -~]{{0,{n}}}$','maxLength':n}
        props={'headline':text(20)}
        for i in range(3):
            allowed=[w['id'] for w in tokens if i or w['start']<=scene['start']+2.5]
            props[f'row_{i+1}']={'type':'object','properties':{'heading':text(16),'detail':text(26),'word':{'type':'string','enum':allowed}},'required':['heading','detail','word']}
        copy_fields={'crick-hero':['headline'],'crick-evidence':['headline'],'crick-paper':['headline','subline'],
                     'crick-book':['headline','subline','caption'],'crick-film':['headline','subline','caption'],'crick-tv':['headline','caption']}
        scene_props={}
        for j,s in enumerate(scenes):
            fields=copy_fields.get(s['effect'],['caption'])
            field_props={f:text(20 if f=='headline' else 26) for f in fields}
            scene_props[f'scene_{j+1}']={'type':'object','properties':field_props,'required':fields,'additionalProperties':False}
        props['copy']={'type':'object','properties':scene_props,'required':list(scene_props),'additionalProperties':False}
        schema={'type':'object','properties':props,'required':list(props),'additionalProperties':False}
        payload={'panel_range':[scene['start'],scene['start']+scene['seconds']],
                 'words':[[w['id'],round(w['start'],3),w['text']] for w in tokens],
                 'measured_error':f'The paper note panel stays empty for {gap:.2f} seconds. The first row must begin within 2.5 seconds of this scene start.',
                 'instruction':'Write the headline and three rows using the actual panel speech. You choose concise natural English wording and precise spoken anchors. A numeric heading must use the FIRST corresponding numeric token as its word anchor. Use the actual Swing/rare token if selecting that fact. Three rows in increasing narration order. Also write NEW English copy for the supplied visible slots of each scene using ONLY that scene transcript. Complete natural labels, never unfinished clauses, truncations, transliterations or invented numbers/superlatives. Do not carry a player name into an unrelated scene. Do not add narration. No creative replacement scene plan or animation is supplied. All existing scene boundaries, effects and photos stay intact.',
                 'scenes':[{'key':f'scene_{j+1}','effect':s['effect'],'visible_slots':list(scene_props[f'scene_{j+1}']['properties']),
                            'speech':' '.join(w['text'] for w in words if s['start_frame']<=frame_at(w['start'])<s['end_frame'])} for j,s in enumerate(scenes)],
                 'memory':d.load('director-input.json')['memory']}
        attempt=max(int(p.stem.rsplit('-',1)[-1]) for p in d.OUT.glob('model-response-*.json'))+1
        body={'model':d.MODEL,'stream':True,'think':False,'format':schema,
              'options':{'num_ctx':8192,'num_predict':1200,'num_thread':4,'temperature':.18,'seed':27},
              'messages':[{'role':'system','content':'You are the same offline documentary director. Repair your own late evidence panel using provided acoustic words and saved local memory. No cloud creative plan is supplied. Return JSON only.'},
                          {'role':'user','content':json.dumps(payload,ensure_ascii=False,separators=(',',':'))}]}
        d.save(f'model-request-{attempt:02}.json',body)
        start=time.time();last=start;content='';final={}
        with session.post('http://127.0.0.1:11434/api/chat',json=body,stream=True,timeout=(10,900)) as response:
            response.raise_for_status()
            for line in response.iter_lines():
                if not line:continue
                item=json.loads(line)
                if 'error' in item:raise RuntimeError(item['error'])
                content+=item.get('message',{}).get('content','')
                if time.time()-last>30:print(f'Local panel repair: {len(content)} characters',flush=True);last=time.time()
                if item.get('done'):final=item
        patch=json.loads(content);answer=copy.deepcopy(previous)
        answer['scenes'][index]['headline']=patch['headline']
        answer['scenes'][index]['notes']=[patch[f'row_{i+1}'] for i in range(3)]
        for j in range(len(answer['scenes'])):answer['scenes'][j].update(patch['copy'][f'scene_{j+1}'])
        metrics={k:v for k,v in final.items() if k!='message'};metrics['elapsed_seconds']=time.time()-start
        d.save(f'model-response-{attempt:02}.json',{'answer':answer,'metrics':metrics,'local_patch':patch,'scene':index+1})
        errors,_=d.validation(answer,words)
        d.save(f'plan-checks-{attempt:02}.json',{'errors':errors})
        if errors:raise ValueError(errors)
        d.save('local-plan.json',answer);previous=answer
        print('Local panel repair accepted: '+json.dumps(patch),flush=True)

if __name__=='__main__':main()
