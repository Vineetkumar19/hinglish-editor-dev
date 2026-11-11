"""Application lifecycle fixtures: no model, font OS, network or native action."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from hinglish_app.caption_intake_lifecycle import CaptionIntakeLifecycle

ROOT=Path(__file__).resolve().parents[1]


class Clock:
    def __init__(self):self.now=1000.
    def __call__(self):return self.now
    def advance(self,value):self.now+=value


class CaptionIntakeLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(dir=ROOT/'tmp',prefix='caption-lifecycle-');self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.videos=self.root/'configured-videos';self.videos.mkdir()
        config=self.root/'hinglish_captions';config.mkdir()
        (config/'auto_caption_references.json').write_text(json.dumps({'reference_folder':str(self.videos),'styles':[]}),'utf8')
        self.clock=Clock();self.allowed=self.ready=self.queue=True;self.calls=[];self.serial_calls=[]
        self.patcher=patch('hinglish_app.caption_intake_lifecycle._prepare_reference',side_effect=self.prepare)
        self.mock_prepare=self.patcher.start();self.addCleanup(self.patcher.stop)

    def source(self,data=b'fixture reference'):
        path=self.videos/'Caption 9.mp4';path.write_bytes(data);return path
    def prepare(self,root,ref,folder,progress):
        self.calls.append(ref);progress('Fixture local model evidence',{'stage':'FIXTURE-ONLY'})
        return {'sha256':hashlib.sha256(Path(ref['source']).read_bytes()).hexdigest(),
            'base_style':'serif_circle_draft','template_source':7,'template_slot':2,
            'vision_model':'NO MODEL EXECUTED','planner_model':'NO MODEL EXECUTED','approximate':False}
    def serial(self,work):self.serial_calls.append('suite queue');return work()
    def lifecycle(self,**kwargs):
        return CaptionIntakeLifecycle(self.root,serial=kwargs.pop('serial',self.serial),
            can_dispatch=kwargs.pop('can_dispatch',lambda:self.queue),
            analysis_permission=kwargs.pop('analysis_permission',lambda:self.allowed),
            local_runtime_ready=kwargs.pop('local_runtime_ready',lambda:self.ready),
            clock=self.clock,poll_interval=5,debounce=2,backoff=5,lease=10,**kwargs)
    def running(self,lifecycle):lifecycle.start(analysis_enabled=True);self.clock.advance(2)

    def test_construction_status_and_unstarted_tick_create_no_cache_or_work(self):
        app=self.lifecycle();self.assertEqual(app.status()['status'],'stopped')
        self.assertFalse(app.can_dispatch());self.assertEqual(app.tick()['status'],'stopped')
        self.assertFalse((self.root/'cache').exists());self.assertEqual(self.calls,[])

    def test_default_start_is_discovery_only_with_font_and_native_gate_blocked(self):
        self.source();app=self.lifecycle();app.start();self.clock.advance(2);result=app.tick()
        self.assertFalse(result['analysis']['requested']);self.assertTrue(result['font_native_gate']['blocked'])
        self.assertEqual(result['font_native_gate']['native_readiness'],'unverified');self.assertEqual(self.calls,[])
        self.assertEqual(result['source_folder'],str(self.videos.resolve()))

    def test_explicit_analysis_uses_existing_runtime_and_exact_prepare_boundary(self):
        self.source();app=self.lifecycle();self.running(app);result=app.tick()
        self.assertEqual(result['status'],'prepared');self.assertEqual(len(self.calls),1)
        self.assertEqual(len(self.serial_calls),1);self.assertTrue(result['font_native_gate']['blocked'])
        self.assertEqual(result['runtime_result']['asset']['result']['template_slot'],2)
        self.assertEqual(result['job_counts'],{'prepared':1})

    def test_permission_runtime_readiness_and_queue_each_block_before_claim(self):
        self.source();app=self.lifecycle();self.running(app)
        for field,reason in (('allowed','analysis_not_permitted'),('ready','local_runtime_not_ready'),('queue','shared_queue_busy')):
            with self.subTest(field=field):
                setattr(self,field,False);result=app.tick()
                self.assertEqual(result['status'],'waiting_for_scheduler');self.assertEqual(result['analysis']['gate_reason'],reason)
                self.assertEqual(self.calls,[]);setattr(self,field,True)
        self.assertEqual(app.tick()['status'],'prepared')

    def test_missing_suite_callbacks_keeps_discovery_available_without_analysis(self):
        self.source();app=self.lifecycle(serial=None,analysis_permission=None,local_runtime_ready=None)
        app.start(analysis_enabled=True);self.clock.advance(2);result=app.tick()
        self.assertFalse(result['analysis']['armed']);self.assertEqual(self.calls,[])

    def test_permission_callback_failure_is_a_blocked_gate_not_a_model_call_or_secret_echo(self):
        def broken():raise RuntimeError('fixture-secret-value')
        self.source();app=self.lifecycle(analysis_permission=broken);self.running(app);result=app.tick()
        self.assertEqual(result['analysis']['gate_reason'],'permission_check_failed');self.assertEqual(self.calls,[])
        self.assertNotIn('fixture-secret-value',json.dumps(result))

    def test_normal_idle_shutdown_and_restart_preserve_opted_in_analysis(self):
        self.source();app=self.lifecycle();self.running(app);app.tick();app.stop()
        self.source(b'new reference content');other=self.lifecycle();other.start();self.clock.advance(2)
        self.assertTrue(other.status()['analysis']['requested']);self.assertTrue(other.status()['analysis']['armed'])
        self.assertEqual(other.tick()['status'],'prepared');self.assertEqual(len(self.calls),2)

    def test_manual_pause_survives_shutdown_and_restart_even_if_startup_pref_is_true(self):
        self.source();app=self.lifecycle();self.running(app);app.pause_analysis();app.stop()
        other=self.lifecycle();other.start(analysis_enabled=True);self.clock.advance(2);other.tick()
        self.assertEqual(self.calls,[]);self.assertFalse(other.status()['analysis']['armed'])
        other.resume_analysis();self.assertEqual(other.tick()['status'],'prepared')

    def test_cancelled_work_stays_cancelled_on_restart_until_explicit_resume(self):
        self.source();app=self.lifecycle();self.running(app);app.cancel_analysis();app.stop()
        other=self.lifecycle();other.start();self.clock.advance(2)
        self.assertEqual(other.tick()['status'],'cancelled');self.assertEqual(self.calls,[])
        other.resume_analysis();self.assertEqual(other.tick()['status'],'prepared')

    def test_status_is_read_only_and_does_not_query_resource_or_model_callbacks(self):
        callbacks=[]
        app=self.lifecycle(analysis_permission=lambda:callbacks.append('permission') or True,
            local_runtime_ready=lambda:callbacks.append('runtime') or True,can_dispatch=lambda:callbacks.append('queue') or True)
        app.start();before=app.runtime.state_path.read_bytes()
        for _ in range(3):app.status()
        self.assertEqual(callbacks,[]);self.assertEqual(app.runtime.state_path.read_bytes(),before)

    def test_renamed_duplicate_is_not_prepared_again_and_source_files_are_preserved(self):
        path=self.source();app=self.lifecycle();self.running(app);app.tick()
        path.rename(self.videos/'renamed.mp4');app.rescan();app.tick();self.clock.advance(2);app.tick()
        self.assertEqual(len(self.calls),1);self.assertEqual((self.videos/'renamed.mp4').read_bytes(),b'fixture reference')

    def test_polling_event_hints_and_rescan_use_same_existing_reference_store(self):
        app=self.lifecycle();app.start(analysis_enabled=True);path=self.source();app.on_event('created',path)
        self.clock.advance(.25);app.tick();self.clock.advance(2);result=app.tick()
        self.assertEqual(result['status'],'prepared')
        self.assertEqual(app.runtime.references.state_path,self.root/'cache/captions/reference-library/intake-state.json')

    def test_transient_prepare_failure_keeps_backoff_and_checkpoint_without_fabricated_resume(self):
        def failed(root,ref,folder,progress):progress('saved fixture',{'stage':'fixture-stage'});raise RuntimeError('fixture failure')
        self.mock_prepare.side_effect=failed;self.source();app=self.lifecycle();self.running(app)
        self.assertEqual(app.tick()['status'],'retry');app.stop();self.mock_prepare.side_effect=self.prepare
        other=self.lifecycle();other.start();self.assertEqual(other.tick()['status'],'idle')
        self.clock.advance(5);self.assertEqual(other.tick()['status'],'prepared')
        self.assertEqual(self.calls[-1]['intake_checkpoint'],{'stage':'fixture-stage'})

    def test_prepare_rechecks_permission_after_queue_wait_without_reacquiring_gpu_lock(self):
        def serial(work):self.allowed=False;return work()
        self.source();app=self.lifecycle(serial=serial);self.running(app)
        self.assertEqual(app.tick()['status'],'retry');self.assertEqual(self.calls,[])

    def test_subscribed_events_are_stopped_without_starting_a_second_watcher(self):
        subscriptions=[]
        def subscribe(callback):subscriptions.append(callback);return lambda:subscriptions.append('stopped')
        app=self.lifecycle(subscribe=subscribe);app.start();app.start();app.stop()
        self.assertEqual(len(subscriptions),2);self.assertEqual(subscriptions[-1],'stopped')

    def test_model_result_cannot_clear_top_level_font_native_block(self):
        original=self.prepare
        self.mock_prepare.side_effect=lambda *args:{**original(*args),'font_native_gate':{'blocked':False,'native_readiness':'ready'}}
        self.source();app=self.lifecycle();self.running(app);result=app.tick()
        self.assertTrue(result['font_native_gate']['blocked']);self.assertEqual(result['font_native_gate']['native_readiness'],'unverified')

    def test_invalid_startup_flag_and_outside_event_do_not_dispatch(self):
        app=self.lifecycle()
        with self.assertRaises(ValueError):app.start(analysis_enabled='yes')
        app.start()
        with self.assertRaises(ValueError):app.on_event('created',self.root/'outside.mp4')
        self.assertEqual(self.calls,[])

    def test_missing_configured_folder_reports_error_preserving_saved_config(self):
        self.videos.rmdir();app=self.lifecycle();result=app.start(analysis_enabled=True)
        self.assertEqual(result['status'],'error');self.assertTrue(result['font_native_gate']['blocked'])
        self.assertTrue((self.root/'hinglish_captions/auto_caption_references.json').is_file())

    def test_startup_preference_write_failure_closes_subscription_and_never_arms(self):
        closed=[]
        app=self.lifecycle(subscribe=lambda callback:lambda:closed.append(True))
        with patch.object(app,'_save_preferences',side_effect=OSError('fixture disk unavailable')):
            result=app.start(analysis_enabled=True)
        self.assertEqual(result['status'],'error');self.assertEqual(closed,[True])
        self.assertFalse(app.can_dispatch());self.assertEqual(self.calls,[])

    def test_shutdown_preference_write_failure_still_unsubscribes_and_disables_dispatch(self):
        closed=[]
        app=self.lifecycle(subscribe=lambda callback:lambda:closed.append(True));app.start(analysis_enabled=True)
        with patch.object(app,'_save_preferences',side_effect=OSError('fixture disk unavailable')):
            result=app.stop()
        self.assertEqual(result['status'],'error');self.assertEqual(closed,[True])
        self.assertFalse(app.can_dispatch());self.assertEqual(self.calls,[])

    def test_cancel_in_progress_keeps_checkpoint_and_prevents_automatic_restart(self):
        app=None
        def cancelled(root,ref,folder,progress):
            app.cancel_analysis();progress('fixture stop',{'stage':'saved-before-cancel'})
            self.fail('Cancellation boundary was ignored')
        self.mock_prepare.side_effect=cancelled;self.source();app=self.lifecycle();self.running(app)
        self.assertEqual(app.tick()['status'],'cancelled');app.stop()
        other=self.lifecycle();other.start();self.clock.advance(20)
        self.assertEqual(other.tick()['status'],'cancelled')
        asset=next(iter(other.runtime.references.snapshot()['assets'].values()))
        self.assertEqual(asset['checkpoint'],{'stage':'saved-before-cancel'})

    def test_damaged_application_preferences_are_preserved_without_partial_startup(self):
        app=self.lifecycle();app.start();app.stop()
        state=json.loads(app.runtime.state_path.read_text('utf8'))
        state['application_lifecycle']['analysis_requested']='wrong type'
        app.runtime.state_path.write_text(json.dumps(state),'utf8');before=app.runtime.state_path.read_bytes()
        other=self.lifecycle();result=other.start(analysis_enabled=True)
        self.assertEqual(result['status'],'error');self.assertEqual(other.runtime.state_path.read_bytes(),before)

    def test_each_suite_tick_prepares_at_most_one_reference(self):
        self.source();(self.videos/'Caption 10.mp4').write_bytes(b'second fixture')
        app=self.lifecycle();self.running(app);app.tick();self.assertEqual(len(self.calls),1)
        app.tick();self.assertEqual(len(self.calls),2)

    @unittest.expectedFailure
    def test_final_review_pause_write_failure_must_return_readable_error(self):
        """Final safe review: no actual model or watcher is active."""
        app=self.lifecycle();app.start(analysis_enabled=True)
        with patch.object(app,'_save_preferences',side_effect=OSError('fixture pause write unavailable')):
            result=app.pause_analysis()
        self.assertEqual(result['status'],'error');self.assertFalse(app.can_dispatch())

    @unittest.expectedFailure
    def test_final_review_cancel_write_failure_must_still_signal_the_running_runtime(self):
        """A fake saved-state failure must not prevent an in-memory cancel signal."""
        app=self.lifecycle();app.start(analysis_enabled=True)
        with patch.object(app,'_save_preferences',side_effect=OSError('fixture cancel write unavailable')):
            result=app.cancel_analysis()
        self.assertEqual(result['status'],'error')
        self.assertTrue(app.runtime.snapshot()['control']['cancel_requested'])


if __name__=='__main__':unittest.main()
