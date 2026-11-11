"""CPU controller checks; not native-editor acceptance."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from hinglish_app.editor_panel import PanelContexts


class MailboxTests(unittest.TestCase):
    def setUp(self):
        from hinglish_app.broll_native_mailbox import NativeChoiceMailbox
        base=Path(__file__).resolve().parents[1]/'cache/test-native-mailbox';base.mkdir(parents=True,exist_ok=True)
        self.tmp=tempfile.TemporaryDirectory(dir=base);self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.contexts=PanelContexts(self.root);self.now=10.
        self.box=NativeChoiceMailbox(self.root,self.contexts,clock=lambda:self.now)
        self.context=self.contexts.save({'host':'aftereffects','project_id':'owner',
          'sequence_id':'comp-1','content_format':'short'})
        self.client='a'*32
        self.manifest={'type':'timed_choice','operation_id':'b'*32,
                       'expected':{'host':'aftereffects','project_id':'owner','sequence_id':'comp-1'}}

    def connect(self):return self.box.register(self.client,self.context['id'])

    def submit(self):
        with patch('hinglish_app.panel_broll_choices.select_timed',return_value={
            'choice_saved':True,'manifest':self.manifest}) as select:
            value=self.box.submit('aftereffects',{'folder':'saved','slot_id':'slot',
                'project':'broll-project.json','candidate_id':'checked'})
            self.assertEqual(select.call_args.args[-1]['sequence_id'],'comp-1')
            return value

    def test_click_requires_one_live_panel_and_never_guesses_a_host_context(self):
        with self.assertRaisesRegex(ValueError,'Open'):self.submit()
        self.connect();self.now+=31
        with self.assertRaisesRegex(ValueError,'Open'):self.submit()

    def test_delivery_replays_same_operation_and_waits_for_native_receipt(self):
        lease=self.connect();first=self.submit();second=self.submit()
        self.assertEqual(first['id'],second['id']);self.assertEqual(first['status'],'queued')
        command=self.box.poll(lease['lease'],self.client)
        self.assertEqual(command['manifest'],self.manifest)
        self.assertEqual(self.box.poll(lease['lease'],self.client)['id'],command['id'])
        with patch('hinglish_app.timed_choice_delivery.TimedChoiceDelivery.accept',return_value={'ok':True}) as accept:
            result=self.box.ack(lease['lease'],self.client,command['id'],{'ok':True})
            self.assertEqual(accept.call_args.kwargs['context']['sequence_id'],'comp-1')
        self.assertEqual(result['status'],'confirmed');self.assertIsNone(self.box.poll(lease['lease'],self.client))

    def test_another_panel_cannot_take_a_live_lease_or_ack_its_operation(self):
        lease=self.connect();command=self.submit()
        with self.assertRaisesRegex(ValueError,'already'):self.box.register('c'*32,self.context['id'])
        with self.assertRaises(ValueError):self.box.ack(lease['lease'],'c'*32,command['id'],{'ok':True})
        self.now+=31
        adopted=self.box.register('c'*32,self.context['id'])
        self.assertEqual(adopted['lease'],lease['lease'])
        self.assertEqual(self.box.poll(adopted['lease'],'c'*32)['id'],command['id'])

    def test_uncertain_failure_is_not_reported_as_imported_or_replaced(self):
        lease=self.connect();command=self.submit()
        result=self.box.ack(lease['lease'],self.client,command['id'],None,error='Host stopped')
        self.assertEqual(result['status'],'unconfirmed')
        self.assertIn('same choice',result['message'])
        self.assertEqual(self.submit()['id'],command['id'])


if __name__=='__main__':unittest.main()
