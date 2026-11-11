from dataclasses import asdict
from types import SimpleNamespace
import unittest
from unittest.mock import Mock,patch

from hinglish_cut.model import Word
from hinglish_captions.core import CaptionWord
from hinglish_captions.numbers import digits
from hinglish_captions.proofread import review,selected


def words(text,kind=Word):
    return [kind(t,i*.2,i*.2+.18) for i,t in enumerate(text.split())]


class CaptionNormalizationTests(unittest.TestCase):
    def test_hindi_english_scores_years_and_units_keep_language(self):
        examples={'sola saal':'16 saal','solah years':'16 years',
            'usne ek sau pachis banaya':'usne 125 banaya',
            'one hundred and twenty five runs':'125 runs',
            'one hundred twenty-five runs':'125 runs',
            'do hazaar terah mein':'2013 mein',
            'two thousand thirteen mein':'2013 mein',
            'paanch sau bees runs':'520 runs','सोलह साल':'16 साल',
            'उसने एक सौ पच्चीस बनाया':'उसने 125 बनाया',
            'दो साल':'2 साल','बीस रन':'20 रन',
            'ek lakh bees hazaar pachis':'120025',
            'scored 125 runs':'scored 125 runs'}
        for source,expected in examples.items():
            with self.subTest(source=source):self.assertEqual(' '.join(w.text for w in digits(words(source))),expected)

    def test_number_span_preserves_punctuation_and_union_timing(self):
        original=words('He scored (one hundred twenty five), runs.',CaptionWord)
        before=[asdict(w) for w in original];result=digits(original)
        self.assertEqual(result[2].text,'(125),')
        self.assertEqual((result[2].start,result[2].end),(original[2].start,original[5].end))
        self.assertEqual([asdict(w) for w in original],before)

    def test_ambiguous_words_and_separate_quantities_are_not_summed(self):
        for text in ('do it now','ek baat suno','teen drama','saath khelo','char value'):
            self.assertEqual(' '.join(w.text for w in digits(words(text))),text)
        self.assertEqual(' '.join(w.text for w in digits(words('twenty, five wickets'))),'20, 5 wickets')
        separated=[Word('one',0,.2),Word('hundred',1.5,1.8)]
        self.assertEqual([w.text for w in digits(separated)],['1','100'])

    def test_shorts_use_digits_on_the_output_clock(self):
        from hinglish_shorts.render import caption_cues
        source=[Word('sola',10,10.3),Word('saal',10.31,10.6)]
        cues=caption_cues(source,[(10,11)])
        self.assertEqual(cues[0].text,'16 saal');self.assertEqual(cues[0].words[0].start,0)
        source=[Word('one',10,10.3),Word('hundred',20,20.3)]
        cues=caption_cues(source,[(10,10.4),(20,20.4)])
        self.assertEqual([w.text for cue in cues for w in cue.words],['1','100'])

    def test_local_spelling_review_preserves_numbers_language_and_timings(self):
        original=words('Rohitt ne sola saal khela')
        brain=Mock();brain.json.return_value={'corrections':[
            {'index':0,'before':'Rohitt','after':'Rohit'},
            {'index':2,'before':'sola','after':'seventeen'},
            {'index':3,'before':'saal','after':'years'},
            {'index':4,'before':'wrong','after':'played'}]}
        result,changes=review(brain,original,lambda _:None)
        self.assertEqual([w.text for w in result],['Rohit','ne','sola','saal','khela'])
        self.assertEqual(len(changes),1)
        self.assertEqual([(w.start,w.end) for w in result],[(w.start,w.end) for w in original])
        self.assertEqual(original[0].text,'Rohitt')

    def test_only_selected_clip_words_go_to_proofreader_and_invalid_response_keeps_original(self):
        original=words('unselected words Rohitt plays')
        brain=Mock();brain.json.return_value={'corrections':[{'index':0,'before':'Rohitt','after':'Rohit'}]}
        result,_=selected(brain,original,[SimpleNamespace(pieces=[(.4,.8)])],lambda _:None)
        self.assertEqual([w.text for w in result],['unselected','words','Rohit','plays'])
        self.assertEqual(len(brain.json.call_args.args[1]['words']),2)
        brain.json.side_effect=RuntimeError('Offline model unavailable')
        result,changes=review(brain,original,lambda _:None)
        self.assertEqual(result,original);self.assertFalse(changes)

    def test_legacy_project_refreshes_caption_layer_once_without_selecting_new_moments(self):
        import json
        import tempfile
        from pathlib import Path
        from hinglish_captions.proofread import ensure_project
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'shorts-project.json'
            project={'settings':{'captions':True},'words':[['Rohitt',0,.3],['sola',.3,.6],['saal',.6,.9]],
                     'shorts':[{'index':1,'pieces':[[0,1]],'mp4':'short.mp4'}]}
            path.write_text(json.dumps(project),'utf-8')
            brain=Mock();brain.name='local 14B fixture'
            brain.json.return_value={'corrections':[{'index':0,'before':'Rohitt','after':'Rohit'}]}
            with patch('hinglish_visuals.brain.open_brain',return_value=brain),\
                 patch('hinglish_shorts.pipeline.rebuild_project') as rebuild:
                ensure_project(Path(folder),path,lambda _:None)
                ensure_project(Path(folder),path,lambda _:None)
            rebuild.assert_called_once();brain.json.assert_called_once()
            changes=rebuild.call_args.args[1]
            self.assertTrue(changes['refresh_captions'])
            self.assertEqual(changes['shorts'],project['shorts'])
            self.assertEqual(changes['caption_words'][0],['Rohit',0,.3])


if __name__=='__main__':unittest.main()
