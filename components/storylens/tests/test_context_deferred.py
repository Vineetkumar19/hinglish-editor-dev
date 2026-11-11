"""Run against staged modules until the protected workflow completes."""
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest


class DeferredContextTests(unittest.TestCase):
    def setUp(self):
        import inspect
        from hinglish_app.chat_context import recent
        if 'exchanges' not in inspect.signature(recent).parameters:
            self.skipTest('Protected workflow still uses original sources; run work/check_context_architecture.py --staged')

    def test_extended_history_preserves_complete_messages_and_recent_exchanges(self):
        from hinglish_app.chat_context import recent
        messages=[{'role':'user','text':f'question {i} '+'exact words '*100} for i in range(16)]
        result=recent(messages,exchanges=20,text_limit=None)
        self.assertEqual(result,messages)
        self.assertEqual(len(recent(messages)),5)
        self.assertLessEqual(len(recent(messages)[0]['text']),600)

    def test_assistant_fit_uses_40k_and_keeps_optional_memory_when_it_fits(self):
        from hinglish_app.assistant_plan_context import fit
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]/'tmp') as directory:
            root=Path(directory)
            (root/'config.models.local.json').write_text('{"context_limit":12288}')
            (root/'config.context.local.json').write_text(json.dumps({'version':1,
                'models':{'text':'local:14b'},'model_limits':{'text':40960},
                'features':{'assistant':{'text':40960}},'deferred_features':[]}))
            data={'request':'Exact source and instructions. '*1600,
                  'conversation':[{'role':'user','text':'Keep these words. '*100}],
                  'shared_memory':{'workflow_knowledge':'Owner approved guidance','messages':['saved memory']}}
            result=fit(SimpleNamespace(root=root),'Read all instructions.',data,{},2400)
            self.assertEqual(result,data)


if __name__=='__main__':unittest.main()
