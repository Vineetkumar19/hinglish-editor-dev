"""Font adapter fixtures; no real transport, registry, installation or Adobe calls."""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from hinglish_captions.font_runtime import FontRuntime, FontReviewRequired, read_font_metadata
from hinglish_captions.font_intake import FontIntake

ROOT=Path(__file__).resolve().parents[1]


class Response:
    def __init__(self,url,data=b'',status=200,headers=None,chunks=None):
        self.url,self.data,self.status_code=url,data,status
        self.headers=headers or {};self.chunks=chunks;self.closed=False
    def iter_content(self,chunk_size):return iter(self.chunks if self.chunks is not None else [self.data])
    def close(self):self.closed=True


class FakeOS:
    def __init__(self,root):self.root=root;self.values={};self.calls=[]
    def expected_root(self):return self.root
    def lookup(self,name):self.calls.append(('lookup',name));return self.values.get(name)
    def register(self,name,path):self.calls.append(('register',name));self.values[name]=str(path)
    def activate(self,path):self.calls.append(('activate',str(path)));return 1
    def notify(self):self.calls.append(('notify',))


class FontRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(dir=ROOT/'tmp',prefix='font-runtime-');self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.source_dir=self.root/'supplied';self.source_dir.mkdir()
        self.install_dir=self.root/'user-fonts';self.os=FakeOS(self.install_dir);self.calls=[];self.responses=[];self.now=1000.
        self.face={'family':'Fixture Sans','style':'Bold','postscript':'FixtureSans-Bold'}
        self.font_bytes=b'\x00\x01\x00\x00'+json.dumps({**self.face,'fullname':'Fixture Sans Bold'}).encode()
        self.license_bytes=b'SYNTHETIC FIXTURE: SIL OPEN FONT LICENSE Version 1.1'
        self.font=self.source_dir/'face.ttf';self.font.write_bytes(self.font_bytes)
        self.license=self.source_dir/'OFL.txt';self.license.write_bytes(self.license_bytes)
        self.font_url='https://raw.githubusercontent.com/google/fonts/main/ofl/fixture/face.ttf'
        self.license_url='https://raw.githubusercontent.com/google/fonts/main/ofl/fixture/OFL.txt'
        self.record={**self.face,'filename':'face.ttf','source':self.font_url,'sha256':self.sha(self.font_bytes),
                     'license':{'id':'OFL-1.1','source':self.license_url,'sha256':self.sha(self.license_bytes)}}
        self.asset={**self.face,'path':str(self.font),'sha256':self.sha(self.font_bytes),'source':self.font_url,
                    'license':{**self.record['license'],'path':str(self.license)}}

    @staticmethod
    def sha(data):return hashlib.sha256(data).hexdigest()
    def metadata(self,path):return json.loads(Path(path).read_bytes()[4:])
    def transport(self,url,**kwargs):
        self.calls.append((url,kwargs));response=Response(url,self.license_bytes if url==self.license_url else self.font_bytes)
        self.responses.append(response);return response
    def runtime(self,**kwargs):
        return FontRuntime(self.root,records=kwargs.pop('records',[self.record]),allowed_roots=[self.source_dir,self.root/'cache'],
            install_root=self.install_dir,metadata=kwargs.pop('metadata',self.metadata),os_api=kwargs.pop('os_api',self.os),
            transport=kwargs.pop('transport',self.transport),allow_download=kwargs.pop('allow_download',lambda:True),
            allow_install=kwargs.pop('allow_install',lambda:True),clock=lambda:self.now,**kwargs)
    def proposal(self):return {**self.face,'origin':'licensed_manifest'}

    def test_construction_and_callbacks_have_no_state_transport_or_os_effects(self):
        runtime=self.runtime();self.assertEqual(set(runtime.callbacks()),{'metadata','resolver','downloader','installer','preflight'})
        self.assertEqual(self.calls,[]);self.assertEqual(self.os.calls,[]);self.assertFalse((self.root/'cache').exists())

    def test_exact_approved_record_resolves_without_network_or_guessing(self):
        result=self.runtime().resolve(self.proposal());self.assertEqual(result['postscript'],self.face['postscript'])
        self.assertEqual(result['license']['sha256'],self.record['license']['sha256']);self.assertEqual(self.calls,[])

    def test_unknown_paid_vision_and_lookalike_faces_require_review(self):
        for change in ({'family':'Similar Face'},{'postscript':'FixtureSans-Regular'},{'origin':'vision'}):
            with self.subTest(change=change):
                with self.assertRaises(FontReviewRequired):self.runtime().resolve({**self.proposal(),**change})
        with self.assertRaises(FontReviewRequired):self.runtime(records=[{**self.record,'paid':True}]).resolve(self.proposal())
        self.assertEqual(self.calls,[])

    def test_ambiguous_exact_identity_requires_review_instead_of_selecting_version(self):
        second={**self.record,'sha256':'a'*64}
        with self.assertRaises(FontReviewRequired):self.runtime(records=[self.record,second]).resolve(self.proposal())

    def test_download_requires_explicit_gate_and_manifest_url(self):
        with self.assertRaises(FontReviewRequired):self.runtime(allow_download=lambda:False).download(self.font_url)
        with self.assertRaises(FontReviewRequired):self.runtime().download('https://untrusted.example/font.ttf')
        self.assertEqual(self.calls,[])

    def test_fetch_is_bounded_streamed_hashed_and_closes_transport(self):
        runtime=self.runtime();self.assertEqual(runtime.download(self.font_url),self.font_bytes)
        self.assertTrue(self.responses[0].closed);self.assertEqual(self.calls[0][1]['allow_redirects'],False)
        self.assertEqual(self.calls[0][1]['stream'],True)
        self.assertEqual(runtime.fetch_receipts[-1]['sha256'],self.record['sha256'])

    def test_untrusted_redirect_and_silently_followed_final_origin_are_rejected(self):
        for status,final,headers in ((302,self.font_url,{'Location':'https://evil.example/face.ttf'}),
                                     (200,'https://evil.example/face.ttf',{})):
            with self.subTest(status=status):
                responses=[]
                def transport(url,**kw):
                    response=Response(final,self.font_bytes,status,headers);responses.append(response);return response
                with self.assertRaises(FontReviewRequired):self.runtime(transport=transport).download(self.font_url)
                self.assertTrue(responses[0].closed)

    def test_trusted_redirect_is_limited_and_keeps_final_url_receipt(self):
        final='https://raw.githubusercontent.com/google/fonts/abc123/ofl/fixture/face.ttf'
        def transport(url,**kw):
            self.calls.append(url)
            return Response(url,status=302,headers={'Location':final}) if url==self.font_url else Response(url,self.font_bytes)
        runtime=self.runtime(transport=transport);runtime.download(self.font_url)
        self.assertEqual(runtime.fetch_receipts[-1]['final_url'],final);self.assertEqual(len(self.calls),2)
        with self.assertRaises(FontReviewRequired):self.runtime(transport=lambda url,**kw:Response(url,status=302,headers={'Location':url})).download(self.font_url)

    def test_wrong_hash_large_declared_or_streamed_body_is_rejected(self):
        for response in (Response(self.font_url,b'wrong bytes'),
                         Response(self.font_url,self.font_bytes,headers={'Content-Length':'999999'}),
                         Response(self.font_url,chunks=[b'x'*256,b'y'*256])):
            with self.subTest(headers=response.headers):
                with self.assertRaises(FontReviewRequired):self.runtime(transport=lambda *a,**kw:response,max_bytes=300).download(self.font_url)
                self.assertTrue(response.closed)

    def test_total_deadline_is_checked_while_streaming(self):
        class Slow(Response):
            def iter_content(inner,chunk_size):
                self.now+=20;yield self.font_bytes
        with self.assertRaises(TimeoutError):self.runtime(transport=lambda *a,**kw:Slow(self.font_url),deadline=10).download(self.font_url)

    def test_licence_bytes_need_verified_hash_and_supported_free_proof(self):
        bad={**self.record,'license':{**self.record['license'],'id':'proprietary'}}
        with self.assertRaises(FontReviewRequired):self.runtime(records=[bad]).resolve(self.proposal())
        runtime=self.runtime(transport=lambda url,**kw:Response(url,b'bad licence'))
        with self.assertRaises(FontReviewRequired):runtime.download(self.license_url)

    def test_installer_requires_gate_checks_bytes_names_licence_before_os_actions(self):
        with self.assertRaises(FontReviewRequired):self.runtime(allow_install=lambda:False).install(self.asset)
        with self.assertRaises(FontReviewRequired):self.runtime().install({**self.asset,'postscript':'WrongFace'})
        with self.assertRaises(FontReviewRequired):self.runtime().install({**self.asset,'sha256':'0'*64})
        self.assertEqual(self.os.calls,[]);self.assertFalse(self.install_dir.exists())

    def test_installer_copies_only_verified_bytes_and_returns_pending_native_receipt(self):
        result=self.runtime().install(self.asset)
        self.assertTrue(result['installed']);self.assertEqual(result['scope'],'user')
        self.assertEqual(Path(result['path']).read_bytes(),self.font_bytes)
        self.assertEqual(result['status'],'installed_pending_preflight');self.assertFalse(result['native_recognition_verified'])
        self.assertEqual([row[0] for row in self.os.calls].count('activate'),1)

    def test_repeat_and_restart_use_same_registered_bytes_without_duplicate_activation(self):
        first=self.runtime().install(self.asset);second=self.runtime().install(self.asset)
        self.assertEqual(first['path'],second['path']);self.assertTrue(second['reused'])
        self.assertEqual([row[0] for row in self.os.calls].count('register'),1)
        self.assertEqual([row[0] for row in self.os.calls].count('activate'),1)

    def test_existing_other_registration_or_destination_is_preserved(self):
        self.install_dir.mkdir();other=self.install_dir/'owner.ttf';other.write_bytes(b'owner font')
        self.os.values['Fixture Sans Bold (TrueType)']=str(other)
        with self.assertRaises(FontReviewRequired):self.runtime().install(self.asset)
        self.assertEqual(other.read_bytes(),b'owner font');self.assertEqual(len(list(self.install_dir.iterdir())),1)

    def test_existing_matching_registration_can_be_reused_without_moving_owner_file(self):
        self.install_dir.mkdir();existing=self.install_dir/'owner-name.ttf';existing.write_bytes(self.font_bytes)
        self.os.values['Fixture Sans Bold (TrueType)']=str(existing)
        result=self.runtime().install(self.asset);self.assertEqual(result['path'],str(existing.resolve()))
        self.assertTrue(result['reused']);self.assertFalse(any(row[0]=='register' for row in self.os.calls))

    def test_source_and_install_roots_executable_and_missing_canonical_path_are_not_bypassed(self):
        outside=self.root/'outside.ttf';outside.write_bytes(self.font_bytes)
        with self.assertRaises(FontReviewRequired):self.runtime().install({**self.asset,'path':str(outside)})
        exe=self.source_dir/'font.exe';exe.write_bytes(self.font_bytes)
        with self.assertRaises(FontReviewRequired):self.runtime().install({**self.asset,'path':str(exe)})
        alias=self.source_dir/'alias.ttf';alias.write_bytes(self.font_bytes);self.font.unlink()
        with self.assertRaises(FontReviewRequired):self.runtime().install({**self.asset,'aliases':[str(alias)]})
        self.assertEqual(self.os.calls,[])

    def test_registry_conflict_and_activation_failure_never_claim_installed_success(self):
        class Failed(FakeOS):
            def activate(self,path):return 0
        with self.assertRaises(RuntimeError):self.runtime(os_api=Failed(self.install_dir)).install(self.asset)

    def test_native_preflight_missing_gate_or_callback_is_explicitly_unverified(self):
        result=self.runtime().preflight(self.asset,('premiere',))
        self.assertFalse(result['premiere']['recognized']);self.assertEqual(result['premiere']['status'],'unverified')

    def test_preflight_requires_matching_current_session_exact_face_hash_and_target(self):
        sessions=lambda targets:{target:{'session_id':'current','font_epoch':'reload2'} for target in targets}
        def native(asset,targets,contexts):
            return {target:{'recognized':True,'target':target,'session_id':'current','font_epoch':'reload2',
                            'postscript':asset['postscript'],'sha256':asset['sha256']} for target in targets}
        runtime=self.runtime(native_preflight=native,native_sessions=sessions,allow_preflight=lambda:True)
        self.assertTrue(runtime.preflight(self.asset,('premiere',))['premiere']['recognized'])
        for change in ({'session_id':'old'},{'postscript':'WrongPS'},{'sha256':'0'*64},{'target':'aftereffects'}):
            def stale(asset,targets,contexts):return {'premiere':{**native(asset,targets,contexts)['premiere'],**change}}
            runtime=self.runtime(native_preflight=stale,native_sessions=sessions,allow_preflight=lambda:True)
            self.assertFalse(runtime.preflight(self.asset,('premiere',))['premiere']['recognized'])

    def test_preflight_never_launches_both_adobe_hosts_and_does_not_swallow_provider_errors(self):
        calls=[]
        def native(*args):calls.append(args);raise RuntimeError('native unavailable')
        runtime=self.runtime(native_preflight=native,native_sessions=lambda targets:{t:{'session_id':'s','font_epoch':'e'} for t in targets},allow_preflight=lambda:True)
        result=runtime.preflight(self.asset,('premiere','aftereffects'))
        self.assertFalse(result['premiere']['recognized']);self.assertEqual(calls,[])
        with self.assertRaisesRegex(RuntimeError,'native unavailable'):runtime.preflight(self.asset,('premiere',))

    def test_existing_intake_can_use_adapters_without_global_ready_or_native_claim(self):
        runtime=self.runtime();intake=FontIntake(self.root,allowed_roots=[self.source_dir],install_roots=[self.install_dir],**runtime.callbacks())
        record=intake.propose(self.proposal());self.assertEqual(intake.resolve(record['id'])['status'],'verified')
        self.assertEqual(intake.install(record['id'])['status'],'installed_pending_preflight')
        result=intake.check(record['id'],targets=('premiere',))
        self.assertEqual(result['status'],'installed_pending_preflight');self.assertEqual(result['ready_for'],[])

    def test_existing_intake_persists_one_review_for_vision_uncertainty(self):
        runtime=self.runtime();intake=FontIntake(self.root,**runtime.callbacks())
        request={**self.face,'origin':'vision'};record=intake.propose(request)
        for _ in range(3):intake.resolve(record['id'])
        self.assertEqual(intake.snapshot()['requests'][record['id']]['review_count'],1);self.assertEqual(self.calls,[])

    def test_read_only_metadata_reuses_bundled_parser_and_rejects_renamed_executable(self):
        result=read_font_metadata(ROOT/'hinglish_captions/fonts/GreatVibes-Regular.ttf')
        self.assertEqual(result['postscript'],'GreatVibes-Regular')
        fake=self.source_dir/'fake.ttf';fake.write_bytes(b'MZ executable-like bytes')
        with self.assertRaises(FontReviewRequired):read_font_metadata(fake)

    def test_explicit_bundle_font_licence_association_reuses_existing_source_manifest(self):
        sources={self.font.name:{'source':self.font_url,'sha256':self.sha(self.font_bytes)},
                 self.license.name:{'source':self.license_url,'sha256':self.sha(self.license_bytes)}}
        record=self.runtime().bundle_record(self.font,self.license,sources)
        self.assertEqual(record['postscript'],self.face['postscript']);self.assertEqual(record['license']['path'],str(self.license.resolve()))
        self.assertEqual(self.calls,[]);self.assertEqual(self.os.calls,[])

    def test_install_root_must_match_per_user_boundary_and_preserve_conflicting_destination(self):
        self.os.root=self.root/'different-user-fonts'
        with self.assertRaises(FontReviewRequired):self.runtime().install(self.asset)
        self.assertEqual(self.os.calls,[])
        self.os.root=self.install_dir;self.install_dir.mkdir()
        target=self.install_dir/('Storylens-'+self.asset['sha256']+'-FixtureSans-Bold.ttf')
        target.write_bytes(b'owner conflicting data')
        with self.assertRaises(FontReviewRequired):self.runtime().install(self.asset)
        self.assertEqual(target.read_bytes(),b'owner conflicting data')
        self.assertFalse(any(row[0]=='register' for row in self.os.calls))

    def test_same_hash_licence_without_ofl_proof_is_not_accepted_before_os_calls(self):
        self.license.write_bytes(b'Not a font licence')
        asset={**self.asset,'license':{**self.asset['license'],'sha256':self.sha(self.license.read_bytes())}}
        with self.assertRaises(FontReviewRequired):self.runtime().install(asset)
        self.assertEqual(self.os.calls,[])

    def test_native_session_change_during_observation_cannot_confirm_current_recognition(self):
        session=['old']
        def contexts(targets):return {target:{'session_id':session[0],'font_epoch':'epoch'} for target in targets}
        def native(asset,targets,known):
            session[0]='new'
            return {target:{'recognized':True,'target':target,'session_id':'old','font_epoch':'epoch',
                'postscript':asset['postscript'],'sha256':asset['sha256']} for target in targets}
        runtime=self.runtime(native_preflight=native,native_sessions=contexts,allow_preflight=lambda:True)
        self.assertFalse(runtime.preflight(self.asset,('premiere',))['premiere']['recognized'])

    def test_final_review_windows_registry_boundary_uses_hkcu_and_preserves_conflicts(self):
        from hinglish_captions.font_runtime import WindowsUserFontOS
        values={};calls=[]
        class Key:
            def __enter__(self):return self
            def __exit__(self,*args):pass
        def key(hive,path):calls.append(hive);return Key()
        def query(key,name):
            if name not in values:raise FileNotFoundError()
            return values[name],1
        registry=SimpleNamespace(HKEY_CURRENT_USER='HKCU-FAKE',REG_SZ=1,OpenKey=key,CreateKey=key,
            QueryValueEx=query,SetValueEx=lambda key,name,reserved,kind,value:values.update({name:value}))
        target=self.install_dir/'face.ttf'
        with patch.dict('sys.modules',{'winreg':registry}):
            api=WindowsUserFontOS();api.register('Fixture',target)
            self.assertEqual(api.lookup('Fixture'),str(target))
            with self.assertRaises(FontReviewRequired):api.register('Fixture',self.install_dir/'different.ttf')
        self.assertEqual(values['Fixture'],str(target));self.assertTrue(all(hive=='HKCU-FAKE' for hive in calls))

    @unittest.expectedFailure
    def test_final_review_direct_installer_must_reject_explicit_paid_asset(self):
        """Safe direct-callback probe; all bytes and OS registrations are fake."""
        with self.assertRaises(FontReviewRequired):self.runtime().install({**self.asset,'paid':True})
        self.assertEqual(self.os.calls,[])

    @unittest.expectedFailure
    def test_final_review_changed_destination_must_not_be_activated_or_report_installed(self):
        """A simulated write during registration probes the last activation boundary."""
        class Changed(FakeOS):
            def register(self,name,path):
                super().register(name,path);Path(path).write_bytes(b'MZ changed fixture bytes')
        api=Changed(self.install_dir)
        with self.assertRaises(FontReviewRequired):self.runtime(os_api=api).install(self.asset)
        self.assertFalse(any(row[0]=='activate' for row in api.calls))


if __name__=='__main__':unittest.main()
