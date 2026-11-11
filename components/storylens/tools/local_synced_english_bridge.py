"""Two small local Qwen calls: interpret speech, then write display slots.

All English interpretation and copy are model outputs. The only automatic
correction is literal-number matching to an already measured acoustic token.
"""
import json,sys,time,copy,re
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import local_documentary_synced as d
from hinglish_motion.speech_clock import compile_plan,frame_at

def main():
    import requests
    words=d.load('timed-words.json');files=sorted(d.OUT.glob('model-response-*.json'))
    previous=next(json.loads(p.read_text(encoding='utf8'))['answer'] for p in reversed(files) if not d.validation(json.loads(p.read_text(encoding='utf8'))['answer'],words)[0])
    scenes=compile_plan(previous,words,d.EFFECTS);session=requests.Session();session.trust_env=False
    def ask(label,messages,format=None,max_tokens=500):
        attempt=max(int(p.stem.rsplit('-',1)[-1]) for p in d.OUT.glob('model-request-*.json'))+1
        body={'model':d.MODEL,'stream':True,'think':False,'options':{'num_ctx':4096,'num_predict':max_tokens,'num_thread':4,'temperature':.18,'seed':27},'messages':messages}
        if format:body['format']=format
        d.save(f'model-request-{attempt:02}.json',body);start=time.time();last=start;content='';final={}
        with session.post('http://127.0.0.1:11434/api/chat',json=body,stream=True,timeout=(10,600)) as response:
            response.raise_for_status()
            for line in response.iter_lines():
                if not line:continue
                item=json.loads(line)
                if 'error' in item:raise RuntimeError(item['error'])
                content+=item.get('message',{}).get('content','')
                if time.time()-last>30:print(f'{label}: {len(content)} characters',flush=True);last=time.time()
                if item.get('done'):final=item
        metrics={k:v for k,v in final.items() if k!='message'};metrics['elapsed_seconds']=time.time()-start
        return attempt,content,metrics
    segments=[{'scene':i+1,'speech':' '.join(w['text'] for w in words if s['start_frame']<=frame_at(w['start'])<s['end_frame'])} for i,s in enumerate(scenes)]
    number,english,metrics=ask('Local English interpretation',[{'role':'system','content':'Interpret these six Hindi/English cricket speech segments in clear English. Output six numbered English paragraphs, at most 25 words each, in the supplied order. Preserve actual names and statistics. No new facts, years or advice. Do not write video labels yet. No timing IDs are present.'},{'role':'user','content':json.dumps(segments,ensure_ascii=False)}],max_tokens=400)
    d.save('local-english-speech.json',{'text':english,'model':d.MODEL,'source':'Local interpretation of supplied ASR; no cloud translation.'})
    d.save(f'model-response-{number:02}.json',{'answer':previous,'metrics':metrics,'local_interpretation':english,'stage':'interpretation_only'})
    print('Local English interpretation completed.',flush=True)
    index=next(i for i,s in enumerate(scenes) if s['effect']=='crick-evidence');panel=scenes[index]
    tokens=[w for w in words if panel['start_frame']<=frame_at(w['start'])<panel['end_frame']]
    plain=lambda n:{'type':'string','pattern':f"^[A-Z][A-Za-z .,'/&()\\-]{{0,{n-1}}}$",'maxLength':n}
    numeric=lambda n:{'type':'string','pattern':f"^[A-Z0-9][A-Za-z0-9 .,'/&()\\-]{{0,{n-1}}}$",'maxLength':n}
    props={'panel_title':plain(20),'opening_caption':plain(26),'film_title':plain(20),'film_subtitle':plain(26),'film_caption':plain(26),'paper_title':plain(20),'paper_subtitle':plain(26),'book_caption':plain(26)}
    for i in range(3):
        props[f'row_{i+1}']={'type':'object','properties':{'heading':numeric(16),'detail':plain(26),'word':{'type':'string','enum':[w['id'] for w in tokens if i or w['start']<=panel['start']+2.5]}},'required':['heading','detail','word']}
    schema={'type':'object','properties':props,'required':list(props),'additionalProperties':False}
    payload={'your_English_interpretation':english,
        'slots':{'opening_caption':'Scene 1','panel_title':'Scene 2','row_1':'Scene 2','row_2':'Scene 2','row_3':'Scene 2','film_title':'Scene 4','film_subtitle':'Scene 4','film_caption':'Scene 4','paper_title':'Scene 5','paper_subtitle':'Scene 5','book_caption':'Scene 6'},
        'panel_cues':[[w['id'],round(w['start'],2),w['text']] for w in tokens if re.search(r'\d|स्विंग|रेयर|विकेट',w['text']) or w['id'] in d.schema(words)['properties']['scenes']['items']['oneOf'][0]['properties']['start_word'].get('enum',[])],
        'instruction':'Write meaningful, complete English display labels from your own interpretation. Titles use words; numbered facts belong in the three notes. First note begins within 2.5 seconds of scene 2 start, at '+str(round(panel['start'],2))+' seconds. All three notes use facts spoken IN scene 2; choose their exact cue IDs. Cue IDs ONLY in word fields, never headings or detail. Notes in chronological order. No invented numbers, years, units or superlatives. Other scene choices and animations remain your previous plan.'}
    number,content,metrics=ask('Local display copy',[{'role':'system','content':'You are the offline local documentary director. Use your own English interpretation to write concise English labels and three accurately narrated evidence rows. Cue IDs are separate timing metadata. Return JSON.'},{'role':'user','content':json.dumps(payload,ensure_ascii=False,separators=(',',':'))}],schema,max_tokens=700)
    patch=json.loads(content);answer=copy.deepcopy(previous);resolutions=[]
    notes=[patch[f'row_{i+1}'] for i in range(3)]
    for note in notes:
        digits=re.findall(r'\d+',note['heading'])
        if digits:
            matches=[w for w in tokens if re.fullmatch(re.escape(digits[0])+r'[,.;]?',w['text'])]
            if len(matches)==1 and note['word']!=matches[0]['id']:
                resolutions.append({'model_word':note['word'],'resolved_word':matches[0]['id'],'numeric_heading':note['heading'],'method':'Exact spoken numeral match; no inferred time.'});note['word']=matches[0]['id']
    for scene in answer['scenes']:
        effect=scene['effect']
        if effect=='crick-evidence':scene.update(headline=patch['panel_title'],notes=notes)
        elif effect=='beneath-road':scene['caption']=patch['opening_caption']
        elif effect=='crick-film':scene.update(headline=patch['film_title'],subline=patch['film_subtitle'],caption=patch['film_caption'])
        elif effect=='crick-paper':scene.update(headline=patch['paper_title'],subline=patch['paper_subtitle'])
        elif effect=='crick-book':scene['caption']=patch['book_caption']
    d.save(f'model-response-{number:02}.json',{'answer':answer,'metrics':metrics,'local_patch':patch,'literal_acoustic_resolutions':resolutions,'stage':'display_copy'})
    errors,_=d.validation(answer,words)
    labels=[v for v in patch.values() if isinstance(v,str)]+[n[f] for n in notes for f in ['heading','detail']]
    if any(re.search(r'\bw\d+\b',v,re.I) for v in labels):errors.append('Timing IDs leaked into visible labels.')
    d.save(f'plan-checks-{number:02}.json',{'errors':errors})
    if errors:raise ValueError(errors)
    d.save('local-plan.json',answer);print('Local English copy accepted: '+json.dumps(patch),flush=True)

if __name__=='__main__':main()
