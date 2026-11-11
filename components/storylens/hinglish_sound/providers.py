"""Bounded, credited Freesound acquisition. Credentials never enter model prompts.

Configure FREESOUND_API_KEY for search and FREESOUND_ACCESS_TOKEN for originals.
The application's API agreement and individual file licences are separate.
"""
import json
import os
from pathlib import Path
import requests

BASE = 'https://freesound.org/apiv2'
LICENSES = {'https://creativecommons.org/publicdomain/zero/1.0/': 'CC0',
            'http://creativecommons.org/publicdomain/zero/1.0/': 'CC0',
            'https://creativecommons.org/licenses/by/4.0/': 'CC-BY-4.0',
            'http://creativecommons.org/licenses/by/4.0/': 'CC-BY-4.0'}


def config(root):
    file = Path(root) / 'config.sound-providers.local.json'
    return json.loads(file.read_text(encoding='utf-8-sig')) if file.exists() else {}


def status(root):
    from .online_sources import status as online_status
    cfg = config(root).get('freesound', {})
    key, token = bool(os.getenv('FREESOUND_API_KEY')), bool(os.getenv('FREESOUND_ACCESS_TOKEN'))
    return {**online_status(root),'legacy_freesound_originals': {'ready': bool(cfg.get('enabled') and key and token and cfg.get('api_use_confirmed')),
            'search_key': key, 'original_download_access': token,
            'api_use_confirmed': bool(cfg.get('api_use_confirmed'))},
            'mmaudio': 'optional research model; checkpoint licence is non-commercial',
            'foleycrafter': 'optional external runtime; not installed',
            'soundcraft': 'optional external mixer; not installed'}


def fetch(root, query, category, limit=2, kind='sfx'):
    if not status(root)['legacy_freesound_originals']['ready']:
        return []
    if category not in ('foley', 'ambience', 'impact', 'whoosh', 'riser', 'poke', 'suspense',
                        'cute', 'glitch', 'retro', 'awkward', 'vanish'):
        raise ValueError('Sound provider category unavailable')
    session = requests.Session()
    session.headers.update({'User-Agent': 'Storylens sound library'})
    try:
        r = session.get(BASE + '/search/text/', params={'query': str(query)[:160],
            'page_size': min(5, limit * 2),
            'filter': 'license:"Creative Commons 0" duration:[0.1 TO 35]',
            'fields': 'id,name,username,url,license,duration,tags,type,filesize'},
            headers={'Authorization': 'Token ' + os.environ['FREESOUND_API_KEY']}, timeout=25)
        r.raise_for_status()
        result = []
        for sound in r.json().get('results', []):
            if len(result) >= min(3, limit):
                break
            if sound.get('license') not in LICENSES or sound.get('filesize', 0) > 30_000_000:
                continue
            suffix = str(sound.get('type', '')).lower()
            if suffix not in ('wav', 'mp3', 'ogg', 'flac', 'aiff'):
                continue
            folder = Path(root) / 'library' / 'sound-online' / category
            folder.mkdir(parents=True, exist_ok=True)
            path = folder / f'freesound-{int(sound["id"])}.{suffix}'
            if not path.is_file():
                response = session.get(f'{BASE}/sounds/{int(sound["id"])}/download/',
                    headers={'Authorization': 'Bearer ' + os.environ['FREESOUND_ACCESS_TOKEN']},
                    timeout=45, stream=True)
                response.raise_for_status()
                temp = path.with_suffix(path.suffix + '.partial')
                try:
                    size = 0
                    with temp.open('wb') as out:
                        for chunk in response.iter_content(65536):
                            size += len(chunk)
                            if size > 30_000_000:
                                raise ValueError('Sound provider file exceeds size limit')
                            out.write(chunk)
                    from .library import decode
                    if decode(temp, rate=8000, limit=1).shape[1] == 0:
                        raise ValueError('Sound provider returned empty audio')
                    temp.replace(path)
                finally:
                    temp.unlink(missing_ok=True)
                    response.close()
            meta = {k: sound.get(k) for k in ('id', 'name', 'username', 'url', 'license', 'tags', 'duration')}
            meta.update(provider='Freesound', category=category, kind=kind, original_quality=True)
            Path(str(path) + '.json').write_text(json.dumps(meta, indent=2), encoding='utf-8')
            result.append(str(path))
        return result
    finally:
        session.close()
