"""Bounded, resumable HTTP ranges for large official model/runtime files."""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
from html.parser import HTMLParser
import os
from pathlib import Path
import re
import time
from urllib.parse import unquote, urljoin, urlsplit
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
CHUNK = 1024 * 1024


def permitted_roots(download_root=None):
    if download_root is None:
        import json
        settings = ROOT / 'config.model_storage.local.json'
        if settings.is_file():
            download_root = json.loads(settings.read_text(encoding='utf-8-sig')).get('root')
    return (ROOT,) if not download_root else (ROOT, Path(download_root).resolve())


def ranged_get(url, stream, size, resume=0, headers=None, workers=32, expected_sha256=None, download_root=None):
    target = Path(stream.name).resolve()
    roots = permitted_roots(download_root)
    if not any(target.is_relative_to(root) for root in roots):
        raise ValueError('Download destination must stay in the configured download roots')
    parts = target.with_name(target.name + '.ranges')
    parts.mkdir(exist_ok=True)
    if not 0 <= resume <= size:
        raise ValueError('Invalid resume position')
    ranges = [(start, min(size, start + CHUNK)) for start in range(resume, size, CHUNK)]

    def fetch(bounds):
        start, end = bounds
        part = parts / f'part-{start}-{end}.bin'
        if part.is_file() and part.stat().st_size == end - start:
            return part
        temporary = part.with_suffix('.tmp')
        for attempt in range(5):
            try:
                # Keep bytes received before a connection reset. Retrying the
                # whole range can otherwise discard nearly-complete chunks.
                saved = temporary.stat().st_size if temporary.is_file() else 0
                if saved > end - start:
                    temporary.unlink()
                    saved = 0
                if saved == end - start:
                    temporary.replace(part)
                    return part
                request_start = start + saved
                started = time.monotonic()
                request_headers = dict(headers or {})
                request_headers.update({'Range': f'bytes={request_start}-{end - 1}', 'Accept-Encoding': 'identity'})
                with urlopen(Request(url, headers=request_headers), timeout=45) as response:
                    content_range = response.headers.get('Content-Range', '')
                    if response.status != 206 or not content_range.startswith(f'bytes {request_start}-{end - 1}/'):
                        raise ValueError('Server did not honor the requested byte range')
                    with temporary.open('ab') as output:
                        remaining = end - request_start
                        while remaining:
                            if time.monotonic() - started > 90:
                                raise TimeoutError('Range transfer exceeded its retry window')
                            # read1 returns available data, letting the transfer deadline
                            # be checked even when a server trickles bytes indefinitely.
                            block = response.read1(min(64 * 1024, remaining))
                            if not block:
                                raise IOError('Range response ended early')
                            output.write(block)
                            remaining -= len(block)
                temporary.replace(part)
                return part
            except Exception:
                if attempt == 4:
                    raise
                time.sleep(min(2 ** attempt, 8))

    stream.seek(resume)
    last_report = resume
    with ThreadPoolExecutor(max_workers=workers) as pool:
        pending = {pool.submit(fetch, bounds): bounds for bounds in ranges}
        ready = {}
        cursor = resume
        for future in as_completed(pending):
            start, end = pending[future]
            ready[start] = (end, future.result())
            # A slow range must not leave every other connection idle. Completed
            # ranges wait on disk until the contiguous prefix can be committed.
            while cursor in ready:
                end, part = ready.pop(cursor)
                with part.open('rb') as source:
                    while block := source.read(1024 * 1024):
                        stream.write(block)
                stream.flush()
                if not any(parts.resolve().is_relative_to(root) for root in roots):
                    raise ValueError('Unsafe temporary download directory')
                part.unlink()
                cursor = end
            written = stream.tell()
            if written - last_report >= 64 * 1024 * 1024 or written == size:
                print(f'  {target.name}: {written / 2**30:.2f}/{size / 2**30:.2f} GiB ({100 * written / size:.0f}%)', flush=True)
                last_report = written
    if stream.tell() != size:
        raise IOError('Download size mismatch')
    stream.flush()
    if expected_sha256:
        with target.open('rb') as source:
            digest = hashlib.file_digest(source, 'sha256').hexdigest()
        if digest.lower() != expected_sha256.lower():
            stream.seek(0)
            stream.truncate()
            raise ValueError('SHA-256 mismatch; partial file reset for a clean retry')
        print('  SHA-256 verified: ' + target.name, flush=True)
    try:
        parts.rmdir()
    except OSError:
        pass


def patch_huggingface(download_root=None):
    import huggingface_hub.file_download as module
    original = module.http_get

    def download(url, temp_file, *, expected_size=None, resume_size=0, headers=None, **kwargs):
        name = Path(temp_file.name).name.removesuffix('.incomplete').rsplit('.', 1)[-1]
        expected_hash = name if re.fullmatch('[0-9a-f]{64}', name) else None
        # LFS tokenizers can also exceed normal transfer timeouts. Their ETags
        # supply a verifiable SHA-256 even in local_dir's prefixed filenames.
        if expected_size and (expected_size >= 64 * 1024 * 1024 or
                              expected_size >= 1024 * 1024 and expected_hash):
            options = {} if download_root is None else {'download_root': download_root}
            return ranged_get(url, temp_file, expected_size, resume_size, headers, expected_sha256=expected_hash, **options)
        return original(url, temp_file, expected_size=expected_size, resume_size=resume_size, headers=headers, **kwargs)

    module.http_get = download


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('url')
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--sha256')
    parser.add_argument('--index-url', help='Resolve the wheel hash from an official simple package index')
    args = parser.parse_args()
    sha = args.sha256
    if args.index_url:
        class Links(HTMLParser):
            hrefs = []
            def handle_starttag(self, tag, attrs):
                if tag == 'a':
                    self.hrefs.extend(v for k, v in attrs if k == 'href')
        with urlopen(args.index_url, timeout=45) as response:
            page = response.read().decode()
        links = Links()
        links.feed(page)
        name = unquote(urlsplit(args.url).path.rsplit('/', 1)[-1])
        link = next(h for h in links.hrefs if unquote(urlsplit(h).path.rsplit('/', 1)[-1]) == name)
        sha = urlsplit(link).fragment.removeprefix('sha256=')
        if not re.fullmatch('[0-9a-f]{64}', sha):
            raise ValueError('Official wheel index did not provide a valid SHA-256')
    with urlopen(Request(args.url, method='HEAD'), timeout=45) as response:
        size = int(response.headers['Content-Length'])
    output = args.output.resolve()
    if not any(output.is_relative_to(root) for root in permitted_roots()):
        raise ValueError('Download destination must stay in the configured download roots')
    output.parent.mkdir(parents=True, exist_ok=True)
    partial = output.with_suffix(output.suffix + '.incomplete')
    if output.is_file() and output.stat().st_size < size and not partial.exists():
        output.replace(partial)
    resume = partial.stat().st_size if partial.is_file() else 0
    if output.is_file() and output.stat().st_size == size and sha:
        with output.open('rb') as source:
            if hashlib.file_digest(source, 'sha256').hexdigest() == sha:
                print('Already verified: ' + str(output))
                return
    with partial.open('r+b' if partial.exists() else 'w+b') as stream:
        ranged_get(args.url, stream, size, resume, expected_sha256=sha)
    partial.replace(output)
    print('Downloaded and verified: ' + str(output), flush=True)


if __name__ == '__main__':
    main()
