"""Import-safe application adapter for the existing local reference intake.

Suite owns real startup, worker ticks and resource grants. This adapter can only
discover/analyze references; no font runtime, installer, native host or renderer
is connected. Production preparation is the unchanged configured local route.
"""
import copy
from pathlib import Path
import time

from hinglish_captions import reference_library
from hinglish_captions.reference_intake import _prepare as _prepare_reference
from hinglish_captions.reference_intake_runtime import ReferenceIntakeRuntime


_PREFERENCE_KEY = 'application_lifecycle'


class CaptionIntakeLifecycle:
    def __init__(self, root, *, serial=None, can_dispatch=None,
                 analysis_permission=None, local_runtime_ready=None, subscribe=None,
                 clock=time.time, poll_interval=5., event_debounce=.25,
                 debounce=2., backoff=30., lease=3600.):
        self.root = Path(root).resolve()
        self._serial = serial
        self._resource_permission = can_dispatch
        self._analysis_permission, self._local_runtime_ready = analysis_permission, local_runtime_ready
        self._subscribe_factory = subscribe
        self._close_subscription = None
        self._subscription_error = self._runtime_started = False
        self._started = self._analysis_requested = self._analysis_armed = False
        self._gate_reason = 'not_started'
        self._last_result = {'status':'stopped'}
        self.runtime = ReferenceIntakeRuntime(self.root,serial=self._run_serial,
            can_dispatch=self.can_dispatch,subscribe=self._subscribe if subscribe is not None else None,prepare=self._prepare_analysis,
            clock=clock,poll_interval=poll_interval,event_debounce=event_debounce,
            debounce=debounce,backoff=backoff,lease=lease)

    def _subscribe(self, callback):
        close = self._subscribe_factory(callback)
        if not callable(close):
            raise ValueError('The suite reference subscription must return an unsubscribe callback.')
        closed = False
        def close_once():
            nonlocal closed
            if not closed:
                closed = True
                try:
                    close()
                except Exception:
                    self._subscription_error = True
                    raise
        self._close_subscription = close_once
        return close_once

    def _cleanup_runtime(self):
        self._started = self._analysis_armed = False
        ok = True
        try:
            if self._runtime_started:
                self._last_result = self.runtime.stop()
        except Exception:
            ok = False
        finally:
            if self._close_subscription is not None:
                try:
                    self._close_subscription()
                except Exception:
                    ok = False
            self._close_subscription = None
            self._runtime_started = False
        return ok and not self._subscription_error

    @staticmethod
    def _preferences(state):
        value = state.get(_PREFERENCE_KEY)
        if value is None:
            return {'version':1,'analysis_requested':False,'manual_pause':False,'shutdown_pause':False}
        if (not isinstance(value,dict) or value.get('version') != 1
                or any(type(value.get(key)) is not bool for key in ('analysis_requested','manual_pause','shutdown_pause'))):
            raise ValueError('Saved caption lifecycle preferences need review; preserve the existing state.')
        return copy.deepcopy(value)

    def _save_preferences(self, **changes):
        with self.runtime.store.transaction() as state:
            value = self._preferences(state)
            value.update(changes)
            state[_PREFERENCE_KEY] = value
        return value

    def _configured(self):
        return all(callable(callback) for callback in (self._serial,self._resource_permission,
                                                       self._analysis_permission,self._local_runtime_ready))

    def _allowed_policy(self):
        try:
            if not callable(self._analysis_permission) or self._analysis_permission() is not True:
                self._gate_reason = 'analysis_not_permitted'; return False
        except Exception:
            self._gate_reason = 'permission_check_failed'; return False
        try:
            if not callable(self._local_runtime_ready) or self._local_runtime_ready() is not True:
                self._gate_reason = 'local_runtime_not_ready'; return False
        except Exception:
            self._gate_reason = 'readiness_check_failed'; return False
        return True

    def can_dispatch(self):
        """Pure suite gates: never probe/start a model, acquire GPU or inspect Adobe."""
        if not self._started or not self._analysis_armed:
            self._gate_reason = 'analysis_not_armed'; return False
        if not self._allowed_policy():
            return False
        try:
            if not callable(self._resource_permission) or self._resource_permission() is not True:
                self._gate_reason = 'shared_queue_busy'; return False
        except Exception:
            self._gate_reason = 'scheduler_check_failed'; return False
        self._gate_reason = 'permitted_local_analysis'
        return True

    def _run_serial(self, work):
        if not callable(self._serial):
            raise RuntimeError('Connect the normal suite worker before reference analysis.')
        return self._serial(work)

    def _prepare_analysis(self, root, reference, folder, progress):
        # Recheck policy after any queue wait, but not resource availability:
        # the current worker may now legitimately own that resource reservation.
        if not self._started or not self._analysis_armed or not self._allowed_policy():
            raise RuntimeError('Local reference analysis is no longer permitted. Saved progress is retained.')
        return _prepare_reference(root,reference,folder,progress)

    def _error(self, message):
        self._last_result = {'status':'error','message':message}
        return self.status()

    def start(self, *, analysis_enabled=None):
        """Normal app startup. Fresh installs discover only; saved opt-in can resume.

        A true startup preference never clears a saved manual pause/cancellation.
        Even an armed start performs no preparation until a later suite tick.
        """
        if analysis_enabled is not None and type(analysis_enabled) is not bool:
            raise ValueError('Caption analysis startup preference must be true, false or omitted.')
        if self._started:
            return self.status()
        try:
            had_state = self.runtime.state_path.exists()
            before = self.runtime.snapshot()
            preferences = self._preferences(before)
            legacy_pause = had_state and _PREFERENCE_KEY not in before and before['control']['paused']
            paused_outside_shutdown = had_state and before['control']['paused'] and not preferences['shutdown_pause']
            self._runtime_started = True
            self._last_result = self.runtime.start()
            if self._last_result['status'] == 'error':
                failed = self._last_result
                self._cleanup_runtime()
                self._last_result = failed
                return self.status()
            self._started = True
            requested = preferences['analysis_requested'] if analysis_enabled is None else analysis_enabled
            preferences = self._save_preferences(analysis_requested=requested,
                manual_pause=bool(preferences['manual_pause'] or legacy_pause or paused_outside_shutdown))
            self._analysis_requested = requested
            if (requested and not preferences['manual_pause'] and not before['control']['cancel_requested']
                    and self._configured()):
                self.runtime.resume()
                self._analysis_armed = True
                self._gate_reason = 'awaiting_suite_tick'
                self._save_preferences(shutdown_pause=False)
                self._last_result = {'status':'analysis_armed',
                    'message':'Reference analysis will wait for the permitted local-model queue.'}
            elif requested and not self._configured():
                self._gate_reason = 'suite_callbacks_not_connected'
            return self.status()
        except Exception:
            self._cleanup_runtime()
            return self._error('Caption reference startup paused. Check the configured folder and saved lifecycle state; existing files were kept.')

    def resume_analysis(self):
        if not self._started:
            raise ValueError('Start caption discovery before resuming analysis.')
        self._analysis_requested = True
        self._save_preferences(analysis_requested=True,manual_pause=False,shutdown_pause=False)
        if not self._configured():
            self._analysis_armed = False; self._gate_reason = 'suite_callbacks_not_connected'
            self._last_result = {'status':'discovery_only','message':'The suite must connect its normal queue, permissions and local runtime check before analysis.'}
        else:
            self.runtime.resume(); self._analysis_armed = True; self._gate_reason = 'awaiting_suite_tick'
            self._last_result = {'status':'analysis_armed','message':'Reference analysis will wait for the permitted local-model queue.'}
        return self.status()

    def pause_analysis(self, reason='Reference analysis paused.'):
        if not self._started:
            raise ValueError('Start caption discovery before pausing analysis.')
        self._analysis_armed = False
        self._save_preferences(manual_pause=True,shutdown_pause=False)
        self._last_result = self.runtime.pause(reason)
        return self.status()

    def cancel_analysis(self, reason='Reference analysis cancelled.'):
        if not self._started:
            raise ValueError('Start caption discovery before cancelling analysis.')
        self._analysis_armed = False
        self._save_preferences(manual_pause=True,shutdown_pause=False)
        self._last_result = self.runtime.request_cancel(reason)
        return self.status()

    def tick(self):
        if self._started:
            self._last_result = self.runtime.tick()
        return self.status()

    def rescan(self):
        self.runtime.rescan()

    def on_event(self, kind, source=None, destination=None):
        return self.runtime.on_event(kind,source,destination)

    def stop(self):
        if not self._started and not self._runtime_started:
            return self.status()
        saved = True
        try:
            state = self.runtime.snapshot()
            preferences = self._preferences(state)
            self._save_preferences(shutdown_pause=bool(self._analysis_requested and not preferences['manual_pause']
                                                      and not state['control']['cancel_requested']))
        except Exception:
            saved = False
        cleaned = self._cleanup_runtime()
        self._gate_reason = 'not_started'
        if not saved or not cleaned:
            self._last_result = {'status':'error',
                'message':'New caption analysis is disabled; saved shutdown state or event subscription needs review.'}
        return self.status()

    def status(self):
        """Read-only application view. No readiness or resource callbacks run here."""
        counts = {}; folder = None; error = None
        try:
            folder = str(reference_library.folder(self.root).resolve())
            if self.runtime.references.state_path.exists():
                for asset in self.runtime.references.snapshot()['assets'].values():
                    counts[asset['status']] = counts.get(asset['status'],0)+1
        except Exception:
            error = 'Saved reference state or configured folder could not be read. Preserve it for recovery.'
        result = copy.deepcopy(self._last_result)
        return {'status':'error' if error else result['status'],
            'message':error or result.get('message',''), 'source_folder':folder,
            'analysis':{'requested':self._analysis_requested,'armed':self._analysis_armed,
                        'gate_reason':self._gate_reason,'provider':'configured_local_ollama'},
            'job_counts':counts,'runtime_state_path':str(self.runtime.state_path),
            'reference_state_path':str(self.runtime.references.state_path),'runtime_result':result,
            'font_native_gate':{'blocked':True,'font_resolution':'blocked','font_download':'blocked',
                'font_install':'blocked','native_preflight':'blocked','native_export':'blocked',
                'native_readiness':'unverified'},
            'live_acceptance':'not_established_by_adapter'}
