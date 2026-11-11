"""Synthetic metadata/file fixtures only: no model, network, render or host calls."""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from hinglish_broll.candidate_manifest import build_manifest, checked_window_receipt, digest, CandidateContractError
from hinglish_broll.candidate_selection import choose, selection_state, save_selections, load_selections, selected_candidates


class CandidateManifestTests(unittest.TestCase):
    def setUp(self):
        temp_root=Path(__file__).resolve().parents[1]/'tmp/broll-manifest-unit'
        temp_root.mkdir(parents=True,exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=temp_root)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.metadata = {}
        self.project_file = self.root / 'broll-project.json'
        self.project = {'version': 3, 'media_policy': 'videos_only', 'collecting': False,
            'timeline': {'name': 'Synthetic speech', 'fps': '30/1', 'duration': 12,
                         'width': 1080, 'height': 1920},
            'slots': [{'index': 4, 'start': 2.14, 'end': 3.1, 'text': 'a small room',
                       'visual': 'room interior', 'meaning': 'A residential room',
                       'collection_complete': True, 'options': [], 'checks': []}]}
        for i in range(6):
            raw = self.root / f'raw-{i}.mp4'; raw.write_bytes(f'SYNTHETIC RAW VIDEO {i}'.encode())
            preview = self.root / f'preview-{i}.mp4'; preview.write_bytes(f'SYNTHETIC PREPARED VIDEO {i}'.encode())
            self.metadata[str(raw)] = {'duration': 20., 'fps': '30/1', 'time_base': '1/90000', 'width': 1920, 'height': 1080}
            self.metadata[str(preview)] = {'duration': 8., 'fps': '30/1', 'time_base': '1/90000', 'width': 1080, 'height': 1920}
            check = {'id': f'stock:{i}', 'passed': True, 'related': True,
                'context_compatible': True, 'real_clear_footage': True,
                'no_intrusive_text': True, 'identity_compatible': True,
                'seen': 'A real residential room', 'judge': 'synthetic-local-checker',
                'frame_checks': [dict(subject_visible=True, real_clear_footage=True,
                    no_dominant_presenter=True, no_intrusive_overlay=True) for _ in range(3)]}
            option = {'id': f'stock:{i}', 'kind': 'video', 'source': 'synthetic-stock',
                'author': 'Fixture creator', 'license': 'Synthetic test fixture',
                'page_url': 'https://example.org/source/'+str(i),
                'path': str(raw), 'clip': preview.name, 'original_offset': 4.,
                'offset': 7., 'source_in': 3., 'source_duration': 8.,
                'checked_window': {'schema':'storylens.broll.checked-window','version':1,
                    'candidate_id':check['id'],'verdict_sha256':digest(check),
                    'source_sha256': hashlib.sha256(raw.read_bytes()).hexdigest(),
                    'prepared_sha256': hashlib.sha256(preview.read_bytes()).hexdigest(),
                    'start': 7., 'end': 7.+29/30,
                    'crop': {'space': 'upright_source_pixels', 'x': 656, 'y': 0, 'width': 608, 'height': 1080}}}
            self.project['slots'][0]['options'].append(option)
            self.project['slots'][0]['checks'].append(check)
        # This is a machine suggestion, never evidence of an owner's decision.
        self.project['slots'][0]['chosen'] = self.project['slots'][0]['options'][0]
        self.write()

    def write(self):
        self.project_file.write_text(json.dumps(self.project), encoding='utf-8')

    def build(self, form='short', previous=None, **kwargs):
        self.write()
        return build_manifest(self.project_file, content_format=form, bank_id='fixture-bank',
                              media_reader=lambda p: self.metadata[str(p)], previous=previous, **kwargs)

    def test_complete_manifest_has_exact_times_original_identity_and_no_auto_selection(self):
        before=self.project_file.read_bytes(); m=self.build(); s=m['slots'][0]; c=s['candidates'][0]
        self.assertEqual(m['schema'], 'storylens.broll.video-candidates'); self.assertEqual(m['version'], 1)
        self.assertEqual(m['collection_state'], 'complete'); self.assertEqual(s['choice']['state'], 'unselected')
        self.assertEqual(s['keyword_id'],'fixture-bank:keyword:4')
        self.assertEqual(c['keyword_id'],s['keyword_id']);self.assertEqual(c['slot_id'],s['id'])
        self.assertEqual(selected_candidates(m), [])
        self.assertEqual(s['anchor']['frames'], {'start': 64, 'end': 93})
        self.assertEqual(s['anchor']['fps'], '30/1')
        self.assertEqual(c['original']['sha256'], hashlib.sha256(Path(c['original']['path']).read_bytes()).hexdigest())
        self.assertEqual(c['mapping']['original_active'], {'start': 7., 'end': 7.+29/30})
        self.assertEqual(c['mapping']['prepared_active'], {'start': 3., 'end': 3.+29/30})
        self.assertEqual(c['mapping']['prepared_origin_in_original'], 4.)
        self.assertEqual(c['handles']['original']['before'], 7.)
        self.assertEqual(c['handles']['prepared']['before'], 3.)
        self.assertEqual(c['check']['state'], 'bound')
        self.assertTrue(c['selectable']); self.assertEqual(self.project_file.read_bytes(), before)

    def test_caps_are_two_long_and_five_short_without_claiming_missing_choices(self):
        for form, count in [('long', 2), ('short', 5)]:
            m=self.build(form); s=m['slots'][0]
            self.assertEqual(len(s['candidates']), count); self.assertEqual(s['available_valid_candidates'], 6)
            self.assertEqual(s['omitted_by_cap'], 6-count)
        self.project['slots'][0]['options']=self.project['slots'][0]['options'][:1]
        self.assertEqual(len(self.build('long')['slots'][0]['candidates']), 1)

    def test_explicit_owner_choice_and_no_broll_survive_json_retry_and_reordering(self):
        m=self.build(); s=m['slots'][0]; selected=s['candidates'][4]['id']
        decided=choose(m,s['id'],'selected',selected)
        self.assertEqual(m['slots'][0]['choice']['state'],'unselected')
        previous=json.loads(json.dumps(selection_state(decided)))
        self.project['slots'][0]['options'].reverse()
        restored=self.build('long', previous)
        self.assertEqual(restored['slots'][0]['choice']['candidate_id'], selected)
        self.assertEqual(restored['slots'][0]['choice']['status'], 'ready')
        self.assertIn(selected,[c['id'] for c in restored['slots'][0]['candidates']])
        self.assertEqual(len(restored['slots'][0]['candidates']),2)
        self.assertEqual(len(selected_candidates(restored)),1)
        no=choose(restored,s['id'],'no_broll')
        self.assertEqual(self.build(previous=selection_state(no))['slots'][0]['choice']['state'],'no_broll')
        self.assertEqual(selected_candidates(no),[])

    def test_changed_or_missing_selected_media_keeps_decision_but_blocks_insertion(self):
        m=self.build(); s=m['slots'][0]; c=s['candidates'][0]
        previous=selection_state(choose(m,s['id'],'selected',c['id']))
        Path(c['original']['path']).write_bytes(b'CHANGED SOURCE')
        changed=self.build(previous=previous)
        choice=changed['slots'][0]['choice']
        self.assertEqual(choice['candidate_id'],c['id']); self.assertEqual(choice['status'],'blocked')
        with self.assertRaises(CandidateContractError): selected_candidates(changed)

    def test_nonvideo_missing_corrupt_and_invalid_trims_are_rejected_individually(self):
        cases={
            'nonvideo': lambda o: o.update(kind='image'),
            'missing': lambda o: o.update(path=str(self.root/'missing.mp4')),
            'corrupt': lambda o: self.metadata.__setitem__(o['path'], ValueError('invalid container')),
            'bounds': lambda o: o.update(source_in=7.8),
            'negative_mapping': lambda o: o.update(original_offset=-1),
        }
        original=copy.deepcopy(self.project)
        for label, mutate in cases.items():
            with self.subTest(label=label):
                self.project=copy.deepcopy(original); mutate(self.project['slots'][0]['options'][0])
                def reader(path):
                    value=self.metadata[str(path)]
                    if isinstance(value,Exception): raise value
                    return value
                self.write(); m=build_manifest(self.project_file,content_format='short',bank_id='fixture-bank',media_reader=reader)
                self.assertEqual(len(m['slots'][0]['rejected_candidates']),1)
                issue=m['slots'][0]['rejected_candidates'][0]['issue']
                self.assertTrue(issue['code'].startswith('broll_')); self.assertIn('message',issue); self.assertIn('details',issue)
                self.metadata[str(self.root/'raw-0.mp4')]={'duration':20.,'fps':'30/1','time_base':'1/90000','width':1920,'height':1080}

    def test_bad_frame_watermark_or_latest_rejection_cannot_be_selected(self):
        for field in ('subject_visible','real_clear_footage','no_dominant_presenter','no_intrusive_overlay'):
            project=copy.deepcopy(self.project)
            self.project['slots'][0]['checks'][0]['frame_checks'][1][field]=False
            m=self.build(); self.assertEqual(len(m['slots'][0]['rejected_candidates']),1)
            self.project=project
        self.project['slots'][0]['checks'].append({'id':'stock:0','passed':False,'reason':'Later check failed'})
        self.assertEqual(len(self.build()['slots'][0]['rejected_candidates']),1)

    def test_unbound_legacy_window_is_visible_but_not_silently_verified(self):
        self.project['slots'][0]['options']=self.project['slots'][0]['options'][:1]
        self.project['slots'][0]['options'][0].pop('checked_window')
        c=self.build()['slots'][0]['candidates'][0]
        self.assertEqual(c['check']['state'],'unbound'); self.assertFalse(c['selectable'])
        m=self.build()
        with self.assertRaises(CandidateContractError):choose(m,m['slots'][0]['id'],'selected',c['id'])

    def test_incomplete_and_no_match_slots_are_preserved_including_unstarted_plan(self):
        self.project['collecting']=True; self.project['slots'][0]['collection_complete']=False
        plan=[{'index':4,'start':2.14,'end':3.1,'text':'a small room','visual':'room interior'},
              {'index':9,'start':8.,'end':9.,'text':'sleeping','visual':'person asleep'}]
        m=self.build(planned_slots=plan)
        self.assertEqual(m['collection_state'],'saved_incomplete'); self.assertEqual(len(m['slots']),2)
        self.assertEqual(m['slots'][1]['collection_state'],'pending')
        self.project['collecting']=False; self.project['slots'][0]['collection_complete']=True
        self.project['slots'][0]['options']=[]
        self.assertEqual(self.build()['slots'][0]['collection_state'],'no_match')

    def test_unknown_format_bad_anchor_or_wrong_bank_state_is_not_guessed(self):
        with self.assertRaises(CandidateContractError):self.build('square')
        self.project['slots'][0]['end']=99
        with self.assertRaises(CandidateContractError):self.build()
        self.project['slots'][0]['end']=3.1
        with self.assertRaises(CandidateContractError):self.build(previous={'schema':'storylens.broll.owner-selections','version':1,'bank_id':'other','choices':{}})

    def test_selection_sidecar_round_trip_cannot_overwrite_saved_project(self):
        m=self.build(); s=m['slots'][0]; m=choose(m,s['id'],'no_broll')
        file=self.root/'owner-selections.json';save_selections(file,m)
        self.assertEqual(load_selections(file),selection_state(m))
        before=self.project_file.read_bytes()
        with self.assertRaises(CandidateContractError):save_selections(self.project_file,m)
        self.assertEqual(self.project_file.read_bytes(),before)

    def test_exact_fractional_timebase_and_different_original_rate_are_preserved(self):
        self.project['timeline']['fps']='30000/1001'
        for info in self.metadata.values():
            info['fps']='30000/1001' if info['height']==1920 else '24/1'
        m=self.build(); c=m['slots'][0]['candidates'][0]
        self.assertEqual(m['timeline']['fps'],'30000/1001')
        self.assertEqual(c['original']['fps'],'24/1')
        self.assertAlmostEqual(c['mapping']['prepared_active']['end'],3+29*1001/30000)

    def test_changed_anchor_blocks_saved_no_broll_without_losing_it(self):
        m=self.build(); s=m['slots'][0]; previous=selection_state(choose(m,s['id'],'no_broll'))
        self.project['slots'][0]['start']=2.2
        m=self.build(previous=previous)
        self.assertEqual(m['slots'][0]['choice']['state'],'no_broll')
        self.assertEqual(m['slots'][0]['choice']['status'],'blocked')

    def test_removed_slot_keeps_its_owner_decision_separately(self):
        m=self.build(); s=m['slots'][0]; previous=selection_state(choose(m,s['id'],'no_broll'))
        self.project['slots']=[];m=self.build(previous=previous)
        self.assertEqual(m['orphaned_choices'][s['id']]['state'],'no_broll')
        self.assertEqual(selection_state(m)['choices'][s['id']]['status'],'blocked')

    def test_duplicate_candidate_ids_do_not_acquire_order_based_identities(self):
        self.project['slots'][0]['options'][1]['id']='stock:0'
        m=self.build()
        self.assertEqual(len(m['slots'][0]['rejected_candidates']),2)
        self.assertTrue(all(c['candidate_id']!='stock:0' for c in m['slots'][0]['candidates']))

    def test_crop_window_prepared_identity_and_metadata_fail_closed(self):
        original=copy.deepcopy(self.project)
        cases={
            'crop':lambda o:o['checked_window']['crop'].update(x=1900),
            'window':lambda o:o['checked_window'].update(end=19),
            'prepared_hash':lambda o:o['checked_window'].update(prepared_sha256='0'*64),
            'path_escape':lambda o:o.update(clip='../outside.mp4'),
        }
        for name,mutate in cases.items():
            with self.subTest(name=name):
                self.project=copy.deepcopy(original);mutate(self.project['slots'][0]['options'][0])
                self.assertEqual(len(self.build()['slots'][0]['rejected_candidates']),1)
        self.project=copy.deepcopy(original)
        self.metadata[str(self.root/'preview-0.mp4')]['width']=720
        self.assertEqual(len(self.build()['slots'][0]['rejected_candidates']),1)

    def test_legacy_mapping_is_explicitly_labelled_and_requires_real_check_bindings(self):
        self.project['slots'][0]['options'][0].pop('original_offset')
        c=self.build()['slots'][0]['candidates'][0]
        self.assertEqual(c['mapping']['prepared_origin_in_original'],4.)
        self.assertEqual(c['mapping']['basis'],'legacy_offset_quantized_to_sequence_rate')
        self.project['slots'][0]['options']=self.project['slots'][0]['options'][:1]
        self.project['slots'][0]['options'][0]['checked_window'].pop('prepared_sha256')
        c=self.build()['slots'][0]['candidates'][0]
        self.assertEqual(c['check']['state'],'unbound');self.assertFalse(c['selectable'])

    def test_handoff_rehashes_both_files_and_never_changes_saved_choice(self):
        m=self.build();s=m['slots'][0];c=s['candidates'][0];m=choose(m,s['id'],'selected',c['id'])
        before=selection_state(m);Path(c['prepared']['path']).write_bytes(b'CHANGED PREVIEW')
        with self.assertRaises(CandidateContractError):selected_candidates(m)
        self.assertEqual(selection_state(m),before)

    def test_source_links_and_shared_error_details_do_not_expose_tokens(self):
        option=self.project['slots'][0]['options'][0]
        option['page_url']='https://user:password@example.org/video?token=secret&clip=123'
        c=self.build()['slots'][0]['candidates'][0]
        self.assertEqual(c['source']['page_url'],'https://example.org/video?clip=123')
        issue=CandidateContractError('broll_fixture','Choose another video.','https://example.org/?api_key=secret').as_issue()
        self.assertNotIn('secret',issue['details']);self.assertIn('Choose another video',issue['message'])

    def test_metadata_injection_never_calls_network_subprocess_models_or_renderer(self):
        from unittest.mock import patch
        with patch('socket.socket',side_effect=AssertionError('Network forbidden')), \
             patch('subprocess.Popen',side_effect=AssertionError('Process launch forbidden')), \
             patch('hinglish_broll.candidate_manifest.local_video_metadata',side_effect=AssertionError('Fixture reader required')):
            m=self.build();self.assertEqual(len(m['slots'][0]['candidates']),5)

    def test_default_reader_rejects_synthetic_nonvideo_bytes(self):
        self.write();m=build_manifest(self.project_file,content_format='short',bank_id='fixture-bank')
        self.assertEqual(m['slots'][0]['candidates'],[])
        self.assertEqual(len(m['slots'][0]['rejected_candidates']),6)
        self.assertTrue(all(r['issue']['code']=='broll_media_corrupt' for r in m['slots'][0]['rejected_candidates']))

    def test_reopened_receipt_cannot_ignore_later_rejection_or_changed_bank_anchor(self):
        m=self.build();s=m['slots'][0];c=s['candidates'][0];selected=choose(m,s['id'],'selected',c['id'])
        self.project['slots'][0]['checks'].append({'id':'stock:0','passed':False});self.write()
        with self.assertRaises(CandidateContractError): selected_candidates(selected)
        self.project['slots'][0]['checks'].pop();self.project['slots'][0]['start']=2.2;self.write()
        with self.assertRaises(CandidateContractError): selected_candidates(selected)

    def test_serialized_candidate_cannot_be_changed_into_an_image(self):
        m=self.build();s=m['slots'][0];c=s['candidates'][0];m=choose(m,s['id'],'selected',c['id'])
        m['slots'][0]['candidates'][0]['kind']='image'
        with self.assertRaises(CandidateContractError):selected_candidates(m)

    def test_ready_candidates_are_visible_before_unbound_legacy_previews(self):
        self.project['slots'][0]['options'][0].pop('checked_window')
        m=self.build('long')
        self.assertTrue(all(c['selectable'] for c in m['slots'][0]['candidates']))
        self.assertEqual(m['slots'][0]['available_selectable_candidates'],5)

    def test_failed_sidecar_write_preserves_old_bytes_and_returns_a_useful_error(self):
        from unittest.mock import patch
        m=self.build();file=self.root/'choices.json';save_selections(file,m);before=file.read_bytes()
        with patch('hinglish_broll.recovery.write_json',side_effect=PermissionError('locked')):
            with self.assertRaises(CandidateContractError) as caught:save_selections(file,m)
        self.assertEqual(caught.exception.code,'broll_choice_save_failed')
        self.assertIn('writable',caught.exception.as_issue()['message']);self.assertEqual(file.read_bytes(),before)

    def snapshots(self):
        short=self.build()
        slot=short['slots'][0]
        previous=selection_state(choose(short,slot['id'],'selected',slot['candidates'][4]['id']))
        long=self.build('long',previous)
        long=choose(long,slot['id'],'selected',slot['candidates'][4]['id'])
        self.project['collecting']=True;self.project['slots'][0]['collection_complete']=False
        self.project['slots'][0]['options']=self.project['slots'][0]['options'][:1]
        self.project['slots'].append({'index':7,'start':5.,'end':6.,'text':'no match',
                                     'visual':'person asleep','options':[],'collection_complete':True})
        plan=[{'index':9,'start':8.,'end':9.,'text':'not started','visual':'closed shop'}]
        incomplete=self.build(planned_slots=plan)
        def normalized(value):
            if isinstance(value,str): return value.replace(str(self.root),'<FIXTURE_ROOT>').replace('\\','/')
            if isinstance(value,list): return [normalized(v) for v in value]
            if isinstance(value,dict): return {k:normalized(v) for k,v in value.items()}
            return value
        return {name:{'fixture_notice':'Synthetic bytes and injected metadata; not playable media or live/native evidence.',
                      'manifest':normalized(m)} for name,m in
                [('short-unselected',short),('long-selected-pinned',long),('incomplete-and-no-match',incomplete)]}

    def test_golden_manifests_match_the_cpu_fixture_contract(self):
        folder=Path(__file__).parent/'fixtures/broll-candidates-v1'
        for name,actual in self.snapshots().items():
            self.assertEqual(json.loads((folder/(name+'.json')).read_text(encoding='utf-8')),actual,name)

    def test_owner_choice_is_idempotent_and_explicit_clear_does_not_select_anything(self):
        m=self.build();s=m['slots'][0];candidate=s['candidates'][0]['id']
        m=choose(m,s['id'],'selected',candidate);again=choose(m,s['id'],'selected',candidate)
        self.assertEqual(selection_state(again),selection_state(m))
        clear=choose(again,s['id'],'unselected')
        self.assertEqual(selected_candidates(clear),[])
        self.assertIsNone(clear['slots'][0]['choice']['candidate_id'])

    def test_missing_approved_file_reappearing_restores_same_decision_without_replacement(self):
        m=self.build();s=m['slots'][0];c=s['candidates'][0];previous=selection_state(choose(m,s['id'],'selected',c['id']))
        file=Path(c['prepared']['path']);data=file.read_bytes();file.unlink()
        blocked=self.build(previous=previous)
        self.assertEqual(blocked['slots'][0]['choice']['status'],'blocked')
        file.write_bytes(data);restored=self.build(previous=selection_state(blocked))
        self.assertEqual(restored['slots'][0]['choice']['candidate_id'],c['id'])
        self.assertEqual(restored['slots'][0]['choice']['status'],'ready')

    def test_invalid_numeric_metadata_and_unsupported_bank_version_are_not_guessed(self):
        original=copy.deepcopy(self.metadata)
        for field,value in [('duration',float('nan')),('fps','0/1'),('time_base','1/0'),('width',0)]:
            with self.subTest(field=field):
                self.metadata=copy.deepcopy(original);self.metadata[str(self.root/'raw-0.mp4')][field]=value
                self.assertEqual(len(self.build()['slots'][0]['rejected_candidates']),1)
        self.metadata=original;self.project['version']=99
        with self.assertRaises(CandidateContractError):self.build()

    def test_corrupt_owner_file_and_boolean_schema_version_are_not_accepted(self):
        m=self.build();state=selection_state(m);state['version']=True
        with self.assertRaises(CandidateContractError):self.build(previous=state)
        file=self.root/'bad-choice.json';file.write_text('{incomplete',encoding='utf-8')
        with self.assertRaises(CandidateContractError):load_selections(file)

    def test_file_mutation_during_metadata_inspection_is_rejected(self):
        self.write()
        def reader(path):
            if path.name=='raw-0.mp4':path.write_bytes(path.read_bytes()+b'CHANGED')
            return self.metadata[str(path)]
        m=build_manifest(self.project_file,content_format='short',bank_id='fixture-bank',media_reader=reader)
        self.assertEqual(m['slots'][0]['rejected_candidates'][0]['issue']['code'],'broll_media_changed')

    def test_malformed_anchor_ids_and_caps_return_contract_errors(self):
        self.project['slots'][0]['text']=None
        with self.assertRaises(CandidateContractError):self.build()
        self.project['slots'][0]['text']='a small room'
        self.project['slots'][0]['options'][0]['id']=None
        self.assertEqual(len(self.build()['slots'][0]['rejected_candidates']),1)
        m=self.build();m['per_keyword_cap']=True
        with self.assertRaises(CandidateContractError):selection_state(m)

    def test_saved_recovery_plan_retains_unstarted_slots_without_restarting_anything(self):
        folder=self.root/'run'/'001-source';folder.mkdir(parents=True)
        for option in self.project['slots'][0]['options']:
            old=self.root/option['clip'];new=folder/old.name;new.write_bytes(old.read_bytes())
            self.metadata[str(new)]=copy.deepcopy(self.metadata[str(old)])
        self.project['slots'][0]['index']=0;self.project['collecting']=True
        self.project_file=folder/'broll-project.json'
        plan={'plans':[{'folder':folder.name,'slots':[
            {'start':2.14,'end':3.1,'text':'a small room','moment':{'visual':'room interior'}},
            {'start':8.,'end':9.,'text':'sleeping','moment':{'visual':'person asleep'}}]}]}
        (folder.parent/'recovery.json').write_text(json.dumps(plan),encoding='utf-8')
        m=self.build()
        self.assertEqual([s['collection_state'] for s in m['slots']],['complete','pending'])
        self.assertEqual(m['collection_state'],'saved_incomplete')

    def test_producer_hook_binds_fresh_supplied_evidence_without_rendering_or_writing(self):
        option=self.project['slots'][0]['options'][0];verdict=self.project['slots'][0]['checks'][0]
        before=self.project_file.read_bytes()
        receipt=checked_window_receipt(option['path'],self.root/option['clip'],
            prepared_origin_in_original=4.,prepared_source_in=3.,active_duration=29/30,
            crop=option['checked_window']['crop'],verdict=verdict,
            media_reader=lambda p:self.metadata[str(p)])
        self.assertEqual(receipt,option['checked_window'])
        self.assertEqual(self.project_file.read_bytes(),before)
        verdict=copy.deepcopy(verdict);verdict['frame_checks'][0]['no_intrusive_overlay']=False
        with self.assertRaises(CandidateContractError):
            checked_window_receipt(option['path'],self.root/option['clip'],
                prepared_origin_in_original=4.,prepared_source_in=3.,active_duration=29/30,
                crop=option['checked_window']['crop'],verdict=verdict,
                media_reader=lambda p:self.metadata[str(p)])

    def test_window_receipt_cannot_be_reused_for_a_new_verdict_or_other_candidate(self):
        self.project['slots'][0]['options'][0]['checked_window']['verdict_sha256']='0'*64
        self.assertEqual(len(self.build()['slots'][0]['rejected_candidates']),1)

    def test_serialized_handoff_cannot_swap_another_candidates_window_reference(self):
        m=self.build();s=m['slots'][0];c=s['candidates'][0]
        m=choose(m,s['id'],'selected',c['id'])
        m['slots'][0]['candidates'][0]['check']['window_ref']=copy.deepcopy(s['candidates'][1]['check']['window_ref'])
        with self.assertRaises(CandidateContractError):selected_candidates(m)


if __name__=='__main__': unittest.main()
