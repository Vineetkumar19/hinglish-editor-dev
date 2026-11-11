"""Ask the same local director to repair factual copy; no replacement cloud labels."""
import copy,json,sys,time,re
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import local_documentary_synced as d

def main():
    import requests
    plan=d.load('local-plan.json');words=d.load('timed-words.json')
    candidates=[w for w in words if w['id'] in ['w011','w013','w043','w051','w054']]
    number=max(int(p.stem.rsplit('-',1)[-1]) for p in d.OUT.glob('model-request-*.json'))+1
    prompt={'corrections':['Bataki is an unrecognized speech transcription error, not a verified place or person. Replace that paper headline with your own concise English label about retirement or later bowling in the US.', '439 wickets was spoken BEFORE this evidence scene. Do not put it in this panel. Its first spoken fact is THREE ten-wicket hauls; later comes 150 km/h, then swing.'],
      'acoustic_cues':[[w['id'],w['text'],w['start']] for w in candidates],
      'format':{'headline':'One or two English words, maximum 20 characters','notes':'Exactly three objects, each with word (one available cue ID), heading (maximum16 characters), detail (maximum26 characters).'},
      'rules':'Use facts actually spoken at each selected ID. Choose distinct chronological IDs. First row cue must be w011 or w013 so evidence begins early. Return only JSON with keys headline and notes.'}
    body={'model':d.MODEL,'stream':False,'think':False,'format':'json','options':{'num_ctx':4096,'num_predict':240,'num_thread':4,'temperature':.1,'seed':31},'messages':[{'role':'system','content':'You are the existing local cricket documentary director. Correct your own text using acoustic facts. No new scene design. Return the requested JSON only.'},{'role':'user','content':json.dumps(prompt,ensure_ascii=False)}]}
    d.save(f'model-request-{number:02}.json',body)
    session=requests.Session();session.trust_env=False;start=time.time()
    response=session.post('http://127.0.0.1:11434/api/chat',json=body,timeout=(10,600));response.raise_for_status();data=response.json()
    text=data['message']['content'];print(text,flush=True);answer=json.loads(text)
    metrics={k:v for k,v in data.items() if k!='message'};metrics['elapsed_seconds']=time.time()-start
    candidate=copy.deepcopy(plan)
    for scene in candidate['scenes']:
        if scene['effect']=='crick-paper':scene['headline']=answer['headline']
        if scene['effect']=='crick-evidence':scene['notes']=answer['notes']
    ids={w['id']:w for w in words};resolutions=[]
    for scene in candidate['scenes']:
        for note in scene['notes']:
            numerals=re.findall(r'\d+',note['heading']+' '+note['detail'])
            matching=[w for w in words if numerals and w['start']>=ids[scene['start_word']]['start'] and all(re.search(r'(?<!\d)'+re.escape(n)+r'(?!\d)',w['text']) for n in numerals)]
            if matching and note['word']!=matching[0]['id']:
                resolutions.append({'old':note['word'],'resolved':matching[0]['id'],'numeric_fact':numerals,'method':'Exact numeral token in this scene, unchanged local wording'})
                note['word']=matching[0]['id']
    d.save('numeric-cue-resolution.json',resolutions)
    errors,_=d.validation(candidate,words)
    if re.search(r'Bataki|439',json.dumps(answer),re.I):errors.append('Rejected unverified or out-of-panel fact')
    if answer['notes'][0]['word'] not in ['w011','w013']:errors.append('First evidence cue still late')
    d.save(f'model-response-{number:02}.json',{'answer':candidate,'metrics':metrics,'local_text':text,'stage':'local_fact_repair'})
    d.save(f'plan-checks-{number:02}.json',{'errors':errors})
    if errors:raise ValueError(errors)
    d.save('local-plan.json',candidate);print('ACCEPTED LOCAL FACT REPAIR',flush=True)

if __name__=='__main__':main()
