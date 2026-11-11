import hashlib,json,sqlite3,tempfile,unittest
from contextlib import closing
from pathlib import Path
from work.activate_context_deferred import activate,ALLOWED

class ActivationTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]/'tmp');self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);out=self.root/'output/context-architecture-20261030';out.mkdir(parents=True)
        self.flow=self.root/'output/publisher-prepare-post/workflows'/('a'*32+'.json');self.flow.parent.mkdir(parents=True)
        self.flow.write_text('{"status":"failed"}')
        self.config=self.root/'config.context.local.json';self.config.write_text(json.dumps({'protected_workflow':'a'*32,'deferred_features':['assistant']}))
        db=self.root/'cache/publisher/queue.sqlite3';db.parent.mkdir(parents=True)
        with closing(sqlite3.connect(db)) as c:c.execute('create table jobs (id text,status text)');c.commit()
        manifest={}
        for name in ALLOWED:
            source=self.root/name;staged=out/'staged'/name
            source.parent.mkdir(parents=True,exist_ok=True);staged.parent.mkdir(parents=True,exist_ok=True)
            source.write_text('# before');staged.write_text('# after')
            manifest[name]={'before_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'staged_sha256':hashlib.sha256(staged.read_bytes()).hexdigest()}
        (out/'deferred-manifest.json').write_text(json.dumps(manifest))

    def test_failed_workflow_requires_explicit_new_owner_authorization(self):
        self.assertEqual(activate(self.root,apply=True)['status'],'waiting')
        result=activate(self.root,apply=True,owner_approved_failed=True)
        self.assertEqual(result['status'],'applied')
        self.assertEqual(json.loads(self.flow.read_text())['status'],'failed')
        self.assertEqual(json.loads(self.config.read_text())['deferred_features'],[])

    def test_owner_failed_permission_never_interrupts_running_workflow(self):
        self.flow.write_text('{"status":"working"}')
        self.assertEqual(activate(self.root,apply=True,owner_approved_failed=True)['status'],'waiting')

    def test_concurrent_source_repair_cannot_be_overwritten(self):
        name=next(iter(ALLOWED));(self.root/name).write_text('# owner repair')
        with self.assertRaisesRegex(ValueError,'Concurrent edit'):
            activate(self.root,apply=True,owner_approved_failed=True)
        self.assertEqual((self.root/name).read_text(),'# owner repair')
