"""Inspect/export/retention controls for architecture-owned data only."""
import json
import time
from pathlib import Path
from core import local_store as store
from core.config import settings

KINDS={'workspace','restore','document','document_task','diagnostic','draft','model_switch','request'}


def inventory():
    with store.connection() as conn:
        counts=[dict(row) for row in conn.execute('SELECT kind,count(*) count,min(updated) oldest FROM records GROUP BY kind')]
    return {'records':counts,'storage':str(Path(settings.memory_dir)/'local_architecture.sqlite3'),
            'retention':'Manual until a reviewed retention policy is enabled.', 'original_files':'Preserved'}


def export_data():
    from datetime import datetime, timezone
    folder=Path(settings.documents_dir)/'Cortana exports'
    folder.mkdir(parents=True,exist_ok=True)
    destination=folder/('local-data-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')+'.json')
    data={kind:store.records(kind,1000) for kind in KINDS}
    with destination.open('x',encoding='utf-8') as output:
        json.dump(data,output,ensure_ascii=False,indent=2)
    return {'exported':str(destination),'scope':'Up to 1000 records per category; original files not copied.'}


def preview_retention(days=90):
    if not 1<=days<=3650:
        raise ValueError('Choose 1–3650 days.')
    cutoff=time.time()-days*86400
    with store.connection() as conn:
        rows=conn.execute("SELECT kind,id,revision FROM records WHERE updated<? AND kind IN ('restore','diagnostic','model_switch','request')",
                          (cutoff,)).fetchall()
    return {'days':days,'cutoff':cutoff,'records':[dict(row) for row in rows],
            'note':'Only old receipts/diagnostics are removed. Saved workspaces, documents and drafts remain.'}


def prepare_prune(days=90):
    preview=preview_retention(days)
    return {'days':days,'_records':preview['records']}, f"Remove {len(preview['records'])} local receipts/diagnostic records older than {days} days. Originals, documents, workspaces and drafts remain."


def prune(days=90,_records=None):
    if _records is None:
        raise ValueError('Review the retention preview first.')
    removed=0
    with store.connection() as conn:
        for record in _records:
            removed+=conn.execute('DELETE FROM records WHERE kind=? AND id=? AND revision=?',
                (record['kind'],record['id'],record['revision'])).rowcount
    return {'removed_records':removed,'original_files_preserved':True}
