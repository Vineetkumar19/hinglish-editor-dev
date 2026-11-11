"""Fixed Adobe script transport unit checks; synthetic receipts are not live proof."""
import hashlib,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from hinglish_app.editor_panel import PanelContexts
from hinglish_app.timed_choice_delivery import TimedChoiceDelivery

class AEDirectTests(unittest.TestCase):
    def setUp(self):
        from hinglish_app.broll_ae_direct import AfterEffectsDirect
        base=Path(__file__).resolve().parents[1]/'cache/test-ae-direct';base.mkdir(parents=True,exist_ok=True)
        self.tmp=tempfile.TemporaryDirectory(dir=base);self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.contexts=PanelContexts(self.root);self.calls=[]
        def execute(script,out,nonce):
            self.calls.append(script.read_text('utf-8'))
            return {'invocation_id':nonce,'result':{'host':'aftereffects','project_id':'owner',
                'sequence_id':'comp','name':'Test comp','fps':30,'width':1080,'height':1920,'duration':36}}
        self.adapter=AfterEffectsDirect(self.root,self.contexts,execute=execute)

    def operation(self):
        file=self.root/'output/clip.mp4';file.parent.mkdir(exist_ok=True);file.write_bytes(b'unit-media')
        context=self.contexts.save({'host':'aftereffects','project_id':'owner','sequence_id':'comp','fps':30,'transport':'aftereffects_script'})
        value={'feature':'broll','bank_id':'bank','slot_id':'slot','slot_fingerprint':'source-slot',
          'asset_id':'one','asset_path':str(file),'asset_sha256':hashlib.sha256(file.read_bytes()).hexdigest(),
          'start_frame':3,'end_frame':64,'fps':'30','source_in':1,'source_duration':8,'width':1080,'height':1920}
        return TimedChoiceDelivery(self.root).prepare(value,context),context

    def test_capture_reads_actual_comp_without_saving_or_opening_a_project(self):
        context=self.adapter.capture()
        self.assertEqual(context['sequence_id'],'comp');self.assertEqual(context['host'],'aftereffects')
        self.assertIn('activeItem',self.calls[0]);self.assertNotIn('app.project.save',self.calls[0])
        self.assertNotIn('app.open(',self.calls[0]);self.assertNotIn('app.newProject',self.calls[0])

    def test_choice_revalidates_the_saved_private_media_and_uses_only_fixed_native_code(self):
        operation,_=self.operation()
        self.adapter.invoke_choice(operation)
        self.assertIn('SLTimedChoice.ae(',self.calls[-1])
        Path(operation['path']).write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError,'changed'):self.adapter.invoke_choice(operation)
        self.assertEqual(len(self.calls),1)

    def test_unmatched_invocation_cannot_be_a_native_receipt(self):
        self.adapter.execute=lambda *args:{'invocation_id':'stale','result':{'ok':True}}
        with self.assertRaisesRegex(ValueError,'receipt'):self.adapter.capture()

    def test_delivery_uses_bound_context_and_accepts_the_actual_host_receipt_only(self):
        operation,context=self.operation()
        receipt={'ok':True,'operation_id':operation['operation_id']}
        with patch('hinglish_app.panel_broll_choices.select_timed',return_value={'manifest':operation}), \
             patch.object(self.adapter,'invoke_choice',return_value=receipt), \
             patch('hinglish_app.timed_choice_delivery.TimedChoiceDelivery.accept',return_value=receipt) as accept:
            result=self.adapter.deliver('bank',{'slot_id':'slot'},context['id'])
        self.assertEqual(result['status'],'confirmed')
        self.assertEqual(accept.call_args.kwargs['context']['sequence_id'],'comp')

if __name__=='__main__':unittest.main()
