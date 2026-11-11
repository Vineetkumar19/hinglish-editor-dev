import json,tempfile,unittest
from pathlib import Path
from unittest.mock import Mock,patch


class OllamaGpuGuardTests(unittest.TestCase):
 def test_legacy_managed_child_fails_before_waiting_on_its_parent(self):
  from hinglish_cut.ollama_gpu import post
  import os
  session=self.session()
  with patch.dict(os.environ,{'HINGLISH_CREATOR_CONTEXT_FILE':'saved-context.json'},clear=True):
   with self.assertRaisesRegex(RuntimeError,'reload Storylens'):
    post(self.workspace(),session,'http://127.0.0.1:11434/api/chat',json={'model':'same:14b','messages':[]})
  session.post.assert_not_called()
 def session(self):
  session=Mock();session.post.return_value.json.return_value={'model_info':{'general.architecture':'qwen3','qwen3.block_count':40}}
  return session
 def workspace(self):
  folder=tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]/'tmp');self.addCleanup(folder.cleanup)
  root=Path(folder.name);(root/'config.models.local.json').write_text(json.dumps({'heavy_workloads_gpu_only':True,'device':'cuda'}));return root
 def test_partial_offload_blocks_before_user_prompt_is_sent(self):
  from hinglish_cut.ollama_gpu import post
  session=self.session();session.get.return_value.json.return_value={'models':[{'name':'same:14b','size':100,'size_vram':60}]}
  body={'model':'same:14b','messages':[{'role':'user','content':'preserve all of this'}],'options':{'num_ctx':12288}}
  with self.assertRaisesRegex(RuntimeError,'CPU offload'):post(self.workspace(),session,'http://127.0.0.1:11434/api/chat',json=body,timeout=9)
  self.assertEqual(session.post.call_count,2);self.assertEqual(session.post.call_args.kwargs['json']['messages'],[])
  self.assertNotIn('num_gpu',body['options'])
 def test_full_gpu_preserves_model_prompt_and_context(self):
  from hinglish_cut.ollama_gpu import post
  session=self.session();session.get.return_value.json.return_value={'models':[{'name':'same:14b','size':100,'size_vram':100}]}
  body={'model':'same:14b','messages':[{'role':'user','content':'exact script'}],'options':{'num_ctx':12288}}
  post(self.workspace(),session,'http://127.0.0.1:11434/api/chat',json=body,timeout=9)
  actual=session.post.call_args.kwargs['json'];self.assertEqual(actual['messages'],body['messages'])
  self.assertEqual(actual['model'],'same:14b');self.assertEqual(actual['options'],{'num_ctx':12288,'num_gpu':41,'num_batch':64})
 def test_embedding_warmup_contains_no_source_text(self):
  from hinglish_cut.ollama_gpu import post
  session=self.session();session.get.return_value.json.return_value={'models':[{'name':'same:8b','size':100,'size_vram':100}]}
  post(self.workspace(),session,'http://127.0.0.1:11434/api/embed',json={'model':'same:8b','input':['saved knowledge']},timeout=9)
  self.assertEqual(session.post.call_args_list[1].kwargs['json']['input'],[])
  self.assertEqual(session.post.call_args_list[2].kwargs['json']['input'],['saved knowledge'])
 def test_explicit_gpu_first_policy_allows_selected_model_partial_cpu_offload(self):
  from hinglish_cut.ollama_gpu import post
  root=self.workspace();config=root/'config.models.local.json';value=json.loads(config.read_text());value.update(allow_ollama_cpu_offload=True,planning_model='same:14b',vision_model='other:9b');config.write_text(json.dumps(value))
  session=self.session();session.get.return_value.json.return_value={'models':[{'name':'same:14b','size':100,'size_vram':60}]}
  body={'model':'same:14b','messages':[{'role':'user','content':'full saved context'}],'options':{'num_ctx':12288}}
  post(root,session,'http://127.0.0.1:11434/api/chat',json=body)
  actual=session.post.call_args.kwargs['json'];self.assertEqual(actual['messages'],body['messages']);self.assertEqual(actual['options']['num_ctx'],12288);self.assertEqual(actual['options']['num_gpu'],-1)
  receipt=json.loads(next((root/'cache/app/gpu-residency').glob('*.json')).read_text());self.assertTrue(receipt['cpu_offload']);self.assertTrue(receipt['cpu_offload_allowed'])
 def test_gpu_first_policy_does_not_silently_accept_cpu_only_model(self):
  from hinglish_cut.ollama_gpu import post
  root=self.workspace();config=root/'config.models.local.json';value=json.loads(config.read_text());value.update(allow_ollama_cpu_offload=True,planning_model='same:14b');config.write_text(json.dumps(value))
  session=self.session();session.get.return_value.json.return_value={'models':[{'name':'same:14b','size':100,'size_vram':0}]}
  with self.assertRaisesRegex(RuntimeError,'GPU-first'):post(root,session,'http://127.0.0.1:11434/api/chat',json={'model':'same:14b','messages':[]})


if __name__=='__main__':unittest.main()
