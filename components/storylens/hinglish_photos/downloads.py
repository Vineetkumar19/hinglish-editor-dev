"""User-selected originals; no preview export and no eager native folder creation."""
from pathlib import Path
import hashlib
import shutil
from PIL import Image
from .quality import meets_quality


def download_one(service, collection_id, item, min_edge=0):
    with service.lock:
        job=service._get(collection_id)
        if job['status']=='archived':raise ValueError('Restore this collection before downloading a photo.')
        row=next((p for p in job['photos'] if str(p['id'])==str(item)),None)
        if row is None:raise ValueError('Choose a photo from this screenshot.')
        folder=service._folder(job)
        if row.get('download_file'):
            saved=download_path(service,collection_id,item)
            return service.snapshot(collection_id)
        if row.get('status') not in ('ready','saved','duplicate') or not row.get('file'):
            raise ValueError('The original photo has not been found yet. The small screenshot preview is not a high-quality download.')
        source=(folder/'originals'/row['file']).resolve()
        if not source.is_relative_to((folder/'originals').resolve()) or not source.is_file():
            raise ValueError('The original source photo is unavailable. Submit the screenshot again to recover it.')
        from .service import decode
        from .core import similarity
        image,fmt=decode(source.read_bytes())
        with Image.open(folder/'crops'/f'{row["id"]:03d}.png') as crop:match=similarity(crop,image)
        if not match['matched'] or not meets_quality({**row,'width':image.width,'height':image.height,'effective_width':match.get('effective_width'),'effective_height':match.get('effective_height'),'match':match},min_edge):
            raise ValueError('A matching original is not available for this photo yet. The screenshot crop will not be substituted.')
        extension={'JPEG':'.jpg','PNG':'.png','WEBP':'.webp','AVIF':'.avif','GIF':'.gif'}.get(fmt)
        if not extension:raise ValueError('This source image format cannot be downloaded.')
        number=max((int(p.get('download_number',0)) for p in job['photos']),default=0)+1
        destination=folder/'downloads';destination.mkdir(exist_ok=True)
        while list(destination.glob(f'Image {number}.*')):number+=1
        target=destination/f'Image {number}{extension}'
        with source.open('rb') as incoming,target.open('xb') as outgoing:shutil.copyfileobj(incoming,outgoing)
        row.update(download_file=target.name,download_number=number,download_sha256=hashlib.sha256(target.read_bytes()).hexdigest(),downloaded=True)
        service.update(collection_id,photos=job['photos'],selective_downloads=True)
        return service.snapshot(collection_id)


def download_path(service,collection_id,item):
    job=service._get(collection_id)
    if job['status']=='archived':raise ValueError('Restore this collection before downloading its photos.')
    row=next((p for p in job['photos'] if str(p['id'])==str(item)),None)
    if not row or not row.get('download_file'):raise ValueError('Press the photo download button first.')
    base=service._folder(job)/'downloads';path=(base/row['download_file']).resolve()
    if not path.is_relative_to(base.resolve()) or not path.is_file():raise ValueError('This downloaded photo is missing. Recover its original before retrying.')
    if row.get('download_sha256') and hashlib.sha256(path.read_bytes()).hexdigest()!=row['download_sha256']:
        raise ValueError('The downloaded photo changed. Keep the existing file and recover its original before importing.')
    return path


def manifest(service,collection_id,host,context):
    if host not in ('aftereffects','premiere'):raise ValueError('Open this feature inside After Effects or Premiere Pro.')
    job=service._get(collection_id);folder=service._folder(job);previous=job.get('native_receipts',{}).get(host)
    context=context or {};project_id=context.get('project_id','')
    if previous and project_id and previous['project']['path']!=project_id:raise ValueError('Return to the project where you downloaded these photos before importing more.')
    rows=sorted((p for p in job['photos'] if p.get('download_file')),key=lambda p:p['download_number'])
    if not rows:raise ValueError('Download a photo before creating its project folder.')
    from .aftereffects import prepare_files
    records=[{'id':row['id'],'path':str(download_path(service,collection_id,row['id'])),'origin':'original','display_name':'Image '+str(row['download_number'])} for row in rows]
    paths,converted=prepare_files(folder,[p['path'] for p in records],records,allow_downloads=True)
    for record,original in zip(converted,records):record['display_name']=original['display_name']
    value={'type':'photos','id':collection_id,'name':job['title'],'host':host,'photos':converted,'paths':paths,'expected':previous['project'] if previous else None,'folder_id':previous.get('folder',{}).get('id') if previous else None,'project_id':project_id}
    pending=dict(job.get('native_pending',{}));pending[host]=value;service.update(collection_id,native_pending=pending)
    return value
