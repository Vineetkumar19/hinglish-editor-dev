import hashlib
import json
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import Mock,patch

import numpy as np

from hinglish_app.workflow_memory import WorkflowMemory,digest,load_guide


class Encoder:
    model='fixture-local-embedding'
    dimensions=8
    def __init__(self):self.calls=[]
    def encode(self,texts,query=False,**kwargs):
        self.calls.append((list(texts),query))
        vectors=[]
        for text in texts:
            values=np.array(list(hashlib.sha256(text.encode()).digest())[:self.dimensions],np.float32)+1
            vectors.append(values/np.linalg.norm(values))
        return np.asarray(vectors,np.float32)
    def close(self):pass


class WorkflowMemoryTests(unittest.TestCase):
    def test_broll_requests_retrieve_saved_owner_procedure(self):
        from hinglish_app.workflow_memory import relevant
        for query in ('Add B-roll to this talking-head video','Find brolls','Choose relevant cutaways','Find stock footage'):
            self.assertTrue(relevant(query),query)
        self.assertFalse(relevant('Hello there'))

    def setUp(self):
        folder=tempfile.TemporaryDirectory();self.addCleanup(folder.cleanup)
        self.root=Path(folder.name)
        (self.root/'config.workflow_memory.local.json').write_text(json.dumps({'enabled':True,'top_k':4,'max_context_chars':3600}))

    def test_persistent_vectors_and_query_survive_reopening_without_reembedding(self):
        encoder=Encoder();memory=WorkflowMemory(self.root,encoder)
        query='Explain my repeated video pipeline with daily YouTube and Instagram publishing.'
        first=memory.retrieve(query)
        self.assertEqual(first['method'],'vector');self.assertFalse(first['cache_hit'])
        self.assertEqual(len(encoder.calls),2)
        from hinglish_app.workflow_memory import load_guide
        guide_count=len(load_guide()['chunks'])
        self.assertEqual(len(encoder.calls[0][0]),guide_count)
        reopened=WorkflowMemory(self.root,Encoder());again=reopened.retrieve(query)
        self.assertTrue(again['cache_hit']);self.assertFalse(reopened.encoder.calls)
        self.assertEqual(first['chunks'],again['chunks'])
        self.assertLessEqual(len(again['chunks']),4)
        self.assertLessEqual(sum(len(c['text']) for c in again['chunks']),3600)
        with reopened.connect() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM workflow_chunks').fetchone()[0],guide_count)
            self.assertTrue(all(len(r[0])==8*4 for r in db.execute('SELECT vector FROM workflow_chunks')))

    def test_changed_model_does_not_mix_incompatible_vectors(self):
        WorkflowMemory(self.root,Encoder()).retrieve('Explain the daily upload workflow.')
        encoder=Encoder();encoder.model='another-installed-local-model';encoder.dimensions=16
        result=WorkflowMemory(self.root,encoder).retrieve('Explain the daily upload workflow.')
        self.assertEqual(result['model'],encoder.model);self.assertFalse(result['cache_hit'])
        with WorkflowMemory(self.root,encoder).connect() as db:
            self.assertEqual([r[0] for r in db.execute('SELECT DISTINCT dimensions FROM workflow_chunks')],[16])

    def test_invalid_embedding_falls_back_without_claiming_vector_retrieval(self):
        encoder=Encoder();encoder.encode=lambda texts,**kw:np.zeros((len(texts),8),np.float32)
        result=WorkflowMemory(self.root,encoder).retrieve('Instagram queue remembers daily future releases.')
        self.assertEqual(result['status'],'degraded');self.assertEqual(result['method'],'keyword_fallback')
        self.assertIn('instagram-queue',[c['id'] for c in result['chunks']])
        with WorkflowMemory(self.root,encoder).connect() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM workflow_chunks').fetchone()[0],0)

    def test_unrelated_request_does_not_load_embeddings(self):
        encoder=Encoder();result=WorkflowMemory(self.root,encoder).retrieve('Explain the color wheel.')
        self.assertEqual(result['status'],'not_needed');self.assertFalse(encoder.calls)

    def test_new_request_wins_over_retrieved_procedure(self):
        from hinglish_app.assistant_edit_workflow import plan
        from hinglish_app.assistant_distribution import WORKFLOW
        brain=Mock();brain.json.return_value={'action':'edit','reply':'Preparing','count':5,'max_seconds':50,
            'profile':'gaming','platforms':'instagram','first_date':'2032-05-04','clock':'18:20',
            'captions':False,'include_longform':False,'verify_account_switches':False}
        knowledge={'chunks':[{'id':'old-example','text':'Old example: two cricket clips in October.'}]}
        result=plan(brain,'Extract 5 Shorts and post on my gaming Instagram page only from 4 May 2032 at 18:20.',
            [],[{'name':'chosen.mp4'}],WORKFLOW,{'workflow_knowledge':knowledge})
        options=result['steps'][-1]['options']
        self.assertEqual(options['distribution_profile'],'gaming');self.assertEqual(options['first_date'],'2032-05-04')
        self.assertEqual(options['clock'],'18:20');self.assertEqual(result['steps'][0]['options']['count'],5)
        self.assertEqual(brain.json.call_args.args[1]['workflow_knowledge'],knowledge)

    def test_fresh_chat_help_uses_workflow_chunks_without_media_or_publishing(self):
        from hinglish_app.server import AppState
        state=AppState(self.root);a=state.assistant
        other=a.create()['id'];a._message(other,'user','Private unrelated video from an older chat.')
        sid=a.create()['id'];query=('Explain my usual long-video publishing workflow from your saved workflow knowledge. '
            'How do you extract the requested Shorts, switch to the intended cricket accounts, upload the full video and Shorts '
            'to YouTube, and remember the later Instagram release days? This is a read-only explanation: do not edit, upload, post or schedule.')
        knowledge={'status':'ready','method':'vector','query_hash':digest(query),'chunks':[
            {'id':'instagram-queue','title':'Durable Instagram queue','text':'Persist future jobs; no daily prompt is needed.'}]}
        brain=Mock();brain.name='local fixture';brain.json.return_value={'reply':'Future posts use a durable local queue.'}
        with patch.object(WorkflowMemory,'retrieve',return_value=knowledge),\
             patch('hinglish_visuals.brain.open_brain',return_value=brain),\
             patch.object(state,'create_job') as render,\
             patch('hinglish_app.assistant_campaign.execute',side_effect=AssertionError('Help must not start a campaign')):
            a.send(sid,query)
            for _ in range(200):
                s=a.snapshot(sid)
                if s['status'] not in ('planning','running'):break
                time.sleep(.01)
        self.assertEqual(s['status'],'idle',s['stage']);render.assert_not_called()
        self.assertEqual(s['workflow_retrieval']['planner_context_ids'],['instagram-queue'])
        supplied=brain.json.call_args.args[1]['shared_memory']
        self.assertEqual(supplied['workflow_knowledge'],knowledge)
        self.assertNotIn('Private unrelated',json.dumps(supplied))
        self.assertFalse(s.get('publishing_review'));self.assertFalse(state.local_browser.data['jobs'])

    def test_guide_has_procedure_not_previous_upload_ids_or_october_slots(self):
        guide=load_guide();text=json.dumps(guide)
        self.assertNotIn('2026-10-',text);self.assertNotIn('watch?v=',text);self.assertNotIn('Dc.mp4',text)
        self.assertIn('not permission',guide['chunks'][0]['text'])
