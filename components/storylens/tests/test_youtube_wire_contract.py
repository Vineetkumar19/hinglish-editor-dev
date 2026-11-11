"""Exercise the real queue payload through the JS worker and Studio DOM fixture."""
from datetime import datetime,timedelta,timezone
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from hinglish_publish.local_browser import LocalBrowser

CHANNEL='UC'+'g'*22
ROOT=Path(__file__).resolve().parents[1]
DRIVER="""
const fs=require('node:fs');
const {fixture}=require('./tests/fixtures/youtube_dom_fixture.cjs');
const wire=JSON.parse(fs.readFileSync(0,'utf8'));
const f=fixture({wireJob:wire,visibility:'Scheduled',wrongDate:true,wrongTime:true});
f.runWorker().then(results=>process.stdout.write(JSON.stringify({results,commits:f.commits()})))
 .catch(e=>{process.stderr.write(e.message);process.exitCode=1});
"""


class WireTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.bridge=LocalBrowser(Path(self.temp.name))
        self.due=(datetime.now(timezone.utc)+timedelta(days=40)).isoformat()

    def test_replacement_flag_survives_json_and_old_workers_cannot_claim(self):
        saved=self.bridge.enqueue_youtube(CHANNEL,'new00000001',self.due,'s',authorized=True,allow_reschedule=True)
        self.assertIsNone(self.bridge.claim('0.4.6',['youtube_schedule'])['job'])
        wire=json.loads(json.dumps(self.bridge.claim('0.4.7',['youtube_schedule'])['job']))
        self.assertIs(wire['allow_reschedule'],True)
        self.assertEqual(wire['id'],saved['id'])
        self.assertEqual(set(wire),{'id','action','channel_id','video_id','publish_at','lease','allow_reschedule',
            'channel_name','video_kind','publish_now','recover_before_submit'})
        self.assertEqual(wire['video_kind'],'short')
        self.assertIs(wire['publish_now'],False)
        self.assertIs(wire['recover_before_submit'],False)

    def test_legacy_jobs_default_to_no_schedule_replacement(self):
        saved=self.bridge.enqueue_youtube(CHANNEL,'new00000001',self.due,'s',authorized=True)
        del self.bridge.data['jobs'][0]['allow_reschedule']
        wire=self.bridge.claim('0.4.7',['youtube_schedule'])['job']
        self.assertIs(wire['allow_reschedule'],False)
        self.assertEqual(wire['id'],saved['id'])

    @unittest.skipUnless(shutil.which('node'),'Node is needed for the cross-language wire contract')
    def test_serialized_real_queue_tasks_reschedule_through_worker_and_dom(self):
        for due in ('2031-12-31T19:30:00+05:30','2032-02-29T00:05:00+05:30','2035-07-09T18:10:00+05:30'):
            with self.subTest(due=due):
                saved=self.bridge.enqueue_youtube(CHANNEL,'new00000001',due,'s',authorized=True,allow_reschedule=True)
                wire=self.bridge.claim('0.4.7',['youtube_schedule'])['job']
                self.assertEqual(wire['id'],saved['id'])
                proc=subprocess.run(['node','-e',DRIVER],cwd=ROOT,input=json.dumps(wire),
                                    text=True,capture_output=True,timeout=20)
                self.assertEqual(proc.returncode,0,proc.stderr)
                result=json.loads(proc.stdout)
                self.assertEqual(result['commits'],1)
                receipt=result['results'][0]
                self.assertEqual(receipt['publish_at'],saved['publish_at'])
                self.assertEqual(receipt['video_id'],saved['video_id'])
                self.bridge.phase(wire['id'],wire['lease'],'sharing')
                self.assertEqual(self.bridge.finish(wire['id'],wire['lease'],receipt)['status'],'submitted')

    @unittest.skipUnless(shutil.which('node'),'Node is needed for the cross-language wire contract')
    def test_serialized_task_without_replacement_authority_cannot_reschedule(self):
        self.bridge.enqueue_youtube(CHANNEL,'new00000001',self.due,'s',authorized=True)
        wire=self.bridge.claim('0.4.7',['youtube_schedule'])['job']
        proc=subprocess.run(['node','-e',DRIVER],cwd=ROOT,input=json.dumps(wire),
                            text=True,capture_output=True,timeout=20)
        self.assertNotEqual(proc.returncode,0)
        self.assertIn('explicit date change is required',proc.stderr)


if __name__=='__main__':unittest.main()
