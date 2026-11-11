"""A completed human-choice bank is evaluated once, never auto-regenerated."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock,patch

from hinglish_eval.runner import run
from hinglish_eval.specs import Check,Evaluation


class ReviewRunnerTests(unittest.TestCase):
    def test_review_shortfall_keeps_failed_quality_report_without_repeated_worker(self):
        base=Path(__file__).resolve().parents[1]/'cache/test-review-runner'
        base.mkdir(parents=True,exist_ok=True)
        with tempfile.TemporaryDirectory(dir=base) as folder:
            root=Path(folder);result=root/'output/review/report.html';result.parent.mkdir(parents=True);result.write_text('fixture review')
            check=Check('coverage','Enough moments',False,hard=True,value='2/10',fix={'broll':{'count_scale':1.2}})
            evaluation=Evaluation('broll',str(result.parent),[check])
            process=Mock(stdout=[f'Results: {result}\n']);process.wait.return_value=0
            with patch('hinglish_eval.runner.subprocess.Popen',return_value=process) as start, \
                 patch('hinglish_eval.runner.evaluate',return_value=[evaluation]), \
                 patch('hinglish_eval.runner.write_report',return_value=result.parent/'quality-check.html'):
                returned=run(root,['-m','hinglish_broll','--review-options'],attempts=3,progress=lambda _:None)
            self.assertEqual(returned,result)
            self.assertEqual(start.call_count,1)
            report=json.loads((result.parent/'quality-check.json').read_text('utf-8'))
            self.assertEqual(len(report['attempts']),1)
            self.assertFalse(report['attempts'][0]['evaluations'][0]['passed'])
            with patch('hinglish_eval.runner.subprocess.Popen',return_value=process) as start, \
                 patch('hinglish_eval.runner.evaluate',return_value=[evaluation]), \
                 patch('hinglish_eval.runner.write_report',return_value=result.parent/'quality-check.html'):
                run(root,['-m','hinglish_broll'],attempts=3,progress=lambda _:None)
            self.assertEqual(start.call_count,3,'Ordinary automatic B-roll edits keep their existing correction attempts.')


if __name__=='__main__':unittest.main()
