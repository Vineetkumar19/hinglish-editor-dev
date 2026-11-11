"""Producer contract component tests: mocked model/I/O boundaries, no real render."""
import copy
from fractions import Fraction
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
import sys

from hinglish_broll import pipeline
from hinglish_broll.candidate_manifest import build_manifest, CandidateContractError
from hinglish_broll.candidate_selection import choose, save_selections, selected_candidates
from hinglish_broll.stock import Candidate
from tests import test_broll_candidate_manifest as fixtures


class ProducerManifestTests(unittest.TestCase):
    def setUp(self):
        self.fixture=fixtures.CandidateManifestTests();self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.folder=self.fixture.root;self.raw=self.folder/'raw-0.mp4'
        self.timeline=SimpleNamespace(width=1080,height=1920,fps=Fraction(30))
        self.slot={'index':0,'start':2.14,'end':3.1,'text':'a small room',
                   'visual':'room interior','meaning':'A residential room',
                   'review_options':True,'checks':[]}
        self.candidate=Candidate('pixabay','stock:0','Fixture room',20,1920,1080,
                                 path=str(self.raw),kind='video')
        self.good=copy.deepcopy(self.fixture.project['slots'][0]['checks'][0])
        self.checker=SimpleNamespace(check=Mock(side_effect=lambda *args:copy.deepcopy(self.good)),
                                     find_window=Mock(return_value=7.013))
        self.reader=lambda p:self.fixture.metadata[str(p)]
        def fake_make(source,offset,duration,width,height,fps,target,device):
            target.parent.mkdir(parents=True,exist_ok=True)
            target.write_bytes(b'SYNTHETIC PREPARED PRODUCER VIDEO')
            self.fixture.metadata[str(target)]={'duration':duration,'fps':str(fps),
                'time_base':'1/90000','width':width,'height':height}
        self.conform=Mock(side_effect=fake_make)

    def render(self,device='cpu'):
        with patch('hinglish_broll.internet.acquire',return_value=(self.raw,20.,7.013)), \
             patch('hinglish_broll.verify.readable_window',side_effect=lambda p,a,n,o,w,h:o), \
             patch('hinglish_broll.pipeline.valid_clip',side_effect=lambda f,r:(Path(f)/r).is_file()), \
             patch('hinglish_broll.pipeline.make_clip',self.conform), \
             patch('hinglish_broll.candidate_manifest.local_video_metadata',self.reader):
            return pipeline.render_choice(self.folder,self.folder,self.timeline,0,self.slot,self.candidate,
                                          device,checker=self.checker)

    def test_review_encode_does_not_compete_with_the_local_vision_model_for_vram(self):
        self.render('cuda')
        self.assertEqual(self.conform.call_args.args[-1],'cpu')
        self.assertEqual(self.checker.check.call_count,2)

    def test_ordinary_nonreview_encode_keeps_explicit_device(self):
        self.slot['review_options']=False
        self.render('cuda')
        self.assertEqual(self.conform.call_args.args[-1],'cuda')

    def save_produced_bank(self,clip):
        data=pipeline._review_option_data(self.folder,self.slot,self.candidate,clip,self.candidate.to_dict())
        project=copy.deepcopy(self.fixture.project)
        project['review_options']=True;project['options_per_moment']=5;project['profile']={'name':'short'}
        project['timeline']['xml_path']=str(self.folder/'source-timeline.xml')
        project['slots']=[{**copy.deepcopy(self.slot),'options':[data],'collection_complete':True,
                           'chosen':None,'clip':None}]
        self.fixture.project=project;self.fixture.write()
        return project

    def test_actual_source_and_prepared_checks_are_both_used_before_receipt(self):
        clip=self.render()
        self.assertEqual(self.checker.check.call_count,2)
        first,second=self.checker.check.call_args_list
        self.assertEqual(first.args[0],self.raw);self.assertEqual(first.args[1],7.)
        self.assertEqual(second.args[0],clip);self.assertEqual(second.args[1],3.)
        self.assertAlmostEqual(first.args[2],29/30);self.assertAlmostEqual(second.args[2],29/30)
        receipt=self.slot['checked_window']
        self.assertEqual(receipt['source_sha256'],hashlib.sha256(self.raw.read_bytes()).hexdigest())
        self.assertEqual(receipt['prepared_sha256'],hashlib.sha256(clip.read_bytes()).hexdigest())
        self.assertEqual(receipt['crop'],{'space':'upright_source_pixels','x':656,'y':0,'width':608,'height':1080})
        self.assertEqual([v['producer_stage'] for v in self.slot['checks']],['original','prepared'])

    def test_ordinary_producer_option_is_bound_and_owner_choice_stays_unselected(self):
        clip=self.render();project=self.save_produced_bank(clip)
        manifest=pipeline.finalize_candidate_bank(self.fixture.project_file,media_reader=self.reader)
        c=manifest['slots'][0]['candidates'][0]
        self.assertTrue(c['selectable']);self.assertEqual(c['check']['state'],'bound')
        self.assertEqual(manifest['slots'][0]['choice']['state'],'unselected')
        self.assertEqual(c['mapping']['prepared_origin_in_original'],4.)
        self.assertEqual(c['mapping']['prepared_active']['start'],3.)
        self.assertEqual(set(c['check']['producer_checks']),{'original','prepared'})
        self.assertTrue((self.folder/'BROLL_CANDIDATES.v1.json').is_file())
        self.assertIsNone(project['slots'][0]['chosen'])

    def test_failed_original_never_renders_or_creates_a_window_receipt(self):
        bad=copy.deepcopy(self.good);bad.update(passed=False,reason='Unrelated subject')
        self.checker.check.side_effect=lambda *args:bad
        with self.assertRaises(ValueError):self.render()
        self.conform.assert_not_called();self.assertNotIn('checked_window',self.slot)

    def test_failed_prepared_check_cannot_bless_a_passing_original(self):
        bad=copy.deepcopy(self.good);bad.update(passed=False,reason='Prepared crop lost the subject')
        self.checker.check.side_effect=[copy.deepcopy(self.good),bad]
        with self.assertRaises(ValueError):self.render()
        self.assertNotIn('checked_window',self.slot)

    def test_mutation_between_original_check_and_preparation_is_rejected(self):
        def check(*args):
            if args[0]==self.raw:self.raw.write_bytes(b'CHANGED DURING MODEL CHECK')
            return copy.deepcopy(self.good)
        self.checker.check.side_effect=check
        with self.assertRaises(ValueError):self.render()
        self.conform.assert_not_called();self.assertNotIn('checked_window',self.slot)

    def test_cached_prepared_bytes_are_rechecked_and_raw_changes_get_a_new_cache_name(self):
        first=self.render();self.render()
        self.assertEqual(self.conform.call_count,1)
        self.assertEqual(self.checker.check.call_count,4)
        self.raw.write_bytes(b'NEW RAW CONTENT FOR SAME SOURCE PATH')
        second=self.render()
        self.assertNotEqual(first,second);self.assertEqual(self.conform.call_count,2)

    def test_retry_finalization_preserves_explicit_owner_selection(self):
        clip=self.render();self.save_produced_bank(clip)
        first=pipeline.finalize_candidate_bank(self.fixture.project_file,media_reader=self.reader)
        slot=first['slots'][0];selected=choose(first,slot['id'],'selected',slot['candidates'][0]['id'])
        save_selections(self.folder/'BROLL_OWNER_SELECTIONS.v1.json',selected)
        again=pipeline.finalize_candidate_bank(self.fixture.project_file,media_reader=self.reader)
        self.assertEqual(again['slots'][0]['choice'],selected['slots'][0]['choice'])

    def test_legacy_options_are_not_backfilled_as_successful_checked_windows(self):
        self.fixture.project['slots'][0]['options'][0].pop('checked_window')
        self.fixture.write()
        manifest=pipeline.finalize_candidate_bank(self.fixture.project_file,media_reader=self.reader)
        self.assertTrue(any(not c['selectable'] for c in manifest['slots'][0]['candidates'])
                        or manifest['slots'][0]['omitted_by_cap']>0)
        saved=json.loads(self.fixture.project_file.read_text(encoding='utf-8'))
        self.assertNotIn('checked_window',saved['slots'][0]['options'][0])

    def test_normal_write_outputs_path_persists_typed_manifest_without_real_media_render(self):
        clip=self.render();project=self.save_produced_bank(clip)
        xml=self.folder/'BROLL_SEQUENCE.xml'
        with patch('hinglish_broll.pipeline.parse_xmeml',return_value=self.timeline), \
             patch('hinglish_broll.pipeline.export_broll_xml',return_value=xml), \
             patch('hinglish_broll.options.export_xml'), \
             patch('hinglish_broll.pipeline.write_report'), \
             patch('hinglish_broll.candidate_manifest.local_video_metadata',self.reader), \
             patch.dict(sys.modules,{'hinglish_zoom.xml_apply':SimpleNamespace(Sequence=Mock(return_value=SimpleNamespace(frames=0))),
                                     'hinglish_zoom.preview':SimpleNamespace(render_preview=Mock())}):
            pipeline.write_outputs(self.folder,self.folder,project)
        manifest=json.loads((self.folder/'BROLL_CANDIDATES.v1.json').read_text(encoding='utf-8'))
        self.assertTrue(manifest['slots'][0]['candidates'][0]['selectable'])
        self.assertEqual(manifest['slots'][0]['choice']['state'],'unselected')
        self.assertFalse((self.folder/'BROLL_OWNER_SELECTIONS.v1.json').exists())

    def test_source_check_change_invalidates_paired_proof_even_when_preview_passed(self):
        clip=self.render();project=self.save_produced_bank(clip)
        manifest=pipeline.finalize_candidate_bank(self.fixture.project_file,media_reader=self.reader)
        slot=manifest['slots'][0]
        selected=choose(manifest,slot['id'],'selected',slot['candidates'][0]['id'])
        project['slots'][0]['checks'][0]['frame_checks'][0]['subject_visible']=False
        self.fixture.write()
        with self.assertRaises(CandidateContractError):selected_candidates(selected)
        changed=pipeline.finalize_candidate_bank(self.fixture.project_file,media_reader=self.reader)
        self.assertEqual(changed['slots'][0]['candidates'],[])

    def test_prepared_mutation_during_its_actual_check_never_gets_a_receipt(self):
        def check(*args):
            if args[0]!=self.raw:Path(args[0]).write_bytes(b'CHANGED DURING PREVIEW CHECK')
            return copy.deepcopy(self.good)
        self.checker.check.side_effect=check
        with self.assertRaises(ValueError):self.render()
        self.assertNotIn('checked_window',self.slot)

    def test_review_options_require_checker_and_full_frame_evidence(self):
        with patch('hinglish_broll.internet.acquire') as acquire:
            with self.assertRaises(ValueError):
                pipeline.render_choice(self.folder,self.folder,self.timeline,0,self.slot,self.candidate,'cpu')
            acquire.assert_not_called()
        bad=copy.deepcopy(self.good);bad['frame_checks'][0]['subject_visible']=False
        self.checker.check.side_effect=lambda *args:bad
        with self.assertRaises(ValueError):self.render()
        self.conform.assert_not_called()

    def test_machine_preview_suggestion_is_not_an_owner_decision_in_finalized_contract(self):
        clip=self.render();project=self.save_produced_bank(clip)
        project['slots'][0]['chosen']=project['slots'][0]['options'][0]
        project['slots'][0]['clip']=clip.relative_to(self.folder).as_posix();self.fixture.write()
        manifest=pipeline.finalize_candidate_bank(self.fixture.project_file,media_reader=self.reader)
        self.assertEqual(manifest['slots'][0]['choice']['state'],'unselected')
        self.assertEqual(selected_candidates(manifest),[])

    def test_option_packing_cannot_relabel_another_candidates_actual_receipt(self):
        clip=self.render();data=self.candidate.to_dict();data['id']='stock:other'
        with self.assertRaises(CandidateContractError):
            pipeline._review_option_data(self.folder,self.slot,self.candidate,clip,data)

    def test_finalization_retains_incomplete_and_explicit_no_match_states(self):
        clip=self.render();project=self.save_produced_bank(clip)
        project['collecting']=True
        project['slots'][0]['collection_complete']=False
        project['slots'].append({'index':1,'start':5.,'end':6.,'text':'sleeping',
                                 'visual':'person asleep','options':[],'checks':[],
                                 'collection_complete':True,'chosen':None,'clip':None})
        self.fixture.write()
        manifest=pipeline.finalize_candidate_bank(self.fixture.project_file,media_reader=self.reader)
        self.assertEqual(manifest['collection_state'],'saved_incomplete')
        self.assertEqual(manifest['slots'][1]['collection_state'],'no_match')
        self.assertEqual(selected_candidates(manifest),[])

    def test_explicit_long_finalization_uses_two_choice_cap(self):
        manifest=pipeline.finalize_candidate_bank(self.fixture.project_file,content_format='long',media_reader=self.reader)
        self.assertEqual(manifest['per_keyword_cap'],2)
        self.assertEqual(len(manifest['slots'][0]['candidates']),2)


if __name__=='__main__':unittest.main()
