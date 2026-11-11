"""Isolated completed-job/source-bank transport fixtures. No live services."""
import copy
import hashlib
import json
import multiprocessing
import shutil
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from tests import test_visuals_source_bank as fixtures


def _worker(root, job, payload, start, results):
    from hinglish_app.visual_source_transport import VisualSourceTransport
    state = SimpleNamespace(root=Path(root), snapshot=lambda key: copy.deepcopy(job) if key == job['id'] else None)
    start.wait(10)
    try:
        VisualSourceTransport(state).select(job['id'], payload)
        results.put('saved')
    except ValueError:
        results.put('rejected')


class VisualSourceTransportTests(unittest.TestCase):
    def setUp(self):
        fixtures.SourceBankTests.setUp(self)
        self.root = self.folder
        self.result = self.root / 'output/visuals/job-a/project-a'
        self.result.mkdir(parents=True)
        shutil.move(str(self.root/'references'), self.result/'references')
        self.asset = self.result/'references/fixture.png'
        self.option['path'] = str(self.asset.resolve())
        self.folder = self.result
        self.file = self.result/'visuals-project.json'
        self.save()
        (self.result/'report.html').write_text('Fixture review', encoding='utf-8')
        self.job = {'id':'job-a', 'mode':'visuals', 'status':'complete',
                    'result':{'folder':str(self.result), 'page':str(self.result/'report.html')}}
        self.jobs = {self.job['id']:self.job}
        self.state = SimpleNamespace(root=self.root, snapshot=lambda key: copy.deepcopy(self.jobs[key]))

    save = fixtures.SourceBankTests.save

    def transport(self):
        from hinglish_app.visual_source_transport import VisualSourceTransport
        return VisualSourceTransport(self.state)

    def request(self, descriptor, choices):
        return {'type':'smart_visuals.source_bank.select','version':1,'project_path':str(self.file),
                'base_manifest':descriptor['manifest_path'],
                'base_manifest_sha256':descriptor['manifest_sha256'],'choices':choices}

    def test_completed_job_exposes_only_its_bound_raw_bank_and_choices(self):
        transport = self.transport()
        before = self.file.read_bytes(), self.asset.read_bytes()
        result = transport.describe('job-a', str(self.file))
        self.assertEqual(result['job_id'], 'job-a')
        self.assertEqual(result['options_per_moment'], 2)
        choice = result['banks'][0]['choices'][0]
        media = transport.resolve_media('job-a', str(self.file), result['manifest_sha256'], choice['asset_id'])
        self.assertEqual(media['path'],str(self.asset.resolve()))
        self.assertEqual(media['mime'],'image/png')
        self.assertEqual(media['sha256'],hashlib.sha256(self.asset.read_bytes()).hexdigest())
        selected = transport.select('job-a', self.request(result, {'0':'web:fixture'}))
        self.assertEqual(len(selected['selected_sources']),1)
        self.assertFalse(selected['auto_insert'])
        self.assertFalse(selected['native_acceptance'])
        self.assertEqual((self.file.read_bytes(),self.asset.read_bytes()),before)
        removed = transport.select('job-a', self.request(selected, {'0':''}))
        self.assertEqual(removed['selected_sources'],[])

    def test_unknown_incomplete_nonvisual_or_unbound_job_cannot_create_state(self):
        variants=[{**self.job,'status':'running'},{**self.job,'mode':'broll'},
                  {**self.job,'result':None},{**self.job,'id':'another-job'}]
        for job in variants:
            self.jobs['job-a']=job
            with self.subTest(job=job),self.assertRaises(ValueError):self.transport().describe('job-a',str(self.file))
        with self.assertRaises(ValueError):self.transport().describe('missing',str(self.file))
        self.assertFalse((self.result/'source-banks').exists())

    def test_outside_output_foreign_and_arbitrary_projects_are_rejected(self):
        foreign=self.root/'output/visuals/job-b/visuals-project.json'
        foreign.parent.mkdir(parents=True);foreign.write_bytes(self.file.read_bytes())
        for project in [foreign,self.root/'private.json',self.asset,self.root/'output/visuals']:
            with self.subTest(project=project),self.assertRaises(ValueError):
                self.transport().describe('job-a',str(project))
        for folder in [self.root,self.root/'output',self.root/'output/visuals']:
            self.job['result']={'folder':str(folder),'page':str(self.result/'report.html')}
            with self.subTest(folder=folder),self.assertRaises(ValueError):self.transport().describe('job-a',str(self.file))
        self.assertFalse((self.result/'source-banks').exists())

    def test_stale_or_foreign_manifest_request_does_not_advance_choices(self):
        transport=self.transport();base=transport.describe('job-a',str(self.file))
        pointer=self.result/'source-banks/active.json';before=pointer.read_bytes()
        for changes in [{'base_manifest':str(self.file)}, {'base_manifest_sha256':'0'*64},
                        {'project_path':str(self.asset)}, {'choices':{'0':'not-offered'}}]:
            request={**self.request(base,{'0':'web:fixture'}),**changes}
            with self.subTest(changes=changes),self.assertRaises(ValueError):transport.select('job-a',request)
            self.assertEqual(pointer.read_bytes(),before)
        transport.select('job-a',self.request(base,{'0':'web:fixture'}))
        with self.assertRaises(ValueError):transport.select('job-a',self.request(base,{'0':''}))
        with self.assertRaises(ValueError):transport.resolve_media('job-a',str(self.file),base['manifest_sha256'],base['banks'][0]['choices'][0]['asset_id'])

    def test_media_requires_active_baseline_and_offered_raw_asset_identity(self):
        transport=self.transport();base=transport.describe('job-a',str(self.file))
        for value in [str(self.asset),str(self.file),'not-offered','../private.png']:
            with self.subTest(value=value),self.assertRaises(ValueError):transport.resolve_media('job-a',str(self.file),base['manifest_sha256'],value)
        self.asset.write_bytes(b'changed source')
        with self.assertRaises(ValueError):transport.resolve_media('job-a',str(self.file),base['manifest_sha256'],base['banks'][0]['choices'][0]['asset_id'])
        with self.assertRaises(ValueError):transport.select('job-a',self.request(base,{'0':'web:fixture'}))

    def test_unsupported_raw_format_is_not_offered_or_selectable_for_transport(self):
        from PIL import Image
        image=self.result/'references/fixture.bmp'
        Image.open(self.asset).save(image)
        self.slot['options']=[{**self.option,'asset':'references/fixture.bmp','path':str(image)}]
        self.save()
        transport=self.transport();base=transport.describe('job-a',str(self.file))
        self.assertEqual(base['banks'][0]['choices'],[])
        self.assertEqual(len(base['banks'][0]['unavailable_choices']),1)
        with self.assertRaises(ValueError):transport.select('job-a',self.request(base,{'0':'web:fixture'}))
        self.assertEqual(transport.select('job-a',self.request(base,{'0':''}))['selected_sources'],[])

    def test_multi_result_index_uses_only_receipted_project_folders(self):
        bundle=self.result.parent
        (bundle/'index.html').write_text('Fixture index',encoding='utf-8')
        (bundle/'result.json').write_text(json.dumps({'results':[{'folder':self.result.name}]}),encoding='utf-8')
        self.job['result']={'folder':str(bundle),'page':str(bundle/'index.html')}
        self.assertEqual(self.transport().describe('job-a',str(self.file))['project_path'],str(self.file.resolve()))
        (bundle/'result.json').write_text(json.dumps({'results':[{'folder':'../job-b'}]}),encoding='utf-8')
        with self.assertRaises(ValueError):self.transport().describe('job-a',str(self.file))

    def test_preexisting_unsupported_selection_cannot_escape_via_empty_update(self):
        from PIL import Image
        image=self.result/'references/fixture.bmp'
        Image.open(self.asset).save(image)
        option={**self.option,'asset':'references/fixture.bmp','path':str(image)}
        self.slot.update(options=[option],chosen=option)
        self.save()
        transport=self.transport();base=transport.describe('job-a',str(self.file))
        pointer=self.result/'source-banks/active.json';before=pointer.read_bytes()
        with self.assertRaises(ValueError):transport.select('job-a',self.request(base,{}))
        self.assertEqual(pointer.read_bytes(),before)
        self.assertEqual(transport.select('job-a',self.request(base,{'0':''}))['selected_sources'],[])

    def test_cross_process_same_baseline_allows_only_one_decision(self):
        base=self.transport().describe('job-a',str(self.file))
        ctx=multiprocessing.get_context('spawn');start=ctx.Event();results=ctx.Queue()
        processes=[ctx.Process(target=_worker,args=(str(self.root),self.job,self.request(base,choices),start,results))
                   for choices in ({'0':'web:fixture'},{'0':''})]
        for process in processes:process.start()
        try:
            start.set();observed=[results.get(timeout=20) for _ in processes]
            self.assertCountEqual(observed,['saved','rejected'])
        finally:
            for process in processes:
                process.join(10)
                if process.is_alive():process.terminate();process.join()
            results.close()
        self.assertTrue(all(p.exitcode==0 for p in processes))


if __name__=='__main__':unittest.main()
