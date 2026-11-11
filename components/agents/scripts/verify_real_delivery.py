"""Owner-authorized internal delivery acceptance using real existing footage.

No invented commercial client, price agreement, sending, or publication. Actual
Suite HTTP routes call the installed StoryLens and Cortana receiving runtimes.
"""
import argparse
import json
import os
from pathlib import Path
import secrets
import sys
import threading
import time
import urllib.request

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--serve', action='store_true')
    parser.add_argument('--port', type=int, default=0)
    args = parser.parse_args()
    folder = ROOT / 'data/real-delivery-acceptance'
    folder.mkdir(parents=True, exist_ok=True)
    from core import config
    config._LOADED = True
    token_path = folder / 'dashboard.token'
    if not token_path.exists():
        token_path.write_text(secrets.token_urlsafe(40), encoding='utf-8')
    token = token_path.read_text(encoding='utf-8')
    os.environ.update(DATA_DIR=str(folder), DB_URL='sqlite:///' + str(folder/'suite.db'),
        DRY_RUN='false', NOTIFY_CHANNELS='store', LOG_LEVEL='CRITICAL', DASHBOARD_TOKEN=token,
        SUITE_INTEGRATIONS_FILE=str(ROOT/'profiles/workflow_integrations.json'))
    from core.store import Store
    from core.workflow_service import WorkflowService
    from server.app import DashboardServer
    store = Store()
    service = WorkflowService(store)
    store.run('''INSERT INTO leads (id,agent,company,email,status,created_at,updated_at)
        VALUES ('owner-internal','video_client','Owner internal acceptance — no commercial client',
        'owner-internal@local.invalid','qualified',?,?) ON CONFLICT(id) DO NOTHING''', (time.time(),time.time()))
    server = DashboardServer(('127.0.0.1', args.port), store=store)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f'http://127.0.0.1:{server.server_port}'
    (folder/'console.json').write_text(json.dumps({'base_url':base,'pid':os.getpid(),
        'review_url':base+'/workflows?token='+token}),encoding='utf-8')
    def request(path, data=None):
        req = urllib.request.Request(base+path, data=json.dumps(data).encode() if data is not None else None,
            headers={'Authorization':'Bearer '+token,'Content-Type':'application/json'})
        with urllib.request.urlopen(req,timeout=330) as response:
            return json.load(response)
    def action(task, verb, data=None):
        return request('/api/workflows/'+task['task_id']+'/'+verb, data or {})
    def run_received(task):
        deadline = time.monotonic()+300
        while True:
            task = action(task,'dispatch')
            if task['state'] in ('succeeded','failed'):
                break
            if time.monotonic() > deadline:
                raise RuntimeError('Actual receiver did not complete within the explicit case budget: '+str(task['result']))
            time.sleep(.75)
        if task['state'] != 'succeeded':
            raise RuntimeError(str(task['result']))
        return task
    result_path = folder/'result.json'
    if not result_path.exists():
        source = request('/api/workflows/artifacts', {'path':'D:/Chrome Downloads/reel1.mp4',
            'project':'owner','revision':'source-original','artifact_id':'owner-reel1-original',
            'evidence':['Owner delegated selection of available files for internal acceptance, 2026-11-04.']})
        brief = {'contact_id':'owner-internal','commission_type':'owner_internal',
            'brief':{'source_ref':'owner:2026-11-04:complete-workflows-and-choose-assets',
                'text':'Prepare a real local editing and unsent delivery case using an existing owner-selected-by-delegation asset.'},
            'scope':'One straight 10-second excerpt from reel1.mp4, unchanged composition and original audio, with a tracked revision and local delivery package.',
            'price':{'amount':0,'currency':'INR','evidence':'Owner internal validation; no sale, fee or payment agreement.'},
            'deliverables':[{'id':'excerpt','description':'Ten-second excerpt with source aspect and audio',
                'acceptance':'Full media decode, matching dimensions, duration within 0.12 seconds, unchanged source SHA256, and hash-verified delivery copy.'}],
            'assets':[source], 'work_order':{'operation':'source_excerpt','source_artifact_id':source['artifact_id'],
                'start_seconds':0,'duration_seconds':10}, '_brain':'chatgpt'}
        task = request('/api/workflows',{'role':'client_delivery','intent':'Owner internal: real excerpt and unsent delivery',
            'inputs':brief,'idempotency_key':'owner-internal-real-delivery-v1','budgets':{'runtime_seconds':300,'storage_bytes':100_000_000}})
        if task['state'] == 'failed':
            raise RuntimeError(task['result'])
        if task['state'] == 'waiting_for_review':
            task = action(task,'approve')
        if task['result'].get('prepared',{}).get('work_request'):
            task = action(task,'request-work')
            task = action(task,'approve')
        task = run_received(task)
        rendering = task['result']['receipt']
        video = next(r for r in rendering['artifacts'] if r['type'] == 'mp4')
        # A real revision of this same task records the owner-internal delivery
        # handoff. It does not fabricate creative feedback from a third party.
        package = {**brief, '_brain':'manual', 'phase':'package','delivery_mode':'local_package',
            'recipient':'owner-internal@local.invalid','files':[video],
            'file_deliverables':{'excerpt':video['artifact_id']},
            'acceptance_evidence':rendering['evidence_refs'],
            'subject':'Owner internal excerpt — ready for review',
            'body':'The requested ten-second source excerpt is attached for your review. This local draft has not been sent. No commercial client or payment is represented.'}
        task = action(task,'revise',{'revision':task['revision'],'inputs':package})
        task = action(task,'prepare')
        if task['state'] != 'waiting_for_review':
            raise RuntimeError(task['result'])
        task = action(task,'approve')
        task = run_received(task)
        replay = action(task,'dispatch')
        if replay['result']['receipt'] != task['result']['receipt']:
            raise AssertionError('Completed dispatch did not reuse its exact receipt')
        result = {'task_id':task['task_id'],'revision':task['revision'],'state':task['state'],
            'case_type':'Real owner-internal job; not a commercial enquiry or customer acceptance',
            'source':source, 'render':rendering, 'delivery':task['result']['receipt'],
            'duplicate_dispatch_reused_receipt':True, 'sent':False, 'published':False,
            'owner_visual_review':'pending', 'console_base_url':base}
        result_path.write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps({'result':str(result_path),'console':base,'state':'delivery prepared and technically verified'}),flush=True)
    if args.serve:
        threading.Event().wait()
    else:
        server.shutdown()


if __name__ == '__main__':
    main()
