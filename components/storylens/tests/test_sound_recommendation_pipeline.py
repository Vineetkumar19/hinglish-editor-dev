"""Injected component fixtures: no real local models, library scan or media render."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from hinglish_sound.recommendation_runtime import CancellationToken
from hinglish_sound.recommendations import CachedRankingIndex
from hinglish_sound.recommendation_pipeline import run, Journal, InsufficientAnalysis, LocalRuntime, _transport, _BrainReceipt


class FixtureRuntime:
    """Intentionally empty prepared library; analysis is a labelled test double."""
    def __init__(self):
        self.calls = []
        self.models = {'planning': {'name': 'fixture:14b', 'digest': 'synthetic'}}
        self.bad = False
        self.empty = False
        self.token = None

    def invoke(self, name, context, journal):
        self.calls.append(name)
        self.context = copy.deepcopy(context)
        if self.token and name == 'observe': self.token.cancel('fixture cancellation')
        if name == 'prepare': return {'id': 'fixture-source', 'duration': 6., 'fps': '30'}
        if name == 'transcribe': return {'words': [{'text': 'water', 'start': 0., 'end': 1.}], 'lines': [{'id': 0, 'start': 0., 'end': 1., 'text': 'water'}]}
        if name == 'observe': return [{'time': 0., 'end': 6., 'setting': 'pool', 'ambience': 'moving water', 'confidence': .9}]
        if name == 'prosody': return []
        if name == 'inventory': return {'revision': 'fixture', 'moods': ['joyful'], 'families': ['ambience']}
        if name == 'plan':
            if self.bad: raise InsufficientAnalysis('Invalid local line IDs')
            return {'music_sections': [] if self.empty else [dict(id='music-0', start=0., end=6., mood='joyful', intent='playful instrumental', role='bed', level_db=-16., evidence=dict(kind='script', precision='phrase', confidence=1., description='water'))],
                    'sfx_events': [] if self.empty else [dict(id='water-0', start=0., end=5., sound_type='ambience', intent='moving pool water', role='bed', level_db=-20., evidence=dict(kind='vision', precision='sampled', confidence=.9, description='pool with moving water'))]}
        raise AssertionError(name)

    def rankings(self, request, journal, token, limit):
        self.calls.append('rankings')
        return CachedRankingIndex([], {}), CachedRankingIndex([], {}), []

    def passage(self, asset, slot): raise AssertionError('Empty fixture has no passages')
    def close(self): self.calls.append('close')


class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.source = self.root / 'source.mp4'
        self.source.write_bytes(b'not decoded by fake runtime')
        self.runtime = FixtureRuntime()
        self.profile = {'profile': 'general', 'instructions': ['Do not remove my full creator guidance'], 'nested': {'keep': 'all'}}

    def tearDown(self): self.tmp.cleanup()

    def call(self, **kwargs):
        return run(self.root, self.source, 'Exact water SCRIPT 42', self.profile,
                   runtime_factory=lambda *args: self.runtime, **kwargs)

    def test_analysis_runs_before_prepared_recommendations_without_full_mix(self):
        result = self.call()
        self.assertEqual(result['status'], 'no_match')
        self.assertEqual(self.runtime.calls, ['prepare','transcribe','observe','prosody','inventory','plan','rankings','close'])
        request = json.loads(Path(result['folder'], 'request.json').read_text())
        self.assertEqual(request['script'], 'Exact water SCRIPT 42')
        self.assertEqual(request['creator_context'], self.profile)
        manifest = json.loads(Path(result['manifest']).read_text())
        self.assertEqual([g['kind'] for g in manifest['groups']], ['music','sfx'])
        self.assertFalse(manifest['capabilities']['mixed'])
        self.assertTrue(result['test_factory_used'])
        self.assertFalse(result['local_agent_acceptance'])

    def test_default_does_not_construct_models_without_explicit_release(self):
        with patch('hinglish_sound.recommendation_pipeline.LocalRuntime') as cls:
            with self.assertRaisesRegex(ValueError, 'resource release'):
                run(self.root, self.source, 'script', self.profile)
            cls.assert_not_called()

    def test_local_execute_still_requires_suite_lease(self):
        with patch('hinglish_sound.recommendation_pipeline.LocalRuntime') as cls:
            with self.assertRaisesRegex(ValueError, 'resource release'):
                run(self.root, self.source, 'script', self.profile, execute_local=True)
            cls.assert_not_called()

    def test_exact_requested_model_mismatch_stops_before_analysis(self):
        result = self.call(expected_models={'planning': 'different:14b'})
        self.assertEqual(result['status'], 'failed')
        self.assertEqual(self.runtime.calls, ['close'])

    def test_invalid_model_analysis_is_not_ready(self):
        self.runtime.bad = True
        result = self.call()
        self.assertEqual(result['status'], 'insufficient_analysis')
        self.assertNotIn('rankings', self.runtime.calls)

    def test_empty_plan_is_not_successful_recommendation(self):
        self.runtime.empty = True
        result = self.call()
        self.assertEqual(result['status'], 'insufficient_analysis')
        self.assertNotIn('rankings', self.runtime.calls)

    def test_missing_timed_speech_does_not_invent_script_times(self):
        invoke = self.runtime.invoke
        self.runtime.invoke = lambda n,c,j: {'words': [], 'lines': []} if n=='transcribe' else invoke(n,c,j)
        result = self.call()
        self.assertEqual(result['status'], 'insufficient_analysis')
        self.assertNotIn('plan', self.runtime.calls)

    def test_missing_visual_analysis_does_not_rank_click_fallback(self):
        invoke = self.runtime.invoke
        self.runtime.invoke = lambda n,c,j: [] if n=='observe' else invoke(n,c,j)
        self.assertEqual(self.call()['status'], 'insufficient_analysis')
        self.assertNotIn('rankings', self.runtime.calls)

    def test_cancel_preserves_fresh_evidence_and_does_not_resume_checkpoint(self):
        self.runtime.token = CancellationToken()
        result = self.call(token=self.runtime.token)
        self.assertEqual(result['status'], 'cancelled')
        self.assertTrue(Path(result['folder'], 'observe.json').is_file())
        self.assertFalse(list(Path(result['folder']).glob('*checkpoint*')))
        self.assertNotIn('plan', self.runtime.calls)

    def test_redacted_receipts_do_not_mutate_original_input(self):
        value = {'authorization': 'Bearer FIXTURE_TOKEN', 'prompt_tokens': 42,
                 'nested': ['https://example.test/?api_key=FIXTURE_KEY', 'Bearer FIXTURE_BEARER']}
        before = copy.deepcopy(value)
        journal = Journal(self.root / 'audit')
        journal.record('fixture', value)
        output = (self.root / 'audit' / '0001-fixture.json').read_text()
        self.assertEqual(value, before)
        self.assertNotIn('FIXTURE_TOKEN', output)
        self.assertNotIn('FIXTURE_KEY', output)
        self.assertNotIn('FIXTURE_BEARER', output)
        self.assertEqual(json.loads(output)['prompt_tokens'], 42)

    def test_fresh_runs_have_separate_directories(self):
        a, b = self.call(), self.call()
        self.assertNotEqual(a['folder'], b['folder'])

    def test_prepared_audio_candidates_keep_scene_duration_and_test_provenance(self):
        import math, struct, wave
        from hinglish_sound.library import Asset
        folder=self.root/'library';folder.mkdir()
        assets=[]
        for kind,category,name in [('music','joyful','fixture instrumental'),('sfx','ambience','fixture pool water')]:
            path=folder/(kind+'.wav')
            with wave.open(str(path),'wb') as wav:
                wav.setnchannels(1);wav.setsampwidth(2);wav.setframerate(8000)
                wav.writeframes(b''.join(struct.pack('<h',round(1000*math.sin(i*.2))) for i in range(48000)))
            assets.append(Asset(str(path),kind,category,name,name,6.,-20.,1.))
        def rankings(request,journal,token,limit):
            return (CachedRankingIndex(assets[:1],{request['music_sections'][0]['intent']:[(assets[0].path,.8)]}),
                    CachedRankingIndex(assets[1:],{request['sfx_events'][0]['intent']:[(assets[1].path,.8)]}),[folder])
        self.runtime.rankings=rankings
        self.runtime.passage=lambda a,s:dict(source_in=0.,basis='synthetic measured fixture; not real water semantics')
        result=self.call()
        self.assertEqual(result['status'],'ready')
        manifest=json.loads(Path(result['manifest']).read_text())
        self.assertTrue(manifest['analysis_provenance']['test_factory_used'])
        self.assertEqual(manifest['groups'][1]['candidates'][0]['timeline'],{'start':0.,'end':5.})

    def test_json_embedded_in_model_message_is_redacted(self):
        journal=Journal(self.root/'audit')
        journal.record('fixture',{'message':{'content':json.dumps({'authorization':'FIXTURE_AUTH','prompt_tokens':123})}})
        self.assertNotIn('FIXTURE_AUTH',(self.root/'audit/0001-fixture.json').read_text())

    def test_protected_delivery_files_unchanged(self):
        import hashlib
        project = Path(__file__).resolve().parents[1]
        frozen = json.loads((project/'docs/sound-candidate-evidence-2026-10-25/frozen-delivery.json').read_text())
        for row in frozen['files']:
            self.assertEqual(hashlib.sha256((project/row['path']).read_bytes()).hexdigest(), row['sha256'])


class LocalAdapterTests(unittest.TestCase):
    """Real controller/tools with mocked model replies; not an inference test."""
    def setUp(self):
        from hinglish_broll.phrases import Phrase
        self.tmp=tempfile.TemporaryDirectory(); self.root=Path(self.tmp.name)
        self.rt=LocalRuntime.__new__(LocalRuntime)
        self.rt.root=self.root;self.rt.folder=self.root;self.rt.progress=lambda *a:None
        self.rt.proxy=object();self.rt.words=[];self.rt.lines=[Phrase(0,0.,6.,'A pool and a slide')]
        self.rt.raw_events=[]
        self.rt.observations=[dict(time=0.,end=6.,setting='pool',action='water flows',mood='joyful',ambience='pool water flowing',confidence=.9,
            action_events=[dict(time=1.,end=4.,kind='foley',label='water splashing',precision='visual_interval',uncertainty=.5,confidence=.95,sound_evidence='water visibly splashes')])]
        self.c=dict(prepare={'duration':6.},inventory={'moods':['joyful'],'families':['foley','ambience']},prosody=[],density='medium',script='Exact SCRIPT')
        self.answer=dict(story='joyful pool',palette='comedic',music=[dict(from_id=0,to_id=0,mode='music',mood='joyful',why='playful instrumental supports the joyful scene')])

    def tearDown(self):self.tmp.cleanup()

    def plan(self,compose):
        with patch('hinglish_sound.director.analyse',return_value=self.answer),patch('hinglish_sound.composition.policy',return_value={'seconds':6.,'version':2}),patch('hinglish_sound.composition.rhetorical_palette',return_value={'palette':'comedic'}),patch('hinglish_sound.layers.augment_moments',side_effect=compose):
            return self.rt._plan(self.c)

    def test_visual_source_interval_confidence_and_natural_tail_survive_mapping(self):
        def composed(brain,events,*args,**kwargs):
            e=next(e for e in events if e['kind']=='foley')
            return [dict(event_id=e['id'],target=1.,duration=2.5,type='foley',role='travel',intent='water splashing',level_db=-15.)]
        plan=self.plan(composed);slot=plan['sfx_events'][0]
        self.assertEqual((slot['start'],slot['end']),(1.,3.5))
        self.assertEqual(slot['evidence']['precision'],'visual_interval')
        self.assertEqual(slot['evidence']['confidence'],.95)
        self.assertEqual(slot['evidence']['uncertainty'],.5)

    def test_unknown_anchor_cannot_create_an_exact_contact(self):
        with self.assertRaisesRegex(InsufficientAnalysis,'measured anchor'):
            self.plan(lambda *a,**k:[dict(event_id='invented',target=1.,duration=2.,type='foley',role='contact',intent='sliding')])

    def test_invalid_music_line_ids_are_not_assigned_fabricated_times(self):
        self.answer['music'][0]['to_id']=99
        with self.assertRaisesRegex(ValueError,'line IDs'):self.plan(lambda *a,**k:[])

    def test_missing_visual_confidence_drops_physical_suggestion(self):
        self.rt.observations[0]['action_events'][0].pop('confidence')
        def composed(brain,events,*args,**kwargs):
            e=next(e for e in events if e['kind']=='foley')
            return [dict(event_id=e['id'],target=1.,duration=2.,type='foley',role='travel',intent='water splashing',level_db=-15.)]
        self.assertEqual(self.plan(composed)['sfx_events'],[])

    def test_scene_factory_and_weight_digest_cache_namespace(self):
        from types import SimpleNamespace
        from hinglish_sound.scenes import inspect
        response=dict(setting='pool',mood='joyful',action='water flows',ambience='water flow',confidence=.9)
        posts=[]
        class Session:
            def post(self,*a,**k):
                posts.append(k['json'])
                return SimpleNamespace(raise_for_status=lambda:None,json=lambda:{'message':{'content':json.dumps(response)}})
        judge=SimpleNamespace(model='fixture:vision',url='http://fixture.invalid',session=Session(),close=lambda:None)
        seq=SimpleNamespace(frames=180,fps=30)
        with patch('hinglish_sound.scenes.frame_at',return_value=object()),patch('hinglish_visuals.evaluator._for_model',side_effect=lambda x:x),patch('hinglish_visuals.evaluator._png64',return_value='synthetic-no-image'):
            for namespace in ('a'*64,'a'*64,'b'*64):
                rows=inspect(self.root,seq,self.root,[],lambda *a:None,judge_factory=lambda root:judge,cache_namespace=namespace,creator_context={'full':'exact profile'})
                self.assertEqual(rows[0]['setting'],'pool')
        self.assertEqual(len(posts),2)
        self.assertEqual(json.loads(json.loads(posts[0]['messages'][1]['content'])['creator_context_json']),{'full':'exact profile'})

    def test_instance_transport_allows_exact_embedding_and_chat_models_only(self):
        from types import SimpleNamespace
        calls=[]
        def post(url,**kwargs):
            calls.append((url,kwargs));return SimpleNamespace(status_code=200,json=lambda:{'done':True})
        owner=SimpleNamespace(session=SimpleNamespace(post=post))
        journal=Journal(self.root/'audit')
        _transport(owner,journal,'fixture:planning',self.root,embedding_model='fixture:embedding')
        owner.session.post('http://127.0.0.1:11434/api/embed',json={'model':'fixture:embedding','input':['query']})
        owner.session.post('http://127.0.0.1:11434/api/chat',json={'model':'fixture:planning'})
        with self.assertRaisesRegex(ValueError,'model changed'):
            owner.session.post('http://127.0.0.1:11434/api/embed',json={'model':'other'})
        with self.assertRaisesRegex(ValueError,'endpoint'):
            owner.session.post('https://example.test/api/chat',json={'model':'fixture:planning'})
        self.assertEqual(len(calls),2)

    def test_brain_adapter_preserves_profile_as_exact_json_and_records_cache_lineage(self):
        from types import SimpleNamespace
        class Brain:
            model='fixture:planning';embed_model='fixture:embedding'
            def __init__(self,path):self.cache=path;self.cache.mkdir()
            def ask(self,system,data,schema,**options):
                self.data=data
                file=self.cache/'reply.json'
                if file.exists():return json.loads(file.read_text())
                file.write_text('{"answer":42}')
                return {'answer':42}
        brain=Brain(self.root/'cache');journal=Journal(self.root/'audit')
        profile={'profile':'general','reference_study':'preserve even optional-looking profile keys'}
        proxy=_BrainReceipt(brain,journal,profile)
        proxy.ask('system',{},{});proxy.ask('system',{}, {})
        self.assertEqual(json.loads(brain.data['creator_context_json']),profile)
        receipts='\n'.join(p.read_text() for p in journal.folder.glob('*.json'))
        self.assertIn('cache.read',receipts)


if __name__ == '__main__': unittest.main()
