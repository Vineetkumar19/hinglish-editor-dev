"""Real receiving-runtime and source-backed acceptance; no outgoing actions."""
import json
import os
from pathlib import Path
import sys
import time
from datetime import datetime, timezone

ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))


def main():
    folder=ROOT/'data/real-delivery-acceptance'
    from core import config
    config._LOADED=True
    os.environ.update(DATA_DIR=str(folder),DB_URL='sqlite:///'+str(folder/'suite.db'),
        DRY_RUN='false',NOTIFY_CHANNELS='store',LOG_LEVEL='CRITICAL',
        SUITE_INTEGRATIONS_FILE=str(ROOT/'profiles/workflow_integrations.json'))
    from core.store import Store
    from core.workflow_service import WorkflowService
    from core.workflow_store import file_hash
    store=Store(); service=WorkflowService(store)
    report={}
    def prepare(role,intent,inputs,key):
        task=service.create(role,intent,inputs,key,budgets={'runtime_seconds':300,'storage_bytes':100_000_000})
        if task['state'] in ('queued','failed'):
            task=service.prepare(task['task_id'])
        if task['state']=='failed':raise RuntimeError(task['result'])
        return task
    def approve(task):
        return service.decide(task['task_id'],True) if task['state']=='waiting_for_review' and task['result'].get('approval_id') else task
    def receive(task):
        deadline=time.monotonic()+300
        while True:
            task=service.dispatch(task['task_id'])
            if task['state']=='succeeded':return task
            if task['state']=='failed' or time.monotonic()>deadline:raise RuntimeError(task['result'])
            time.sleep(.75)
    health=prepare('system_health','Live integrated workflow readiness',{},'integrated-health-v1')
    report['readiness']=health['result']
    if not health['result'].get('receipt'):
        health=service.request_diagnostics(health['task_id'])
        health=approve(health)
    health=receive(health)
    report['cortana_diagnostics']=health['result']['receipt']
    print('Cortana native diagnostics received',flush=True)
    now=time.time()
    store.run('''INSERT INTO leads(id,agent,company,email,status,created_at,updated_at)
        VALUES ('owner-internal-dev','fullstack_sales','Owner internal repository acceptance','owner-internal@local.invalid','qualified',?,?)
        ON CONFLICT(id) DO NOTHING''',(now,now))
    dev=prepare('client_delivery','Owner internal: bounded repository verification',{
        'contact_id':'owner-internal-dev','commission_type':'owner_internal',
        'brief':{'source_ref':'owner:2026-11-04:complete-workflows','text':'Verify the actual repository receiver using isolated regression checks.'},
        'scope':'Run the planning boundary tests and retain their actual report; no deployment.',
        'price':{'amount':0,'currency':'INR','evidence':'Internal acceptance; no fee agreement'},
        'deliverables':[{'id':'report','description':'Actual repository test report','acceptance':'Installed runtime exits zero; exact test source hash retained'}],
        'work_order':{'operation':'validate_repository','repository':str(ROOT),'test_pattern':'test_workflow_brain.py'}},'real-repository-v1')
    dev=approve(dev)
    if dev['result'].get('prepared',{}).get('work_request'):
        dev=approve(service.request_work(dev['task_id']))
    dev=receive(dev)
    report['repository']=dev['result']['receipt']
    print('Repository receiver tests completed',flush=True)
    delivery=json.loads((folder/'result.json').read_text())
    proof=delivery['delivery']['artifacts'][0]
    learn=prepare('learning_evidence','Real personal lab evidence: Suite delivery integration',{
        'goal':'Reliable typed application handoffs','period':'4 November 2026','_brain':'chatgpt',
        'entries':[{'description':'Completed one owner-internal ten-second excerpt through StoryLens, then saved a hash-verified Cortana package and unsent draft. No commercial delivery or publication.',
            'stage':'demonstrated','context':'personal_lab','source_ref':str(folder/'result.json'),'artifacts':[proof]}]},'real-learning-v1')
    report['learning']={'task_id':learn['task_id'],'state':learn['state'],'result':learn['result']}
    intake_file=folder/'selected-message-intake.json'
    if not intake_file.exists():
        intake_file.write_text(json.dumps({'received_at':datetime.now(timezone.utc).isoformat(),
            'received_at_basis':'Actual Suite import time; exact original message timestamp unavailable',
            'original_source_date':'2026-11-04','original_time_precision':'day'}),encoding='utf-8')
    message={'source_ref':'owner:2026-11-04:current-chat','source_id':'owner-complete-workflows',
        'contact_id':'owner-internal',**json.loads(intake_file.read_text()),
        'text':"Then complete it. Don't stop without completing it. Give him a brain, 14 billion or 9 billion parameter model, or give the option to directly accessible by ChatGPT.",
        'commitments':[{'quote':'Then complete it.','description':'Complete the requested Suite workflow acceptance','status':'proposed'}]}
    inbox=prepare('inbox_commitment','Selected owner message: source-linked follow-up',{'messages':[message],
        'reply_drafts':['ChatGPT, 14B and 9B planning have each answered a live request. The real internal excerpt is packaged locally; nothing was sent or published.']},'real-inbox-v2')
    inbox=approve(inbox)
    before=len(store.kv_list('commitments'))
    replay=prepare('inbox_commitment','Reimport the same selected owner message',{'messages':[message]},'real-inbox-reimport-v2')
    replay=approve(replay)
    assert before==len(store.kv_list('commitments'))
    report['inbox']={'task_id':inbox['task_id'],'same_message_reimport_added_commitments':0,
        'deadline_inferred':False,'sent':False,'receipt_time_note':message['received_at_basis'],
        'supersedes':'v1 used midnight as a day-level placeholder; it was not the actual original receipt time.'}
    catalog_path=Path('D:/Full Drive/remove silence/hinglish_captions/reference_catalog.json')
    catalog=json.loads(catalog_path.read_text(encoding='utf-8'))
    refs=[r for r in catalog['references'] if r['number'] in (1,2,3,5,6,8)]
    clips=[]
    for r in refs:
        if file_hash(r['source']) != r['sha256']:raise ValueError('Catalogue source changed')
        clips.append({'id':r['style_id'],'text':r['name'],'source_ref':r['source'],'sha256':r['sha256']})
    queries=[('blue keyword','caption_1'),('lime zoom','caption_2'),('soft serif','caption_3'),
        ('red word clusters','caption_5'),('circle serif','caption_6'),('kinetic gold','caption_8')]
    dataset={'provenance':'Six actual StoryLens catalogue video names; manually declared held-out lookup queries before measurement. Labels use catalogue identity, not visual model judgments.',
        'catalogue_sha256':file_hash(catalog_path),'clips':clips,
        'queries':[{'id':'q'+str(i),'text':q,'relevant_ids':[target],'split':'held_out'} for i,(q,target) in enumerate(queries)]}
    dataset_path=folder/'real-catalogue-retrieval-v2.json'
    dataset_path.write_text(json.dumps(dataset,indent=2),encoding='utf-8')
    ref=service.ledger.register_artifact(dataset_path,project='agents',revision='2',artifact_id='real-catalogue-retrieval',evidence=[str(catalog_path)])
    experiment_input={'question':'Does TF-IDF improve metadata lookup of the six actual StoryLens caption reference videos over token overlap?',
        'source_ref':'https://scikit-learn.org/stable/modules/feature_extraction.html#tfidf-term-weighting',
        'license':'Local metadata comparison; no external code downloaded, videos redistributed or reference approval altered.', 'dataset':ref}
    first=prepare('research_experiment','Actual StoryLens catalogue retrieval comparison',experiment_input,'real-catalogue-experiment-v2')
    second=prepare('research_experiment','Reproduce the catalogue retrieval comparison',experiment_input,'real-catalogue-experiment-repeat-v2')
    assert first['result']['baseline']['mrr']==second['result']['baseline']['mrr']
    assert first['result']['candidate']['mrr']==second['result']['candidate']['mrr']
    report['experiment']={'task_id':first['task_id'],'manifest':first['result']['manifest'],
        'baseline':first['result']['baseline'],'candidate':first['result']['candidate'],'reproduced':True}
    sources=json.loads((folder/'public-demand-sources.json').read_text())
    chosen={9493:('retry_budget','Your interrupt-and-retry report describes repeated questions after the configured attempt limit. My local workflow prototype persists an action retry budget across reconciliation. I have not verified it inside LangGraph. Would a small, clearly scoped example of the persisted counter be useful?'),
        8837:('exact_approval','Your stale resume-value report highlights why each approval should bind one exact action revision. My local prototype checks the payload hash, target, expiry and consumed state before execution. This is not a LangGraph fix. Would a minimal example of those checks help your investigation?'),
        7417:('reconcile','Your long-running tool report describes duplicate work after checkpoint redispatch. My local prototype reuses an action ID and queries the receiver before retrying. It has been tested on a local media delivery. I have not tested your Cloud deployment. Would the small receiver example be useful?'),
        9240:('outcome','Your documentation request separates checkpoint durability from external side effects. My local prototype records receiver evidence separately from runner completion and retains uncertainty after a lost acknowledgement. It does not promise exactly-once effects on arbitrary services. Would a compact example be useful?'),
        9546:('revision','Your crash-recovery report describes fresh upstream output beside stale downstream output. My local prototype binds each reviewed request to a task revision and artifact hashes. This does not establish a fix for the Functional API. Would a narrow example of that binding help?')}
    capabilities={name:{'status':'working','evidence_ref':str(folder/'result.json')+'; D:/Agents/tests/test_workflows.py'} for name,_ in chosen.values()}
    capabilities['framework_fix']={'status':'unverified','evidence_ref':''}
    signals=[]
    for source in sources:
        contact='github:'+source['author'].lower()
        store.run('''INSERT INTO leads(id,agent,company,person,source_url,status,created_at,updated_at)
            VALUES (?,'saas_sales',?,?,?,'research_only',?,?) ON CONFLICT(id) DO NOTHING''',
            (contact,'Public issue research',source['author'],'https://github.com/'+source['author'],now,now))
        number=int(source['url'].rsplit('/',1)[1]); match=chosen.get(number)
        signals.append({'contact_id':contact,'source_ref':source['url'],'observed_at':source['observed_at'],
            'expressed_need':source['title'],'source_text':source['source_text'],
            'capability_ids':[match[0]] if match else ['framework_fix'], 'draft':match[1] if match else '',
            'inferred_signals':['No buying intent established','Reported upstream issue is not independently reproduced','Issue state: '+source['state']]})
    sales=prepare('saas_sales','Twenty real public demand signals and five unsent drafts',{'signals':signals,'capabilities':capabilities},'real-demand-v1')
    sales=approve(sales)
    report['sales']={'task_id':sales['task_id'],'source_count':len(sources),'unique_contacts':len(sales['result']['prepared']['ranked_needs']),
        'draft_count':len(sales['result']['review_ids']),'owner_usefulness_review':'pending','sent':False}
    assert report['sales']['draft_count']==5
    (folder/'integrated-result.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps({'result':str(folder/'integrated-result.json'),'completed':['diagnostics','repository','learning evidence','inbox dedup','real metadata experiment','20 public signals / 5 drafts'],'external_actions':0}),flush=True)


if __name__=='__main__':main()
