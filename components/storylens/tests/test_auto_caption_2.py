import json
from pathlib import Path
import unittest
from concurrent.futures import ThreadPoolExecutor
from tempfile import TemporaryDirectory

from hinglish_captions.auto_caption import validated_plan, validate, references, black_canvas_colors, profile_for, save
from hinglish_captions.script_preview import script_cues

ROOT=Path(__file__).resolve().parents[1]


class LocalCaptionPlanTests(unittest.TestCase):
    def test_original_caption_data_is_retrieved_without_rewriting_script(self):
        from hinglish_captions.shared_knowledge import for_script
        text='Karen Pollard scored 250 for Mumbai Indies'
        pack=for_script(ROOT,text,profile_for('caption_2'))
        self.assertGreater(pack['receipt']['available_entities'],100)
        self.assertIn('Kieron Pollard',pack['context']['entities'])
        self.assertTrue(any(r['heard']=='Karen Pollard' for r in pack['context']['recognition_examples']))
        self.assertEqual(text,'Karen Pollard scored 250 for Mumbai Indies')
        self.assertEqual({Path(s['path']).name for s in pack['receipt']['sources']},
                         {'references.json','cricket_vocabulary.json','creative_recipes.json'})
        self.assertTrue(all(len(s['sha256']) == 64 for s in pack['receipt']['sources']))
        self.assertTrue(pack['context']['creative_design_guidance']['design'])
        self.assertTrue(pack['context']['selected_style_examples'])

    def test_unrelated_caption_script_does_not_receive_cricket_entities(self):
        from hinglish_captions.shared_knowledge import for_script
        pack=for_script(ROOT,'Build extraordinary stories today',profile_for('caption_2'))
        self.assertEqual(pack['context']['entities'],[])
        self.assertEqual(pack['context']['recognition_examples'],[])

    def test_progress_updates_are_atomic_during_reads(self):
        with TemporaryDirectory(dir=ROOT/'tmp') as directory:
            file=Path(directory)/'status.json';save(file,{'index':0})
            def write():
                for i in range(30):save(file,{'index':i})
            def read():
                for _ in range(200):self.assertIn('index',json.loads(file.read_text('utf-8')))
            with ThreadPoolExecutor(max_workers=3) as pool:
                jobs=[pool.submit(write),pool.submit(read),pool.submit(read)]
                for job in jobs:job.result()

    def test_missing_repeated_and_reordered_words_rejected(self):
        tokens='I saved 250 rupees today'.split();recipes=[{'text':'A caption'}]
        for groups in ([{'start':1,'end':5,'recipe':0}],
                       [{'start':0,'end':3,'recipe':0},{'start':2,'end':5,'recipe':0}],
                       [{'start':0,'end':4,'recipe':0}],
                       [{'start':0,'end':5,'recipe':99}]):
            with self.subTest(groups=groups),self.assertRaises(ValueError):
                validated_plan({'groups':groups},tokens,recipes)

    def test_exact_numbers_and_long_words_stay_in_order(self):
        tokens='We saved 25,000 through extraordinary consistency today'.split()
        plan={'groups':[{'start':0,'end':3,'recipe':0},{'start':3,'end':7,'recipe':1}]}
        groups=validated_plan(plan,tokens,[{'text':'A 10'},{'text':'consistent work'}])
        self.assertEqual([w for g in groups for w in tokens[g['start']:g['end']]],tokens)

    def test_six_words_and_boolean_indices_rejected(self):
        for group in ({'start':0,'end':6,'recipe':0},{'start':False,'end':5,'recipe':0}):
            with self.subTest(group=group),self.assertRaises(ValueError):
                validated_plan({'groups':[group]},list('abcdef'),[{'text':'x'}])

    def test_invalid_duration_and_empty_text_fail_before_inference(self):
        for text,duration in [('',10),('hello',float('nan')),('hello',True),('hello',200)]:
            with self.subTest(text=text,duration=duration),self.assertRaises(ValueError):
                validate(ROOT,{'style':'caption_2','text':text,'duration':duration})

    def test_all_mapped_reference_files_exist(self):
        self.assertGreaterEqual(len(references(ROOT)),7)
        self.assertTrue(all(r['available'] for r in references(ROOT)))

    def test_generation_method_is_explicit_and_validated(self):
        settings,_=validate(ROOT,{'style':'caption_2','text':'Default generation uses Hyperframes'})
        self.assertEqual(settings['method'],'hyperframes')
        for method in ('local_llm','hyperframes'):
            settings,_=validate(ROOT,{'style':'caption_2','text':'Try a different design','method':method})
            self.assertEqual(settings['method'],method)
        with self.assertRaises(ValueError):validate(ROOT,{'text':'hello','method':'unknown'})

    def test_black_canvas_keeps_colored_caption_five_hero(self):
        cues=script_cues('Imagine a MONUMENT',10,'caption_5')
        colors=black_canvas_colors(cues,'caption_5',profile_for('caption_5'))
        self.assertTrue(any(value=='#FFFFFF' for row in colors for value in row))
        self.assertTrue(any(value is None for row in colors for value in row))


if __name__=='__main__':unittest.main()
