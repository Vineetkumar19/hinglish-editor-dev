"""Small reasoning-enabled local repair; no cloud-authored labels or notes."""
import copy,json,sys,time,re
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import local_documentary_synced as d
from hinglish_motion.speech_clock import compile_plan,frame_at

def main():
    import requests
    words=d.load('timed-words.json')
    records=sorted(d.OUT.glob('model-response-*.json'))
    previous=next(json.loads(p.read_text(encoding='utf8'))['answer'] for p in reversed(records)
                  if not d.validation(json.loads(p.read_text(encoding='utf8'))['answer'],words)[0])
    scenes=compile_plan(previous,words,d.EFFECTS)
    index=next(i for i,s in enumerate(scenes) if s['effect']=='crick-evidence')
    panel=scenes[index]
    tokens=[w for w in words if panel['start_frame']<=frame_at(w['start'])<panel['end_frame']]
    text=lambda n:{'type':'string','maxLength':n,'pattern':f"^[A-Z0-9][A-Za-z0-9 .,'/&()\\-]{{0,{n-1}}}$"}
    props={'panel_title':text(20),'opening_caption':text(26),'film_title':text(20),'film_subtitle':text(26),
           'film_caption':text(26),'paper_title':text(20),'paper_subtitle':text(26),'book_caption':text(26)}
    for i in range(3):
        allowed=[w['id'] for w in tokens if i or w['start']<=panel['start']+2.5]
        props[f'row_{i+1}']={'type':'object','properties':{'heading':text(16),'detail':text(26),'word':{'type':'string','enum':allowed}},'required':['heading','detail','word']}
    schema={'type':'object','properties':props,'required':list(props),'additionalProperties':False}
    payload={'request':'Repair your local edit. Timing IDs belong ONLY in row.word. All titles, captions, headings and details must be meaningful natural English, never IDs or unfinished phrases. Reason briefly about the speech before answering.',
        'panel_range':[panel['start'],panel['start']+panel['seconds']],
        'spoken_words':[{'cue':w['id'],'onset':round(w['start'],3),'spoken':w['text']} for w in tokens],
        'panel_problem':'The old notes stay empty for 8.6 seconds. Choose three actually narrated facts. The first row must start within 2.5 seconds of panel start. Use the first numeric token for numeric statements; rows in narration order. No invented years or units.',
        'scene_speech':{s['effect']:' '.join(w['text'] for w in words if s['start_frame']<=frame_at(w['start'])<s['end_frame']) for s in scenes},
        'copy_problem':'The paper scene wrongly named Sachin while its speech discusses the main bowler retiring. Some captions were unfinished clauses. Write your own complete English labels for the requested fields from the corresponding scene speech. Do not copy IDs or translate by listing tokens.',
        'local_style_memory':[{'name':m['name'],'rules':m['rules'][-2:]} for m in d.load('director-input.json')['memory']]}
    attempt=max(int(p.stem.rsplit('-',1)[-1]) for p in records)+1
    body={'model':d.MODEL,'stream':True,'think':True,'format':schema,
          'options':{'num_ctx':8192,'num_predict':1500,'num_thread':4,'temperature':.18,'seed':27},
          'messages':[{'role':'system','content':'You are the offline local documentary director. Interpret the supplied Hindi/English narration and write short, complete English display labels. You choose the labels and notes yourself. No cloud creative text is supplied. Cue IDs are metadata, NEVER display text. Think concisely, then return JSON.'},
                      {'role':'user','content':json.dumps(payload,ensure_ascii=False,separators=(',',':'))}]}
    d.save(f'model-request-{attempt:02}.json',body)
    session=requests.Session();session.trust_env=False;start=time.time();last=start;content='';thinking_count=0;final={}
    with session.post('http://127.0.0.1:11434/api/chat',json=body,stream=True,timeout=(10,900)) as response:
        response.raise_for_status()
        for line in response.iter_lines():
            if not line:continue
            item=json.loads(line)
            if 'error' in item:raise RuntimeError(item['error'])
            message=item.get('message',{});content+=message.get('content','');thinking_count+=len(message.get('thinking',''))
            if time.time()-last>30:
                print(f'Local reasoning repair: {thinking_count} reasoning characters, {len(content)} answer characters',flush=True);last=time.time()
            if item.get('done'):final=item
    patch=json.loads(content);answer=copy.deepcopy(previous)
    for scene in answer['scenes']:
        effect=scene['effect']
        if effect=='crick-evidence':scene.update(headline=patch['panel_title'],notes=[patch[f'row_{i+1}'] for i in range(3)])
        elif effect=='beneath-road':scene['caption']=patch['opening_caption']
        elif effect=='crick-film':scene.update(headline=patch['film_title'],subline=patch['film_subtitle'],caption=patch['film_caption'])
        elif effect=='crick-paper':scene.update(headline=patch['paper_title'],subline=patch['paper_subtitle'])
        elif effect=='crick-book':scene['caption']=patch['book_caption']
    metrics={k:v for k,v in final.items() if k!='message'};metrics['elapsed_seconds']=time.time()-start
    d.save(f'model-response-{attempt:02}.json',{'answer':answer,'metrics':metrics,'local_patch':patch,'reasoning_enabled':True})
    errors,_=d.validation(answer,words)
    if re.search(r'\bw\d+\b',json.dumps(patch),re.I):
        # IDs in the word fields are valid; only visible strings are forbidden.
        labels=[v for k,v in patch.items() if not isinstance(v,dict)]
        labels.extend(n[f] for n in answer['scenes'][index]['notes'] for f in ['heading','detail'])
        if any(re.search(r'\bw\d+\b',v,re.I) for v in labels):errors.append('Internal timing IDs leaked into display labels.')
    d.save(f'plan-checks-{attempt:02}.json',{'errors':errors})
    if errors:raise ValueError(errors)
    d.save('local-plan.json',answer)
    print('Local reasoning repair accepted: '+json.dumps(patch),flush=True)

if __name__=='__main__':main()
