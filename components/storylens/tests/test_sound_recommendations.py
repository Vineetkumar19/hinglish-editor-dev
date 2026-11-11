"""Independent recommendations: no full soundtrack, model, render or host required."""
import copy
import json
import math
from pathlib import Path
import struct
import tempfile
import unittest
import wave


def tone(path, frequency, seconds=3.):
    path.parent.mkdir(parents=True,exist_ok=True)
    with wave.open(str(path),'wb') as out:
        out.setparams((1,2,8000,0,'NONE','not compressed'))
        out.writeframes(b''.join(struct.pack('<h',int(4000*math.sin(2*math.pi*frequency*n/8000))) for n in range(round(seconds*8000))))
    return path


class RecommendationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        from hinglish_sound.library import Asset
        self.assets=[]
        for i,(kind,category,name) in enumerate([('music','upbeat','Warm instrumental'),('music','upbeat','Playful instrumental'),('sfx','foley','Pool water lapping'),('sfx','foley','Horse galloping')]):
            p=tone(self.root/'library'/kind/(str(i)+'.wav'),220+100*i)
            self.assets.append(Asset(str(p),kind,category,name,name,3.,-20.,.1))
        Path(self.assets[0].path+'.json').write_text(json.dumps({'name':'Warm instrumental','source_url':'https://example.invalid/source','license':'Fixture only','author':'Test creator'}))
        self.request={'timeline':{'id':'sequence-42','duration':12.,'fps':'30'},'script':'Exact words 123',
            'creator_context':{'brief':'Keep ALL creator guidance','references':[{'text':'Long saved instructions'}]},
            'library_revision':'fixture-v1',
            'music_sections':[{'id':'opening','start':0.,'end':2.,'mood':'upbeat','intent':'playful instrumental',
                'role':'bed','level_db':-16.,'evidence':{'kind':'script','precision':'phrase','confidence':.8,'description':'Playful opening'}}],
            'sfx_events':[{'id':'water','start':3.,'end':5.,'sound_type':'foley','intent':'pool water lapping',
                'role':'detail','level_db':-14.,'evidence':{'kind':'vision','precision':'visual_interval','confidence':.95,'description':'Visible moving pool water'}}]}

    def indices(self, music=None, sfx=None, facts=None):
        from hinglish_sound.recommendations import CachedRankingIndex
        return (CachedRankingIndex(self.assets,{'playful instrumental':music if music is not None else [(self.assets[0].path,.9),(self.assets[1].path,.8)]},facts=facts),
                CachedRankingIndex(self.assets,{'pool water lapping':sfx if sfx is not None else [(self.assets[3].path,.95),(self.assets[2].path,.8)]}))

    def build(self, **kwargs):
        from hinglish_sound.recommendations import recommend
        return recommend(self.root,self.request,*self.indices(),**kwargs)

    def test_both_ranked_music_alternatives_and_relevant_sfx_are_concrete(self):
        result=self.build();self.assertEqual(result['schema'],'storylens.sound-recommendations');self.assertEqual(result['version'],1)
        music,sfx=result['groups'];self.assertEqual([c['kind'] for c in music['candidates']],['music','music'])
        self.assertEqual([c['rank'] for c in music['candidates']],[1,2]);self.assertEqual(len(sfx['candidates']),1)
        self.assertEqual(sfx['candidates'][0]['name'],'Pool water lapping')
        c=music['candidates'][0];self.assertEqual(c['timeline'],{'start':0.,'end':2.})
        self.assertEqual(c['source']['in'],0.);self.assertEqual(c['source']['out'],2.)
        self.assertEqual(c['source']['available_end'],3.);self.assertTrue(Path(c['source']['path']).is_file())
        self.assertTrue(c['source']['sha256']);self.assertEqual(c['credits']['license'],'Fixture only')
        self.assertEqual(result['creator_context'],self.request['creator_context'])

    def test_rank_order_can_change_without_changing_candidate_identity(self):
        from hinglish_sound.recommendations import recommend
        a=self.build();m,s=self.indices(music=[(self.assets[1].path,.95),(self.assets[0].path,.8)])
        b=recommend(self.root,self.request,m,s)
        ids=lambda x:{c['source']['sha256']:c['id'] for c in x['groups'][0]['candidates']}
        self.assertEqual(ids(a),ids(b));self.assertNotEqual(a['groups'][0]['candidates'][0]['id'],b['groups'][0]['candidates'][0]['id'])

    def test_cached_excerpt_offset_and_partial_music_are_explicit(self):
        self.request['music_sections'][0]['end']=5.
        result=self.build(passage_selector=lambda asset,slot:{'source_in':1.,'basis':'cached passage'})
        c=result['groups'][0]['candidates'][0]
        self.assertEqual(c['source']['in'],1.);self.assertEqual(c['source']['out'],3.)
        self.assertEqual(c['timeline']['end'],2.);self.assertEqual(c['coverage'],'partial')
        self.assertFalse(c['loop']);self.assertEqual(c['source']['selection_basis'],'cached passage')

    def test_explicit_minus_one_rejection_never_becomes_a_choice(self):
        self.request['music_sections'][0]['decision']=-1
        r=self.build();g=r['groups'][0];self.assertEqual(g['status'],'rejected');self.assertEqual(g['decision'],-1);self.assertEqual(g['candidates'],[])

    def test_no_match_is_explicit_and_instrumental_guard_is_not_bypassed(self):
        from hinglish_sound.recommendations import recommend
        m,s=self.indices(facts={a.path:{'vocals':True} for a in self.assets[:2]})
        r=recommend(self.root,self.request,m,s)
        self.assertEqual(r['groups'][0]['status'],'no_match');self.assertEqual(r['groups'][0]['candidates'],[])

    def test_missing_cached_ranking_never_calls_models_or_substitutes(self):
        self.request['sfx_events'][0]['intent']='unavailable exact query'
        r=self.build();self.assertEqual(r['groups'][1]['status'],'no_match')
        self.assertEqual(r['groups'][1]['reason_code'],'ranking_cache_missing')

    def test_original_stems_bans_and_source_bounds_are_enforced(self):
        from hinglish_sound.recommendations import recommend
        from dataclasses import replace
        source=tone(self.root/'library/music/dialogue.wav',880)
        self.assets.append(replace(self.assets[0],path=str(source),name='Dialogue'))
        m,s=self.indices(music=[(str(source),1.),(self.assets[0].path,.9),(self.assets[1].path,.8)])
        r=recommend(self.root,self.request,m,s,banned_paths=[self.assets[0].path])
        self.assertEqual([c['source']['path'] for c in r['groups'][0]['candidates']],[str(Path(self.assets[1].path).resolve())])
        self.request['sfx_events'][0]['end']=8.
        self.assertEqual(self.build()['groups'][1]['status'],'no_match')

    def test_invalid_times_nonfinite_confidence_and_duplicate_ids_are_rejected(self):
        for field,value in [('start',True),('end',13.),('level_db',float('nan'))]:
            with self.subTest(field=field):
                previous=self.request['sfx_events'][0][field];self.request['sfx_events'][0][field]=value
                with self.assertRaises(ValueError):self.build()
                self.request['sfx_events'][0][field]=previous
        self.request['music_sections'].append(copy.deepcopy(self.request['music_sections'][0]))
        with self.assertRaisesRegex(ValueError,'unique'):self.build()

    def test_speech_alone_cannot_create_literal_water_foley(self):
        self.request['sfx_events'][0]['evidence']['kind']='script'
        r=self.build();self.assertEqual(r['groups'][1]['status'],'no_match')
        self.assertEqual(r['groups'][1]['reason_code'],'unsupported_source_evidence')

    def test_cancellation_keeps_completed_groups_and_resume_is_cache_only(self):
        from hinglish_sound.recommendation_runtime import CancellationToken,CheckpointStore
        token=CancellationToken();store=CheckpointStore(self.root/'checkpoint')
        r=self.build(token=token,checkpoint=store,on_group=lambda g:token.cancel('owner stop'))
        self.assertEqual(r['status'],'cancelled');self.assertEqual(len(r['groups']),1)
        resumed=self.build(checkpoint=store);self.assertEqual(resumed['status'],'ready');self.assertEqual(len(resumed['groups']),2)
        self.assertTrue(any(x.get('cache')=='hit' and x['name']=='checkpoint.group' for x in resumed['telemetry']))
        self.request['script']='Different script'
        with self.assertRaisesRegex(ValueError,'different'):self.build(checkpoint=store)

    def test_changed_source_cannot_be_reused_from_checkpoint(self):
        from hinglish_sound.recommendation_runtime import CheckpointStore
        store=CheckpointStore(self.root/'checkpoint');self.build(checkpoint=store)
        tone(Path(self.assets[0].path),999)
        with self.assertRaisesRegex(ValueError,'changed'):self.build(checkpoint=store)

    def test_telemetry_uses_injected_monotonic_clock_and_records_failure(self):
        from hinglish_sound.recommendation_runtime import Telemetry
        ticks=iter([4.,5.5,6.,8.]);sink=[];audit=Telemetry(clock=lambda:next(ticks),sink=sink.append)
        with audit.stage('rank',kind='call',cache='hit',retry=0):pass
        with self.assertRaises(RuntimeError):
            with audit.stage('probe'):raise RuntimeError('not secret diagnostic')
        self.assertEqual(audit.receipts[0]['seconds'],1.5);self.assertEqual(audit.receipts[0]['cache'],'hit')
        self.assertEqual(audit.receipts[1]['status'],'failed');self.assertEqual(sink,audit.receipts)

    def test_saved_owner_bans_are_loaded_without_changing_taste_memory(self):
        memory=self.root/'cache/learning/sound-preferences.json';memory.parent.mkdir(parents=True)
        memory.write_text(json.dumps({'files':{self.assets[0].path:{'kept':0,'removed':2}},'examples':[]}))
        original=memory.read_bytes();r=self.build()
        self.assertEqual([c['name'] for c in r['groups'][0]['candidates']],['Playful instrumental'])
        self.assertEqual(memory.read_bytes(),original)

    def test_processing_is_typed_and_not_an_executable_payload(self):
        self.request['sfx_events'][0]['processing']={'command':'run a shell'}
        with self.assertRaisesRegex(ValueError,'processing'):self.build()

    def test_changed_credit_changes_candidate_identity(self):
        a=self.build()['groups'][0]['candidates'][0]
        sidecar=Path(self.assets[0].path+'.json');meta=json.loads(sidecar.read_text());meta['license']='Different fixture licence';sidecar.write_text(json.dumps(meta))
        b=self.build()['groups'][0]['candidates'][0]
        self.assertNotEqual(a['id'],b['id'])

    def test_corrupt_checkpoint_cannot_offer_outside_library_files(self):
        from hinglish_sound.recommendation_runtime import CheckpointStore
        store=CheckpointStore(self.root/'checkpoint');self.build(checkpoint=store)
        outside=tone(self.root/'outside.wav',999)
        outside.write_bytes(Path(self.assets[0].path).read_bytes())
        Path(str(outside)+'.json').write_bytes(Path(self.assets[0].path+'.json').read_bytes())
        data=json.loads(store.path.read_text());data['groups'][0]['candidates'][0]['source']['path']=str(outside)
        store.path.write_text(json.dumps(data))
        with self.assertRaisesRegex(ValueError,'library|changed|checkpoint'):self.build(checkpoint=store)

    def test_only_cached_excerpt_not_full_music_track_is_proposed(self):
        r=self.build(passage_selector=lambda a,s:{'source_in':1.,'source_out':2.5,'basis':'cached musical phrase'})
        c=r['groups'][0]['candidates'][0]
        self.assertEqual(c['source']['out']-c['source']['in'],1.5)
        self.assertEqual(c['audition']['path'],c['source']['path']);self.assertFalse(c['audition']['rendered'])

    def test_uncached_ranker_is_not_called_without_explicit_release(self):
        from hinglish_sound.recommendations import recommend
        class UnsafeIndex:
            assets=[]
            def search(self,*a,**kw):raise AssertionError('Must not start a model implicitly')
        with self.assertRaisesRegex(ValueError,'prepared|cached'):
            recommend(self.root,self.request,UnsafeIndex(),UnsafeIndex())

    def test_typed_timeline_role_and_rejection_metadata_are_checked(self):
        cases=[('timeline','fps','0'),('timeline','id',None),('sfx','role',[]),
               ('sfx','rejected_source_ids','not-a-list'),('evidence','precision',False)]
        for target,key,value in cases:
            with self.subTest(target=target,key=key):
                data=copy.deepcopy(self.request)
                obj=data['timeline'] if target=='timeline' else data['sfx_events'][0]['evidence'] if target=='evidence' else data['sfx_events'][0]
                obj[key]=value
                from hinglish_sound.recommendations import recommend
                with self.assertRaises(ValueError):recommend(self.root,data,*self.indices())

    def test_suite_can_recheck_immutable_candidate_before_import(self):
        from hinglish_sound.recommendations import verify_candidate_source
        c=self.build()['groups'][0]['candidates'][0]
        receipt=verify_candidate_source(self.root,c)
        self.assertEqual(receipt['sha256'],c['source']['sha256'])
        tone(Path(c['source']['path']),999)
        with self.assertRaisesRegex(ValueError,'changed'):verify_candidate_source(self.root,c)


if __name__=='__main__':unittest.main()
