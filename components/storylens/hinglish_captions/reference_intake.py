"""Durable reference intake. The host supplies scheduling; importing starts no work.

``scan`` consumes the existing reference library, ``notify`` is only a rescan hint,
and ``run_next`` hands one synchronous callable to the host's serial queue. The
existing prepare function owns its GPU lock: never wrap it in another GPU lock.
"""
from contextlib import contextmanager
import copy
import hashlib
import json
import os
from pathlib import Path
import threading
import time
import uuid

from . import reference_library


class UnsupportedMotion(ValueError):
    """A renderer must be supplied before this reference can be prepared."""


def contained(path, roots):
    path = Path(path).resolve()
    if not any(path.is_relative_to(Path(root).resolve()) for root in roots):
        raise ValueError('Path is outside the allowed folder.')
    return path


def file_sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


_locks = {}
_locks_guard = threading.Lock()


class DurableState:
    """Short cross-process transactions; callbacks must run outside transactions."""
    def __init__(self, root, path, kind, initial):
        self.path = contained(path, [root])
        self.kind, self.initial = kind, initial
        with _locks_guard:
            self.lock = _locks.setdefault(str(self.path).casefold(), threading.RLock())

    @contextmanager
    def transaction(self, write=True):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.lock, self.path.with_suffix('.lock').open('a+b') as handle:
            handle.seek(0, 2)
            if handle.tell() == 0:
                handle.write(b'0'); handle.flush()
            handle.seek(0)
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(handle.fileno(), msvcrt.LK_LOCK, 1)
            else:
                import fcntl
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            try:
                if self.path.exists():
                    try:
                        state = json.loads(self.path.read_text('utf8'))
                        if state.get('version') != 1 or state.get('kind') != self.kind:
                            raise ValueError('Unsupported state version or kind')
                        for key, value in self.initial.items():
                            if not isinstance(state.get(key), type(value)):
                                raise ValueError('Invalid state field: ' + key)
                    except (ValueError, AttributeError) as error:
                        raise ValueError('Saved intake state cannot be read; preserve it for recovery.') from error
                else:
                    state = {'version': 1, 'kind': self.kind, **copy.deepcopy(self.initial)}
                yield state
                if write:
                    temporary = self.path.with_name(self.path.name + '.' + uuid.uuid4().hex + '.tmp')
                    try:
                        with temporary.open('x', encoding='utf8') as output:
                            json.dump(state, output, ensure_ascii=False, indent=2, allow_nan=False)
                            output.flush(); os.fsync(output.fileno())
                        os.replace(temporary, self.path)
                    finally:
                        temporary.unlink(missing_ok=True)
            finally:
                handle.seek(0)
                if os.name == 'nt':
                    msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    fcntl.flock(handle.fileno(), fcntl.LOCK_UN)

    def snapshot(self):
        with self.transaction(write=False) as state:
            return copy.deepcopy(state)


def _prepare(root, ref, folder, progress):
    try:
        return reference_library.prepare(root, ref, folder, progress)
    except ValueError as error:
        if 'renderer' in str(error).lower() or 'compatible motion' in str(error).lower():
            raise UnsupportedMotion(str(error)) from error
        raise


class ReferenceIntake:
    def __init__(self, root, *, clock=time.time, debounce=2., backoff=30.,
                 lease=3600., prepare=None, serial=None, discover=None, digest=None,
                 state_path=None):
        self.root = Path(root).resolve()
        self.clock, self.debounce, self.backoff, self.lease = clock, debounce, backoff, lease
        if debounce < 0 or backoff <= 0 or lease <= 0:
            raise ValueError('Intake timing must be positive.')
        self.prepare = prepare or _prepare
        self.serial = serial
        self.discover = discover or reference_library.discover
        self.digest = digest or reference_library.digest
        self.store = DurableState(self.root, state_path or self.root/'cache/captions/reference-library/intake-state.json',
                                  'caption-references', {'observations': {}, 'assets': {}})
        self.state_path = self.store.path

    def snapshot(self):
        return self.store.snapshot()

    def _source(self, path):
        try:
            result = contained(path, [reference_library.folder(self.root)])
        except ValueError as error:
            raise ValueError('Reference must be inside the configured reference folder.') from error
        if result.suffix.lower() not in reference_library.EXTENSIONS:
            raise ValueError('Unsupported reference video file.')
        return result

    def notify(self, path):
        """Validate a watcher hint. The host should debounce/coalesce calls to scan."""
        self._source(path)

    def startup(self):
        return self.scan()

    @staticmethod
    def _signature(path):
        stat = path.stat()
        return [stat.st_size, stat.st_mtime_ns]

    def scan(self):
        rows = list(self.discover(self.root))
        sources = [(self._source(row['source']), row) for row in rows]
        now = self.clock()
        with self.store.transaction() as state:
            for observation in state['observations'].values():
                observation['present'] = False
            for path, row in sources:
                if not path.is_file():
                    continue
                key = str(path).casefold()
                signature = self._signature(path)
                old = state['observations'].get(key)
                if not old or old['signature'] != signature:
                    old = {'signature': signature, 'stable_since': now, 'source': str(path)}
                    state['observations'][key] = old
                old['present'] = True
                if not signature[0] or now - old['stable_since'] < self.debounce:
                    continue
                if not old.get('sha256'):
                    sha = self.digest(path)
                    after = self._signature(path)
                    if signature != after:
                        old.update(signature=after, stable_since=now)
                        continue
                    if len(sha) != 64 or any(c not in '0123456789abcdef' for c in sha):
                        raise ValueError('Reference digest must be a SHA256.')
                    old['sha256'] = sha
                sha = old['sha256']
                asset = state['assets'].setdefault(sha, {'sha256': sha, 'status': 'queued',
                                                       'attempts': 0, 'sources': [], 'checkpoint': {}})
                if str(path) not in asset['sources']:
                    asset['sources'].append(str(path))
                asset['reference'] = {**row, 'source': str(path)}
        return self.snapshot()

    def retry(self, sha):
        with self.store.transaction() as state:
            asset = state['assets'][sha]
            if asset['status'] == 'unsupported':
                raise ValueError('A compatible renderer must be supplied before retrying this reference.')
            if asset['status'] not in ('prepared', 'running'):
                asset.update(status='queued', retry_at=0)

    def run_next(self):
        if self.serial is None:
            raise ValueError('Connect the existing serialized analysis queue before processing references.')
        now = self.clock(); token = uuid.uuid4().hex
        with self.store.transaction() as state:
            for item in state['assets'].values():
                if item['status'] == 'running':
                    if item['lease_until'] > now:
                        return None
                    item.update(status='retry', retry_at=now, message='Analysis stopped; resuming saved progress.')
            candidate = next((item for item in state['assets'].values()
                              if item['status'] in ('queued', 'retry') and item.get('retry_at', 0) <= now
                              and any(o.get('present') and o.get('sha256') == item['sha256']
                                      for o in state['observations'].values())), None)
            if candidate is None:
                return None
            sha = candidate['sha256']
            source = next(o['source'] for o in state['observations'].values()
                          if o.get('present') and o.get('sha256') == sha)
            candidate.update(status='running', token=token, lease_until=now+self.lease,
                             attempts=candidate['attempts']+1)
            ref = {**candidate['reference'], 'source': source,
                   'intake_checkpoint': copy.deepcopy(candidate['checkpoint'])}

        def progress(message, checkpoint=None):
            with self.store.transaction() as state:
                item = state['assets'][sha]
                if item.get('token') != token:
                    raise RuntimeError('Reference claim expired; discard this result.')
                item.update(message=str(message), lease_until=self.clock()+self.lease)
                if checkpoint is not None:
                    item['checkpoint'] = copy.deepcopy(checkpoint)

        def work():
            path = self._source(source)
            if file_sha(path) != sha:
                raise ValueError('Reference changed before analysis. Rescan the folder.')
            folder = self.root/'cache/captions/reference-library/intake-jobs'/sha
            folder.mkdir(parents=True, exist_ok=True)
            result = self.prepare(self.root, ref, folder, progress)
            if not isinstance(result, dict) or result.get('sha256') != sha or not result.get('base_style'):
                raise ValueError('Reference analysis returned no usable matching renderer receipt.')
            if file_sha(path) != sha:
                raise ValueError('Reference changed during analysis. Rescan the folder.')
            return result

        try:
            result = self.serial(work)
            if not isinstance(result, dict) or result.get('sha256') != sha:
                raise ValueError('The queue must return the completed preparation receipt synchronously.')
            status, message = 'prepared', 'Reference prepared.'
        except UnsupportedMotion as error:
            result = None; status, message = 'unsupported', str(error)
        except Exception as error:
            result = None; status, message = 'retry', 'Reference preparation paused. Retry after the source or service recovers.'
            diagnostic = str(error)
        with self.store.transaction() as state:
            item = state['assets'][sha]
            if item.get('token') != token:
                return copy.deepcopy(item)
            item.update(status=status, message=message)
            item.pop('token', None); item.pop('lease_until', None)
            if result is not None:
                item['result'] = copy.deepcopy(result)
            if status == 'retry':
                item.update(retry_at=self.clock()+min(3600, self.backoff*2**min(item['attempts']-1, 10)),
                            technical_details=diagnostic)
            return copy.deepcopy(item)
