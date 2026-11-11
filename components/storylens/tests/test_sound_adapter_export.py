import unittest,importlib.util,copy
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
class AdapterExportTests(unittest.TestCase):
    def test_converter_metadata_preserves_architecture_and_original(self):
        spec=importlib.util.spec_from_file_location('adapter_export',ROOT/'tools/sound_training/export_adapter.py')
        m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
        src={'model_type':'qwen3','hidden_size':5120,'quantization_config':{'quant_method':'bitsandbytes'}};before=copy.deepcopy(src)
        result=m.adapter_base_config(src)
        self.assertEqual(src,before)
        self.assertNotIn('quantization_config',result)
        self.assertEqual(result['hidden_size'],5120)
        with self.assertRaises(ValueError):m.adapter_base_config({'model_type':'different'})
if __name__=='__main__':unittest.main()
