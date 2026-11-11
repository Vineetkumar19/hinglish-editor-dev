"""Receipt-bound individual timeline choices, shared by B-roll and Visuals.

Only controllers holding a verified candidate may prepare an operation. A saved
owner choice and a confirmed host insertion are separate records. An uncertain
operation is reconciled by repeating its ID, never by creating a second insert.
"""
from fractions import Fraction
from pathlib import Path
import hashlib
import json
import math
import re
import shutil
import threading
import uuid

from hinglish_broll.recovery import read_json, write_json

_LOCK = threading.RLock()


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def file_digest(path):
    sha = hashlib.sha256()
    with path.open('rb') as stream:
        while chunk := stream.read(1024*1024):sha.update(chunk)
    return sha.hexdigest()


class TimedChoiceDelivery:
    def __init__(self,root):
        self.root=Path(root).resolve()
        self.folder=self.root/'output/editor-handoffs/timed-choices'

    def _operation(self,operation_id):
        if not isinstance(operation_id,str) or not re.fullmatch(r'[a-f0-9]{32}',operation_id):
            raise ValueError('Choose a saved timeline operation before accepting its receipt.')
        record=read_json(self.folder/'operations'/f'{operation_id}.json',{})
        if record.get('manifest',{}).get('operation_id')!=operation_id:
            raise ValueError('Reopen the saved timeline choice; its receipt has no operation.')
        return record

    def prepare(self,value,context):
        if context.get('host')=='capcut':
            raise ValueError('CapCut currently opens a separate editable project. Direct replacement in an open timeline is not available.')
        if context.get('host') not in ('premiere','aftereffects'):
            raise ValueError('Connect Premiere Pro or After Effects before inserting a timed choice.')
        if any(not str(context.get(k,'')).strip() for k in ('project_id','sequence_id')) or context.get('sequence_id')=='_project_':
            raise ValueError('Connect the actual timeline or composition before inserting a timed choice.')
        if value.get('feature') not in ('broll','visuals'):
            raise ValueError('Choose a verified B-roll or Smart Visuals source.')
        for key in ('bank_id','slot_id','slot_fingerprint','asset_id'):
            if not isinstance(value.get(key),str) or not value[key].strip() or len(value[key])>512:
                raise ValueError('Reopen this verified source bank before inserting its choice.')
        path=Path(value.get('asset_path','')).resolve()
        if not path.is_relative_to(self.root/'output') or not path.is_file():
            raise ValueError('Choose a checked, saved media file from this project.')
        if file_digest(path)!=value.get('asset_sha256'):
            raise ValueError('This media changed. Check this exact video again before inserting it.')
        start,end=value.get('start_frame'),value.get('end_frame')
        if type(start) is not int or type(end) is not int or start<0 or end<=start:
            raise ValueError('Restore the original spoken word frames before inserting this choice.')
        try:
            fps=Fraction(str(value['fps']));source_in=float(value['source_in']);duration=float(value['source_duration'])
            if fps<=0 or fps>240 or not math.isfinite(source_in) or not math.isfinite(duration) or source_in<0 or source_in+float((end-start)/fps)>duration+1e-7:
                raise ValueError()
            if context.get('fps') and abs(float(Fraction(str(context['fps'])))-float(fps))>1e-5:
                raise ValueError()
        except (KeyError,TypeError,ValueError,ZeroDivisionError):
            raise ValueError('The media trim or timeline frame rate does not match. Reconnect and check this choice.') from None
        expected={k:str(context[k]) for k in ('host','project_id','sequence_id')}
        identity={**expected,'feature':value['feature'],'bank_id':value['bank_id'],'slot_id':value['slot_id']}
        binding_id=digest(identity)
        request={**value,'asset_path':str(path),'expected':expected}
        request_sha=digest(request)
        with _LOCK:
            binding_file=self.folder/'bindings'/f'{binding_id}.json'
            binding=read_json(binding_file,{})
            pending=binding.get('pending')
            if pending:
                previous=self._operation(pending)
                if previous['request_sha256']!=request_sha:
                    raise ValueError('First confirm the previous timeline operation. Its delivery is uncertain; retry the same choice to reconcile it.')
                return {**previous['manifest'],'already_confirmed':False}
            current=binding.get('current')
            if current and current['request_sha256']==request_sha:
                return {**self._operation(current['operation_id'])['manifest'],'already_confirmed':True}
            if current and current['slot_fingerprint']!=value['slot_fingerprint']:
                raise ValueError('This spoken slot changed. Reconnect its original timeline before replacing the saved item.')
            operation_id=uuid.uuid4().hex
            host_path=path
            if expected['host'] in ('premiere','aftereffects'):
                # Premiere changes the media path of a ProjectItem. Give each
                # slot its own file identity so that operation cannot relink
                # the same source in unrelated owner clips.
                host_path=self.folder/'media'/binding_id/(value['asset_sha256']+path.suffix.lower())
                host_path.parent.mkdir(parents=True,exist_ok=True)
                if not host_path.is_file():
                    temporary=host_path.with_suffix(host_path.suffix+'.'+operation_id+'.tmp')
                    shutil.copyfile(path,temporary)
                    if file_digest(temporary)!=value['asset_sha256']:
                        raise ValueError('This media changed while preparing the private timeline source.')
                    temporary.replace(host_path)
                if file_digest(host_path)!=value['asset_sha256']:
                    raise ValueError('The private timeline source changed. Restore its checked media before delivery.')
            manifest={'type':'timed_choice','version':1,'operation_id':operation_id,'binding_id':binding_id,
                      'action':'replace' if current else 'insert','feature':value['feature'],
                      'asset_id':value['asset_id'],'asset_sha256':value['asset_sha256'],'path':str(host_path),
                      'expected':expected,'expected_item_id':current['item_id'] if current else None,
                      'previous_operation_id':current['operation_id'] if current else None,
                      'previous_path':self._operation(current['operation_id'])['manifest']['path'] if current else None,
                      'start_frame':start,'end_frame':end,'fps':str(fps),
                      'source_in':source_in,'source_duration':duration,
                      'width':value.get('width'),'height':value.get('height'),
                      'preserve_host_edits':True}
            record={'request_sha256':request_sha,'slot_fingerprint':value['slot_fingerprint'],
                    'manifest':manifest,'receipt':None}
            write_json(self.folder/'operations'/f'{operation_id}.json',record)
            write_json(binding_file,{**binding,'identity':identity,'pending':operation_id})
            return {**manifest,'already_confirmed':False}

    def accept(self,operation_id,receipt,*,context=None):
        with _LOCK:
            record=self._operation(operation_id);manifest=record['manifest']
            if context and any(str(context.get(k,''))!=v for k,v in manifest['expected'].items()):
                raise ValueError('Reconnect the original editor project and timeline before confirming this receipt.')
            if not isinstance(receipt,dict) or receipt.get('ok') is not True:
                raise ValueError('The editor has not confirmed this timeline operation. Retry the same choice to reconcile it.')
            for key in ('operation_id','binding_id','asset_id','asset_sha256','path'):
                if receipt.get(key)!=manifest[key]:raise ValueError('This native receipt belongs to another timeline choice.')
            if any(str(receipt.get(k,''))!=v for k,v in manifest['expected'].items()):
                raise ValueError('This native receipt belongs to another editor project or timeline.')
            item_id=receipt.get('item_id')
            if not isinstance(item_id,str) or not item_id:
                raise ValueError('The native receipt did not identify the timeline item.')
            if manifest['expected_item_id'] and item_id!=manifest['expected_item_id']:
                raise ValueError('The editor replaced a different item. Reconcile the saved choice before continuing.')
            try:
                start,end,source_in=(float(receipt[k]) for k in ('start','end','source_in'))
                if not all(math.isfinite(v) for v in (start,end,source_in)) or start<0 or end<=start or source_in<0:
                    raise ValueError()
            except (KeyError,TypeError,ValueError):raise ValueError('The native receipt has no readable placement and trim.') from None
            if not record['receipt'] and manifest['action']=='insert':
                fps=float(Fraction(manifest['fps']))
                if any(abs(a-b)>1e-5 for a,b in ((start,manifest['start_frame']/fps),(end,manifest['end_frame']/fps),(source_in,manifest['source_in']))):
                    raise ValueError('The editor did not confirm the original speech timestamp and trim.')
            binding_file=self.folder/'bindings'/f'{manifest["binding_id"]}.json'
            binding=read_json(binding_file,{})
            if record['receipt'] and binding.get('pending')!=operation_id:
                return record['receipt']
            if binding.get('pending')!=operation_id:
                raise ValueError('Reconcile the current pending timeline operation before accepting this receipt.')
            record['receipt']=receipt;write_json(self.folder/'operations'/f'{operation_id}.json',record)
            binding.update(pending=None,current={'operation_id':operation_id,'item_id':item_id,
                'request_sha256':record['request_sha256'],'slot_fingerprint':record['slot_fingerprint']})
            write_json(binding_file,binding)
            return receipt
