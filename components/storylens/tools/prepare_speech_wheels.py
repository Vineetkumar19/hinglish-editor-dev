"""Prefetch the already-resolved speech dependencies with hashes and resumable ranges."""
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import shutil
import time
from urllib.parse import unquote, urlsplit
from urllib.request import Request, urlopen
from ranged_download import ranged_get

STORE = Path(r'C:\Ai Models')
WHEELS = STORE/'runtimes/wheels'


def main():
    WHEELS.mkdir(parents=True,exist_ok=True)
    report = json.loads((STORE/'logs/speech-runtime-install.json').read_text())
    temporary_files = {p.name:p for p in (STORE/'runtimes/tmp').rglob('*') if p.is_file() and p.name.endswith(('.whl','.tar.gz'))}
    def fetch(row):
        info = row['download_info']; url = info['url']; parsed = urlsplit(url)
        name = unquote(parsed.path.rsplit('/',1)[-1]); target = WHEELS/name
        digest = info['archive_info']['hashes']['sha256']
        def valid(path):
            return path.is_file() and hashlib.sha256(path.read_bytes()).hexdigest()==digest
        if valid(target):
            return
        if parsed.scheme=='file':
            source = Path(unquote(parsed.path).lstrip('/'))
            if not source.resolve().is_relative_to(STORE.resolve()) or not valid(source):
                raise ValueError('Invalid local wheel source')
            shutil.copy2(source,target);return
        if parsed.scheme!='https' or parsed.hostname!='files.pythonhosted.org':
            raise ValueError('Only the resolved official PyPI artifacts are allowed')
        partial = target.with_name(name+'.incomplete')
        saved = temporary_files.get(name)
        if saved and not partial.exists():
            shutil.copy2(saved,partial)
        for attempt in range(5):
            try:
                with urlopen(Request(url,method='HEAD'),timeout=45) as response:
                    size = int(response.headers['Content-Length'])
                with partial.open('r+b' if partial.exists() else 'w+b') as stream:
                    resume = stream.seek(0,2)
                    ranged_get(url,stream,size,resume,workers=8,expected_sha256=digest,download_root=STORE)
                partial.replace(target)
                print('SPEECH_WHEEL_VERIFIED '+name,flush=True)
                return
            except Exception:
                if attempt==4:raise
                time.sleep(min(2**attempt,12))
    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(fetch,report['install']))
    print('ALL_SPEECH_DEPENDENCIES_CACHED',flush=True)


if __name__=='__main__':main()
