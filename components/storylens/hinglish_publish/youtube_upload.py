"""Encrypted, source-bound resumable transfer checkpoints, never a second insert."""
import hashlib
import json
from pathlib import Path
import re
import time
from urllib.parse import urlsplit

from . import secrets


class UploadSessionError(RuntimeError):
    pass


class Session:
    def __init__(self, root, job):
        self.root=Path(root);self.job=job
        if not re.fullmatch(r'[a-f0-9]{16}',str(job.get('id',''))):
            raise UploadSessionError('A saved queue identity is required for upload recovery.')
        self.key='youtube-upload-'+job['id'];self.path=self.root/'cache/publisher'/(self.key+'.dpapi')
        source=Path(job['video']).resolve();stat=source.stat()
        self.binding={'job':job['id'],'channel':job['account_id'],'profile':job.get('profile','general'),
            'source_sha256':job['fingerprint'],'path':str(source),'bytes':stat.st_size,'mtime_ns':stat.st_mtime_ns,
            'copy_sha256':hashlib.sha256(json.dumps({k:job.get(k) for k in
                ('metadata','visibility','made_for_kids','synthetic_media')},sort_keys=True).encode()).hexdigest()}
        self.data=secrets.load(self.root,self.key) if self.path.exists() else None
        if self.data is not None and self.data.get('binding')!=self.binding:
            raise UploadSessionError('The saved upload source, channel or text changed. No replacement upload was started.')

    def save(self):
        self.data['updated']=time.time();secrets.save(self.root,self.key,self.data)

    def resumable(self):
        return bool(self.data and (self.data.get('result') or
            self.data.get('uri') and self.data.get('retryable',True) and self.data.get('resumes',0)<8))

    def ready(self):
        return self.resumable() and self.data.get('next_retry',0)<=time.time()

    def run(self, request, progress):
        try:
            return self._run(request,progress)
        finally:
            if request is not None and request.resumable.has_stream():
                request.resumable.stream().close()

    def _run(self, request, progress):
        if self.data and self.data.get('result'):
            return self.data['result']
        if self.data:
            if not self.resumable():
                raise UploadSessionError('This interrupted transfer has no usable saved session. Check its existing YouTube entry; no replacement upload was started.')
            uri=self.data['uri'];parsed=urlsplit(uri)
            if parsed.scheme!='https' or parsed.hostname not in ('www.googleapis.com','youtube.googleapis.com') or parsed.username or parsed.password:
                raise UploadSessionError('The saved upload session is invalid. No transfer was started.')
            request.resumable_uri=uri
            request.resumable_progress=self.data.get('acknowledged',0)
            # Always ask YouTube for its current byte offset/result after a
            # restart, including a response lost after the final media chunk.
            request._in_error_state=True
            self.data['resumes']=self.data.get('resumes',0)+1;self.save()
        else:
            # If initiation's response itself is lost we deliberately cannot
            # start another session: YouTube may have accepted the first one.
            self.data={'binding':self.binding,'phase':'initializing','acknowledged':0,'resumes':0}
            self.save()
        session=self;http=request.http
        class CheckpointHTTP:
            def request(self, uri, method='GET', body=None, headers=None, **kwargs):
                response,content=http.request(uri,method=method,body=body,headers=headers,**kwargs)
                if request.resumable_uri is None and uri==request.uri and response.status==200 and response.get('location'):
                    # Commit the capability before googleapiclient sends ANY
                    # media bytes in this same next_chunk call.
                    session.data.update(uri=response['location'],phase='transferring',retryable=True)
                    session.save()
                return response,content
        transport=CheckpointHTTP()
        try:
            result=None
            while result is None:
                status,result=request.next_chunk(http=transport,num_retries=0)
                acknowledged=int(request.resumable_progress)
                if result:
                    if not isinstance(result.get('id'),str) or not result['id']:
                        raise UploadSessionError('YouTube returned no upload identity. The transfer checkpoint is retained.')
                    acknowledged=self.binding['bytes'];self.data.update(result=result,phase='uploaded',retryable=False)
                self.data.update(acknowledged=acknowledged,next_retry=0);self.save()
                if progress:progress({'bytes':acknowledged,'total':self.binding['bytes'],
                    'percent':min(100,round(100*acknowledged/self.binding['bytes'],1)),
                    'updated':time.time(),'state':'uploaded' if result else 'uploading'})
            return result
        except Exception as error:
            from httplib2 import HttpLib2Error
            from google.auth.exceptions import TransportError
            code=getattr(getattr(error,'resp',None),'status',None)
            transient=isinstance(error,(TimeoutError,ConnectionError,OSError,HttpLib2Error,TransportError)) or code in (408,429,500,502,503,504)
            self.data.update(retryable=bool(self.data.get('uri') and transient),
                next_retry=time.time()+min(300,5*2**self.data.get('resumes',0)))
            self.save()
            # Never expose the resumable capability or raw request URL.
            raise UploadSessionError('The transfer was interrupted. Its saved session will resume automatically.' if self.resumable() else
                'The transfer needs review. Its saved upload session is kept; no replacement upload was started.') from None
