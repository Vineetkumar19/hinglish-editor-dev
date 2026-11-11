import tempfile
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from hinglish_app.assistant import Assistant


class MemoryTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup)
        self.root=Path(temp.name);self.assistant=Assistant(SimpleNamespace(root=self.root))

    def test_new_chat_is_isolated_and_reopening_restores_its_own_context(self):
        first=self.assistant.create()['id']
        self.assistant._update(first,profile='gaming')
        self.assistant._message(first,'user','Write long SEO descriptions about the video only. Never mention Storylens in public copy.')
        second=self.assistant.create()['id']
        restored=Assistant(SimpleNamespace(root=self.root))
        result=restored.memory.retrieve('What did I tell you about SEO descriptions?',second)
        self.assertFalse(result['messages'])
        reopened=restored.memory.retrieve('What did I tell you about SEO descriptions?',first)
        self.assertTrue(any('long SEO descriptions' in m['text'] for m in reopened['messages']))
        self.assertIn('never new permission',result['rules'])

    def test_archive_retains_messages_beyond_active_chat_context(self):
        session=self.assistant.create()['id']
        for i in range(92):self.assistant._message(session,'user',f'Message {i} keeps the full conversation available.')
        self.assertEqual(len(self.assistant.snapshot(session)['messages']),80)
        restored=Assistant(SimpleNamespace(root=self.root))
        page=restored.memory.messages(session)
        self.assertTrue(page['has_more']);self.assertEqual(len(page['messages']),80)
        older=restored.memory.messages(session,page['messages'][0]['id'])
        self.assertEqual(len(older['messages']),12)
        self.assertTrue(older['messages'][0]['text'].startswith('Message 0 '))
        self.assertFalse(older['has_more'])

    def test_search_and_reopen_do_not_replay_commands(self):
        first=self.assistant.create()['id']
        self.assistant._message(first,'user','Upload seven Kolkata Shorts at 18:00.')
        self.assistant._message(first,'assistant','The files are ready for review.')
        second=self.assistant.create()['id'];self.assistant._message(second,'user','Use Typography 4 for captions.')
        with patch.object(self.assistant,'send') as send:
            chats=self.assistant.memory.history('Kolkata')
            saved=self.assistant.snapshot(chats[0]['id'])
        self.assertEqual(len(chats),1);self.assertEqual(saved['id'],first);send.assert_not_called()
        self.assertEqual(len(self.assistant.memory.history()),2)

    def test_old_context_is_archived_but_not_reintroduced_into_model_memory(self):
        session=self.assistant.create()['id']
        self.assistant._message(session,'user','My unusual watermark preference is the golden peacock.')
        for i in range(85):self.assistant._message(session,'user',f'Unrelated turn {i}.')
        restored=Assistant(SimpleNamespace(root=self.root))
        result=restored.memory.retrieve('Recall my watermark preference.',session)
        self.assertFalse(any('golden peacock' in m['text'] for m in result['messages']))
        self.assertEqual(len(result['messages']),5)
        self.assertEqual(result['messages'][0]['text'],'Unrelated turn 80.')

    def test_planner_never_receives_another_chats_preferences(self):
        from hinglish_app.assistant_plan import plan
        first=self.assistant.create()['id'];self.assistant._message(first,'user','My captions preference is Typography 4.')
        second=self.assistant.create()['id']
        memory=self.assistant.memory.retrieve('What is my captions preference?',second)
        captured={}
        class Brain:
            name='Local fixture'
            def json(self,system,data,schema,**kw):
                captured.update(data);return {'reply':'You prefer Typography 4.','question':'','combine':False,'steps':[]}
            def close(self):pass
        with patch('hinglish_visuals.brain.open_brain',return_value=Brain()):
            plan(self.root,'Tell me my earlier captions preference.',[],[],False,memory_context=memory)
        self.assertFalse(any('Typography 4' in m['text'] for m in captured['shared_memory'].get('messages',[])))

    def test_five_exchanges_are_bounded_even_with_many_progress_replies(self):
        from hinglish_app.chat_context import recent
        messages=[]
        for i in range(12):
            messages.append({'role':'user','text':f'Request {i} '+('x'*2000)})
            messages.extend({'role':'assistant','text':f'Progress {j} '+('y'*2000)} for j in range(6))
        selected=recent(messages)
        self.assertEqual(len(selected),10)
        self.assertTrue(selected[0]['text'].startswith('Request 7 '))
        self.assertTrue(selected[-1]['text'].startswith('Progress 5 '))
        self.assertLessEqual(sum(len(m['text']) for m in selected),6000)
