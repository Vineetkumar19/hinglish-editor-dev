"""Validated Intro Create entry points, reusing the workbench job queue."""
from pathlib import Path
from hinglish_cinematic.curation import Store,validate_intros
from .workbench_jobs import service


def create(state, value, *, reuse_job_id=None):
    database=Store(state.root/'cache/curation/projects.sqlite3')
    body=database.get(value['dataset_id'])
    if value['mode']=='cinematic':
        dataset=service(state).snapshot(value['dataset_id'])
        if dataset['kind']!='footage' or dataset['status']!='complete':raise ValueError('Choose a completed footage dataset.')
    else:
        dataset={'id':value['dataset_id']}
        if not body.get('documentary') or body.get('category')!='cricket':raise ValueError('Import a cricket documentary body first.')
    if not body.get('body'):raise ValueError('Save the body storyboard before planning an intro.')
    if value['mode']=='documentary':
        graph=body.get('story_graph')
        if not graph or graph.get('review_state')!='approved':
            raise ValueError('Import and review the cricket script/timeline question-to-payoff graph before creating a documentary intro.')
    if value['body_revision']!=body['revision']:raise ValueError('The body changed. Reload before creating intros.')
    candidates={r['id']:r for r in body['candidates'] if r['review_state']!='rejected'}
    from hinglish_cinematic.recipes import bind_edit_recipe
    plans=[bind_edit_recipe(plan) for plan in value['plans']];sources={}
    for plan in plans:
        for span in plan['source_spans']:
            candidate=candidates.get(span['candidate_id'])
            if candidate is None:raise ValueError('Choose an available candidate from this dataset.')
            if value['mode']=='cinematic' and (candidate['review_state']!='approved' or candidate['id'] in body['body'].get('banned',[])):
                raise ValueError('Choose reviewed, approved and unbanned intro moments.')
            if span['source_id']!=candidate['source_id']:raise ValueError('Candidate/source identity mismatch.')
            if not candidate['start']<=span['start']<span['end']<=candidate['start']+candidate['duration']:
                raise ValueError('An intro span must stay within its selected candidate.')
            key=candidate['source_id']
            source=sources.setdefault(key,{'path':candidate['source'],'hash':candidate['source_sha256'],'duration':0})
            source['duration']=max(source['duration'],candidate['start']+candidate['duration'])
    if value['mode']=='documentary':
        from hinglish_cinematic.story_graph import protect_sources,validate_promises
        sources=protect_sources(sources,body['story_graph'])
        for plan in plans:validate_promises(plan,body['story_graph'])
    documentary_clock=None
    if value['mode']=='documentary':
        from hinglish_cinematic.recipes import EDIT_RECIPES
        recipe=EDIT_RECIPES['EDIT_CRICKET40_v1']
        if len(plans)!=1:
            raise ValueError('Choose one documentary intro.')
        roles={node['id']:node['kind'] for node in body['story_graph']['nodes']}
        spans=[]
        cursor=0
        for span in plans[0]['source_spans']:
            end=cursor+span['frames']
            spans.append({'node_id':span['node_id'],'role':roles[span['node_id']],
                          'intro_in_frame':cursor,'intro_out_frame':end,
                          'source_in':span['start'],'source_out':span['end']})
            cursor=end
        documentary_clock={'recipe_id':'EDIT_CRICKET40_v1','version':recipe['version'],'fps':30,
                           'sections':[{'role':role,'start_frame':start*30,'end_frame':end*30}
                                       for role,start,end in zip(recipe['section_roles'],recipe['sections'],recipe['sections'][1:])],
                           'actual_spans':spans}
    reference_style=None
    if value.get('reference_card_id'):
        if value['mode']!='documentary':
            raise ValueError('Reference style cards are reviewed in documentary planning.')
        from .reference_style import approved_context
        reference_style=approved_context(database,value['reference_card_id'])
    qa=validate_intros(plans,sources,body['revision'],value['mode'],value['category'])
    id=value['plan_id']
    if not isinstance(id,str) or len(id)!=32 or any(c not in '0123456789abcdef' for c in id):raise ValueError('Use a generated intro plan identity.')
    expected=sorted(source['hash'] for source in sources.values())
    if sorted(value['input_hashes'])!=expected:raise ValueError('Intro input hashes do not match its source set.')
    result=database.mutate(id,'intro',value,lambda old:{'plans':plans,'sources':sources,'body_revision':body['revision'],
        'dataset_id':dataset['id'],'mode':value['mode'],'category':value['category'],'qa':qa,'approval_state':'plan_review',
        **({'reference_style':reference_style} if reference_style else {}),
        **({'documentary_clock':documentary_clock} if documentary_clock else {}),
        **({'reuse_job_id': reuse_job_id} if reuse_job_id else {})})
    return result


def replace_variant(state, value):
    jobs = service(state)
    prior_job = jobs.snapshot(value['intro_job_id'])
    if prior_job['kind'] != 'intro' or prior_job['status'] != 'complete':
        raise ValueError('Choose a completed set of cinematic intro renders.')
    prior = validate_saved(state.root, prior_job['request']['plan_id'], prior_job['request']['plan_revision'],
                           prior_job['request']['body_revision'])
    index = value['variant']
    if prior['mode'] != 'cinematic' or type(index) is not int or index not in range(3):
        raise ValueError('Choose one of the three cinematic intros.')
    plans = list(prior['plans'])
    plans[index] = {**plans[index], 'source_spans': value['source_spans']}
    if plans == prior['plans']:
        raise ValueError('Change at least one source moment for the replacement intro.')
    sources = sorted({span['source_id'] for plan in plans for span in plan['source_spans']})
    if sorted(value.get('input_hashes', [])) != sources:
        raise ValueError('Reload the exact source identities for this replacement.')
    plan = create(state, {**value, 'plans': plans, 'mode': prior['mode'], 'category': prior['category'],
                         'dataset_id': prior['dataset_id'], 'body_revision': prior['body_revision']},
                  reuse_job_id=prior_job['id'])
    return render(state, {'plan_id': plan['id'], 'idempotency_key': value['idempotency_key'] + ':render'})


def render(state,value):
    database=Store(state.root/'cache/curation/projects.sqlite3')
    plan=database.get(value['plan_id']);body=database.get(plan['dataset_id'])
    if body['revision']!=plan['body_revision']:raise ValueError('The body changed. Create a new comparison set.')
    validate_saved(state.root,plan['id'],plan['revision'],body['revision'])
    return service(state).start('intro',{'plan_id':plan['id'],'plan_revision':plan['revision'],'body_revision':body['revision'],'idempotency_key':value['idempotency_key']})


def validate_saved(root, plan_id, plan_revision=None, body_revision=None):
    """Revalidate immutable input evidence before work and before promotion."""
    from hinglish_cinematic.curation import file_hash
    database=Store(Path(root)/'cache/curation/projects.sqlite3')
    plan=database.get(plan_id);body=database.get(plan['dataset_id'])
    if plan.get('kind')!='intro' or (plan_revision is not None and plan['revision']!=plan_revision):
        raise ValueError('The intro plan changed; review its current revision.')
    if body['revision']!=plan['body_revision'] or (body_revision is not None and body['revision']!=body_revision):
        raise ValueError('The body changed; rebuild this intro comparison.')
    for source in plan['sources'].values():
        if file_hash(source['path'])!=source['hash']:raise ValueError('Intro source media changed after review.')
    if plan['mode']=='documentary':
        for name in ('script','transcript'):
            if file_hash(body[name+'_path'])!=body[name+'_hash']:
                raise ValueError('The documentary '+name+' changed after review.')
        from hinglish_cinematic.story_graph import validate_promises
        for item in plan['plans']:validate_promises(item,body['story_graph'])
    else:
        rows={c['id']:c for c in body['candidates']};banned=body['body'].get('banned',[])
        for item in plan['plans']:
            for span in item['source_spans']:
                candidate=rows.get(span['candidate_id'])
                if not candidate or candidate['review_state']!='approved' or candidate['id'] in banned:
                    raise ValueError('An intro source moment is no longer approved or available.')
    return plan
