"""Frozen-body rendering and optional intro trials on the existing queue."""
from pathlib import Path
from hinglish_cinematic.curation import Store,file_hash
from .workbench_jobs import service

def request(state,value,kind):
    database=Store(state.root/'cache/curation/projects.sqlite3');body=database.get(value['dataset_id'])
    if body['kind']!='curation' or body['revision']!=value['expected_revision']:raise ValueError('Reload the current body storyboard.')
    if kind=='body':
        return service(state).start('body',{'dataset_id':body['id'],'expected_revision':body['revision'],'idempotency_key':value['idempotency_key']})
    job=service(state).snapshot(value['intro_job_id'])
    if job['kind'] not in ('intro','intro-sound') or job['status']!='complete':raise ValueError('Render the introductions before making comparison trials.')
    from .intro_sound import validate_chain
    validate_chain(state.root,job,service(state))
    intro=database.get(job['request']['plan_id'])
    if intro['dataset_id']!=body['id'] or intro['body_revision']!=body['revision'] or intro['revision']!=job['request']['plan_revision']:
        raise ValueError('These introductions are obsolete. Render the current body and intro revisions.')
    if value.get('mode','prepend')!='prepend':raise ValueError('Dedicated-slot assembly needs a validated native template slot.')
    request = {'dataset_id': body['id'], 'expected_revision': body['revision'], 'intro_job_id': job['id'],
               'idempotency_key': value['idempotency_key'], 'mode': 'prepend'}
    if value.get('previous_trial_job_id'):
        previous = service(state).snapshot(value['previous_trial_job_id'])
        if (previous['kind'] != 'trials' or previous['status'] != 'complete'
                or previous['request']['dataset_id'] != body['id']
                or previous['request']['expected_revision'] != body['revision']):
            raise ValueError('Choose a previous comparison from this exact body revision.')
        request['previous_trial_job_id'] = previous['id']
    return service(state).start('trials', request)

def render_trials(root,value,folder,stop,jobs):
    from hinglish_cinematic.body_render import render_body
    from hinglish_cinematic.variant_assembly import assemble
    database=Store(Path(root)/'cache/curation/projects.sqlite3');current=database.get(value['dataset_id'])
    if current['revision']!=value['expected_revision']:raise ValueError('The body changed before trial rendering.')
    intro_job=jobs.snapshot(value['intro_job_id']);plan=database.get(intro_job['request']['plan_id'])
    if plan['revision']!=intro_job['request']['plan_revision']:raise ValueError('The intro plan changed before assembly.')
    from .intro_sound import validate_chain
    validate_chain(root,intro_job,jobs)
    body=render_body(root,current['id'],current['revision'],Path(folder)/'body',stop)
    results=[]
    reusable = []
    if value.get('previous_trial_job_id'):
        previous = jobs.snapshot(value['previous_trial_job_id'])
        if previous['kind'] == 'trials' and previous['status'] == 'complete':
            reusable = previous['result']['trials']
    for index, intro in enumerate(intro_job['result']['intros']):
        variant_dir = Path(folder) / ('Trial_' + 'ABC'[index])
        prior = reusable[index] if index < len(reusable) else None
        results.append(assemble(intro, body, variant_dir, stop, value['mode'],
                                reusable=prior, workbench_root=Path(root) / 'output/workbench'))
    if database.get(current['id'])['revision']!=current['revision'] or database.get(plan['id'])['revision']!=plan['revision']:
        raise ValueError('The edit changed during assembly. These trials are obsolete.')
    validate_chain(root,intro_job,jobs)
    return {'body':body,'trials':results,'body_revision':current['revision'],'dataset_id':current['id'],'approval_state':'preview'}
