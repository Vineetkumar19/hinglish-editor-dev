"""Use unconstrained local English generation, then validate outside sampling."""
import copy,json,re,sys,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import local_documentary_synced as d
from hinglish_motion.speech_clock import compile_plan,frame_at

def main():
    import requests
    words=d.load('timed-words.json');files=sorted(d.OUT.glob('model-response-*.json'))
    previous=next(json.loads(p.read_text(encoding='utf8'))['answer'] for p in reversed(files) if not d.validation(json.loads(p.read_text(encoding='utf8'))['answer'],words)[0])
    english=d.load('local-english-speech.json')['text']
    paragraphs=[re.sub(r'^\d+\.\s*','',p.strip()) for p in english.split('\n\n') if p.strip()]
    session=requests.Session();session.trust_env=False
    def ask(task,source,limit=160):
        attempt=max(int(p.stem.rsplit('-',1)[-1]) for p in d.OUT.glob('model-request-*.json'))+1
        body={'model':d.MODEL,'stream':True,'think':False,'options':{'num_ctx':4096,'num_predict':limit,'num_thread':4,'temperature':.18,'seed':27},
              'messages':[{'role':'system','content':'Write concise, natural English display labels for a cricket documentary. Use the provided speech meaning. Avoid unproven superlatives, dates and extra facts. Follow the requested plain-text format; no explanatory prose.'},
                          {'role':'user','content':task+'\nSpeech meaning from your local interpretation:\n'+source}]}
        d.save(f'model-request-{attempt:02}.json',body);start=time.time();last=start;content='';final={}
        with session.post('http://127.0.0.1:11434/api/chat',json=body,stream=True,timeout=(10,600)) as response:
            response.raise_for_status()
            for line in response.iter_lines():
                if not line:continue
                item=json.loads(line)
                if 'error' in item:raise RuntimeError(item['error'])
                content+=item.get('message',{}).get('content','')
                if time.time()-last>30:print('Local plain labels: '+str(len(content))+' characters',flush=True);last=time.time()
                if item.get('done'):final=item
        metrics={k:v for k,v in final.items() if k!='message'};metrics['elapsed_seconds']=time.time()-start
        d.save(f'model-response-{attempt:02}.json',{'answer':previous,'metrics':metrics,'local_text':content,'stage':'plain_labels'})
        print('LOCAL TEXT: '+content,flush=True)
        return attempt,content,metrics
    def lines(text):
        values=[]
        for line in text.splitlines():
            line=line.strip().strip('"`*')
            line=re.sub(r'^(?:\d+[.)]\s*|[-#]\s*|(?:Title|Subtitle|Caption|Label)\s*:\s*)','',line,flags=re.I)
            if line:values.append(line)
        return values
    def labels(source,count,caps):
        task=f'Give {count} separate English topic labels. Each label must have only one or two words and no digits. '
        task+='Maximum character lengths in order: '+', '.join(map(str,caps))+'. Output exactly '+str(count)+' lines, one label per line, no bullets or prefixes.'
        cached=[]
        for p in sorted(d.OUT.glob('model-response-*.json'),reverse=True):
            record=json.loads(p.read_text(encoding='utf8'))
            request=p.with_name(p.name.replace('response','request'))
            if record.get('stage')=='plain_labels' and request.exists():
                body=json.loads(request.read_text(encoding='utf8'))
                prompt=body['messages'][-1]['content']
                if prompt.endswith(source) and prompt.startswith(f'Give {count} separate English topic labels.'):
                    cached=lines(record.get('local_text',''))[:count]
                    if len(cached)==count and all(len(v)<=n and not re.search(r'\d|[\u0900-\u097f]',v) for v,n in zip(cached,caps)):break
                    cached=[]
        if cached:return cached
        _,text,_=ask(task,source,limit=100)
        values=lines(text)[:count]
        if len(values)!=count or any(len(v)>n or re.search(r'\d|[\u0900-\u097f]',v) for v,n in zip(values,caps)):
            _,text,_=ask(task+' Your previous labels failed the length/count check: '+repr(values)+'. Use shorter complete labels.',source,limit=100);values=lines(text)[:count]
        if len(values)==count:
            for i,cap in enumerate(caps):
                if len(values[i])>cap:
                    _,text,_=ask(f'Shorten your label {values[i]!r} to a single English word. Maximum {cap} characters. Return only that one label.',source,limit=35)
                    values[i]=lines(text)[0]
        if len(values)!=count or any(len(v)>n for v,n in zip(values,caps)):raise ValueError('Local label lengths/count invalid: '+repr(values))
        return values
    opening=labels(paragraphs[0],1,[26])[0]
    panel=labels(paragraphs[1],1,[20])[0]
    film=labels(paragraphs[3],3,[20,26,26])
    paper=labels(paragraphs[4],2,[20,26])
    book=labels(paragraphs[5],1,[26])[0]
    scenes=compile_plan(previous,words,d.EFFECTS);index=next(i for i,s in enumerate(scenes) if s['effect']=='crick-evidence');scene=scenes[index]
    candidates=[w for w in words if scene['start_frame']<=frame_at(w['start'])<scene['end_frame'] and re.search(r'\d|स्विंग|रेयर',w['text'])]
    task='Create exactly three English evidence rows from facts actually spoken in this panel. Each line must be cueID | heading | detail. No line numbering. Heading one or two words, maximum16 characters; detail one or two words, maximum26 characters. IDs belong only in first column. Use three distinct cues in spoken order. First row must use an early cue, within2.5 seconds of panel start. All numeric headings must match an actually spoken numeral. Do not invent facts or copy paragraph numbering. Available acoustic cues: '+json.dumps([[w['id'],round(w['start'],2),w['text']] for w in candidates],ensure_ascii=False)
    number,text,metrics=ask(task,paragraphs[0]+'\n'+paragraphs[1],limit=180)
    rows=[]
    for line in lines(text):
        fields=[x.strip() for x in line.split('|')]
        if len(fields)==3 and re.fullmatch(r'w\d+',fields[0]):rows.append({'word':fields[0],'heading':fields[1],'detail':fields[2]})
    if len(rows)!=3:raise ValueError('Local evidence output needs three plain rows: '+text)
    ids={w['id']:w for w in words};rows.sort(key=lambda r:ids[r['word']]['start'])
    if any(len(r['heading'])>16 or len(r['detail'])>26 for r in rows):raise ValueError('Local evidence labels exceed template slots')
    if ids[rows[0]['word']]['start']-scene['start']>2.5:raise ValueError('Local first evidence row still late')
    answer=copy.deepcopy(previous)
    for s in answer['scenes']:
        if s['effect']=='beneath-road':s['caption']=opening
        elif s['effect']=='crick-evidence':s.update(headline=panel,notes=rows)
        elif s['effect']=='crick-film':s.update(headline=film[0],subline=film[1],caption=film[2])
        elif s['effect']=='crick-paper':s.update(headline=paper[0],subline=paper[1])
        elif s['effect']=='crick-book':s['caption']=book
    errors,_=d.validation(answer,words);d.save(f'plan-checks-{number:02}.json',{'errors':errors})
    d.save(f'model-response-{number:02}.json',{'answer':answer,'metrics':metrics,'local_text':text,'stage':'final_plain_labels','row_order_method':'Measured acoustic order; no invented cue times.'})
    if errors:raise ValueError(errors)
    d.save('local-plan.json',answer);print('ACCEPTED LOCAL PLAN',flush=True)

if __name__=='__main__':main()
