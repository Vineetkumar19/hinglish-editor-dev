import json
import struct
import tempfile
import unittest
from pathlib import Path

from tools.aigen.worker import complete, complete_weight


def weight(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    header = json.dumps({'tensor': {'dtype': 'F32', 'shape': [1], 'data_offsets': [0, 4]}}).encode()
    path.write_bytes(len(header).to_bytes(8, 'little') + header + struct.pack('<f', 1.0))


def pipeline(folder):
    (folder / 'model_index.json').write_text(json.dumps({
        name: ['diffusers', 'Model'] for name in ('text_encoder', 'transformer', 'vae')}))
    for name in ('text_encoder', 'transformer', 'vae', 'scheduler', 'tokenizer'):
        (folder / name).mkdir()
    (folder / 'scheduler/scheduler_config.json').write_text('{}')
    (folder / 'tokenizer/tokenizer_config.json').write_text('{}')
    (folder / 'tokenizer/spiece.model').write_bytes(b'fixture')
    for name in ('text_encoder', 'transformer', 'vae'):
        (folder / name / 'config.json').write_text('{}')
        prefix = 'model' if name == 'text_encoder' else 'diffusion_pytorch_model'
        weight(folder / name / (prefix + '.safetensors'))


class ModelFilesTests(unittest.TestCase):
    def test_complete_pipeline_and_truncated_weight(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            pipeline(folder)
            self.assertTrue(complete(folder))
            path = folder / 'vae/diffusion_pytorch_model.safetensors'
            path.write_bytes(path.read_bytes()[:-1])
            self.assertFalse(complete_weight(path))
            self.assertFalse(complete(folder))

    def test_every_indexed_shard_is_required(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            pipeline(folder)
            component = folder / 'transformer'
            (component / 'diffusion_pytorch_model.safetensors.index.json').write_text(json.dumps({
                'weight_map': {'a': 'part-1.safetensors', 'b': 'part-2.safetensors'}}))
            weight(component / 'part-1.safetensors')
            self.assertFalse(complete(folder))
            weight(component / 'part-2.safetensors')
            self.assertTrue(complete(folder))

    def test_incomplete_download_and_missing_tokenizer_block_readiness(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            pipeline(folder)
            partial = folder / '.cache/huggingface/download/weights.incomplete'
            partial.parent.mkdir(parents=True)
            partial.touch()
            self.assertFalse(complete(folder))
            partial.unlink()
            self.assertTrue(complete(folder))
            (folder / 'tokenizer/spiece.model').unlink()
            self.assertFalse(complete(folder))

    def test_bf16_index_selects_matching_component_weights(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            pipeline(folder)
            (folder / 'transformer/diffusion_pytorch_model.safetensors.index.bf16.json').write_text(
                json.dumps({'weight_map': {'a': 'part.bf16.safetensors'}}))
            weight(folder / 'transformer/part.bf16.safetensors')
            self.assertFalse(complete(folder))
            weight(folder / 'text_encoder/model.bf16.safetensors')
            weight(folder / 'vae/diffusion_pytorch_model.bf16.safetensors')
            self.assertTrue(complete(folder))

    def test_malformed_or_traversing_index_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            pipeline(folder)
            index = folder / 'transformer/diffusion_pytorch_model.safetensors.index.json'
            index.write_text('broken')
            self.assertFalse(complete(folder))
            index.write_text(json.dumps({'weight_map': {'a': '../outside.safetensors'}}))
            self.assertFalse(complete(folder))

    def test_zimage_requires_the_tokenizer_chat_template(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            pipeline(folder)
            model = json.loads((folder / 'model_index.json').read_text())
            model['_class_name'] = 'ZImagePipeline'
            (folder / 'model_index.json').write_text(json.dumps(model))
            self.assertFalse(complete(folder))
            (folder / 'tokenizer/chat_template.jinja').write_text(' ')
            self.assertFalse(complete(folder))
            (folder / 'tokenizer/chat_template.jinja').write_text('{{ messages }}')
            self.assertTrue(complete(folder))


if __name__ == '__main__':
    unittest.main()
