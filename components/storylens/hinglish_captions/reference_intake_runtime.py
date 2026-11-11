"""Explicit suite-driven reference lifecycle; no thread/watcher starts on import.

The suite owns ticks, event subscription and resource scheduling. This controller
reuses ReferenceIntake's state, prepare callback and internal GPU serialization.
Cancellation is cooperative at adapter/progress boundaries, not a model abort.
"""
from contextlib import contextmanager
import copy
import os
from pathlib import Path
import threading
import time
import uuid

from . import reference_library
from .reference_intake import DurableState, ReferenceIntake, _prepare, contained


_guards = {}
_guard_lock = threading.Lock()


class _Cancelled(RuntimeError):
    pass


class _DispatchGuard:
    """Nonblocking feature mutex, distinct from the existing GPU lock.

    Held across synchronous work; process death releases the OS lock. A wall-clock
    lease expiry alone must never permit overlap with a still-running worker.
    """
    def __init__(self, path):
        self.path = path
        with _guard_lock:
            self.local = _guards.setdefault(str(path.resolve()).casefold(), threading.Lock())

    @contextmanager
    def acquire(self):
        if not self.local.acquire(blocking=False):
            yield False
            return
        handle = None; acquired = False
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            handle = self.path.open('a+b')
            handle.seek(0, 2)
            if handle.tell() == 0:
                handle.write(b'0'); handle.flush()
            handle.seek(0)
            try:
                if os.name == 'nt':
                    import msvcrt
                    msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                acquired = True
            except (BlockingIOError, PermissionError):
                pass
            yield acquired
        finally:
            if handle is not None:
                if acquired:
                    handle.seek(0)
                    if os.name == 'nt':
                        msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
                    else:
                        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
                handle.close()
            self.local.release()


class ReferenceIntakeRuntime:
    def __init__(self, root, *, serial=None, can_dispatch=None, subscribe=None,
                 prepare=None, clock=time.time, poll_interval=5., event_debounce=.25,
                 debounce=2., backoff=30., lease=3600., state_path=None):
        self.root = Path(root).resolve()
        if poll_interval <= 0 or event_debounce < 0:
            raise ValueError('Polling must be positive and event debounce cannot be negative.')
        self.clock, self.poll_interval, self.event_debounce = clock, poll_interval, event_debounce
        self.serial, self.can_dispatch, self.subscribe = serial, can_dispatch, subscribe
        self._author = prepare or _prepare
        self._started = self._armed = self._in_tick = self._cancel_observed = False
        self._unsubscribe = None
        self._initial = {'control': {'paused': True, 'cancel_requested': False, 'reason': '',
                                     'watch_mode': 'polling', 'event_error': ''},
                         'schedule': {'next_poll_at': 0, 'event_at': None, 'stable_at': None,
                                      'event_sequence': 0, 'scan_requested': True},
                         'last': {}, 'dispatcher': {}}
        self.store = DurableState(self.root, state_path or self.root/'cache/captions/reference-library/intake-runtime-state.json',
                                  'caption-reference-runtime', self._initial)
        self.state_path = self.store.path
        self.guard = _DispatchGuard(self.state_path.with_suffix('.dispatch.lock'))
        self.references = ReferenceIntake(self.root, clock=clock, debounce=debounce, backoff=backoff,
                                          lease=lease, prepare=self._prepare, serial=self._serial)

    def snapshot(self):
        if not self.state_path.exists():
            return {'version':1, 'kind':'caption-reference-runtime', **copy.deepcopy(self._initial)}
        return self.store.snapshot()

    def _view(self, status, **fields):
        control = self.snapshot()['control']
        result = {'status':status, 'watch_mode':control['watch_mode'],
                  'native_preflight':'unverified', **fields}
        if control.get('event_error') and not result.get('technical_details'):
            result['technical_details'] = control['event_error']
        return result

    def _record(self, status, **fields):
        result = self._view(status, **fields)
        with self.store.transaction() as state:
            state['last'] = {**copy.deepcopy(result), 'at':self.clock()}
        return result

    def _error(self, error, *, startup=False):
        fields = {'message': ('Reference startup paused. Check the configured folder and saved progress, then retry.'
                              if startup else 'Reference processing paused. Check the configured folder, scheduler and saved progress, then retry.'),
                  'technical_details': str(error)}
        try:
            return self._record('error', **fields)
        except Exception:
            # A damaged/unwritable state file must not prevent readable reporting
            # or cause the original recovery evidence to be reset/overwritten.
            return {'status':'error', 'watch_mode':'unavailable', 'native_preflight':'unverified', **fields}

    def _require_started(self):
        if not self._started:
            raise ValueError('Start the reference runtime before changing its scheduling state.')

    def start(self):
        """Initialize discovery/subscription only. Every process starts unarmed."""
        try:
            return self._start()
        except Exception as error:
            self._started = self._armed = False
            unsubscribe, self._unsubscribe = self._unsubscribe, None
            if unsubscribe is not None:
                try:
                    unsubscribe()
                except Exception:
                    pass
            return self._error(error, startup=True)

    def _start(self):
        if self._started:
            return self._view('paused' if not self._armed else 'idle')
        self._started = True; self._armed = False
        with self.store.transaction() as state:
            state['schedule']['scan_requested'] = True
            state['control'].update(watch_mode='polling', event_error='')
        if self.subscribe is not None:
            try:
                unsubscribe = self.subscribe(self.on_event)
                if not callable(unsubscribe):
                    raise ValueError('Event subscription must return an unsubscribe callback.')
                self._unsubscribe = unsubscribe
                with self.store.transaction() as state:
                    state['control']['watch_mode'] = 'events+polling'
            except Exception as error:
                with self.store.transaction() as state:
                    state['control'].update(watch_mode='polling', event_error=str(error))
        return self.tick()

    def resume(self):
        """Explicitly allow dispatch, still subject to suite resource permission."""
        self._require_started()
        if not callable(self.serial) or not callable(self.can_dispatch):
            raise ValueError('Connect the existing serial scheduler and resource-permission callback first.')
        with self.store.transaction() as state:
            state['control'].update(paused=False, cancel_requested=False, reason='')
        self._armed = True
        return self._view('idle')

    def pause(self, reason='Reference analysis paused.'):
        self._require_started()
        with self.store.transaction() as state:
            state['control'].update(paused=True, reason=str(reason))
        return self._view('paused')

    def request_cancel(self, reason='Reference analysis cancellation requested.'):
        self._require_started()
        with self.store.transaction() as state:
            state['control'].update(paused=True, cancel_requested=True, reason=str(reason))
        return self._view('cancel_requested', cancellation_observed=False, model_abort_verified=False)

    def stop(self):
        if not self._started:
            return self._view('stopped')
        self._started = self._armed = False
        with self.store.transaction() as state:
            state['control']['paused'] = True
            if self._in_tick:
                state['control']['cancel_requested'] = True
        unsubscribe, self._unsubscribe = self._unsubscribe, None
        if unsubscribe is not None:
            try:
                unsubscribe()
            except Exception as error:
                with self.store.transaction() as state:
                    state['control']['event_error'] = str(error)
        return self._view('stopped', model_abort_verified=False)

    def rescan(self):
        """Schedule a full rescan on the next host tick; does not analyze."""
        self._require_started()
        with self.store.transaction() as state:
            state['schedule'].update(scan_requested=True,
                                     event_sequence=state['schedule']['event_sequence']+1)

    def on_event(self, kind, source=None, destination=None):
        if not self._started:
            return False
        if kind not in ('created','modified','deleted','moved','overflow'):
            raise ValueError('Unsupported reference folder event.')
        accepted = kind == 'overflow'
        for path in (source, destination):
            if path is None:
                continue
            try:
                path = contained(path, [reference_library.folder(self.root)])
            except ValueError as error:
                raise ValueError('Reference event must stay inside the configured folder.') from error
            if path.suffix.lower() in reference_library.EXTENSIONS:
                self.references.notify(path); accepted = True
        if not accepted:
            return False
        with self.store.transaction() as state:
            schedule = state['schedule']
            schedule.update(event_at=self.clock()+self.event_debounce,
                            event_sequence=schedule['event_sequence']+1)
        return True

    def _scan_if_due(self):
        schedule = self.snapshot()['schedule']; now = self.clock()
        deadlines = [schedule['next_poll_at'], schedule.get('event_at'), schedule.get('stable_at')]
        if not schedule['scan_requested'] and not any(d is not None and d <= now for d in deadlines):
            return
        state = self.references.scan()
        stable = [o['stable_since']+self.references.debounce for o in state['observations'].values()
                  if o.get('present') and not o.get('sha256') and o['signature'][0]]
        # A file that keeps changing is scanned again on the next polling/event tick.
        next_stable = min((deadline for deadline in stable if deadline > now), default=None)
        with self.store.transaction() as state:
            current = state['schedule']
            current.update(next_poll_at=now+self.poll_interval, stable_at=next_stable,
                           last_scan_at=now)
            if current['event_sequence'] == schedule['event_sequence']:
                current.update(event_at=None, scan_requested=False)

    def _check_cancel(self):
        if not self._started or self.snapshot()['control']['cancel_requested']:
            self._cancel_observed = True
            raise _Cancelled('Reference analysis stopped at a cooperative boundary; model abort is unverified.')

    def _serial(self, work):
        self._check_cancel()
        def guarded_work():
            self._check_cancel()
            return work()
        return self.serial(guarded_work)

    def _prepare(self, root, ref, folder, progress):
        self._check_cancel()
        def checkpoint(message, data=None):
            progress(message, data)
            self._check_cancel()
        result = self._author(root, ref, folder, checkpoint)
        self._check_cancel()
        return result

    def tick(self):
        """At most one synchronous job; the suite owns when/where ticks run."""
        if not self._started:
            try:
                return self._view('stopped')
            except Exception as error:
                return self._error(error)
        try:
            with self.guard.acquire() as acquired:
                if not acquired:
                    return self._view('busy', message='Another reference worker is still active.')
                self._in_tick = True; self._cancel_observed = False
                token = uuid.uuid4().hex
                try:
                    with self.store.transaction() as state:
                        state['dispatcher'] = {'token':token, 'pid':os.getpid(), 'started_at':self.clock(),
                                               'lease_until':self.clock()+self.references.lease}
                    self._scan_if_due()
                    control = self.snapshot()['control']
                    if control['cancel_requested']:
                        return self._record('cancelled', cancellation_observed=False, model_abort_verified=False,
                                            message='New reference analysis is cancelled; saved work is retained.')
                    if not self._armed or control['paused']:
                        return self._record('paused', message='Reference discovery is active; analysis is paused.')
                    if self.can_dispatch() is not True:
                        return self._record('waiting_for_scheduler', message='Waiting for the shared analysis queue.')
                    asset = self.references.run_next()
                    if self._cancel_observed:
                        return self._record('cancelled', asset=asset, cancellation_observed=True,
                                            model_abort_verified=False,
                                            message='Analysis stopped at a cooperative boundary. Saved progress is retained.')
                    if asset is None:
                        active = [item for item in self.references.snapshot()['assets'].values()
                                  if item['status'] == 'running']
                        if active:
                            return self._record('waiting_for_worker',
                                message='Waiting for the previous reference worker claim to expire or finish.',
                                lease_until=max(item['lease_until'] for item in active))
                        return self._record('idle')
                    return self._record(asset['status'], asset=asset, message=asset.get('message',''))
                finally:
                    self._in_tick = False
                    with self.store.transaction() as state:
                        if state['dispatcher'].get('token') == token:
                            state['dispatcher'] = {}
        except Exception as error:
            return self._error(error)
