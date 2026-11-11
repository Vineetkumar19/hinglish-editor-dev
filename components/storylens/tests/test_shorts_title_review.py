import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock,patch

from hinglish_shorts.title_review import review,ensure_project,spoken_years,short_heading


class TitleReviewTests(unittest.TestCase):
    def test_live_saha_misspelling_is_rejected_until_local_model_resolves_it(self):
        brain=Mock()
        brain.json.side_effect=[
            {'titles':[{'index':1,'title':'Reddimaan Saha Career Best Performance','reason':'ASR spelling'}]},
            {'titles':[{'index':1,'title':'Wriddhiman Saha Career Best Performance','reason':'Canonical name supported by the speech'}]}]
        result=review(brain,[{'index':1,'title':'Reddimaan Saha Career Best Performance',
            'text':'Reddimaan Saha ne apni career best performance di'}],lambda _:None)
        self.assertEqual(result[1]['title'],'Wriddhiman Saha Career Best Performance')
        self.assertEqual(brain.json.call_count,2)
        self.assertTrue(brain.json.call_args.args[1]['spelling_checks'][0]['candidates'])

    def test_evidence_and_indices_reach_local_model_without_changing_moments(self):
        brain=Mock();brain.json.return_value={'titles':[{'index':1,'title':'RCB Finals Heartbreak','reason':'The speech says do hazaar nau and solah, not 2019.'}]}
        item={'index':1,'title':'RCB 2019 Final Collapse','text':'Do hazaar nau aur do hazaar solah final haar gai.','pieces':[[4,20]]}
        result=review(brain,[item],lambda _:None)
        self.assertEqual(result[1]['title'],'RCB Finals Heartbreak')
        self.assertEqual(brain.json.call_args.args[1]['clips'][0]['text'],item['text'])
        self.assertNotIn('pieces',brain.json.call_args.args[1]['clips'][0])
        self.assertEqual(item['title'],'RCB 2019 Final Collapse')

    def test_missing_or_duplicate_indices_fail_closed(self):
        brain=Mock();brain.json.return_value={'titles':[{'index':9,'title':'Wrong clip title'}]}
        with self.assertRaisesRegex(ValueError,'could not validate'):
            review(brain,[{'index':1,'title':'Actual title','text':'Evidence'}],lambda _:None)
        self.assertEqual(brain.json.call_count,2)

    def test_hindi_year_evidence_rejects_a_hallucinated_title_year(self):
        self.assertEqual(spoken_years('Do hazaar nau aur do hazaar solah final.'),{'2009','2016'})
        brain=Mock();brain.json.side_effect=[
            {'titles':[{'index':1,'title':'RCB 2019 final collapse','reason':'wrong'}]},
            {'titles':[{'index':1,'title':'RCB finals heartbreak','reason':'neutral supported title'}]}]
        result=review(brain,[{'index':1,'title':'RCB 2019 final collapse','text':'Do hazaar nau aur do hazaar solah final.'}],lambda _:None)
        self.assertEqual(result[1]['title'],'RCB finals heartbreak');self.assertEqual(brain.json.call_count,2)

    def test_supported_title_is_saved_once_without_re_rendering(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'shorts-project.json';path.write_text(json.dumps({'shorts':[{'index':1,'title':'Actual title','text':'Evidence','mp4':'clip.mp4'}]}))
            brain=Mock();brain.name='local14b';brain.json.return_value={'titles':[{'index':1,'title':'Actual title','reason':'Supported'}]}
            with patch('hinglish_visuals.brain.open_brain',return_value=brain),patch('hinglish_shorts.pipeline.rebuild_project') as rebuild:
                ensure_project(folder,path,lambda _:None);ensure_project(folder,path,lambda _:None)
            rebuild.assert_not_called();self.assertEqual(brain.json.call_count,1)
            self.assertEqual(json.loads(path.read_text())['title_review']['model'],'local14b')
            self.assertEqual(path.with_name('clip.txt').read_text(),'Evidence')

    def test_local_model_must_shorten_heading_to_seven_words_without_truncation(self):
        original='Rohit Sharma achieved in 10 years what Dhoni took 16'
        brain=Mock();brain.json.side_effect=[
            {'words':['Rohit','Sharma’s','Rapid','Rise']},
            {'titles':[{'index':1,'title':original,'reason':'Too long'}]},
            {'titles':[{'index':1,'title':'Rohit Sharma’s Rapid Rise','reason':'Concise supported topic'}]}]
        answer=review(brain,[{'index':1,'title':original,'text':'Rohit Sharma achieved it in das saal.'}],lambda _:None)
        self.assertLessEqual(len(answer[1]['title'].split()),7)
        self.assertIn('AT MOST SEVEN WORDS',brain.json.call_args.args[1]['validation_error'])

    def test_title_layout_preserves_all_words_and_prefers_one_line(self):
        from PIL import Image,ImageDraw
        from hinglish_shorts.render import _title_font
        draw=ImageDraw.Draw(Image.new('RGB',(1080,1920)))
        for text in ('ROHIT SHARMA’S RAPID RISE','MUMBAI INDIANS WIN A MEMORABLE FINAL'):
            font,lines=_title_font(draw,text,824)
            self.assertEqual(' '.join(lines),text)
            self.assertLessEqual(len(lines),2)
            self.assertTrue(all(draw.textlength(line,font=font)<=824 for line in lines))

    def test_word_budget_writer_rejects_dangling_or_embedded_words_instead_of_cropping(self):
        brain=Mock();brain.json.side_effect=[{'words':['Rohit','Sharma','achieves','what']},
            {'words':['Rohit','Sharma’s','Rapid','Rise']}]
        self.assertEqual(short_heading(brain,'Rohit ne das saal mein kiya.',set(),lambda _:None),'Rohit Sharma’s Rapid Rise')
        self.assertEqual(brain.json.call_args.args[2]['properties']['words']['maxItems'],6)
        self.assertNotIn('title',brain.json.call_args.args[1])


if __name__=='__main__':unittest.main()
