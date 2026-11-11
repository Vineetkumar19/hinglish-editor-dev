import json
import tempfile
import unittest
from pathlib import Path
from tools.sound_training import continuation


class ContinuationTests(unittest.TestCase):
    def test_parent_must_match_base_rank_and_targets_and_stay_separate(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder); parent=root/'parent'; parent.mkdir(); output=root/'child'
            config=dict(base_model_name_or_path=str(root/'base'),peft_type='LORA',r=8,lora_alpha=16,
                        target_modules=['q_proj','k_proj','v_proj','o_proj'],bias='none')
            (parent/'adapter_config.json').write_text(json.dumps(config))
            (parent/'adapter_model.safetensors').write_bytes(b'fixture-not-loaded')
            receipt=continuation.validate_parent(parent,output,root/'base',8,16)
            self.assertEqual(len(receipt['sha256']),64)
            with self.assertRaises(ValueError):continuation.validate_parent(parent,parent,root/'base',8,16)
            with self.assertRaises(ValueError):continuation.validate_parent(parent,output,root/'other-base',8,16)
            with self.assertRaises(ValueError):continuation.validate_parent(parent,output,root/'base',16,16)
            config['target_modules'].append('lm_head')
            (parent/'adapter_config.json').write_text(json.dumps(config))
            with self.assertRaises(ValueError):continuation.validate_parent(parent,output,root/'base',8,16)

    def test_only_complete_finite_matching_lora_tensors_are_accepted(self):
        import torch
        expected={'layer.lora_A.weight':torch.ones(2,3),'layer.lora_B.weight':torch.ones(3,2)}
        continuation.validate_weights(expected,expected)
        with self.assertRaises(ValueError):continuation.validate_weights(expected,{'layer.lora_A.weight':torch.ones(2,3)})
        with self.assertRaises(ValueError):continuation.validate_weights(expected,{**expected,'lm_head.weight':torch.ones(1)})
        with self.assertRaises(ValueError):continuation.validate_weights(expected,{**expected,'layer.lora_A.weight':torch.ones(1,3)})
        with self.assertRaises(ValueError):continuation.validate_weights(expected,{**expected,'layer.lora_A.weight':torch.full((2,3),float('nan'))})
