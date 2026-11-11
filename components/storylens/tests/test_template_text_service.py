import json
from pathlib import Path
import tempfile
import unittest
import shutil
from contextlib import contextmanager
from unittest.mock import patch
from hinglish_app.template_text import TemplateTextJobs,save
from test_template_text import snapshot

TEST_ROOT=(Path(__file__).resolve().parents[1]/'output/template-text-evidence/test-work').resolve()
TEST_ROOT.mkdir(parents=True,exist_ok=True)
@contextmanager
def workspace_temp():
    folder=Path(tempfile.mkdtemp(dir=TEST_ROOT)).resolve()
    try:yield str(folder)
    finally:
        if not folder.is_relative_to(TEST_ROOT):raise RuntimeError('Refusing cleanup outside this test workspace.')
        shutil.rmtree(folder)

class Process:
    pid=900001
    def __init__(self,*a,**kw):self.returncode=None;self.terminated=False
    def poll(self):return self.returncode
    def terminate(self):self.terminated=True;self.returncode=-1

class TemplateTextServiceTests(unittest.TestCase):
    def test_scan_plan_receipt_roundtrip_keeps_project_guard(self):
        with workspace_temp() as temp,patch('hinglish_app.template_text.subprocess.Popen',Process):
            jobs=TemplateTextJobs(temp);job=jobs.start({'script':'Mumbai won in 2020','snapshot':snapshot()});folder=jobs.folder(job['id'])
            plan={'job_id':job['id'],'project_id':'owner.aep','composition_id':'42','fingerprint':'native-1','actions':[]};save(folder/'plan.json',plan);save(folder/'status.json',{**job,'status':'ready'})
            self.assertEqual(jobs.plan(job['id']),plan)
            with self.assertRaises(ValueError):jobs.accept(job['id'],{'ok':True,'job_id':job['id'],'project_id':'other.aep','composition_id':'42'})
            result=jobs.accept(job['id'],{'ok':True,'job_id':job['id'],'project_id':'owner.aep','composition_id':'42','changed':1,'hidden':1});self.assertEqual(result['status'],'applied');self.assertTrue((folder/'native-receipt.json').exists())
    def test_same_pending_request_reuses_job_instead_of_launching_twice(self):
        with workspace_temp() as temp,patch('hinglish_app.template_text.subprocess.Popen',Process):
            jobs=TemplateTextJobs(temp);request={'script':'Mumbai won','snapshot':snapshot()};first=jobs.start(request);second=jobs.start(request);self.assertEqual(first['id'],second['id']);self.assertEqual(len(jobs.processes),1)
    def test_stop_only_terminates_its_own_worker_and_retains_saved_request(self):
        with workspace_temp() as temp,patch('hinglish_app.template_text.subprocess.Popen',Process):
            jobs=TemplateTextJobs(temp);job=jobs.start({'script':'Mumbai won','snapshot':snapshot()});self.assertEqual(jobs.cancel(job['id'])['status'],'cancelled');self.assertTrue(jobs.processes[job['id']].terminated);self.assertTrue((jobs.folder(job['id'])/'request.json').exists())
            with self.assertRaises(ValueError):jobs.plan(job['id'])
    def test_second_distinct_running_pass_refuses_before_new_worker(self):
        with workspace_temp() as temp,patch('hinglish_app.template_text.subprocess.Popen',Process):
            jobs=TemplateTextJobs(temp);jobs.start({'script':'Mumbai won','snapshot':snapshot()})
            with self.assertRaises(ValueError):jobs.start({'script':'Chennai won','snapshot':snapshot()})
            self.assertEqual(len(jobs.processes),1)
    def test_missing_script_never_launches_worker_or_creates_job(self):
        with workspace_temp() as temp,patch('hinglish_app.template_text.subprocess.Popen') as spawn:
            jobs=TemplateTextJobs(temp)
            with self.assertRaises(ValueError):jobs.start({'script':'','snapshot':snapshot()})
            spawn.assert_not_called();self.assertFalse(jobs.base.exists())
    def test_path_traversal_does_not_read_foreign_job(self):
        with workspace_temp() as temp:
            with self.assertRaises(ValueError):TemplateTextJobs(temp).snapshot('../owner')

if __name__=='__main__':unittest.main()
