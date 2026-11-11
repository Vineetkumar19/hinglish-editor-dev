"""Controller contract only; these fixtures are not native editor acceptance."""
import hashlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from hinglish_app.timed_choice_delivery import TimedChoiceDelivery


class TimedChoiceTests(unittest.TestCase):
    def setUp(self):
        base=Path(__file__).resolve().parents[1]/'cache/test-timed-choices'
        base.mkdir(parents=True,exist_ok=True)
        self.temp=tempfile.TemporaryDirectory(dir=base);self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.output=self.root/'output';self.output.mkdir()
        self.first=self.output/'one.mp4';self.first.write_bytes(b'fixture-one')
        self.second=self.output/'two.mp4';self.second.write_bytes(b'fixture-two')
        self.service=TimedChoiceDelivery(self.root)
        self.context={'host':'aftereffects','project_id':'project','sequence_id':'comp-1','fps':30}

    def prepare(self,path=None,**change):
        path=path or self.first
        value={'feature':'broll','bank_id':'bank','slot_id':'slot','slot_fingerprint':'slot-revision',
               'asset_id':path.name,'asset_path':str(path),'asset_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
               'source_in':3.,'source_duration':8.,'start_frame':64,'end_frame':93,'fps':'30/1',
               'width':1080,'height':1920}
        value.update(change)
        return self.service.prepare(value,self.context)

    def receipt(self,operation,**change):
        value={'ok':True,'operation_id':operation['operation_id'],'binding_id':operation['binding_id'],
               'host':'aftereffects','project_id':'project','sequence_id':'comp-1',
               'item_id':'layer-7','asset_id':operation['asset_id'],'asset_sha256':operation['asset_sha256'],
               'path':operation['path'],'start':64/30,'end':93/30,'source_in':3.}
        value.update(change);return value

    def test_pending_click_reuses_operation_and_alternative_waits_for_receipt(self):
        op=self.prepare()
        self.assertEqual(self.prepare()['operation_id'],op['operation_id'])
        with self.assertRaisesRegex(ValueError,'confirm'):
            self.prepare(self.second)

    def test_swap_binds_same_native_item_after_receipt_and_duplicate_does_not_reinsert(self):
        op=self.prepare();self.service.accept(op['operation_id'],self.receipt(op))
        same=self.prepare();self.assertEqual(same['operation_id'],op['operation_id'])
        self.assertTrue(same['already_confirmed'])
        swap=self.prepare(self.second)
        self.assertEqual(swap['binding_id'],op['binding_id'])
        self.assertEqual(swap['action'],'replace')
        self.assertEqual(swap['expected_item_id'],'layer-7')
        self.assertTrue(swap['preserve_host_edits'])

    def test_wrong_host_or_item_receipt_cannot_confirm_operation(self):
        op=self.prepare()
        with self.assertRaisesRegex(ValueError,'receipt'):
            self.service.accept(op['operation_id'],self.receipt(op,sequence_id='other'))
        self.service.accept(op['operation_id'],self.receipt(op))
        swap=self.prepare(self.second)
        with self.assertRaisesRegex(ValueError,'item'):
            self.service.accept(swap['operation_id'],self.receipt(swap,item_id='layer-8'))

    def test_changed_media_and_invalid_time_are_rejected_before_host_mutation(self):
        with self.assertRaisesRegex(ValueError,'changed'):
            self.prepare(asset_sha256='0'*64)
        with self.assertRaises(ValueError):self.prepare(end_frame=63)
        with self.assertRaises(ValueError):self.prepare(source_in=7.5)
        with self.assertRaises(ValueError):self.prepare(start_frame=True)

    def test_capcut_is_not_misrepresented_as_active_timeline_control(self):
        self.context['host']='capcut'
        with self.assertRaisesRegex(ValueError,'CapCut'):
            self.prepare()

    def test_premiere_gets_a_private_per_slot_project_item_source(self):
        self.context['host']='premiere'
        op=self.prepare()
        self.assertNotEqual(Path(op['path']),self.first)
        self.assertEqual(Path(op['path']).read_bytes(),self.first.read_bytes())
        other=self.prepare(slot_id='another-slot')
        self.assertNotEqual(other['path'],op['path'])

    def test_after_effects_also_gets_a_private_source_for_uncertain_insert_reconciliation(self):
        op=self.prepare()
        self.assertNotEqual(Path(op['path']),self.first)
        self.assertEqual(Path(op['path']).read_bytes(),self.first.read_bytes())

    def test_receipt_commit_interruption_can_be_reconciled_without_another_insert(self):
        from hinglish_app.timed_choice_delivery import write_json
        op=self.prepare();failed=[False]
        def interrupt(path,value):
            if Path(path).parent.name=='bindings' and value.get('pending') is None and not failed[0]:
                failed[0]=True;raise OSError('fixture interrupted binding commit')
            return write_json(path,value)
        with patch('hinglish_app.timed_choice_delivery.write_json',side_effect=interrupt):
            with self.assertRaises(OSError):self.service.accept(op['operation_id'],self.receipt(op))
        self.service.accept(op['operation_id'],self.receipt(op))
        self.assertTrue(self.prepare()['already_confirmed'])

    def test_broll_controller_delivers_only_the_clicked_slot_with_its_original_frame(self):
        from tests import test_broll_candidate_manifest as fixture
        from hinglish_app import panel_broll_choices
        f=fixture.CandidateManifestTests();f.setUp();self.addCleanup(f.doCleanups)
        bank=f.build();row=bank['slots'][0];candidate=row['candidates'][1]
        request={'project':str(f.project_file),'slot_id':row['id'],'candidate_id':candidate['id'],'state':'selected'}
        with patch.object(panel_broll_choices,'load_bank',return_value=bank), \
             patch('hinglish_app.timed_choice_delivery.TimedChoiceDelivery.prepare',return_value={'type':'timed_choice'}) as prepare:
            result=panel_broll_choices.select_timed(self.root,self.output,request,self.context)
        self.assertEqual(result['manifest']['type'],'timed_choice')
        value=prepare.call_args.args[0]
        self.assertEqual(value['asset_id'],candidate['id'])
        self.assertEqual(value['start_frame'],64);self.assertEqual(value['end_frame'],93)
        self.assertEqual(value['source_in'],3.)

    def test_capcut_new_draft_spec_contains_only_owner_choices_at_spoken_frames(self):
        from tests import test_broll_candidate_manifest as fixture
        from hinglish_broll.candidate_selection import choose
        from hinglish_app import panel_broll_choices
        from types import SimpleNamespace
        f=fixture.CandidateManifestTests();f.setUp();self.addCleanup(f.doCleanups)
        f.project['timeline']['xml_path']=str(f.root/'source-timeline.xml');(f.root/'source-timeline.xml').write_text('<xmeml/>')
        bank=f.build();row=bank['slots'][0];candidate=row['candidates'][1]
        bank=choose(bank,row['id'],'selected',candidate['id'])
        from fractions import Fraction
        timeline=SimpleNamespace(clips=[SimpleNamespace(path=str(f.root/'base.mp4'),start=0.,end=12.,source_in=0.)],
                                 fps=Fraction(30),width=1080,height=1920,duration=12.)
        with patch('hinglish_broll.timeline.parse_xmeml',return_value=timeline):
            spec=panel_broll_choices.capcut_selected_spec(bank)
        self.assertEqual(len(spec['overlays']),1)
        self.assertEqual(spec['overlays'][0]['path'],candidate['prepared']['path'])
        self.assertEqual(spec['overlays'][0]['start'],round(64/30*1e6))
        self.assertEqual(spec['overlays'][0]['source_in'],3000000)
        self.assertEqual(spec['options'],[])


if __name__=='__main__':unittest.main()
