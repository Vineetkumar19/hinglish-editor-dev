"""Loading-order/placement contract with fake runtimes; no real model import."""
import builtins
from contextlib import nullcontext
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock,patch


class ModelLoadingTests(unittest.TestCase):
    def test_cuda_releases_planner_before_importing_torch(self):
        from hinglish_broll.vision import Vision
        events=[];original=builtins.__import__
        torch=SimpleNamespace(cuda=SimpleNamespace(is_available=lambda:True),set_num_threads=lambda _:None)
        def importing(name,*args,**kwargs):
            if name=='torch':events.append('torch');return torch
            if name=='transformers':return SimpleNamespace(CLIPModel=Mock(),CLIPProcessor=Mock())
            return original(name,*args,**kwargs)
        base=Path(__file__).resolve().parents[1]/'cache/test-loading';base.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=base) as folder:
            root=Path(folder);selected={'repo':'fixture-embedding','path':str(root)}
            with patch('builtins.__import__',side_effect=importing), \
                 patch('hinglish_cut.model_storage.role',return_value=selected), \
                 patch('hinglish_cut.model_preferences.release_ollama',side_effect=lambda _:events.append('release')), \
                 patch('hinglish_broll.vl_embedding.load_encoder',return_value=(Mock(),Mock())):
                Vision('fixture-embedding',root,device='cuda')
        self.assertLess(events.index('release'),events.index('torch'))

    def test_embedding_loader_places_weights_directly_on_requested_gpu(self):
        from hinglish_broll import vl_embedding
        encoder=Mock();torch=SimpleNamespace(bfloat16='bf16',float32='fp32')
        with patch('hinglish_broll.vl_embedding.windows_reader',return_value=nullcontext()):
            result=vl_embedding.load_pretrained(encoder,'local-model','cuda',torch)
        self.assertIs(result,encoder.from_pretrained.return_value.eval.return_value)
        kwargs=encoder.from_pretrained.call_args.kwargs
        self.assertEqual(kwargs['device_map'],{'':'cuda:0'})
        self.assertEqual(kwargs['dtype'],'bf16')
        self.assertTrue(kwargs['local_files_only'])
        encoder.from_pretrained.return_value.to.assert_not_called()

    def test_windows_reader_avoids_mapped_slices_and_restores_the_library(self):
        from hinglish_broll.vl_embedding import sequential_reader
        original=Mock();module=SimpleNamespace(safe_open=original)
        with sequential_reader(module):module.safe_open('local-weights',framework='pt')
        self.assertEqual(original.call_args.kwargs['backend'],'pread')
        self.assertIs(module.safe_open,original)
        with self.assertRaisesRegex(ValueError,'fixture'):
            with sequential_reader(module):raise ValueError('fixture')
        self.assertIs(module.safe_open,original)


if __name__=='__main__':unittest.main()
