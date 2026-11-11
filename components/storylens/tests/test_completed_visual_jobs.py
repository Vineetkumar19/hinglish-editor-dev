"""Durability of actual completed-job receipts, using isolated file fixtures."""
import copy
import json
from pathlib import Path
import tempfile
import unittest


class CompletedVisualJobsTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(dir='cache');self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name).resolve();self.folder=self.root/'output/visuals/job/project';self.folder.mkdir(parents=True)
        (self.folder/'report.html').write_text('Synthetic report')
        (self.folder/'visuals-project.json').write_text(json.dumps({'timeline':{'name':'Exact source'},'slots':[]}))
        self.job={'id':'actual-job','mode':'visuals','status':'complete','created':12,'progress':100,
            'result':{'folder':str(self.folder),'page':str(self.folder/'report.html')},'payload':{'not_for_receipt':'private'}}

    def test_completed_receipt_reopens_on_same_port_without_rerunning_any_job(self):
        from hinglish_app.completed_visual_jobs import save,load,results
        save(self.root,8765,self.job);jobs=load(self.root,8765)
        self.assertEqual(jobs['actual-job']['result'],self.job['result']);self.assertNotIn('payload',jobs['actual-job'])
        rows=results(self.root,jobs.values());self.assertEqual(rows[0]['job_id'],'actual-job')
        self.assertEqual(rows[0]['project_path'],str(self.folder/'visuals-project.json'))
        self.assertEqual(rows[0]['name'],'Exact source')
        self.assertEqual(load(self.root,8766),{})

    def test_failed_running_or_foreign_receipts_cannot_be_restored_as_completed(self):
        from hinglish_app.completed_visual_jobs import save,load
        for status in ('failed','running','queued'):
            self.assertFalse(save(self.root,8765,{**self.job,'status':status}))
        foreign=copy.deepcopy(self.job);foreign['result']['folder']=str(self.root)
        self.assertFalse(save(self.root,8765,foreign));self.assertEqual(load(self.root,8765),{})

    def test_relinked_result_page_outside_job_is_rejected_after_restart(self):
        from hinglish_app.completed_visual_jobs import save,load
        save(self.root,8765,self.job)
        (self.folder/'report.html').unlink()
        self.assertEqual(load(self.root,8765),{})

