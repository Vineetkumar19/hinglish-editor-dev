import json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from types import SimpleNamespace

class CaptionGpuTests(unittest.TestCase):
    def test_priority_admission_requires_idle_gpu_and_memory_headroom(self):
        from hinglish_app.caption_compute import priority_gpu_ready
        self.assertTrue(priority_gpu_ready(10000,0))
        self.assertFalse(priority_gpu_ready(3000,0))
        self.assertFalse(priority_gpu_ready(10000,65))

    def test_cuda_choice_reaches_transcription_and_direct_alignment(self):
        from hinglish_app.caption_native_timing import recognize
        from hinglish_app.caption_audio_alignment import WhisperScriptAligner
        calls=[]
        class Model:
            def __init__(self,*a,**kw):calls.append(kw);self.hf_tokenizer=None;self.model=SimpleNamespace(is_multilingual=True)
            def transcribe(self,*a,**kw):return iter([]),None
        options={'device':'cuda','compute_type':'int8_float16'}
        recognize(Model,'installed','voice.wav',3,lambda *a:None,model_options=options)
        with patch.dict('sys.modules',{'faster_whisper':SimpleNamespace(WhisperModel=Model),'faster_whisper.tokenizer':SimpleNamespace(Tokenizer=lambda *a,**kw:None)}):
            WhisperScriptAligner('installed',**options)
        self.assertEqual([c['device'] for c in calls],['cuda','cuda'])
        self.assertEqual([c['compute_type'] for c in calls],['int8_float16','int8_float16'])
        self.assertTrue(all(c['num_workers']==1 and c['local_files_only'] for c in calls))

    def test_selected_cuda_has_no_silent_cpu_fallback(self):
        from hinglish_app.caption_compute import options_for
        with tempfile.TemporaryDirectory(dir='tmp') as tmp:
            root=Path(tmp);(root/'config.caption-native.local.json').write_text(json.dumps({'device':'cuda','compute_type':'int8_float16'}))
            self.assertEqual(options_for(root),{'device':'cuda','compute_type':'int8_float16'})
            (root/'config.caption-native.local.json').write_text(json.dumps({'device':'invalid'}))
            with self.assertRaises(ValueError):options_for(root)
