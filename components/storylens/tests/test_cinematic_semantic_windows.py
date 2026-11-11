"""Synthetic CPU contracts only; no actual Vision/media/runtime acceptance."""
from contextlib import nullcontext
import copy
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

from PIL import Image

from hinglish_cinematic.semantic_windows import (
    SemanticContractError, Limits, assess_windows, choose_diverse,
    frame_digest, ConfiguredLocalVision,
)


def source(n):
    return dict(id='source-'+str(n),content_sha256=format(n+1,'064x'),
                time_base=[1,90000],origin_pts=9000,end_pts=9000+90000*20,path='never-open-source-'+str(n)+'.mp4')


def window(s,n=0):
    return dict(id=s['id']+'-window-'+str(n),source_id=s['id'],source_sha256=s['content_sha256'],
                in_pts=9000+n*90000*8,out_pts=9000+(n*8+6)*90000,measured_quality=.7)


class Frames:
    """Invented tiny pixels, never a decoded user frame."""
    def __init__(self):self.calls=[];self.override=None
    def __call__(self,s,w):
        self.calls.append(w['id'])
        rows=[]
        for n in range(3):
            im=Image.new('RGB',(8,8),(n*40,10,20))
            rows.append(dict(id=w['id']+'-frame-'+str(n),source_id=s['id'],
                source_sha256=s['content_sha256'],pts=w['in_pts']+(n+1)*90000,
                time_base=s['time_base'],sha256=frame_digest(im),image=im))
        result=dict(source_sha256=s['content_sha256'],frames=rows)
        return self.override(result) if self.override else result


class VisionBoundary:
    def __init__(self):
        self.provenance=dict(provider='injected-boundary',model='CPU fixture',model_digest='f'*64,runtime_version='fixture')
        self.calls=[];self.answer_hook=None
    def look(self,images,system,schema=None,prompt=None):
        import json
        data=json.loads(prompt);self.calls.append(copy.deepcopy(data))
        rows=[]
        for w in data['windows']:
            rows.append(dict(window_id=w['id'],status='eligible',interest=3,confidence=.85,
                subject='person',action='visible performance',setting='room',activity_type='performing',
                shot_scale='medium',camera_angle='level',evidence_frame_ids=[w['frames'][1]['id']],
                reason='The sampled middle frame shows a clear deliberate gesture.'))
        answer={'windows':rows}
        return self.answer_hook(answer,data) if self.answer_hook else answer


class SemanticWindowTests(unittest.TestCase):
    def setUp(self):self.judge=VisionBoundary();self.frames=Frames();self.s=source(0);self.w=window(self.s)
    def assess(self,sources=None,windows=None,**kw):
        return assess_windows(sources or [self.s],windows or [self.w],brief='Choose readable purposeful performance shots.',
            creator_context={'profile':'gaming','feedback':'Keep creator direction intact.'},
            judge=self.judge,frame_loader=self.frames,**kw)

    def test_meaning_and_actual_frame_bindings_are_retained(self):
        result=self.assess()
        self.assertEqual('assessed',result['state'])
        row=result['assessments'][0]
        self.assertEqual('visible performance',row['action'])
        self.assertEqual(self.s['content_sha256'],row['source_sha256'])
        self.assertEqual(9000+180000,row['frames'][1]['pts'])
        self.assertEqual([1,90000],row['frames'][1]['time_base'])
        self.assertNotIn('image',row['frames'][0])
        self.assertTrue(result['provenance']['intervention'])
        self.assertFalse(result['runtime_ready'])
        self.assertEqual('Keep creator direction intact.',self.judge.calls[0]['creator_context']['feedback'])

    def test_50_real_contract_sources_propose_10_distinct_not_a_fake_timeline(self):
        ss=[source(i) for i in range(50)];ws=[window(s) for s in ss]
        result=self.assess(ss,ws)
        selected=choose_diverse(result,10)
        self.assertEqual('selection_proposed',selected['state'])
        self.assertEqual(10,len(selected['selected']))
        self.assertEqual(10,len({w['source_sha256'] for w in selected['selected']}))
        self.assertEqual(50,len(self.judge.calls))
        self.assertTrue(selected['requires_timing_assignment'])
        self.assertNotIn('timeline',selected)

    def test_higher_semantic_interest_can_beat_higher_exposure_quality(self):
        a,b=source(0),source(1);wa,wb=window(a),window(b);wa['measured_quality']=.99;wb['measured_quality']=.6
        def answer(raw,data):
            raw['windows'][0]['interest']=4 if data['source_id']==b['id'] else 1
            return raw
        self.judge.answer_hook=answer
        chosen=choose_diverse(self.assess([a,b],[wa,wb]),1)
        self.assertEqual(b['id'],chosen['selected'][0]['source_id'])

    def test_soft_diversity_and_one_per_original_content(self):
        ss=[source(i) for i in range(3)];ws=[window(s) for s in ss]
        def answer(raw,data):
            if data['source_id']==ss[2]['id']:raw['windows'][0].update(shot_scale='wide',camera_angle='high')
            return raw
        self.judge.answer_hook=answer
        chosen=choose_diverse(self.assess(ss,ws),2)
        self.assertEqual([ss[0]['id'],ss[2]['id']],[r['source_id'] for r in chosen['selected']])
        second=window(ss[0],1)
        chosen=choose_diverse(self.assess([ss[0]],[ws[0],second]),2)
        self.assertEqual('insufficient_eligible',chosen['state']);self.assertEqual(1,len(chosen['selected']))

    def test_uncertain_low_confidence_and_no_eligible_are_not_measured_fallback(self):
        self.judge.answer_hook=lambda raw,data:{'windows':[{**r,'status':'uncertain','confidence':.2} for r in raw['windows']]}
        result=self.assess();self.assertEqual('no_eligible',result['state'])
        self.assertEqual([],choose_diverse(result,1)['selected'])
        self.assertNotIn('fallback',result)

    def test_invalid_id_and_evidence_get_one_targeted_correction_total(self):
        def answer(raw,data):
            if len(self.judge.calls)==1:raw['windows'][0]['evidence_frame_ids']=['invented']
            return raw
        self.judge.answer_hook=answer
        result=self.assess()
        self.assertEqual('assessed',result['state']);self.assertEqual(2,len(self.judge.calls))
        self.assertEqual(1,result['usage']['corrections'])

    def test_second_invalid_reply_stops_without_positive_approval(self):
        self.judge.answer_hook=lambda raw,data:{'windows':[{**r,'confidence':True} for r in raw['windows']]}
        result=self.assess()
        self.assertEqual('blocked',result['state']);self.assertEqual([],result['assessments'])
        self.assertEqual(2,len(self.judge.calls))

    def test_window_source_hash_and_bounds_fail_before_inference(self):
        for change in ({'source_sha256':'e'*64},{'in_pts':0},{'out_pts':self.s['end_pts']+1}):
            bad={**self.w,**change}
            with self.assertRaises(SemanticContractError):self.assess(windows=[bad])
        self.assertEqual([],self.judge.calls)

    def test_frame_hash_source_timestamp_and_pixels_cannot_be_substituted(self):
        for field,value in [('sha256','e'*64),('source_sha256','e'*64),('pts',0),('time_base',[1,25])]:
            def mutate(batch):batch['frames'][0][field]=value;return batch
            self.frames.override=mutate
            result=self.assess()
            self.assertEqual('blocked',result['state'])
        self.assertEqual([],self.judge.calls)

    def test_sparse_frames_cannot_be_reported_as_continuous_event_timing(self):
        result=self.assess()
        self.assertEqual('sampled_frames_only',result['coverage'])
        self.assertNotIn('contact_time',result['assessments'][0])

    def test_input_caps_reject_excess_sources_windows_and_extra_per_source(self):
        with self.assertRaises(SemanticContractError):self.assess([source(i) for i in range(51)],[self.w])
        with self.assertRaises(SemanticContractError):self.assess(windows=[window(self.s,i) for i in range(3)])
        with self.assertRaises(SemanticContractError):Limits(max_calls=1000)
        self.assertEqual([],self.judge.calls)

    def test_cache_is_bound_to_provider_content_frame_rubric_and_creator(self):
        cache={};first=self.assess(cache=cache);count=len(self.judge.calls)
        again=self.assess(cache=cache)
        self.assertEqual(count,len(self.judge.calls));self.assertEqual(1,again['usage']['cache_hits'])
        self.judge.provenance['model_digest']='e'*64
        self.assess(cache=cache);self.assertEqual(count+1,len(self.judge.calls))
        self.assertEqual(first['assessments'][0]['window_id'],again['assessments'][0]['window_id'])

    def test_cancel_before_frames_and_between_requests_preserves_checkpoint(self):
        event=threading.Event();event.set();saved=[]
        result=self.assess(cancel=event,checkpoint=lambda value:saved.append(value))
        self.assertEqual('cancelled',result['state']);self.assertEqual([],self.frames.calls)
        self.assertEqual([],self.judge.calls)
        self.assertTrue(saved)

    def test_timeout_is_uncertain_no_retry_or_automatic_measured_selection(self):
        self.judge.answer_hook=lambda *_:(_ for _ in ()).throw(TimeoutError('Injected local request timed out'))
        saved=[];result=self.assess(checkpoint=lambda value:saved.append(value))
        self.assertEqual('needs_review',result['state']);self.assertEqual(1,len(self.judge.calls))
        self.assertIsNotNone(result['pending_request'])
        again=self.assess(resume=result)
        self.assertEqual('needs_review',again['state']);self.assertEqual(1,len(self.judge.calls))

    def test_fake_cannot_claim_actual_local_runtime_acceptance(self):
        self.judge.provenance['provider']='ollama';self.judge.provenance['intervention']=False
        self.assertTrue(self.assess()['provenance']['intervention'])

    def test_no_network_process_provider_or_actual_media_in_contract_run(self):
        with patch('socket.socket',side_effect=AssertionError('No network')),patch('subprocess.Popen',side_effect=AssertionError('No process')):
            result=self.assess()
        self.assertEqual('assessed',result['state'])


class RuntimeFactoryContractTests(unittest.TestCase):
    def test_factory_is_lazy_and_requires_explicit_context(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]/'tmp') as folder:
            with patch('socket.socket',side_effect=AssertionError('No network')):
                adapter=ConfiguredLocalVision(folder)
            with self.assertRaises(RuntimeError):adapter.look([], '',schema={},prompt='{}')

    def test_factory_reads_local_model_manifest_digest_and_marks_injected_session(self):
        calls=[]
        class Response:
            def __init__(self,data):self.data=data
            def raise_for_status(self):pass
            def json(self):return self.data
        class Session:
            def get(self,url,**kw):
                calls.append(url)
                return Response({'models':[{'name':'local-vision:9b','digest':'a'*64}]} if url.endswith('/api/tags') else {'version':'fixture-1'})
            def close(self):calls.append('closed')
        client=type('Client',(),dict(model='local-vision:9b',url='http://127.0.0.1:11434',session=Session(),
                                    look=lambda *a,**kw:{'windows':[]}))()
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]/'tmp') as folder:
            with ConfiguredLocalVision(folder,client_factory=lambda _:client,guard_factory=lambda _:nullcontext()) as adapter:
                self.assertEqual('a'*64,adapter.provenance['model_digest'])
                self.assertEqual('fixture-1',adapter.provenance['runtime_version'])
                self.assertTrue(adapter.provenance['intervention'])
            self.assertIn('closed',calls)


if __name__=='__main__':unittest.main()
