"""Body-only previews, independently versioned from optional introductions."""
from pathlib import Path
from .curation import Store,digest,file_hash
from .intro_render import render_intro


def render_body(root,dataset_id,expected_revision,folder,stop,canvas=(720,1280)):
    from hinglish_app.workbench_jobs import atomic_json
    database=Store(Path(root)/'cache/curation/projects.sqlite3');data=database.get(dataset_id)
    if data['revision']!=expected_revision:raise ValueError('The body changed before rendering.')
    body=data.get('body')
    if not body or not body['ordered_clip_ids']:raise ValueError('Choose the body clips first.')
    rows={r['id']:r for r in data['candidates']};spans=[];sources={}
    for id in body['ordered_clip_ids']:
        row=rows[id]
        if row['review_state']=='rejected':raise ValueError('A selected body clip was rejected.')
        source=sources.setdefault(row['source_id'],{'path':row['source'],'hash':row['source_sha256'],'duration':0})
        source['duration']=max(source['duration'],row['start']+row['duration'])
        spans.append({'candidate_id':id,'source_id':row['source_id'],'start':row['start'],
                      'end':row['start']+row['duration'],'frames':row['output_frames']})
    plan={'fps':30,'frame_count':sum(s['frames'] for s in spans),'body_revision':expected_revision,
          'source_spans':spans,'canvas':list(canvas),'variant':'body','dataset_id':dataset_id}
    for source in sources.values():
        if file_hash(source['path'])!=source['hash']:raise ValueError('A body source changed after review.')
    identity=digest(plan)[:32]
    try:
        prior=database.get(identity)
        if file_hash(prior['path'])==prior['checksum']:return prior
    except (ValueError,OSError):pass
    result=render_intro(plan,sources,folder,root,stop)
    if database.get(dataset_id)['revision']!=expected_revision:raise ValueError('The body changed during rendering; this preview is obsolete.')
    for source in sources.values():
        if file_hash(source['path'])!=source['hash']:raise ValueError('A body source changed during rendering.')
    path=Path(result['path']);target=path.with_name('Body_only.mp4');path.replace(target)
    result.update(path=str(target),dataset_id=dataset_id,body_revision=expected_revision,duration=plan['frame_count']/30,
                  canvas=list(canvas),source_plan=plan,approval_state='preview')
    atomic_json(Path(folder)/'artifact.json',result)
    try:revision=database.get(identity)['revision']
    except ValueError:revision=0
    command={'command_id':identity+':'+str(revision),'idempotency_key':'body:'+identity+':'+str(revision),'expected_revision':revision,
             'input_hashes':sorted(sources),'settings_version':1}
    return database.mutate(identity,'body_artifact',command,lambda old:result)
