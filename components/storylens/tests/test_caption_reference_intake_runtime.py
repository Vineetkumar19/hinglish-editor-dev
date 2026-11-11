"""Runtime controller tests: temporary inputs, fake scheduling/preparation only."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from hinglish_captions.reference_intake_runtime import ReferenceIntakeRuntime

ROOT = Path(__file__).resolve().parents[1]


class Clock:
    def __init__(self): self.now = 1000.
    def __call__(self): return self.now
    def advance(self, value): self.now += value


class ReferenceIntakeRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=ROOT/'tmp', prefix='caption-intake-runtime-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name); self.videos = self.root/'configured-videos'; self.videos.mkdir()
        config = self.root/'hinglish_captions'; config.mkdir()
        (config/'auto_caption_references.json').write_text(json.dumps({'reference_folder':str(self.videos),'styles':[]}), 'utf8')
        self.clock = Clock(); self.calls = []; self.dispatches = []; self.allowed = True

    def source(self, name='Caption 9.mp4', data=b'synthetic reference'):
        path=self.videos/name;path.write_bytes(data);return path

    def prepare(self, root, ref, folder, progress):
        self.calls.append(ref)
        progress('Synthetic stage', {'stage':'fixture-vision'})
        return {'sha256':hashlib.sha256(Path(ref['source']).read_bytes()).hexdigest(),
                'base_style':'serif_circle_draft','template_source':7,'template_slot':2,
                'approximate':False,'provider':'FAKE-COMPONENT-ONLY'}

    def serial(self, work):
        self.dispatches.append('existing scheduler');return work()

    def runtime(self, **kwargs):
        return ReferenceIntakeRuntime(self.root,clock=self.clock,poll_interval=5,event_debounce=.25,
            debounce=2,backoff=5,lease=10,prepare=kwargs.pop('prepare',self.prepare),
            serial=kwargs.pop('serial',self.serial),can_dispatch=kwargs.pop('can_dispatch',lambda:self.allowed),**kwargs)

    def armed(self, runtime):
        runtime.start();runtime.resume();self.clock.advance(2)

    def test_construction_and_unstarted_tick_have_no_filesystem_or_analysis_side_effect(self):
        runtime=self.runtime();self.assertFalse((self.root/'cache').exists())
        self.assertEqual(runtime.tick()['status'],'stopped')
        self.assertFalse((self.root/'cache').exists());self.assertEqual(self.calls,[])

    def test_startup_scans_but_requires_explicit_resume_before_dispatch(self):
        self.source();runtime=self.runtime();runtime.start();self.clock.advance(2)
        result=runtime.tick();self.assertEqual(result['status'],'paused');self.assertEqual(self.calls,[])
        runtime.resume();result=runtime.tick();self.assertEqual(result['status'],'prepared')
        self.assertEqual(result['asset']['result']['template_source'],7);self.assertEqual(len(self.dispatches),1)

    def test_missed_filesystem_event_is_found_by_polling_without_background_thread(self):
        runtime=self.runtime();runtime.start();runtime.resume();self.source()
        self.clock.advance(5);self.assertEqual(runtime.tick()['status'],'idle')
        self.clock.advance(2);self.assertEqual(runtime.tick()['status'],'prepared')

    def test_events_coalesce_and_partial_copy_waits_for_stable_bytes(self):
        runtime=self.runtime();runtime.start();runtime.resume();path=self.source(data=b'part')
        for _ in range(10):runtime.on_event('modified',path)
        self.assertEqual(runtime.tick()['status'],'idle');self.assertEqual(self.calls,[])
        self.clock.advance(.25);runtime.tick();self.clock.advance(1)
        path.write_bytes(b'complete longer source');runtime.on_event('modified',path)
        self.clock.advance(.25);runtime.tick();self.clock.advance(1);runtime.tick()
        self.assertEqual(self.calls,[]);self.clock.advance(1);self.assertEqual(runtime.tick()['status'],'prepared')
        self.assertEqual(len(self.calls),1)

    def test_zero_byte_input_never_enters_preparation(self):
        self.source(data=b'');runtime=self.runtime();self.armed(runtime)
        for _ in range(3):runtime.tick();self.clock.advance(5)
        self.assertEqual(self.calls,[])

    def test_move_from_temporary_extension_and_delete_event_do_not_prepare_missing_file(self):
        runtime=self.runtime();runtime.start();runtime.resume();temporary=self.source('copy.tmp')
        self.assertFalse(runtime.on_event('created',temporary))
        final=temporary.rename(self.videos/'Caption 10.mp4');self.assertTrue(runtime.on_event('moved',temporary,final))
        self.clock.advance(.25);runtime.tick();final.unlink();runtime.on_event('deleted',final)
        self.clock.advance(3);runtime.tick();self.assertEqual(self.calls,[])

    def test_outside_event_is_rejected_and_overflow_requests_safe_full_rescan(self):
        runtime=self.runtime();runtime.start()
        with self.assertRaisesRegex(ValueError,'configured'):runtime.on_event('created',self.root/'outside.mp4')
        self.source();self.assertTrue(runtime.on_event('overflow'))
        self.clock.advance(.25);runtime.tick();self.clock.advance(2);runtime.resume()
        self.assertEqual(runtime.tick()['status'],'prepared')

    def test_missing_event_backend_falls_back_to_polling_with_diagnostics(self):
        def unavailable(callback):raise OSError('fixture event backend unavailable')
        runtime=self.runtime(subscribe=unavailable);result=runtime.start()
        self.assertEqual(result['watch_mode'],'polling');self.assertIn('backend',result['technical_details'])
        self.source();runtime.resume();self.clock.advance(5);runtime.tick();self.clock.advance(2)
        self.assertEqual(runtime.tick()['status'],'prepared')

    def test_injected_subscription_is_stopped_and_late_events_are_ignored(self):
        events=[];handlers=[]
        def subscribe(callback):
            handlers.append(callback);events.append('subscribed');return lambda:events.append('unsubscribed')
        runtime=self.runtime(subscribe=subscribe);runtime.start();runtime.stop()
        self.assertEqual(events,['subscribed','unsubscribed']);before=runtime.snapshot()
        self.assertFalse(handlers[0]('created',self.source()));self.assertEqual(runtime.snapshot(),before)

    def test_scheduler_busy_does_not_claim_or_prepare_then_continues_when_allowed(self):
        self.source();self.allowed=False;runtime=self.runtime();self.armed(runtime)
        self.assertEqual(runtime.tick()['status'],'waiting_for_scheduler')
        self.assertEqual(self.dispatches,[])
        self.assertTrue(all(a['attempts']==0 for a in runtime.references.snapshot()['assets'].values()))
        self.allowed=True;self.assertEqual(runtime.tick()['status'],'prepared')

    def test_no_scheduler_adapter_cannot_enable_dispatch(self):
        runtime=self.runtime(can_dispatch=None);runtime.start()
        with self.assertRaisesRegex(ValueError,'scheduler'):runtime.resume()
        self.assertEqual(runtime.tick()['status'],'paused');self.assertEqual(self.calls,[])

    def test_pause_persists_and_restart_is_never_implicitly_armed(self):
        self.source();runtime=self.runtime();self.armed(runtime);runtime.pause('owner paused')
        other=self.runtime();other.start();self.assertEqual(other.tick()['status'],'paused')
        other.resume();self.assertEqual(other.tick()['status'],'prepared');other.stop()
        third=self.runtime();third.start();self.assertEqual(third.tick()['status'],'paused')

    def test_restart_reuses_prepared_content_and_queues_only_replacement(self):
        path=self.source();runtime=self.runtime();self.armed(runtime);runtime.tick();runtime.stop()
        path.rename(self.videos/'renamed.mp4');other=self.runtime();self.armed(other)
        self.assertEqual(other.tick()['status'],'idle');self.assertEqual(len(self.calls),1)
        path=self.videos/'renamed.mp4';path.write_bytes(b'different reference');other.rescan();other.tick()
        self.clock.advance(2);self.assertEqual(other.tick()['status'],'prepared');self.assertEqual(len(self.calls),2)

    def test_cooperative_cancel_preserves_checkpoint_and_blocks_automatic_retry(self):
        runtime=None
        def cancelled(root,ref,folder,progress):
            self.calls.append(ref);runtime.request_cancel('owner cancelled')
            progress('checkpoint before stopping',{'stage':'saved-fixture'})
            self.fail('Cancellation was not observed at progress boundary')
        self.source();runtime=self.runtime(prepare=cancelled);self.armed(runtime)
        result=runtime.tick();self.assertEqual(result['status'],'cancelled')
        self.assertTrue(result['cancellation_observed']);self.assertFalse(result['model_abort_verified'])
        asset=next(iter(runtime.references.snapshot()['assets'].values()))
        self.assertEqual(asset['checkpoint'],{'stage':'saved-fixture'});self.assertEqual(asset['status'],'retry')
        self.clock.advance(20);self.assertEqual(runtime.tick()['status'],'cancelled');self.assertEqual(len(self.calls),1)
        other=self.runtime();other.start();self.assertEqual(other.tick()['status'],'cancelled')

    def test_cancel_before_dispatch_does_not_create_a_reference_attempt(self):
        self.source();runtime=self.runtime();self.armed(runtime);runtime.request_cancel()
        self.assertEqual(runtime.tick()['status'],'cancelled');self.assertEqual(self.calls,[])
        self.assertTrue(all(a['attempts']==0 for a in runtime.references.snapshot()['assets'].values()))

    def test_cancel_is_not_a_claim_that_uncooperative_work_was_aborted(self):
        runtime=None
        def late_cancel(*args):
            result=self.prepare(*args);runtime.request_cancel();return result
        self.source();runtime=self.runtime(prepare=late_cancel);self.armed(runtime)
        result=runtime.tick();self.assertEqual(result['status'],'cancelled')
        self.assertFalse(result['model_abort_verified']);self.assertEqual(len(self.calls),1)

    def test_dispatch_mutex_blocks_another_runtime_even_after_lease_clock_advances(self):
        self.source();other=self.runtime();other.start();other.resume()
        def during(root,ref,folder,progress):
            self.clock.advance(20)
            self.assertEqual(other.tick()['status'],'busy')
            return self.prepare(root,ref,folder,progress)
        runtime=self.runtime(prepare=during);self.armed(runtime)
        self.assertEqual(runtime.tick()['status'],'prepared');self.assertEqual(len(self.calls),1)

    def test_preparation_failure_uses_existing_backoff_and_checkpoint_without_claiming_real_stage_resume(self):
        def fail(root,ref,folder,progress):
            progress('checkpoint',{'stage':'fixture-only'});raise RuntimeError('fixture interruption')
        self.source();runtime=self.runtime(prepare=fail);self.armed(runtime)
        result=runtime.tick();self.assertEqual(result['status'],'retry');runtime.stop()
        other=self.runtime();other.start();other.resume();self.assertEqual(other.tick()['status'],'idle')
        self.clock.advance(5);self.assertEqual(other.tick()['status'],'prepared')
        self.assertEqual(self.calls[-1]['intake_checkpoint'],{'stage':'fixture-only'})

    def test_scan_error_is_presented_and_owner_file_is_preserved(self):
        runtime=self.runtime();runtime.start();path=self.source();path.unlink();self.videos.rmdir()
        runtime.rescan();result=runtime.tick();self.assertEqual(result['status'],'error')
        self.assertIn('folder',result['message'].lower());self.assertIn('unavailable',result['technical_details'])
        self.assertTrue((self.root/'hinglish_captions/auto_caption_references.json').is_file())

    def test_corrupt_runtime_state_has_readable_failure_and_is_never_replaced(self):
        runtime=self.runtime();runtime.state_path.parent.mkdir(parents=True)
        runtime.state_path.write_text('damaged runtime state','utf8')
        result=runtime.start();self.assertEqual(result['status'],'error')
        self.assertIn('saved',result['message'].lower())
        self.assertEqual(runtime.state_path.read_text('utf8'),'damaged runtime state')

    def test_scheduler_failure_preserves_queued_work_without_calling_prepare(self):
        def unavailable():raise RuntimeError('fixture scheduler unavailable')
        self.source();runtime=self.runtime(can_dispatch=unavailable);self.armed(runtime)
        result=runtime.tick();self.assertEqual(result['status'],'error')
        self.assertIn('scheduler unavailable',result['technical_details']);self.assertEqual(self.calls,[])
        self.assertTrue(all(a['attempts']==0 for a in runtime.references.snapshot()['assets'].values()))

    def test_persisted_running_claim_is_waiting_not_an_idle_or_success_receipt(self):
        self.source();runtime=self.runtime();self.armed(runtime);runtime.pause();runtime.tick()
        with runtime.references.store.transaction() as state:
            asset=next(iter(state['assets'].values()))
            asset.update(status='running',token='interrupted-worker',lease_until=self.clock()+10,attempts=1)
        runtime.resume();self.assertEqual(runtime.tick()['status'],'waiting_for_worker')
        self.assertEqual(self.calls,[])
        self.clock.advance(11);self.assertEqual(runtime.tick()['status'],'prepared')

    def test_native_file_mutex_blocks_a_second_python_process_without_starting_work(self):
        runtime=self.runtime();runtime.start()
        script="""import json,sys
from hinglish_captions.reference_intake_runtime import ReferenceIntakeRuntime
runtime=ReferenceIntakeRuntime(sys.argv[1])
print(json.dumps(runtime.start()))
"""
        with runtime.guard.acquire() as acquired:
            self.assertTrue(acquired)
            child=subprocess.run([sys.executable,'-c',script,str(self.root)],cwd=ROOT,capture_output=True,text=True,timeout=15)
        self.assertEqual(child.returncode,0,child.stderr)
        self.assertEqual(json.loads(child.stdout)['status'],'busy');self.assertEqual(self.calls,[])

    def test_final_review_unwritable_runtime_state_reports_failure_without_touching_source_or_job(self):
        """Safe final review; source implementation remains frozen after this stage."""
        path=self.source();runtime=self.runtime();self.armed(runtime);runtime.pause();runtime.tick()
        runtime.resume();before=runtime.references.state_path.read_bytes();source=path.read_bytes()
        with patch.object(runtime.store,'transaction',side_effect=OSError('fixture disk unavailable')):
            result=runtime.tick()
        self.assertEqual(result['status'],'error');self.assertIn('disk unavailable',result['technical_details'])
        self.assertEqual(path.read_bytes(),source);self.assertEqual(runtime.references.state_path.read_bytes(),before)
        self.assertEqual(self.calls,[])

    def test_final_review_unserializable_result_never_becomes_a_prepared_receipt(self):
        """Corrupt adapter output must retain the durable active claim for recovery."""
        def invalid(*args):return {**self.prepare(*args),'bad_value':object()}
        path=self.source();runtime=self.runtime(prepare=invalid);self.armed(runtime)
        result=runtime.tick();self.assertEqual(result['status'],'error')
        asset=next(iter(runtime.references.snapshot()['assets'].values()))
        self.assertEqual(asset['status'],'running');self.assertNotIn('result',asset)
        self.assertEqual(path.read_bytes(),b'synthetic reference')


if __name__=='__main__':unittest.main()
