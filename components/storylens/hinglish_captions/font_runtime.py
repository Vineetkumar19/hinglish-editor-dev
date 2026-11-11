"""Suite-gated exact-font callbacks; no network/OS/host work on import.

Uses the existing bundled name parser and per-user Windows installation approach.
Approved manifests are explicit inputs, not a crawled or inferred font catalogue.
This module never computes global font readiness or repairs protected intake state.
"""
from contextlib import contextmanager
import copy
import hashlib
import os
from pathlib import Path
import re
import time
from urllib.parse import urljoin

from .font_intake import TARGETS, _face, _hash, _official
from .reference_intake import contained, file_sha
from .reference_intake_runtime import _DispatchGuard


class FontReviewRequired(ValueError):
    """Exact identity/source/licence or a safe execution boundary needs review."""


def _signature(data):
    if data[:4] not in (b'\0\1\0\0', b'OTTO', b'true'):
        raise FontReviewRequired('The file is not a supported TTF/OTF font. Keep it for review; do not execute it.')


def read_font_metadata(path):
    """Read exact bundled sfnt name IDs, without running the existing installer."""
    from tools.install_caption_fonts import names
    path = Path(path)
    if path.suffix.lower() not in ('.ttf', '.otf') or not 0 < path.stat().st_size <= 32*1024*1024:
        raise FontReviewRequired('Choose a bounded TTF or OTF font file.')
    with path.open('rb') as source:
        _signature(source.read(4))
    try:
        table = names(path)
        return {**_face({'family':table.get(16) or table.get(1),
                         'style':table.get(17) or table.get(2),'postscript':table.get(6)}),
                'fullname':table.get(4) or ''}
    except Exception as error:
        raise FontReviewRequired('The font has no usable exact family/style/PostScript metadata.') from error


class WindowsUserFontOS:
    """Lazy HKCU-only boundary, following tools/install_caption_fonts.py.

    Constructing does not access the registry. The suite must gate actual calls.
    No batch installer, system-wide registration, elevation or Adobe launch.
    """
    KEY = r'Software\Microsoft\Windows NT\CurrentVersion\Fonts'

    def expected_root(self):
        if os.name != 'nt' or not os.environ.get('LOCALAPPDATA'):
            raise FontReviewRequired('Per-user Windows font installation is unavailable on this computer.')
        return Path(os.environ['LOCALAPPDATA'])/'Microsoft/Windows/Fonts'

    def lookup(self, name):
        import winreg
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, self.KEY) as key:
                value, kind = winreg.QueryValueEx(key, name)
                if kind != winreg.REG_SZ or not isinstance(value, str):
                    raise FontReviewRequired('An existing font registration needs review; it was preserved.')
                return value
        except FileNotFoundError:
            return None

    def register(self, name, path):
        import winreg
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, self.KEY) as key:
            try:
                previous, _ = winreg.QueryValueEx(key, name)
            except FileNotFoundError:
                previous = None
            if previous is not None and str(Path(previous).resolve()).casefold() != str(Path(path).resolve()).casefold():
                raise FontReviewRequired('A different existing font registration was kept. Review it before installing this face.')
            winreg.SetValueEx(key, name, 0, winreg.REG_SZ, str(path))

    def activate(self, path):
        import ctypes
        return ctypes.windll.gdi32.AddFontResourceExW(str(path), 0, None)

    def notify(self):
        import ctypes
        result = ctypes.c_size_t()
        ctypes.windll.user32.SendMessageTimeoutW(0xffff, 0x001D, 0, 0, 2, 3000, ctypes.byref(result))


class FontRuntime:
    def __init__(self, root, *, records=(), allowed_roots=(), install_root=None,
                 metadata=read_font_metadata, transport=None, os_api=None,
                 allow_download=None, allow_install=None, allow_preflight=None,
                 native_preflight=None, native_sessions=None, clock=time.monotonic,
                 max_bytes=32*1024*1024, deadline=45., max_redirects=3):
        self.root = Path(root).resolve()
        self.records = copy.deepcopy(list(records))
        self.allowed_roots = tuple(Path(path).resolve() for path in allowed_roots)
        self.install_root = Path(install_root).resolve() if install_root is not None else None
        self.metadata, self.transport = metadata, transport
        self.os_api = os_api or WindowsUserFontOS()
        self.allow_download, self.allow_install, self.allow_preflight = allow_download, allow_install, allow_preflight
        self.native_preflight, self.native_sessions = native_preflight, native_sessions
        if max_bytes <= 0 or deadline <= 0 or max_redirects < 0:
            raise ValueError('Font transport limits must be positive.')
        self.clock, self.max_bytes, self.deadline, self.max_redirects = clock, max_bytes, deadline, max_redirects
        self.fetch_receipts = []
        self.guard = _DispatchGuard(self.root/'cache/captions/reference-library/font-install.dispatch.lock')

    def callbacks(self):
        return {'metadata':self.metadata,'resolver':self.resolve,'downloader':self.download,
                'installer':self.install,'preflight':self.preflight}

    @staticmethod
    def _gate(callback, action):
        if not callable(callback) or callback() is not True:
            raise FontReviewRequired('The suite must explicitly permit '+action+' before it can start.')

    @staticmethod
    def _record(record):
        try:
            _face(record); _hash(record.get('sha256'))
            if record.get('paid') or record.get('proprietary'):
                raise ValueError('Paid/proprietary font')
            license_record = record['license']
            if license_record.get('id') != 'OFL-1.1':
                raise ValueError('This adapter currently supports explicit OFL-1.1 proof only')
            _hash(license_record.get('sha256'))
            if not _official(record.get('source','')) or not _official(license_record.get('source','')):
                raise ValueError('Font and licence require approved official HTTPS sources')
            filename = record['filename']
            if not isinstance(filename,str) or Path(filename).name != filename or Path(filename).suffix.lower() not in ('.ttf','.otf'):
                raise ValueError('Unsupported font filename')
            return copy.deepcopy(record)
        except (ValueError, KeyError, TypeError, AttributeError) as error:
            raise FontReviewRequired('The exact free font/source/licence manifest needs review: '+str(error)) from error

    def resolve(self, request):
        try:
            face = _face(request)
            if request.get('origin') not in ('licensed_manifest','supplied_manifest'):
                raise ValueError('A pixel/vision guess cannot prove the exact font identity')
            candidates = [record for record in self.records if all(record.get(key)==value for key,value in face.items())]
            if len(candidates) != 1:
                raise ValueError('Supply one unambiguous exact licensed manifest; no lookalike will be substituted')
            return self._record(candidates[0])
        except ValueError as error:
            raise FontReviewRequired('Font identity needs review: '+str(error)) from error

    def _approved_fetch(self, url):
        matches = []
        for raw in self.records:
            if raw.get('source') != url and raw.get('license',{}).get('source') != url:
                continue
            record = self._record(raw)
            if record['source'] == url:
                matches.append((record['sha256'],'font'))
            if record['license']['source'] == url:
                matches.append((record['license']['sha256'],'license'))
        if not matches or len(set(matches)) != 1 or not _official(url):
            raise FontReviewRequired('This font URL has no unambiguous approved official-free manifest.')
        return matches[0]

    @contextmanager
    def _response(self, url, timeout):
        response = session = None
        try:
            if self.transport is not None:
                response = self.transport(url, timeout=timeout, stream=True, allow_redirects=False)
            else:
                import requests
                session = requests.Session(); session.trust_env = False
                response = session.get(url,timeout=timeout,stream=True,allow_redirects=False)
            yield response
        finally:
            if response is not None:
                response.close()
            if session is not None:
                session.close()

    @staticmethod
    def _ofl(data):
        text = data.decode('utf-8-sig',errors='replace').casefold()
        if 'sil open font license' not in text or 'version 1.1' not in text:
            raise FontReviewRequired('The supplied bytes do not contain the expected OFL-1.1 licence proof.')

    def download(self, url):
        self._gate(self.allow_download,'a font source download')
        expected, kind = self._approved_fetch(url)
        started = self.clock(); current = url; chain = []
        for hop in range(self.max_redirects+1):
            remaining = self.deadline-(self.clock()-started)
            if remaining <= 0:
                raise TimeoutError('The bounded font download time expired. Retry when the source is available.')
            if not _official(current):
                raise FontReviewRequired('The font source redirected outside trusted official HTTPS sources.')
            with self._response(current,(min(5.,remaining),min(5.,remaining))) as response:
                final = response.url or current
                if not _official(final):
                    raise FontReviewRequired('The transport returned an untrusted final source.')
                chain.append(final)
                if response.status_code in (301,302,303,307,308):
                    location = response.headers.get('Location')
                    if not location or hop == self.max_redirects:
                        raise FontReviewRequired('The font source redirect chain needs review.')
                    current = urljoin(final,location)
                    continue
                if response.status_code != 200:
                    raise OSError('The official font source is temporarily unavailable (HTTP '+str(response.status_code)+').')
                length = response.headers.get('Content-Length')
                if length is not None:
                    try:
                        declared = int(length)
                    except (ValueError,TypeError) as error:
                        raise FontReviewRequired('The font source returned an invalid size.') from error
                    if declared < 0 or declared > self.max_bytes:
                        raise FontReviewRequired('The font source exceeds the approved size limit.')
                data = bytearray()
                for chunk in response.iter_content(chunk_size=64*1024):
                    if self.clock()-started > self.deadline:
                        raise TimeoutError('The bounded font download time expired.')
                    if not chunk:
                        continue
                    if not isinstance(chunk,bytes) or len(data)+len(chunk) > self.max_bytes:
                        raise FontReviewRequired('The font source exceeds the approved size limit.')
                    data.extend(chunk)
                data = bytes(data)
                if not data or hashlib.sha256(data).hexdigest() != expected:
                    raise FontReviewRequired('Downloaded font/licence bytes differ from the approved manifest.')
                self._ofl(data) if kind == 'license' else _signature(data)
                self.fetch_receipts.append({'requested_url':url,'final_url':final,'redirects':chain,
                    'sha256':expected,'bytes':len(data),'kind':kind,'elapsed_seconds':self.clock()-started})
                self.fetch_receipts = self.fetch_receipts[-100:]
                return data
        raise FontReviewRequired('The font source redirect chain needs review.')

    def _file(self, path, expected, roots):
        try:
            path = contained(path,roots)
            if path.suffix.lower() not in ('.ttf','.otf') or not path.is_file() or not 0 < path.stat().st_size <= self.max_bytes:
                raise ValueError('Unsupported or missing font file')
            data = path.read_bytes(); _signature(data)
            if len(data)>self.max_bytes or hashlib.sha256(data).hexdigest()!=_hash(expected['sha256']):
                raise ValueError('Font bytes differ from the approved SHA256')
            metadata = self.metadata(path)
            if _face(metadata) != _face(expected) or file_sha(path) != expected['sha256']:
                raise ValueError('Parsed font identity differs from the approved face or changed during reading')
            for name in (*_face(metadata).values(), metadata.get('fullname','')):
                if not isinstance(name,str) or any(ord(character)<32 for character in name):
                    raise ValueError('Invalid control character in font names')
            return path, metadata, data
        except Exception as error:
            raise FontReviewRequired('The exact source font needs review: '+str(error)) from error

    def _license_file(self, license_record):
        try:
            path = contained(license_record['path'],self.allowed_roots)
            if license_record.get('id') != 'OFL-1.1' or not path.is_file() or not 0 < path.stat().st_size <= self.max_bytes:
                raise ValueError('Missing verified OFL-1.1 proof')
            data = path.read_bytes()
            if hashlib.sha256(data).hexdigest() != _hash(license_record.get('sha256')):
                raise ValueError('Licence proof differs from its expected SHA256')
            self._ofl(data)
            return path
        except Exception as error:
            raise FontReviewRequired('Font licence proof needs review: '+str(error)) from error

    def bundle_record(self, font, license_path, sources):
        """Read a caller-selected existing font/licence association; never guess it."""
        try:
            font = contained(font,self.allowed_roots); license_path = contained(license_path,self.allowed_roots)
            entry, license_entry = sources[font.name], sources[license_path.name]
            metadata = self.metadata(font)
            record = {**_face(metadata),'filename':font.name,'source':entry['source'],'sha256':entry['sha256'],
                'license':{'id':'OFL-1.1','source':license_entry['source'],'sha256':license_entry['sha256'],'path':str(license_path)}}
            self._record(record); self._file(font,record,self.allowed_roots); self._license_file(record['license'])
            return record
        except Exception as error:
            raise FontReviewRequired('The bundled font/licence association needs review: '+str(error)) from error

    def install(self, asset):
        self._gate(self.allow_install,'a per-user font installation')
        # Deliberately require the canonical source. Do not route around the
        # protected missing-canonical-alias finding in FontIntake.
        source, metadata, data = self._file(asset['path'],asset,self.allowed_roots)
        self._license_file(asset.get('license',{}))
        if self.install_root is None or self.install_root != Path(self.os_api.expected_root()).resolve():
            raise FontReviewRequired('Choose the approved per-user Windows font directory before installing.')
        title = metadata.get('fullname') or metadata['family']+' '+metadata['style']
        value = title+(' (OpenType)' if source.suffix.lower()=='.otf' else ' (TrueType)')
        safe = re.sub(r'[^A-Za-z0-9_.-]','_',asset['postscript'])[:80]
        target = self.install_root/('Storylens-'+asset['sha256']+'-'+safe+source.suffix.lower())
        with self.guard.acquire() as acquired:
            if not acquired:
                raise RuntimeError('Another font installation is active. Wait for its receipt before retrying.')
            registered = self.os_api.lookup(value)
            if registered is not None:
                target, _, _ = self._file(registered,asset,[self.install_root])
                return self._installed(asset,target,reused=True)
            self.install_root.mkdir(parents=True,exist_ok=True)
            if target.exists():
                self._file(target,asset,[self.install_root])
            else:
                # Exclusive creation: never replace an existing owner's file.
                with target.open('xb') as output:
                    output.write(data); output.flush(); os.fsync(output.fileno())
                self._file(target,asset,[self.install_root])
            self.os_api.register(value,target)
            if str(Path(self.os_api.lookup(value)).resolve()).casefold() != str(target.resolve()).casefold():
                raise RuntimeError('Windows did not confirm the expected per-user font registration. Review its state.')
            if not self.os_api.activate(target):
                raise RuntimeError('The font was saved but activation was not confirmed. Review it before retrying; native recognition remains unverified.')
            self.os_api.notify()
            return self._installed(asset,target,reused=False)

    @staticmethod
    def _installed(asset,target,*,reused):
        return {'installed':True,'scope':'user','path':str(target.resolve()),'sha256':asset['sha256'],
            'postscript':asset['postscript'],'status':'installed_pending_preflight',
            'native_recognition_verified':False,'reused':reused}

    @staticmethod
    def _unverified(targets, reason):
        return {target:{'recognized':False,'status':'unverified','reason':reason} for target in targets}

    def preflight(self, asset, targets):
        if not targets or any(target not in TARGETS for target in targets):
            raise FontReviewRequired('Choose supported per-target font checks.')
        if len(set(targets)&{'premiere','aftereffects'}) > 1:
            return self._unverified(targets,'The suite must check one Adobe host at a time.')
        if (not callable(self.allow_preflight) or self.allow_preflight() is not True
                or not callable(self.native_preflight) or not callable(self.native_sessions)):
            return self._unverified(targets,'The suite must supply permitted actual host/renderer recognition and current-session callbacks.')
        contexts = self.native_sessions(tuple(targets))
        if any(not contexts.get(target,{}).get('session_id') or not contexts.get(target,{}).get('font_epoch') for target in targets):
            return self._unverified(targets,'Current native session/font reload identity is unverified.')
        # Provider failures deliberately propagate. Do not mask/route around
        # FontIntake's protected stale-global-readiness finding.
        receipts = self.native_preflight(copy.deepcopy(asset),tuple(targets),copy.deepcopy(contexts))
        current_contexts = self.native_sessions(tuple(targets))
        result = {}
        for target in targets:
            receipt = receipts.get(target,{})
            recognized = (receipt.get('recognized') is True and receipt.get('target')==target
                and current_contexts.get(target)==contexts[target]
                and receipt.get('session_id')==contexts[target]['session_id']
                and receipt.get('font_epoch')==contexts[target]['font_epoch']
                and receipt.get('postscript')==asset['postscript'] and receipt.get('sha256')==asset['sha256'])
            result[target] = {**receipt,'recognized':recognized,
                'status':'recognized_current_session' if recognized else 'unverified'}
        return result
