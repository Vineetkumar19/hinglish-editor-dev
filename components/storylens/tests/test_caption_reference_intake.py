"""Persistent intake components only: synthetic bytes, fake preparation, no watcher."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from hinglish_captions.reference_intake import ReferenceIntake, UnsupportedMotion

ROOT = Path(__file__).resolve().parents[1]


class Clock:
    def __init__(self): self.now = 1000.
    def __call__(self): return self.now
    def advance(self, seconds): self.now += seconds


class ReferenceIntakeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=ROOT/'tmp', prefix='caption-reference-intake-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name); self.videos = self.root/'existing-videos'; self.videos.mkdir()
        config = self.root/'hinglish_captions'; config.mkdir()
        (config/'auto_caption_references.json').write_text(json.dumps({'reference_folder':str(self.videos),'styles':[]}), 'utf8')
        self.clock = Clock(); self.calls = []; self.queued = []

    def author(self, root, ref, folder, progress):
        self.calls.append(ref)
        return {'sha256':hashlib.sha256(Path(ref['source']).read_bytes()).hexdigest(),
                'base_style':'serif_circle_draft','approximate':False,
                'template_source':7,'template_slot':2,'accepted_pattern':{'font':'Accepted Face','motion':[1,2]}}

    def serial(self, work):
        self.queued.append('existing-queue'); return work()

    def intake(self, **kwargs):
        return ReferenceIntake(self.root, clock=self.clock, debounce=2, backoff=5,
                               prepare=kwargs.pop('prepare', self.author),
                               serial=kwargs.pop('serial', self.serial), **kwargs)

    def stable(self, intake):
        intake.startup(); self.clock.advance(2); return intake.scan()

    def test_startup_waits_for_stable_write_then_uses_existing_prepare_and_serial_callback(self):
        source=self.videos/'Caption 6.mp4'; source.write_bytes(b'complete reference')
        intake=self.intake(); intake.startup()
        self.assertEqual(intake.snapshot()['assets'], {}); self.assertEqual(self.calls, [])
        self.clock.advance(2); intake.scan(); result=intake.run_next()
        self.assertEqual(result['status'],'prepared'); self.assertEqual(len(self.queued),1)
        self.assertEqual(result['result']['template_source'],7)
        self.assertEqual(result['result']['template_slot'],2)
        self.assertEqual(result['result']['accepted_pattern'],{'font':'Accepted Face','motion':[1,2]})
        self.assertEqual(self.calls[0]['source'],str(source.resolve()))

    def test_partial_copy_resets_debounce_and_zero_bytes_are_not_queued(self):
        source=self.videos/'copy.mp4'; source.touch(); intake=self.intake(); intake.startup()
        self.clock.advance(3); intake.scan(); self.assertIsNone(intake.run_next())
        source.write_bytes(b'part'); intake.notify(source); intake.scan(); self.clock.advance(1)
        source.write_bytes(b'complete copy'); intake.scan(); self.clock.advance(1); intake.scan()
        self.assertIsNone(intake.run_next()); self.clock.advance(1); intake.scan()
        self.assertEqual(intake.run_next()['status'],'prepared')

    def test_sha_idempotency_survives_new_filename_and_service_restart(self):
        source=self.videos/'a.mp4'; source.write_bytes(b'same content'); intake=self.intake()
        self.stable(intake); original=intake.run_next()['result']
        source.rename(self.videos/'renamed.mp4'); (self.videos/'duplicate.mov').write_bytes(b'same content')
        restarted=self.intake(); restarted.startup(); self.clock.advance(2); restarted.scan()
        self.assertIsNone(restarted.run_next()); self.assertEqual(len(self.calls),1)
        assets=restarted.snapshot()['assets']; self.assertEqual(len(assets),1)
        self.assertEqual(next(iter(assets.values()))['result'],original)

    def test_replacement_queues_only_new_content_and_keeps_accepted_result(self):
        source=self.videos/'a.mp4'; source.write_bytes(b'old'); intake=self.intake()
        self.stable(intake); first=intake.run_next(); frozen=first['result']
        source.write_bytes(b'replacement reference'); intake.scan(); self.clock.advance(2); intake.scan()
        second=intake.run_next(); self.assertNotEqual(first['sha256'],second['sha256'])
        self.assertEqual(intake.snapshot()['assets'][first['sha256']]['result'],frozen)
        self.assertEqual(len(self.calls),2)

    def test_failure_checkpoint_and_backoff_survive_restart(self):
        source=self.videos/'a.mp4'; source.write_bytes(b'content')
        def failing(root, ref, folder, progress):
            progress('Vision evidence saved', {'vision':'saved-evidence.json'})
            raise RuntimeError('temporary planner failure')
        intake=self.intake(prepare=failing); self.stable(intake); failed=intake.run_next()
        self.assertEqual(failed['status'],'retry'); self.assertEqual(failed['attempts'],1)
        def resume(root, ref, folder, progress):
            self.assertEqual(ref['intake_checkpoint'],{'vision':'saved-evidence.json'})
            return self.author(root,ref,folder,progress)
        restarted=self.intake(prepare=resume); self.assertIsNone(restarted.run_next())
        self.clock.advance(5); done=restarted.run_next()
        self.assertEqual(done['status'],'prepared'); self.assertEqual(done['attempts'],2)

    def test_unsupported_motion_stops_without_generic_substitution_or_repeated_calls(self):
        (self.videos/'a.mp4').write_bytes(b'unsupported')
        def unsupported(*args): raise UnsupportedMotion('A new renderer is required')
        intake=self.intake(prepare=unsupported); self.stable(intake); result=intake.run_next()
        self.assertEqual(result['status'],'unsupported'); self.assertNotIn('result',result)
        self.clock.advance(1000); intake.scan(); self.assertIsNone(intake.run_next())
        with self.assertRaisesRegex(ValueError,'renderer'):intake.retry(result['sha256'])

    def test_an_active_claim_blocks_another_instance_and_expired_claim_keeps_checkpoint(self):
        (self.videos/'a.mp4').write_bytes(b'a'); (self.videos/'b.mp4').write_bytes(b'b')
        other=self.intake()
        def blocked(root, ref, folder, progress):
            progress('working',{'stage':'vision'})
            self.assertIsNone(other.run_next())
            return self.author(root,ref,folder,progress)
        intake=self.intake(prepare=blocked); self.stable(intake)
        self.assertEqual(intake.run_next()['status'],'prepared')
        self.assertEqual(other.run_next()['status'],'prepared')

    def test_atomic_write_failure_preserves_last_durable_state(self):
        (self.videos/'a.mp4').write_bytes(b'a'); intake=self.intake(); intake.startup()
        before=intake.state_path.read_bytes(); self.clock.advance(3)
        with patch('hinglish_captions.reference_intake.os.replace',side_effect=OSError('disk unavailable')):
            with self.assertRaises(OSError):intake.scan()
        self.assertEqual(intake.state_path.read_bytes(),before)
        self.assertEqual(self.intake().snapshot()['assets'],{})

    def test_corrupt_state_is_not_silently_replaced(self):
        intake=self.intake(); intake.state_path.parent.mkdir(parents=True,exist_ok=True)
        intake.state_path.write_text('broken saved state','utf8')
        with self.assertRaisesRegex(ValueError,'state'):intake.startup()
        self.assertEqual(intake.state_path.read_text('utf8'),'broken saved state')

    def test_outside_source_and_state_paths_are_rejected(self):
        outside=self.root/'outside.mp4'; outside.write_bytes(b'not in the configured folder')
        with self.assertRaises(ValueError):self.intake(state_path=self.root.parent/'outside-state.json')
        intake=self.intake(discover=lambda root:[{'source':str(outside),'name':'outside','style':'unknown'}])
        with self.assertRaisesRegex(ValueError,'configured'):intake.startup()
        with self.assertRaisesRegex(ValueError,'configured'):self.intake().notify(outside)

    def test_file_changing_during_digest_is_debounced_again(self):
        source=self.videos/'a.mp4'; source.write_bytes(b'a'); calls=[]
        def changing(path):
            data=Path(path).read_bytes()
            if not calls:Path(path).write_bytes(b'new longer content')
            calls.append(1); return hashlib.sha256(data).hexdigest()
        intake=self.intake(digest=changing); self.stable(intake)
        self.assertIsNone(intake.run_next()); self.clock.advance(2); intake.scan()
        self.assertEqual(intake.run_next()['status'],'prepared')

    def test_empty_author_result_never_becomes_prepared(self):
        (self.videos/'a.mp4').write_bytes(b'a'); intake=self.intake(prepare=lambda *args:{})
        self.stable(intake); self.assertEqual(intake.run_next()['status'],'retry')

    def test_expired_reference_claim_resumes_checkpoint_and_rejects_old_result(self):
        (self.videos/'a.mp4').write_bytes(b'a'); other=self.intake(lease=3)
        def stale(root, ref, folder, progress):
            progress('saved', {'stage':'vision'})
            self.clock.advance(4)
            recovered=other.run_next()
            self.assertEqual(recovered['status'],'prepared')
            self.assertEqual(self.calls[-1]['intake_checkpoint'],{'stage':'vision'})
            return {**self.author(root,ref,folder,progress),'accepted_pattern':'STALE'}
        intake=self.intake(prepare=stale,lease=3);self.stable(intake)
        result=intake.run_next();self.assertEqual(result['status'],'prepared')
        self.assertNotEqual(result['result']['accepted_pattern'],'STALE')

    def test_default_prepare_adapter_maps_unsupported_error_without_entering_gpu_lock(self):
        from hinglish_captions.reference_intake import _prepare
        with patch('hinglish_captions.reference_library.prepare',side_effect=ValueError('A compatible motion renderer is required')):
            with self.assertRaises(UnsupportedMotion):_prepare(self.root,{},self.root,lambda *args:None)


if __name__=='__main__':unittest.main()
