"""Repair unsupported publishing copy locally before any new upload starts."""
import json
from pathlib import Path


def ensure(assistant,session_id,review,job):
    if job.get('remote'):return job
    text_file=Path(job['video']).with_suffix('.txt')
    if not text_file.is_file():return job
    from hinglish_publish.metadata import validate_source_copy,generate_youtube,validate
    transcript=text_file.read_text('utf-8-sig')
    try:validate_source_copy(job['metadata'],transcript);return job
    except ValueError:pass
    assistant._progress(session_id,'Local AI is correcting unsupported details in the publishing copy')
    with assistant.state.work_lock:
        meta,model=generate_youtube(assistant.root,Path(job['video']),profile=job['profile'],
            notes='Use the actual clip speech. Correct unsupported dates and remove internal editorial commentary.',
            progress=lambda m:assistant._progress(session_id,m))
    meta=validate(meta);validate_source_copy(meta,transcript)
    assistant.state.publisher.edit({'id':job['id'],'metadata':meta})
    for row in review['rows']:
        if row['id']==job['id']:row['metadata']=meta
    folder=Path(job.get('campaign') or '')
    manifest=folder/'campaign.json'
    if manifest.is_file() and manifest.resolve().is_relative_to((assistant.root/'output/campaigns').resolve()):
        campaign=json.loads(manifest.read_text('utf-8'))
        for clip in campaign.get('clips',[]):
            if clip['fingerprint']==job['fingerprint']:clip['metadata']=meta
        partial=manifest.with_suffix('.partial');partial.write_text(json.dumps(campaign,ensure_ascii=False,indent=2),'utf-8');partial.replace(manifest)
    assistant._update(session_id,publishing_review=review)
    return assistant.state.publisher.store.get(job['id'])
