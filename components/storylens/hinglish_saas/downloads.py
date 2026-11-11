"""Only published, verified customer release artifacts are downloadable."""
import hashlib
import json
from pathlib import Path
from fastapi import HTTPException, Request
from fastapi.responses import FileResponse


def mount_downloads(app,settings,store,account):
    folder=settings.data_dir/'releases'

    def catalog():
        try:
            manifest=json.loads((folder/'release.json').read_text(encoding='utf-8'))
            if manifest.get('release_ready') is not True:return []
            items=manifest.get('artifacts',[])
            return [item for item in items if isinstance(item,dict) and all(isinstance(item.get(k),str) for k in ('id','label','edition','version','file','sha256'))] if isinstance(items,list) else []
        except (OSError,ValueError):return []

    def validated(item):
        name=item.get('file','')
        if not isinstance(name,str) or Path(name).name!=name or '\\' in name or '/' in name:return None
        path=(folder/name).resolve()
        if not path.is_relative_to(folder.resolve()) or not path.is_file():return None
        if item.get('edition') not in ('desktop','plugins') or path.suffix not in ('.exe','.msi','.zip','.ccx','.zxp'):return None
        checksum=hashlib.sha256()
        with path.open('rb') as handle:
            for block in iter(lambda:handle.read(1024**2),b''):checksum.update(block)
        sha=checksum.hexdigest()
        return path if sha==item.get('sha256') else None

    @app.get('/api/downloads')
    def available(request:Request):
        user=account(request)
        allowed={edition:store.entitlement(user['user_id'],edition=edition)['active'] for edition in ('desktop','plugins')}
        return {'items':[{k:item[k] for k in ('id','label','edition','version','sha256')}
                         for item in catalog() if allowed.get(item.get('edition')) and validated(item)],
                'message':'Customer installers appear after a signed release passes host testing.'}

    @app.get('/api/downloads/{artifact_id}')
    def download(artifact_id:str,request:Request):
        user=account(request)
        item=next((item for item in catalog() if item.get('id')==artifact_id),None)
        if not item:raise HTTPException(404,'This release is unavailable.')
        if not store.entitlement(user['user_id'],edition=item.get('edition'))['active']:raise HTTPException(402,'Purchase Storylens before downloading it.')
        path=validated(item)
        if not path:raise HTTPException(404,'This release failed verification and is unavailable.')
        return FileResponse(path,filename=path.name,media_type='application/octet-stream')
