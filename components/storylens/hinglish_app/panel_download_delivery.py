"""Project-bin delivery of existing downloader outputs; no timeline/XML import."""
from pathlib import Path
from .downloader import service

def prepare(root,key,kind,context):
    downloads=service(root);path=downloads.media(key,kind);job=downloads.snapshot(key)
    if context.get('host') not in ('aftereffects','premiere'):raise ValueError('Download delivery: open the Storylens Adobe panel.')
    return {'id':key,'kind':kind,'host':context['host'],'expected_project_id':context['project_id'],
            'path':str(path),'bytes':path.stat().st_size,'folder':'Downloader Video' if kind=='video' else 'Downloader Audio',
            'name':str(job.get('title') or kind)[:180]}

def accept(root,key,kind,context,receipt):
    manifest=prepare(root,key,kind,context)
    if not isinstance(receipt,dict) or not receipt.get('ok') or any(receipt.get(k)!=manifest[k] for k in ('id','kind','host','folder')) or receipt.get('project_id')!=context['project_id'] or not receipt.get('item_id') or Path(receipt.get('path','')).resolve()!=Path(manifest['path']).resolve():
        raise ValueError('Download delivery: the editor has not confirmed this media. The downloaded file is kept; select Video or Audio to retry.')
    downloads=service(root)
    with downloads.lock:
        job=downloads.snapshot(key);records=list(job.get('native_deliveries',[]))
        records=[r for r in records if (r.get('host'),r.get('project_id'),r.get('kind'))!=(context['host'],context['project_id'],kind)]
        downloads._save(key,native_deliveries=records+[receipt])
    return receipt
