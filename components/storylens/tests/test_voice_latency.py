from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Thread, Event
from time import perf_counter
from unittest import TestCase
from unittest.mock import patch
from hinglish_cut.gpu_lock import gpu_lock, held_by_current_thread
from hinglish_app import support_call_local as local

class InteractiveGpuTests(TestCase):
    def test_busy_gpu_fails_bounded_without_releasing_owner(self):
        with TemporaryDirectory() as folder:
            attempts=[]
            def attempt():
                start=perf_counter()
                try:
                    with gpu_lock(folder,timeout=.08): attempts.append('entered')
                except TimeoutError: attempts.append(perf_counter()-start)
            with gpu_lock(folder):
                worker=Thread(target=attempt);worker.start();worker.join(1)
                self.assertFalse(worker.is_alive())
                self.assertEqual(len(attempts),1)
                self.assertIsInstance(attempts[0],float)
                self.assertLess(attempts[0],.5)
                self.assertTrue(held_by_current_thread(folder))
            with gpu_lock(folder,timeout=0): self.assertTrue(held_by_current_thread(folder))

    def test_nested_owner_can_reenter_zero_wait(self):
        with TemporaryDirectory() as folder:
            with gpu_lock(folder):
                with gpu_lock(folder,timeout=0):
                    self.assertTrue(held_by_current_thread(folder))

    def test_telemetry_does_not_need_the_voice_worker_lock(self):
        import io,json
        from uuid import uuid4
        call_id=str(uuid4()); call=local._session(call_id,create=True)
        record={'id':uuid4().hex,'status':'answered'}
        call.receipts.append(record['id'])
        with local._RECENT_LOCK: local._RECENT.append(record)
        payload=json.dumps({'id':record['id'],'audio_started':True,
                           'client_timings':{'audio_start_ms':820,'secret':'not saved'}}).encode()
        class Handler:
            headers={'X-Storylens-Call':call_id,'Content-Length':str(len(payload))}
            rfile=io.BytesIO(payload)
            def _json(self,status,value): self.status=status;self.value=value
        h=Handler()
        with local._WORK, patch.object(local.speech,'available',return_value=True), patch.object(local,'_persist_metrics'):
            local.handle(h,Path.cwd(),'/api/support-call/local-result')
        self.assertEqual(h.status,200)
        self.assertEqual(record['status'],'answered')
        self.assertEqual(record['client_timings'],{'audio_start_ms':820})
        self.assertTrue(record['audio_started'])
        with local._SESSIONS_LOCK: local._SESSIONS.pop(call_id,None)

class GeneralConversationTests(TestCase):
    def test_general_question_does_not_use_storylens_router(self):
        response = {'message': {'content': '{"answer":"An atom is a basic unit of matter.","needs_lookup":false}'}}
        with patch.object(local.speech, 'transcribe', return_value=('What is an atom?', 'en')), \
             patch.object(local.speech, 'synthesize', return_value=b'speech'), patch.object(local, 'gpu_lock'), \
             patch.object(local, '_ollama_post', return_value=response) as model, \
             patch.object(local, 'routing_context') as product, patch.object(local, 'public_evidence') as lookup, \
             patch.object(local, '_persist_metrics'):
            result = local._answer(Path.cwd(), local.Call(), b'audio', 'clean', 'en')
        self.assertIn('basic unit of matter', result['text'])
        self.assertIsNone(result['action'])
        self.assertIs(model.call_args.args[2]['format'], local._GENERAL_SCHEMA)
        product.assert_not_called()
        lookup.assert_not_called()

    def test_unknown_public_fact_gets_evidence_without_using_desktop(self):
        question = 'What is Lionel Messi known for?'
        first = {'message': {'content': '{"answer":"","needs_lookup":true}'}}
        second = {'message': {'content': '{"answer":"He is an Argentine footballer.","needs_lookup":false}'}}
        evidence = [{'title': 'Lionel Messi', 'url': 'https://en.wikipedia.org/wiki/Lionel_Messi',
                     'text': 'Lionel Messi is an Argentine professional footballer.'}]
        with patch.object(local, 'gpu_lock'), patch.object(local, '_ollama_post', side_effect=[first, second]) as model, \
             patch.object(local, 'public_evidence', return_value=evidence) as lookup:
            reply, sources = local._general_answer(Path.cwd(), local.Call(), question, 'en')
        lookup.assert_called_once_with(question.strip('?'))
        self.assertEqual(sources, evidence)
        self.assertIn('Argentine footballer', reply)
        self.assertIn(evidence[0]['text'], model.call_args.args[2]['messages'][-1]['content'])

    def test_public_identity_gets_evidence_before_the_local_model_answers(self):
        evidence = [{'title': 'Lionel Messi', 'url': 'https://en.wikipedia.org/wiki/Lionel_Messi',
                     'text': 'Lionel Messi is an Argentine professional footballer.'}]
        response = {'message': {'content': '{"answer":"Lionel Messi is an Argentine footballer.","needs_lookup":false}'}}
        with patch.object(local, 'gpu_lock'), patch.object(local, '_ollama_post', return_value=response) as model, \
             patch.object(local, 'public_evidence', return_value=evidence) as lookup:
            reply, sources = local._general_answer(Path.cwd(), local.Call(), 'Who is Messi?', 'en')
        lookup.assert_called_once_with('Who is Messi')
        model.assert_called_once()
        self.assertIn('Argentine footballer', reply)
        self.assertEqual(sources, evidence)

    def test_greeting_and_private_data_are_not_search_queries(self):
        for question in ('How are you today?', 'Are you doing well today?', 'Who is my doctor?',
                         'Search for D:/My Files/report.xlsx', 'Look up user@example.com'):
            self.assertEqual(local.lookup_query(question), ('', False))


class FastGuideIntegrationTests(TestCase):
    def test_basic_feature_question_uses_prepared_answer_without_model_or_tts(self):
        with patch.object(local.speech,'transcribe',return_value=('What does Smart Clean do?','en')),              patch.object(local,'gpu_lock'), patch.object(local.help_audio,'combine',return_value=b'prepared'),              patch.object(local.speech,'synthesize') as synth, patch.object(local,'_ollama_post') as model,              patch.object(local,'_persist_metrics'):
            value=local._answer(Path.cwd(),local.Call(),b'audio','clean','en')
        self.assertIn('silent gaps',value['text'])
        self.assertIsNone(value['action'])
        synth.assert_not_called();model.assert_not_called()

    def test_grounded_option_avoids_file_worker_and_model(self):
        with patch.object(local.speech,'transcribe',return_value=('Hyper Frame Cardo','en')),              patch.object(local,'gpu_lock'), patch.object(local,'_ollama_post') as model,              patch('hinglish_app.support_call_actions._worker') as desktop,              patch.object(local,'_persist_metrics'):
            value=local._answer(Path.cwd(),local.Call(),b'audio','motion','en',deferred=True)
        self.assertEqual(value['action']['value'],'hyperframes')
        desktop.assert_not_called();model.assert_not_called()
