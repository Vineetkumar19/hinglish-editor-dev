"""Typed photo transfers and checked host receipts for the unified Adobe panel."""
from pathlib import Path
import uuid
from PIL import Image
from .core import similarity
from .service import decode,write_json
from .quality import meets_quality

def prepare(service,id,host,context=None):
 if host not in ('aftereffects','premiere'):raise ValueError('Choose After Effects or Premiere Pro for this collection.')
 context=context or {};job=service._get(id);folder=service._folder(job)
 if job.get('selective_downloads'):
  from .downloads import manifest
  return manifest(service,id,host,context)
 if job['status']=='archived':raise ValueError('Restore this collection before importing it.')
 previous=job.get('native_receipts',{}).get(host) or (job.get('ae_receipt') if host=='aftereffects' else None)
 project_id=context.get('project_id','')
 if previous and project_id and previous['project']['path']!=project_id:raise ValueError('The active project changed. Choose the original project before upgrading its photos.')
 originals=[];records=[]
 for row in job['photos']:
  if row['status'] in ('ready','saved','duplicate'):
   path=service.file(id,'photo',row['id']);image,_=decode(path.read_bytes())
   with Image.open(folder/'crops'/f'{row["id"]:03d}.png') as crop:match=similarity(crop,image)
   if match['matched'] and meets_quality({**row,'width':image.width,'height':image.height,'match':match,'effective_width':match.get('effective_width'),'effective_height':match.get('effective_height')},job.get('min_edge',0)):originals.append(row['id'])
 for row in job['photos']:
  if row['id'] in originals:
   service.save(id,row['id']);path=service.file(id,'photo',row['id']);origin='original'
  elif job.get('previews') and row.get('preview_file'):
   path=(folder/'previews'/row['preview_file']).resolve();origin='screenshot-preview'
   if not path.is_relative_to((folder/'previews').resolve()):raise ValueError('Photo file invalid: a labelled preview is outside this collection. Reopen the collection before importing.')
   if not path.is_file():raise ValueError('Photo file missing: a labelled preview is unavailable. Restore its file or submit the saved screenshot again before importing. Confirmed originals are kept.')
  else:continue
  records.append({'id':row['id'],'path':str(path).replace('\\','/'),'origin':origin})
 if not records:raise ValueError('No photos are ready. Continue the search or enable labelled previews.')
 from .aftereffects import prepare_files
 paths,records=prepare_files(folder,[r['path'] for r in records],records)
 manifest={'type':'photos','id':id,'name':job['title'],'host':host,'photos':records,'paths':[r['path'] for r in records],
           'expected':previous['project'] if previous else None,'folder_id':previous.get('folder',{}).get('id') if previous else None,'project_id':project_id}
 pending=dict(job.get('native_pending',{}));pending[host]=manifest;service.update(id,native_pending=pending)
 return manifest

def accept_receipt(service,id,host,receipt):
 job=service._get(id);manifest=job.get('native_pending',{}).get(host)
 if not manifest or not isinstance(receipt,dict) or receipt.get('status')!='done' or receipt.get('host')!=host or receipt.get('collection_id')!=id:raise ValueError('The editor has not confirmed this photo import. Check its project before retrying.')
 project=receipt.get('project') or {};folder=receipt.get('folder') or {}
 if manifest.get('project_id') and project.get('path')!=manifest['project_id']:raise ValueError('The receipt belongs to a different project. Reconnect the intended project.')
 if not folder.get('id') or folder.get('parent') not in ('Photo Collector','Images') or not str(folder.get('name','')).startswith('Screenshot '):raise ValueError('The editor did not confirm the Photo Collector screenshot folder.')
 actual={str(r.get('photo_id')):r for key in ('imported','upgraded','already_present') for r in receipt.get(key,[])}
 for row in manifest['photos']:
  found=actual.get(str(row['id']))
  if not found or not found.get('id') or Path(found.get('path','')).resolve()!=Path(row['path']).resolve() or (row['origin']=='original' and found.get('origin')!='original'):raise ValueError('The editor did not confirm every photo. Inspect the screenshot folder before retrying.')
 target=service._folder(job)/'native-receipts';target.mkdir(exist_ok=True);path=target/(host+'-'+uuid.uuid4().hex[:12]+'.json');write_json(path,receipt)
 receipts=dict(job.get('native_receipts',{}));receipts[host]={**receipt,'receipt':str(path)}
 changes={'native_receipts':receipts}
 if host=='aftereffects':changes.update(ae_status='done',ae_receipt=receipts[host],ae_expected=project)
 service.update(id,**changes);return service.snapshot(id)
