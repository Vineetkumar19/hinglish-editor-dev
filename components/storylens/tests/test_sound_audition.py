"""Small synthetic WAVs and injected encoders only; no owner audio or editor."""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
import wave
from unittest.mock import patch

from tests import test_sound_recommendations as recommendation_fixtures
from hinglish_sound.recommendation_runtime import CancellationToken
from hinglish_sound.audition import prepare


class AuditionTests(unittest.TestCase):
    def setUp(self):
        self.base=recommendation_fixtures.RecommendationTests();self.base.setUp();self.addCleanup(self.base.doCleanups)
        self.root=self.base.root;self.job=self.root/'output/sound-recommendations/job';self.job.mkdir(parents=True)
        # Distinct seconds make an off-by-one-second window observable rather
        # than comparing identical periods of the old sine-tone fixture.
        with wave.open(self.base.assets[0].path,'wb') as wav:
            wav.setparams((1,2,8000,0,'NONE','not compressed'))
            wav.writeframes(b'\xe8\x03'*8000+b'\xd0\x07'*8000+b'\xb8\x0b'*8000)
        self.manifest=self.base.build(passage_selector=lambda a,s:dict(source_in=1.,basis='synthetic window'))
        self.path=self.job/'manifest.json';self.save()
        self.candidate=self.manifest['groups'][0]['candidates'][0]
        self.calls=[]
        self.source_before={str(p):p.read_bytes() for p in (self.root/'library').rglob('*') if p.is_file()}

    def save(self):
        self.path.write_text(json.dumps(self.manifest,indent=2),encoding='utf-8')
        self.manifest_bytes=self.path.read_bytes()
        self.sha=hashlib.sha256(self.path.read_bytes()).hexdigest()

    def encoder(self,source,output,start,end,token):
        self.calls.append((str(source),start,end))
        with wave.open(str(source),'rb') as src:
            params=src.getparams();src.setpos(round(start*src.getframerate()));data=src.readframes(round((end-start)*src.getframerate()))
        with wave.open(str(output),'wb') as dst:
            dst.setparams(params);dst.writeframes(data)

    def call(self,**options):
        defaults=dict(encoder=self.encoder,encoder_revision='synthetic-fixture-v1')
        defaults.update(options)
        return prepare(self.root,self.path,self.sha,self.candidate['id'],**defaults)

    def test_explicit_candidate_exact_window_and_credit_identity(self):
        result=self.call();self.assertEqual(result['status'],'ready')
        self.assertEqual(result['manifest_sha256'],self.sha)
        self.assertEqual(result['candidate_id'],self.candidate['id'])
        self.assertEqual(result['source']['in'],1.);self.assertEqual(result['source']['out'],3.)
        self.assertEqual(result['credits'],self.candidate['credits'])
        self.assertEqual(result['preview']['duration'],2.)
        self.assertTrue(result['test_encoder_used']);self.assertFalse(result['native_imported'])
        with wave.open(self.candidate['source']['path'],'rb') as src:
            src.setpos(8000);expected=src.readframes(16000)
        with wave.open(result['preview']['path'],'rb') as preview:self.assertEqual(preview.readframes(16000),expected)
        self.assertEqual(self.path.read_bytes(),self.manifest_bytes)
        for p,data in self.source_before.items():self.assertEqual(Path(p).read_bytes(),data)

    def test_repeated_audition_reuses_verified_output(self):
        a=self.call();b=self.call()
        self.assertEqual(a['id'],b['id']);self.assertEqual(len(self.calls),1)
        self.assertTrue(b['cache_hit'])

    def test_stale_manifest_rejected_before_encoder(self):
        self.path.write_text(self.path.read_text()+' ')
        result=self.call();self.assertEqual(result['status'],'failed');self.assertEqual(self.calls,[])
        self.assertIn('refresh',result['notice'].lower())

    def test_changed_source_bytes_rejected_even_for_existing_preview(self):
        self.call();Path(self.candidate['source']['path']).write_bytes(b'changed')
        self.assertEqual(self.call()['status'],'failed');self.assertEqual(len(self.calls),1)

    def test_changed_licence_sidecar_rejected(self):
        Path(self.candidate['source']['path']+'.json').write_text('{"license":"Changed"}')
        self.assertEqual(self.call()['status'],'failed');self.assertEqual(self.calls,[])

    def test_unknown_candidate_has_no_implicit_first_winner(self):
        result=prepare(self.root,self.path,self.sha,'not-selected',encoder=self.encoder,encoder_revision='fixture')
        self.assertEqual(result['status'],'failed');self.assertEqual(self.calls,[])

    def test_duplicate_candidate_ids_rejected(self):
        self.manifest['groups'][0]['candidates'].append(copy.deepcopy(self.candidate));self.save()
        self.assertEqual(self.call()['status'],'failed');self.assertEqual(self.calls,[])

    def test_malformed_source_window_rejected_even_with_updated_manifest_hash(self):
        self.candidate['source']['in']=-1.;self.save()
        self.assertEqual(self.call()['status'],'failed');self.assertEqual(self.calls,[])

    def test_modified_candidate_identity_is_not_accepted(self):
        self.candidate['timeline']['start']=1.;self.candidate['timeline']['end']=3.;self.save()
        self.assertEqual(self.call()['status'],'failed');self.assertEqual(self.calls,[])

    def test_non_job_manifest_and_unregistered_path_rejected(self):
        outside=self.root/'manifest.json';outside.write_bytes(self.path.read_bytes())
        result=prepare(self.root,outside,self.sha,self.candidate['id'],encoder=self.encoder,encoder_revision='fixture')
        self.assertEqual(result['status'],'failed');self.assertEqual(self.calls,[])
        self.candidate['source']['path']=str(self.path);self.save()
        self.assertEqual(self.call()['status'],'failed');self.assertEqual(self.calls,[])

    def test_bad_encoder_output_does_not_commit_ready_descriptor(self):
        def invalid(source,output,start,end,token):output.write_bytes(b'not a WAV')
        result=self.call(encoder=invalid)
        self.assertEqual(result['status'],'failed')
        self.assertFalse(list((self.job/'auditions').glob('*.json')))

    def test_truncated_and_wrong_duration_previews_rejected(self):
        def too_short(source,output,start,end,token):
            with wave.open(str(output),'wb') as wav:
                wav.setparams((1,2,8000,0,'NONE','not compressed'));wav.writeframes(b'\x00\x00'*800)
        self.assertEqual(self.call(encoder=too_short)['status'],'failed')

    def test_encoder_failure_keeps_source_and_saved_plan(self):
        plan=self.job/'plan.json';plan.write_text('{"keep":true}')
        def fail(*args):raise RuntimeError('synthetic encoder failure')
        self.assertEqual(self.call(encoder=fail)['status'],'failed')
        self.assertEqual(plan.read_text(),'{"keep":true}')
        self.assertFalse(list((self.job/'auditions').glob('*.wav')))

    def test_changed_cached_output_is_rejected_without_regenerating(self):
        first=self.call();Path(first['preview']['path']).write_bytes(b'changed')
        second=self.call();self.assertEqual(second['status'],'failed');self.assertEqual(len(self.calls),1)

    def test_mid_encode_source_change_and_manifest_change_do_not_commit(self):
        def change(source,output,start,end,token):
            self.encoder(source,output,start,end,token)
            self.path.write_text(self.path.read_text()+' ')
        self.assertEqual(self.call(encoder=change)['status'],'failed')
        self.assertFalse(list((self.job/'auditions').glob('*.json')))

    def test_cancelled_audition_has_no_finished_output(self):
        token=CancellationToken();token.cancel('fixture')
        result=self.call(token=token)
        self.assertEqual(result['status'],'cancelled');self.assertEqual(self.calls,[])

    def test_encoder_requires_explicit_revision_and_no_listener_is_started(self):
        result=self.call(encoder_revision=None)
        self.assertEqual(result['status'],'failed');self.assertEqual(self.calls,[])

    def test_altered_cached_descriptor_window_is_rejected(self):
        first=self.call();receipt=Path(first['preview']['path']).with_suffix('.json')
        saved=json.loads(receipt.read_text());saved['source']['in']=0.;receipt.write_text(json.dumps(saved))
        self.assertEqual(self.call()['status'],'failed');self.assertEqual(len(self.calls),1)

    def test_original_source_change_during_encode_is_not_committed(self):
        def change(source,output,start,end,token):
            self.assertNotEqual(str(source),self.candidate['source']['path'])
            self.encoder(source,output,start,end,token)
            original=Path(self.candidate['source']['path']);original.write_bytes(original.read_bytes()+b'changed')
        self.assertEqual(self.call(encoder=change)['status'],'failed')
        self.assertFalse(list((self.job/'auditions').glob('*.json')))

    def test_snapshot_size_limit_stops_without_large_copy(self):
        with patch('hinglish_sound.audition.MAX_SOURCE_BYTES',1):
            self.assertEqual(self.call()['status'],'failed')
        self.assertEqual(self.calls,[])

    def test_default_pcm_window_encoder_on_tiny_synthetic_audio_only(self):
        result=prepare(self.root,self.path,self.sha,self.candidate['id'])
        self.assertEqual(result['status'],'ready',result)
        self.assertFalse(result['test_encoder_used'])
        self.assertFalse(result['local_agent_acceptance'])
        with wave.open(result['preview']['path'],'rb') as audio:
            self.assertEqual((audio.getnchannels(),audio.getframerate(),audio.getnframes()),(1,48000,96000))
            import struct
            values=struct.unpack('<'+str(96000)+'h',audio.readframes(96000))
            self.assertTrue(1990<=values[4800]<=2010)
            self.assertTrue(2990<=values[72000]<=3010)


if __name__=='__main__':unittest.main()
