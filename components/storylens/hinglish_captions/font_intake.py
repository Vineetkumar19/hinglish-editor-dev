"""Explicit, licensed font intake with injected source/install/host adapters.

No imports or constructors download, install, launch Adobe, or start watchers.
Vision suggestions are review items, never proof of a font's identity/licence.
"""
import copy
import hashlib
from pathlib import Path
import time
from urllib.parse import urlsplit, unquote
import uuid

from .reference_intake import DurableState, contained, file_sha


TARGETS = ('hyperframes', 'premiere', 'aftereffects')
FREE_LICENSES = frozenset(('OFL-1.1', 'Apache-2.0', 'MIT', 'Ubuntu-font-1.0'))
MAX_BYTES = 32 * 1024 * 1024
FACE_KEYS = ('family', 'style', 'postscript')


def _names(path):
    # Read-only existing parser. Its install routine is deliberately never called.
    from tools.install_caption_fonts import names
    names_by_id = names(path)
    return {'family': names_by_id.get(16) or names_by_id.get(1),
            'style': names_by_id.get(17) or names_by_id.get(2),
            'postscript': names_by_id.get(6)}


def _face(value):
    if not isinstance(value, dict) or any(not isinstance(value.get(k), str) or not value[k].strip()
                                          for k in FACE_KEYS):
        raise ValueError('Exact family, style and PostScript metadata are required.')
    return {k: value[k].strip() for k in FACE_KEYS}


def _hash(value):
    if not isinstance(value, str) or len(value) != 64 or any(c not in '0123456789abcdef' for c in value):
        raise ValueError('A verified SHA256 is required.')
    return value


def _official(url):
    parsed = urlsplit(url)
    path = unquote(parsed.path)
    if (parsed.scheme != 'https' or parsed.username or parsed.password or parsed.port not in (None, 443)
            or parsed.query or parsed.fragment or '..' in path.split('/') or '\\' in path):
        return False
    # Narrow, auditable official repositories; arbitrary GitHub repositories are not trusted.
    return parsed.hostname == 'raw.githubusercontent.com' and any(
        path.startswith(prefix) for prefix in ('/google/fonts/', '/googlefonts/', '/rsms/inter/'))


class FontIntake:
    def __init__(self, root, *, allowed_roots=(), install_roots=(), metadata=None,
                 clock=time.time, backoff=30., resolver=None, downloader=None,
                 installer=None, preflight=None, state_path=None, lease=300.):
        self.root = Path(root).resolve()
        self.allowed_roots = tuple(Path(p).resolve() for p in allowed_roots)
        self.install_roots = tuple(Path(p).resolve() for p in install_roots)
        self.metadata = metadata or _names
        self.clock, self.backoff = clock, backoff
        if backoff <= 0 or lease <= 0:
            raise ValueError('Font intake timing must be positive.')
        self.lease = lease
        self.resolver, self.downloader = resolver, downloader
        self.installer, self.preflight = installer, preflight
        self.cache = self.root/'cache/captions/reference-library/font-assets'
        self.store = DurableState(self.root, state_path or self.root/'cache/captions/reference-library/font-intake-state.json',
                                  'caption-fonts', {'requests': {}, 'assets': {}})
        self.state_path = self.store.path

    def snapshot(self):
        return self.store.snapshot()

    @staticmethod
    def _id(request):
        identity = '\0'.join(str(request.get(k, '')).strip().casefold() for k in FACE_KEYS)
        return hashlib.sha256(identity.encode('utf8')).hexdigest()

    def _get(self, request_id):
        return self.snapshot()['requests'][request_id]

    def _update(self, request_id, *, claim=None, **values):
        with self.store.transaction() as state:
            record = state['requests'][request_id]
            if claim is None or record.get('token') == claim:
                record.update(copy.deepcopy(values))
                if record['status'] not in ('resolving', 'installing'):
                    record.pop('token', None); record.pop('lease_until', None)
            return copy.deepcopy(record)

    def _review(self, request_id, reason, *, claim=None):
        return self._update(request_id, claim=claim, status='needs_review', review_count=1,
                            message='This font needs review before it can be used. Supply exact licensed font files or an approved source.',
                            technical_details=str(reason), ready_for=[])

    def propose(self, request):
        request_id = self._id(request)
        with self.store.transaction() as state:
            record = state['requests'].get(request_id)
            if record is None:
                record = {'id': request_id, **{k: request.get(k, '') for k in FACE_KEYS},
                          'origin': request.get('origin', 'unknown'), 'status': 'pending_source',
                          'ready_for': [], 'attempts': 0}
                if request.get('origin') not in ('licensed_manifest', 'supplied_manifest') or not all(record[k] for k in FACE_KEYS):
                    record.update(status='needs_review', review_count=1,
                                  message='Font identity is uncertain. Supply exact licensed metadata for review.')
                state['requests'][request_id] = record
            return copy.deepcopy(record)

    def _check_file(self, path, expected, roots):
        path = contained(path, roots)
        if path.suffix.lower() not in ('.ttf', '.otf'):
            raise ValueError('Only a TTF or OTF font file is supported.')
        if not path.is_file() or not 0 < path.stat().st_size <= MAX_BYTES:
            raise ValueError('Font file is empty, missing or too large.')
        if file_sha(path) != _hash(expected['sha256']):
            raise ValueError('Font bytes do not match the approved SHA256.')
        actual = _face(self.metadata(path))
        if actual != _face(expected):
            raise ValueError('Parsed font family/style/PostScript does not match the requested face.')
        return path, actual

    def _license(self, license_record, roots):
        if license_record.get('id') not in FREE_LICENSES:
            raise ValueError('The supplied licence requires review.')
        path = contained(license_record['path'], roots)
        if not path.is_file() or not 0 < path.stat().st_size <= MAX_BYTES:
            raise ValueError('Licence proof is empty, missing or too large.')
        if file_sha(path) != _hash(license_record.get('sha256')):
            raise ValueError('Licence proof does not match the approved SHA256.')
        return {**license_record, 'path': str(path)}

    def _verified(self, request_id, path, manifest, roots, *, claim=None):
        path, face = self._check_file(path, manifest, roots)
        if face != _face(self._get(request_id)):
            raise ValueError('Resolved face differs from the requested font.')
        if manifest.get('paid') or manifest.get('proprietary') or not manifest.get('source'):
            raise ValueError('A free licensed source must be verified before use.')
        license_record = self._license(manifest.get('license', {}), roots)
        sha = manifest['sha256']
        with self.store.transaction() as state:
            record = state['requests'][request_id]
            if claim is not None and record.get('token') != claim:
                return copy.deepcopy(record)
            if claim is None and record['status'] in ('resolving', 'installing'):
                return copy.deepcopy(record)
            asset = state['assets'].setdefault(sha, {**face, 'sha256': sha, 'path': str(path),
                                                     'source': manifest['source'], 'license': license_record,
                                                     'aliases': []})
            if str(path) not in asset['aliases']:
                asset['aliases'].append(str(path))
            # A second filename must not erase an installation or its host receipts.
            same = record.get('asset_sha256') == sha
            if not same:
                record.pop('installation', None); record.pop('preflight', None)
            if not same or record['status'] not in ('installed_pending_preflight', 'ready'):
                record.update(status='verified', ready_for=[])
            record.update(asset_sha256=sha, **face)
            record.pop('token', None); record.pop('lease_until', None)
            return copy.deepcopy(record)

    def register_local(self, path, manifest):
        path = contained(path, self.allowed_roots)
        if path.suffix.lower() not in ('.ttf', '.otf'):
            raise ValueError('Only a TTF or OTF font file is supported.')
        record = self.propose({**manifest, 'origin': 'supplied_manifest'})
        try:
            return self._verified(record['id'], path, manifest, self.allowed_roots)
        except Exception as error:
            return self._review(record['id'], error)

    def _recover(self, request_id):
        with self.store.transaction() as state:
            record = state['requests'][request_id]
            if record['status'] in ('resolving', 'installing') and record.get('lease_until', 0) <= self.clock():
                if record['status'] == 'installing':
                    record.update(status='needs_review', review_count=1, ready_for=[],
                                  message='The previous font installation stopped without a receipt. Review the installed font before trying again.')
                else:
                    record.update(status='retry', retry_at=self.clock(),
                                  message='Font source preparation stopped. Resuming saved progress.')
                record.pop('token', None); record.pop('lease_until', None)
            return copy.deepcopy(record)

    def startup(self):
        """Explicit recovery hook. Does not start source, installation or host work."""
        for request_id in self.snapshot()['requests']:
            self._recover(request_id)
        return self.snapshot()

    def _resolution(self, record):
        if record.get('paid') or record.get('proprietary'):
            raise ValueError('Paid or proprietary fonts need owner review.')
        _face(record); _hash(record.get('sha256'))
        license_record = record.get('license', {})
        if license_record.get('id') not in FREE_LICENSES:
            raise ValueError('No supported free licence proof was supplied.')
        _hash(license_record.get('sha256'))
        if not _official(record.get('source', '')) or not _official(license_record.get('source', '')):
            raise ValueError('Font and licence must come from trusted official HTTPS sources.')
        filename = record.get('filename', '')
        if Path(filename).name != filename or Path(filename).suffix.lower() not in ('.ttf', '.otf'):
            raise ValueError('Resolved font filename is invalid.')
        return record

    def _download(self, url, sha, target):
        if target.exists() and file_sha(target) == sha:
            return
        data = self.downloader(url)
        if not isinstance(data, bytes) or not 0 < len(data) <= MAX_BYTES or hashlib.sha256(data).hexdigest() != sha:
            raise ValueError('Downloaded bytes do not match the approved SHA256 or size.')
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_name(target.name + '.' + uuid.uuid4().hex + '.tmp')
        try:
            with temporary.open('xb') as output:
                output.write(data); output.flush()
                import os
                os.fsync(output.fileno())
            os.replace(temporary, target)
        finally:
            temporary.unlink(missing_ok=True)

    def resolve(self, request_id):
        record = self._recover(request_id)
        if record['status'] not in ('pending_source', 'retry') or record.get('retry_at', 0) > self.clock():
            return record
        if not self.downloader or (not record.get('resolution') and not self.resolver):
            return self._review(request_id, 'Connect an approved resolver and downloader first.')
        token = uuid.uuid4().hex
        with self.store.transaction() as state:
            current = state['requests'][request_id]
            if current['status'] not in ('pending_source', 'retry'):
                return copy.deepcopy(current)
            current.update(status='resolving', attempts=current['attempts']+1,
                           token=token, lease_until=self.clock()+self.lease)
        try:
            resolution = self._resolution(record.get('resolution') or self.resolver(copy.deepcopy(record)))
            if _face(resolution) != _face(record):
                raise ValueError('Source resolver returned a different font face.')
            # Checkpoint before network I/O, so retry never needs to repeat source selection.
            checkpoint = self._update(request_id, claim=token, resolution=resolution)
            if checkpoint.get('token') != token:
                return checkpoint
            folder = self.cache/resolution['sha256']
            font_path = folder/resolution['filename']; license_path = folder/'LICENSE.txt'
            self._download(resolution['source'], resolution['sha256'], font_path)
            self._download(resolution['license']['source'], resolution['license']['sha256'], license_path)
            manifest = {**resolution, 'license': {**resolution['license'], 'path': str(license_path)}}
            return self._verified(request_id, font_path, manifest, [self.cache], claim=token)
        except (ValueError, KeyError, TypeError) as error:
            return self._review(request_id, error, claim=token)
        except Exception as error:
            attempts = self._get(request_id)['attempts']
            return self._update(request_id, claim=token, status='retry', retry_at=self.clock()+min(3600, self.backoff*2**min(attempts-1, 10)),
                                message='Font source is unavailable. Saved progress will be reused on retry.', technical_details=str(error))

    def _asset(self, record):
        return self.snapshot()['assets'][record['asset_sha256']]

    def _installed(self, asset, receipt):
        if (receipt.get('installed') is not True or receipt.get('scope') != 'user'
                or receipt.get('sha256') != asset['sha256'] or receipt.get('postscript') != asset['postscript']):
            raise ValueError('The installer did not confirm the exact font in the user scope.')
        self._check_file(receipt['path'], asset, self.install_roots)

    def install(self, request_id):
        record = self._recover(request_id)
        token = uuid.uuid4().hex
        claim = None
        if record['status'] not in ('verified', 'installed_pending_preflight', 'ready'):
            return record
        try:
            asset = self._asset(record)
            self._check_file(asset['path'], asset, (*self.allowed_roots, self.cache))
            if record.get('installation'):
                self._installed(asset, record['installation'])
                return record
            if not self.installer:
                raise ValueError('Connect the approved user-scope installer first.')
            with self.store.transaction() as state:
                current = state['requests'][request_id]
                if current['status'] != 'verified':
                    return copy.deepcopy(current)
                current.update(status='installing', token=token, lease_until=self.clock()+self.lease)
                claim = token
            receipt = self.installer(copy.deepcopy(asset))
            self._installed(asset, receipt)
            return self._update(request_id, claim=token, status='installed_pending_preflight', installation=receipt, ready_for=[])
        except Exception as error:
            # Do not blindly retry a callback that may already have installed a font.
            return self._review(request_id, error, claim=claim)

    def check(self, request_id, targets=TARGETS):
        if not targets or any(target not in TARGETS for target in targets):
            raise ValueError('Choose supported font preflight targets.')
        record = self._get(request_id)
        if record['status'] not in ('installed_pending_preflight', 'ready'):
            return record
        try:
            asset = self._asset(record); self._installed(asset, record['installation'])
            if not self.preflight:
                return record
            receipts = self.preflight(copy.deepcopy(asset), tuple(targets))
            previous = record.get('preflight', {})
            for target in targets:
                receipt = receipts.get(target, {})
                previous[target] = {**receipt, 'verified': receipt.get('recognized') is True
                                    and receipt.get('postscript') == asset['postscript']
                                    and receipt.get('sha256') == asset['sha256']}
            ready = [target for target in TARGETS if previous.get(target, {}).get('verified')]
            return self._update(request_id, preflight=previous, ready_for=ready,
                                status='ready' if len(ready) == len(TARGETS) else 'installed_pending_preflight')
        except Exception as error:
            return self._update(request_id, status='installed_pending_preflight', ready_for=[],
                                message='Font recognition has not been confirmed. Recheck the exact face in the requested editor.',
                                technical_details=str(error))
