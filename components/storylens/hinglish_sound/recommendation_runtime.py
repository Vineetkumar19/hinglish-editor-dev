"""Feature-owned cooperative control and receipts; no application/host coupling."""
from contextlib import contextmanager
import copy
import json
import math
import os
from pathlib import Path
import threading
import time
import uuid


class RecommendationCancelled(Exception):
    pass


class CancellationToken:
    def __init__(self):
        self._event=threading.Event();self.reason='Cancellation requested'

    def cancel(self, reason='Cancellation requested'):
        self.reason=str(reason)[:240];self._event.set()

    def check(self):
        if self._event.is_set():raise RecommendationCancelled(self.reason)


class Telemetry:
    """Two monotonic reads per stage/call; metadata never includes script/secrets."""
    def __init__(self, *, clock=time.monotonic, sink=None):
        self.clock=clock;self.sink=sink;self.receipts=[]

    @contextmanager
    def stage(self, name, *, kind='stage', cache='unknown', retry=0, metadata=None):
        if cache not in ('hit','miss','unknown','not_applicable') or type(retry) is not int or retry<0:
            raise ValueError('Use an explicit cache state and nonnegative retry count')
        start=self.clock();status='complete';error_type=None
        try:yield
        except BaseException as error:
            status='cancelled' if isinstance(error,RecommendationCancelled) else 'failed'
            error_type=type(error).__name__;raise
        finally:
            end=self.clock()
            if not all(type(t) in (float,int) and math.isfinite(t) for t in (start,end)) or end<start:
                raise ValueError('The profiling clock must be monotonic and finite')
            row=dict(name=str(name),kind=kind,start=start,end=end,seconds=end-start,
                     status=status,cache=cache,retry=retry,metadata=copy.deepcopy(metadata or {}))
            if error_type:row['error_type']=error_type
            self.receipts.append(row)
            if self.sink:self.sink(copy.deepcopy(row))


def write_json_atomic(path, value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    temporary=path.with_name(path.name+'.'+uuid.uuid4().hex+'.tmp')
    try:
        with temporary.open('w',encoding='utf-8') as out:
            json.dump(value,out,ensure_ascii=False,allow_nan=False,indent=2)
            out.flush();os.fsync(out.fileno())
        os.replace(temporary,path)
    finally:
        if temporary.exists():temporary.unlink()


class CheckpointStore:
    """Only complete recommendation groups are durable. Never execute saved data."""
    def __init__(self, directory):self.path=Path(directory)/'recommendation-checkpoint.json'

    def load(self, fingerprint):
        if not self.path.exists():return None
        value=json.loads(self.path.read_text('utf-8'))
        if value.get('checkpoint_version')!=1 or value.get('fingerprint')!=fingerprint:
            raise ValueError('This checkpoint belongs to different inputs or versions; keep it and start a new checkpoint folder.')
        return value

    def save(self, fingerprint, groups, status):
        write_json_atomic(self.path,dict(checkpoint_version=1,fingerprint=fingerprint,
                                      groups=copy.deepcopy(groups),status=status))
