"""Real googleapiclient resumable protocol against a deterministic fake transport."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from googleapiclient.http import HttpRequest, MediaFileUpload
from httplib2 import Response

from hinglish_publish.youtube_upload import Session, UploadSessionError


URI='https://www.googleapis.com/upload/youtube/v3/videos?upload_id=fixture-capability'


class ResumeProtocol(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]/'tmp')
        self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
        self.video=self.root/'video.mp4';self.video.write_bytes(b'0123456789abcdefg')
        self.job={'id':'a'*16,'prepare_post_id':'prepared','video':str(self.video),'account_id':'channel',
            'profile':'cricket','fingerprint':hashlib.sha256(self.video.read_bytes()).hexdigest(),
            'metadata':{'title':'Exact copy','description':'Exact description','tags':['test']},
            'made_for_kids':False,'synthetic_media':False,'visibility':'private'}
        self.patch=patch('hinglish_publish.secrets.crypt',side_effect=lambda data,**kwargs:data)
        self.patch.start();self.addCleanup(self.patch.stop)
        self.progress=[]

    def request(self,http):
        return HttpRequest(http,lambda response,content:json.loads(content.decode()),
            'https://www.googleapis.com/upload/youtube/v3/videos?uploadType=resumable',
            method='POST',body='{}',headers={},resumable=MediaFileUpload(str(self.video),chunksize=8,resumable=True))

    def test_restart_queries_server_offset_and_never_initializes_second_upload(self):
        calls=[];outer=self
        class First:
            def request(self,uri,method='GET',body=None,headers=None,**kwargs):
                calls.append((method,headers.get('Content-Range')))
                if method=='POST':return Response({'status':'200','location':URI}),b''
                # The first media chunk may not leave until its URI is durable.
                outer.assertEqual(Session(outer.root,outer.job).data['uri'],URI)
                if headers['Content-Range']=='bytes 0-7/17':return Response({'status':'308','range':'bytes=0-7'}),b''
                raise TimeoutError('response lost')
        with self.assertRaises(UploadSessionError):Session(self.root,self.job).run(self.request(First()),self.progress.append)
        self.assertEqual(Session(self.root,self.job).data['acknowledged'],8)
        class Second:
            def request(self,uri,method='GET',body=None,headers=None,**kwargs):
                calls.append((method,headers.get('Content-Range')));outer.assertEqual(uri,URI)
                if headers['Content-Range']=='bytes */17':return Response({'status':'308','range':'bytes=0-7'}),b''
                if headers['Content-Range']=='bytes 8-15/17':return Response({'status':'308','range':'bytes=0-15'}),b''
                outer.assertEqual(headers['Content-Range'],'bytes 16-16/17')
                return Response({'status':'200'}),b'{"id":"same-video"}'
        result=Session(self.root,self.job).run(self.request(Second()),self.progress.append)
        self.assertEqual(result['id'],'same-video');self.assertEqual(sum(method=='POST' for method,_ in calls),1)
        self.assertEqual(self.progress[-1]['bytes'],17);self.assertEqual(self.progress[-1]['percent'],100)
        self.assertNotIn('fixture-capability',json.dumps(self.progress))

    def test_lost_final_response_is_recovered_by_status_query_without_media(self):
        session=Session(self.root,self.job)
        session.data={'binding':session.binding,'uri':URI,'acknowledged':8,'resumes':0};session.save()
        calls=[]
        class Finished:
            def request(self,uri,method='GET',body=None,headers=None,**kwargs):
                calls.append((method,headers['Content-Range']))
                return Response({'status':'200'}),b'{"id":"accepted-video"}'
        result=session.run(self.request(Finished()),self.progress.append)
        self.assertEqual(result['id'],'accepted-video');self.assertEqual(calls,[('PUT','bytes */17')])
        # A second process can restore the final receipt without any HTTP call.
        self.assertTrue(Session(self.root,self.job).ready())
        result=Session(self.root,self.job).run(None,self.progress.append)
        self.assertEqual(result['id'],'accepted-video')

    def test_changed_account_source_or_copy_cannot_reuse_session(self):
        session=Session(self.root,self.job);session.data={'binding':session.binding,'uri':URI};session.save()
        for changes in ({'account_id':'other'},{'fingerprint':'f'*64},{'metadata':{'title':'changed'}}):
            with self.assertRaises(UploadSessionError):Session(self.root,{**self.job,**changes})

    def test_expired_session_stops_without_new_insert_or_secret_in_error(self):
        session=Session(self.root,self.job);session.data={'binding':session.binding,'uri':URI,'resumes':0};session.save()
        calls=[]
        class Expired:
            def request(self,uri,method='GET',body=None,headers=None,**kwargs):
                calls.append(method);return Response({'status':'404'}),b'{"error":{"message":"expired"}}'
        with self.assertRaises(UploadSessionError) as caught:session.run(self.request(Expired()),None)
        self.assertEqual(calls,['PUT']);self.assertNotIn('fixture-capability',str(caught.exception))
        self.assertFalse(Session(self.root,self.job).resumable())

    def test_missing_initiation_receipt_never_creates_replacement_session(self):
        session=Session(self.root,self.job);session.data={'binding':session.binding,'phase':'initializing'};session.save()
        with self.assertRaises(UploadSessionError):session.run(None,None)


if __name__=='__main__':unittest.main()
