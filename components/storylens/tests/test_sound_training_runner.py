import importlib.util
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
class Tokenizer:
    eos_token='<eos>'
    def apply_chat_template(self,messages,**kwargs):return 'PROMPT:'+messages[-1]['content']+'\nASSISTANT:'
    def encode(self,text,**kwargs):return [ord(c) for c in text]

class RunnerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        spec=importlib.util.spec_from_file_location('runner',ROOT/'tools/sound_training/train.py')
        cls.m=importlib.util.module_from_spec(spec);spec.loader.exec_module(cls.m)
    def row(self):return {'id':'a','messages':[{'role':'system','content':'rules'},{'role':'user','content':'scene'},{'role':'assistant','content':'answer'}]}
    def test_prompt_tokens_are_masked(self):
        r=self.m.encode_record(self.row(),Tokenizer(),100)
        self.assertEqual(sum(v!=-100 for v in r['labels']),len('answer<eos>'))
        self.assertTrue(all(v==-100 for v in r['labels'][:-len('answer<eos>')]))
    def test_long_rows_are_not_truncated(self):
        with self.assertRaises(ValueError):self.m.encode_record(self.row(),Tokenizer(),10)
    def test_target_required(self):
        r=self.row();r['messages'][-1]['content']=''
        with self.assertRaises(ValueError):self.m.encode_record(r,Tokenizer(),100)
    def test_wrong_role_rejected(self):
        r=self.row();r['messages'][-1]['role']='user'
        with self.assertRaises(ValueError):self.m.encode_record(r,Tokenizer(),100)
    def test_dataset_cannot_overlap_eval(self):
        with self.assertRaises(ValueError):self.m.validate_split([self.row()],[self.row()])
    def test_target_loss_must_be_finite(self):
        with self.assertRaises(ValueError):self.m.checked_loss(float('nan'))
    def test_config_has_small_batch_and_no_live_deployment(self):
        c=self.m.DEFAULTS
        self.assertEqual(c['per_device_train_batch_size'],1)
        self.assertFalse(c['auto_deploy'])
        self.assertFalse(c['full_finetuning'])
    def test_revision_settings_are_bounded_and_do_not_overwrite_first_run(self):
        with self.assertRaises(ValueError):self.m.configure(ROOT/'output/sound-training/revision-test',epochs=0,learning_rate=1e-5)
        with self.assertRaises(ValueError):self.m.configure(ROOT/'output/sound-training/revision-test',epochs=1,learning_rate=.1)
        with self.assertRaises(ValueError):self.m.configure(ROOT/'outside-training',epochs=1,learning_rate=1e-5)
        self.m.configure(ROOT/'output/sound-training/revision-test',epochs=1,learning_rate=1e-5)
        self.assertEqual(self.m.OUT.name,'revision-test')
        self.assertEqual(self.m.DEFAULTS['learning_rate'],1e-5)

if __name__=='__main__':unittest.main()
