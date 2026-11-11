"""Synthetic font bytes and fake callbacks only; no OS or Adobe installation."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from hinglish_captions.font_intake import FontIntake
from tests.test_caption_reference_intake import Clock

ROOT=Path(__file__).resolve().parents[1]


class FontIntakeTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(dir=ROOT/'tmp',prefix='caption-font-intake-');self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.fonts=self.root/'supplied';self.fonts.mkdir();self.installed=self.root/'installed';self.installed.mkdir()
        self.clock=Clock();self.calls=[]
        self.face={'family':'Fixture Sans','style':'Bold','postscript':'FixtureSans-Bold'}
        self.font_bytes=json.dumps(self.face,sort_keys=True).encode();self.sha=hashlib.sha256(self.font_bytes).hexdigest()
        self.license_bytes=b'SIL OPEN FONT LICENSE Version 1.1 - synthetic fixture'
        self.license_sha=hashlib.sha256(self.license_bytes).hexdigest()
        self.path=self.fonts/'face.ttf';self.path.write_bytes(self.font_bytes)
        self.license=self.fonts/'OFL.txt';self.license.write_bytes(self.license_bytes)
        self.manifest={**self.face,'sha256':self.sha,'source':'supplied licensed fixture',
                       'license':{'id':'OFL-1.1','path':str(self.license),'sha256':self.license_sha}}

    def names(self,path):return json.loads(Path(path).read_bytes())
    def install_callback(self,asset):
        self.calls.append('install');target=self.installed/'face.ttf';target.write_bytes(Path(asset['path']).read_bytes())
        return {'installed':True,'scope':'user','path':str(target),'sha256':asset['sha256'],'postscript':asset['postscript']}
    def intake(self,**kw):
        return FontIntake(self.root,allowed_roots=[self.fonts],install_roots=[self.installed],
                          metadata=self.names,clock=self.clock,backoff=5,
                          installer=kw.pop('installer',self.install_callback),**kw)
    def register(self,intake):return intake.register_local(self.path,self.manifest)
    def proposal(self):return {**self.face,'origin':'licensed_manifest'}
    def resolution(self):
        return {**self.face,'source':'https://raw.githubusercontent.com/google/fonts/main/ofl/fixture/face.ttf',
                'filename':'face.ttf','sha256':self.sha,'license':{'id':'OFL-1.1','sha256':self.license_sha,
                'source':'https://raw.githubusercontent.com/google/fonts/main/ofl/fixture/OFL.txt'}}
    def download(self,url):self.calls.append(url);return self.license_bytes if url.endswith('OFL.txt') else self.font_bytes

    def test_metadata_and_licensed_bytes_are_verified_but_file_presence_is_not_ready(self):
        intake=self.intake();record=self.register(intake)
        self.assertEqual(record['status'],'verified');self.assertEqual(record['postscript'],'FixtureSans-Bold')
        self.assertEqual(record['asset_sha256'],self.sha);self.assertEqual(self.calls,[])

    def test_vision_unknown_is_one_persistent_review_and_never_auto_resolved(self):
        calls=[];intake=self.intake(resolver=lambda req:calls.append(req))
        record=intake.propose({'family':'Maybe proprietary','style':'Bold','origin':'vision'})
        for _ in range(3):intake.resolve(record['id'])
        other=self.intake(resolver=lambda req:calls.append(req));again=other.propose({'family':'Maybe proprietary','style':'Bold','origin':'vision'})
        self.assertEqual(again['id'],record['id']);self.assertEqual(again['status'],'needs_review')
        self.assertEqual(again['review_count'],1);self.assertEqual(calls,[])

    def test_paid_or_untrusted_resolution_is_reviewed_without_downloading(self):
        for number,changed in enumerate(({'paid':True},{'source':'https://untrusted.example/font.ttf'})):
            with self.subTest(changed=changed):
                isolated=self.root/str(number);isolated.mkdir()
                intake=FontIntake(isolated,metadata=self.names,resolver=lambda req:{**self.resolution(),**changed},downloader=self.download)
                record=intake.propose(self.proposal());done=intake.resolve(record['id'])
                self.assertEqual(done['status'],'needs_review');self.assertEqual(self.calls,[])

    def test_official_free_resolution_verifies_hash_and_exact_postscript_before_install(self):
        intake=self.intake(resolver=lambda req:self.resolution(),downloader=self.download)
        record=intake.propose(self.proposal());verified=intake.resolve(record['id'])
        self.assertEqual(verified['status'],'verified');self.assertEqual(verified['postscript'],self.face['postscript'])
        done=intake.install(record['id']);self.assertEqual(done['status'],'installed_pending_preflight')
        self.assertEqual(self.calls.count('install'),1);self.assertNotEqual(done['status'],'ready')

    def test_install_is_deduplicated_across_filename_and_restart(self):
        intake=self.intake();first=self.register(intake);intake.install(first['id'])
        alias=self.fonts/'renamed.ttf';alias.write_bytes(self.font_bytes)
        restarted=self.intake();again=restarted.register_local(alias,self.manifest)
        restarted.install(again['id']);self.assertEqual(again['id'],first['id']);self.assertEqual(self.calls.count('install'),1)

    def test_download_hash_and_parsed_postscript_mismatch_never_install(self):
        for change in ({'sha256':'0'*64},{'postscript':'DifferentFace-Bold'}):
            with self.subTest(change=change):
                root=self.root/('hash-case' if 'sha256' in change else 'name-case');root.mkdir()
                intake=FontIntake(root,metadata=self.names,clock=self.clock,allowed_roots=[self.fonts],install_roots=[self.installed],
                                  resolver=lambda req:{**self.resolution(),**change},downloader=self.download,installer=self.install_callback)
                record=intake.propose(self.proposal());self.assertEqual(intake.resolve(record['id'])['status'],'needs_review')
        self.assertNotIn('install',self.calls)

    def test_blank_metadata_or_unverified_license_never_becomes_ready(self):
        intake=self.intake()
        bad={**self.manifest,'license':{'id':'OFL-1.1','path':str(self.license),'sha256':'0'*64}}
        self.assertEqual(intake.register_local(self.path,bad)['status'],'needs_review')
        blank=self.fonts/'blank.ttf';blank.write_text(json.dumps({'family':'','style':'','postscript':''}),'utf8')
        manifest={**self.manifest,'sha256':hashlib.sha256(blank.read_bytes()).hexdigest()}
        self.assertEqual(intake.register_local(blank,manifest)['status'],'needs_review');self.assertEqual(self.calls,[])

    def test_installed_receipt_hash_name_and_actual_file_must_all_match(self):
        for mode in ('hash','name','file'):
            with self.subTest(mode=mode):
                root=self.root/mode;root.mkdir()
                def bad_install(asset):
                    receipt=self.install_callback(asset)
                    if mode=='hash':receipt['sha256']='0'*64
                    if mode=='name':receipt['postscript']='WrongPS'
                    if mode=='file':Path(receipt['path']).write_bytes(b'different bytes')
                    return receipt
                intake=FontIntake(root,metadata=self.names,clock=self.clock,allowed_roots=[self.fonts],install_roots=[self.installed],installer=bad_install)
                record=intake.register_local(self.path,self.manifest)
                self.assertEqual(intake.install(record['id'])['status'],'needs_review')

    def test_preflight_requires_exact_face_and_hash_for_each_target_without_launching_hosts(self):
        def preflight(asset,targets):
            self.calls.append(tuple(targets))
            return {target:{'recognized':True,'postscript':asset['postscript'],'sha256':asset['sha256']} for target in targets}
        intake=self.intake(preflight=preflight);record=self.register(intake);intake.install(record['id'])
        partial=intake.check(record['id'],targets=('hyperframes','premiere'))
        self.assertEqual(partial['status'],'installed_pending_preflight');self.assertNotIn('aftereffects',partial['ready_for'])
        ready=intake.check(record['id'],targets=('aftereffects',));self.assertEqual(ready['status'],'ready')
        self.assertEqual(set(ready['ready_for']),{'hyperframes','premiere','aftereffects'})

    def test_missing_or_wrong_host_recognition_cannot_mark_ready(self):
        intake=self.intake(preflight=lambda asset,targets:{target:{'recognized':True,'postscript':'WrongPS','sha256':asset['sha256']} for target in targets})
        record=self.register(intake);intake.install(record['id']);result=intake.check(record['id'])
        self.assertEqual(result['status'],'installed_pending_preflight');self.assertEqual(result['ready_for'],[])

    def test_download_failure_retries_after_backoff_with_persisted_resolution(self):
        calls=[]
        def unavailable(url):calls.append(url);raise OSError('temporary source failure')
        intake=self.intake(resolver=lambda req:self.resolution(),downloader=unavailable)
        record=intake.propose(self.proposal());self.assertEqual(intake.resolve(record['id'])['status'],'retry')
        restarted=self.intake(resolver=lambda req:(_ for _ in ()).throw(AssertionError('Resolution checkpoint lost')),downloader=self.download)
        restarted.resolve(record['id']);self.assertEqual(self.calls,[])
        self.clock.advance(5);self.assertEqual(restarted.resolve(record['id'])['status'],'verified');self.assertEqual(len(calls),1)

    def test_source_and_install_path_restrictions(self):
        outside=self.root/'outside.ttf';outside.write_bytes(self.font_bytes)
        with self.assertRaisesRegex(ValueError,'allowed'):self.intake().register_local(outside,self.manifest)
        exe=self.fonts/'font.exe';exe.write_bytes(self.font_bytes)
        with self.assertRaisesRegex(ValueError,'font'):self.intake().register_local(exe,self.manifest)
        def bad_install(asset):return {'installed':True,'scope':'user','path':str(outside),'sha256':self.sha,'postscript':self.face['postscript']}
        intake=self.intake(installer=bad_install);record=self.register(intake)
        self.assertEqual(intake.install(record['id'])['status'],'needs_review')

    def test_replaced_font_version_does_not_reuse_old_installation_or_preflight(self):
        def preflight(asset,targets):
            return {target:{'recognized':True,'postscript':asset['postscript'],'sha256':asset['sha256']} for target in targets}
        intake=self.intake(preflight=preflight);record=self.register(intake)
        intake.install(record['id']);self.assertEqual(intake.check(record['id'])['status'],'ready')
        newer=json.dumps({**self.face,'version':'two'}).encode();self.path.write_bytes(newer)
        manifest={**self.manifest,'sha256':hashlib.sha256(newer).hexdigest()}
        self.assertEqual(intake.register_local(self.path,manifest)['status'],'verified')
        self.assertEqual(intake.install(record['id'])['status'],'installed_pending_preflight')
        partial=intake.check(record['id'],targets=('hyperframes',))
        self.assertEqual(partial['status'],'installed_pending_preflight')
        self.assertEqual(partial['ready_for'],['hyperframes']);self.assertEqual(self.calls.count('install'),2)

    def test_expired_source_claim_recovers_resolution_after_worker_disappears(self):
        intake=self.intake(resolver=lambda req:self.resolution(),downloader=self.download,lease=3)
        record=intake.propose(self.proposal())
        with intake.store.transaction() as state:
            state['requests'][record['id']].update(status='resolving',token='dead-worker',lease_until=self.clock()+3,
                resolution=self.resolution(),attempts=1)
        restarted=self.intake(resolver=lambda req:self.fail('Lost source checkpoint'),downloader=self.download,lease=3)
        self.assertEqual(restarted.resolve(record['id'])['status'],'resolving')
        self.clock.advance(4);self.assertEqual(restarted.resolve(record['id'])['status'],'verified')

    def test_interrupted_install_is_reviewed_instead_of_automatically_installing_again(self):
        intake=self.intake(lease=3);record=self.register(intake)
        with intake.store.transaction() as state:
            state['requests'][record['id']].update(status='installing',token='dead-worker',lease_until=self.clock()+3)
        self.clock.advance(4)
        self.assertEqual(self.intake(lease=3).install(record['id'])['status'],'needs_review')
        self.assertEqual(self.calls,[])

    def test_parser_failure_is_a_persistent_review_with_a_useful_message(self):
        def broken(path):raise RuntimeError('unreadable font table')
        intake=FontIntake(self.root,allowed_roots=[self.fonts],metadata=broken)
        result=intake.register_local(self.path,self.manifest)
        self.assertEqual(result['status'],'needs_review');self.assertIn('review',result['message'])

    def test_changed_source_before_install_is_reviewed_and_never_sent_to_installer(self):
        intake=self.intake();record=self.register(intake);self.path.write_bytes(b'changed')
        self.assertEqual(intake.install(record['id'])['status'],'needs_review');self.assertEqual(self.calls,[])

    def test_concurrent_registration_does_not_clear_an_active_install_claim(self):
        calls=[]
        def installer(asset):
            calls.append('install')
            if len(calls)==1:
                other=self.intake(installer=installer)
                again=other.register_local(self.path,self.manifest);other.install(again['id'])
            return self.install_callback(asset)
        intake=self.intake(installer=installer);record=self.register(intake)
        self.assertEqual(intake.install(record['id'])['status'],'installed_pending_preflight')
        self.assertEqual(len(calls),1)

    def test_read_only_default_parser_reads_bundled_exact_names_without_installing(self):
        from hinglish_captions.font_intake import _names
        names=_names(ROOT/'hinglish_captions/fonts/GreatVibes-Regular.ttf')
        self.assertEqual(names['family'],'Great Vibes');self.assertEqual(names['style'],'Regular')
        self.assertEqual(names['postscript'],'GreatVibes-Regular');self.assertEqual(self.calls,[])

    @unittest.expectedFailure
    def test_review_finding_verified_alias_should_survive_removal_of_first_filename(self):
        """Final-review finding; retained without a production fix per owner rule."""
        intake=self.intake();record=self.register(intake)
        alias=self.fonts/'renamed.ttf';alias.write_bytes(self.font_bytes)
        intake.register_local(alias,self.manifest);self.path.unlink()
        self.assertEqual(intake.install(record['id'])['status'],'installed_pending_preflight')

    @unittest.expectedFailure
    def test_review_finding_failed_full_preflight_should_invalidate_prior_target_receipts(self):
        """Final-review finding; no Adobe or actual font installation occurs."""
        def recognized(asset,targets):
            return {target:{'recognized':True,'postscript':asset['postscript'],'sha256':asset['sha256']} for target in targets}
        intake=self.intake(preflight=recognized);record=self.register(intake);intake.install(record['id'])
        self.assertEqual(intake.check(record['id'])['status'],'ready')
        intake.preflight=lambda *args:(_ for _ in ()).throw(RuntimeError('host unavailable'))
        self.assertEqual(intake.check(record['id'])['ready_for'],[])
        intake.preflight=recognized
        self.assertEqual(intake.check(record['id'],targets=('hyperframes',))['status'],'installed_pending_preflight')


if __name__=='__main__':unittest.main()
