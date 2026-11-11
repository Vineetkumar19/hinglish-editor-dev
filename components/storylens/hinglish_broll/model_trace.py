"""Local per-call timing evidence; never changes a model decision.

Zero observed HTTP calls is recorded literally, not asserted to prove cache
freshness. No raw prompt, creator profile, credential or image is logged here.
"""
import hashlib
import json
from pathlib import Path
import time
import uuid


class ModelTrace:
    def __init__(self,model,file):
        self.model,self.file=model,Path(file)
        self.responses=[]
        hooks=getattr(getattr(model,'session',None),'hooks',None)
        if isinstance(hooks,dict):hooks.setdefault('response',[]).append(self._response)

    def _response(self,response,*args,**kwargs):
        row={'http_status':getattr(response,'status_code',None)}
        try:
            data=response.json()
            for key in ('model','total_duration','load_duration','prompt_eval_count',
                        'prompt_eval_duration','eval_count','eval_duration','done_reason'):
                if key in data:row[key]=data[key]
        except (ValueError,TypeError):pass
        self.responses.append(row)

    def look(self,images,system,schema=None,*args):
        began=time.monotonic();offset=len(self.responses);status='failed'
        record={'version':1,'call_id':uuid.uuid4().hex,'wall_start_ns':time.time_ns(),
                'model':getattr(self.model,'name',getattr(self.model,'model','unknown')),
                'image_count':len(images),'request_sha256':hashlib.sha256(
                    json.dumps([system,schema,args],sort_keys=True,ensure_ascii=False).encode()).hexdigest()}
        try:
            result=self.model.look(images,system,schema,*args);status='returned'
            return result
        finally:
            record.update(status=status,elapsed_seconds=time.monotonic()-began,
                          http_requests_observed=len(self.responses)-offset,responses=self.responses[offset:])
            try:
                self.file.parent.mkdir(parents=True,exist_ok=True)
                with self.file.open('a',encoding='utf-8') as stream:
                    stream.write(json.dumps(record,ensure_ascii=False)+'\n')
            except OSError:
                # Diagnostics must not turn a valid video check into a failure.
                print('B-roll timing details could not be saved; video checking continues.',flush=True)
