import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock,patch

from hinglish_app.assistant_stream import reply_prefix
from hinglish_cut.ollama_gpu import _request


class LiveProgressTests(unittest.TestCase):
    def test_partial_reply_decoding_excludes_tool_json_and_private_reasoning(self):
        self.assertEqual(reply_prefix('{"reply":"Hello\\nworld'), 'Hello\nworld')
        self.assertEqual(reply_prefix('{"reply":"Hi\\u'), 'Hi')
        self.assertEqual(reply_prefix('{"reply":"Hi\\ud83d'), 'Hi')
        self.assertEqual(reply_prefix('{"reply":"Hi\\ud83d\\ude00'), 'Hi😀')
        self.assertEqual(reply_prefix('{"thinking":"private","reply":"Hello"}'), '')
        self.assertEqual(reply_prefix('{"steps":[{"tool":"upload"}]}'), '')

    def response(self,packets):
        response=Mock();response.status_code=200
        response.iter_lines.return_value=[json.dumps(p).encode() for p in packets]
        return response

    def test_stream_is_consumed_incrementally_before_returning_final_usage(self):
        response=self.response([{'message':{'content':'{"reply":"Hi'}},
            {'message':{'content':' there"}'},'done':True,'prompt_eval_count':9,'eval_count':4}])
        session=Mock();session.post.return_value=response;chunks=[]
        result=_request(session,'localhost',{'model':'local','stream':False},chunks.append)
        self.assertEqual(chunks,['{"reply":"Hi','{"reply":"Hi there"}'])
        self.assertEqual(result.json()['message']['content'],'{"reply":"Hi there"}')
        self.assertEqual(result.json()['prompt_eval_count'],9);response.close.assert_called_once()
        self.assertTrue(session.post.call_args.kwargs['stream'])

    def test_broken_stream_is_not_reported_as_a_complete_reply(self):
        response=self.response([{'message':{'content':'{"reply":"partial'}}]);session=Mock();session.post.return_value=response
        with self.assertRaises(ConnectionError):_request(session,'localhost',{},lambda _:None)
        response.close.assert_called_once()

    def test_progress_read_does_not_start_delivery_or_return_transcript_content(self):
        from hinglish_app.assistant_progress import present
        assistant=Mock();engine=Mock();workflow=Mock()
        workflow.get.return_value={'profile':'cricket','created':10,'updated':20,'status':'failed',
            'assistant_plan':{'session':'session','message_id':'current'},'intent':{'count':3},'preparations':{'shorts':'prep'},'jobs':{}}
        engine.get.return_value={'id':'prep','mode':'shorts','count':3,'status':'failed','current_stage':'copy:youtube:1',
            'stages':{'speech':{'words':['must not duplicate full transcript']}},'errors':{'copy:youtube:1':{'error':'Needs review'}}}
        snapshot={'id':'session','status':'needs_review','active_request_message_id':'current','upload_workflow':{'id':'flow','profile':'cricket'}}
        with patch('hinglish_app.prepare_post_http.service',return_value=engine) as service,patch('hinglish_app.prepare_post_http.workflow_service',return_value=workflow):
            result=present(assistant,snapshot);self.assertEqual(result['drafts'][0]['stages'],{'speech':{}})
            service.assert_called_once_with(assistant.state,recover_delivery=False);engine.start_delivery.assert_not_called()
            snapshot['active_request_message_id']='different';self.assertIsNone(present(assistant,snapshot))

    def test_a_rejected_provider_cache_is_preserved_without_being_reused(self):
        from hinglish_publish.prepare_post_runtime import RecordedBrain
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]/'tmp') as folder:
            root=Path(folder);cache=root/'provider';cache.mkdir();target=cache/'cache.json';target.write_text('{"subject":"Virat Kohli"}')
            raw=Mock();raw.name='local';raw.last_usage={};raw.cache=cache;raw.last_cache_file=target;raw.json.return_value={'subject':'Virat Kohli'}
            brain=RecordedBrain(raw,root,{});answer=brain.json('Brief',{},{});brain.reject_result(answer,'Not a supported subject')
            self.assertFalse(target.exists());self.assertEqual(len(list(cache.glob('cache.rejected-*.json'))),1)


if __name__=='__main__':unittest.main()
