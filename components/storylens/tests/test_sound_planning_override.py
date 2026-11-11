import json,tempfile,unittest
from pathlib import Path
from hinglish_sound.recommendation_pipeline import sound_model_names

class SoundPlanningOverrideTests(unittest.TestCase):
    def test_sound_override_does_not_replace_vision_or_global_config(self):
        config=dict(planning_model='base:14b',vision_model='vision:9b',embedding_model='embed:8b')
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            self.assertEqual(sound_model_names(root,config)['planning'],'base:14b')
            (root/'config.sound.local.json').write_text(json.dumps(dict(think_model='trained-sound:14b')))
            result=sound_model_names(root,config)
            self.assertEqual(result,dict(planning='trained-sound:14b',vision='vision:9b',embedding='embed:8b'))
            self.assertEqual(config['planning_model'],'base:14b')
            (root/'config.sound.local.json').write_text(json.dumps(dict(think_model='qwen3:8b')))
            self.assertEqual(sound_model_names(root,config)['planning'],'base:14b')

    def test_remote_or_blank_override_is_rejected(self):
        config=dict(planning_model='base:14b',vision_model='vision:9b',embedding_model='embed:8b')
        with tempfile.TemporaryDirectory() as temp:
            for name in ['', 'anything:cloud','http://example.com/model']:
                root=Path(temp);(root/'config.sound.local.json').write_text(json.dumps(dict(think_model=name)))
                with self.assertRaises(ValueError):sound_model_names(root,config)
