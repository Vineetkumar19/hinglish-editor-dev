"""Durable, per-export preparation. Restarting never invents a new batch."""
import hashlib
import json
import shutil
from pathlib import Path

from .durable_json import write


def prepare(assistant, session_id, selected, profile, platforms, dates, text, progress):
    from hinglish_publish.store import fingerprint
    from hinglish_shorts.source import open_video
    from .assistant_distribution import prepare_copy
    from .assistant_publish import transcripts

    # Identity follows the real exports and destination, not a random retry ID.
    sources = [{'video': str(Path(video).resolve()), 'fingerprint': fingerprint(video),
                'kind': kind, 'index': index} for video, kind, index in selected]
    identity = {'sources': sources, 'profile': profile, 'platforms': platforms}
    key = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()[:20]
    folder = assistant.root / 'output/campaigns' / ('edited-' + session_id + '-' + key)
    folder.mkdir(parents=True, exist_ok=True)
    checkpoint = folder / 'preparation.json'
    saved = json.loads(checkpoint.read_text('utf-8')) if checkpoint.exists() else {
        'identity': identity, 'clips': {}, 'model': ''}
    if saved['identity'] != identity:
        raise ValueError('The saved preparation belongs to different exports.')
    assistant._update(session_id, preparation_folder=str(folder))
    media = []
    for source in sources:
        if assistant._stopped(session_id):
            raise ValueError('Stopped. Finished editing outputs are preserved.')
        path = Path(source['video'])
        facts = open_video(path)
        kind, index = source['kind'], source['index']
        if kind == 'short' and (facts.width >= facts.height or facts.duration > 50.1):
            raise ValueError('The workflow requires portrait Shorts no longer than 50 seconds.')
        copied = folder / (f'short-{index:02}.mp4' if kind == 'short' else 'long-youtube.mp4')
        if copied.exists():
            if fingerprint(copied) != source['fingerprint']:
                raise ValueError('A saved campaign export changed. Review it before continuing.')
        else:
            # An interrupted copy cannot masquerade as a finished export.
            partial = copied.with_suffix('.copying')
            shutil.copy2(path, partial)
            partial.replace(copied)
        for suffix in ('.txt', '.publish.json'):
            sidecar = path.with_suffix(suffix)
            if sidecar.is_file() and not copied.with_suffix(suffix).exists():
                shutil.copy2(sidecar, copied.with_suffix(suffix))
        media.append((copied, source, facts))
    from hinglish_publish.features import features,instagram_text_mode
    policy=features(assistant.root)
    needs_writing=('youtube' in platforms and policy['publishing_copy']!='minimal' or
        'instagram' in platforms and (instagram_text_mode(assistant.root,text)=='title_hashtags' or policy['instagram_captions']))
    if needs_writing:
        transcripts(assistant.root, [p for p, _, _ in media], progress)
    clips, longs = [], []
    for copied, source, facts in media:
        if assistant._stopped(session_id):
            raise ValueError('Stopped. Finished editing outputs are preserved.')
        clip_key = source['kind'] + ':' + str(source['index'])
        cached = saved['clips'].get(clip_key)
        if cached:
            if cached['fingerprint'] != source['fingerprint']:
                raise ValueError('The prepared caption belongs to a different export.')
            meta = cached['metadata']
        else:
            meta, model = prepare_copy(assistant.root, copied, profile, text, progress,
                source['kind'] == 'short' and 'instagram' in platforms, transcribe=False,
                youtube=source['kind']=='long' or 'youtube' in platforms,
                source_title=Path(source['video']).stem)
            saved['clips'][clip_key] = {'fingerprint': source['fingerprint'], 'metadata': meta}
            saved['model'] = model
            write(checkpoint, saved)  # Commit each local-model result before the next clip.
        clip = {'index': source['index'], 'video': str(copied),
                'fingerprint': source['fingerprint'], 'duration': facts.duration,
                'publish_at': dates[source['index'] - 1] if source['kind'] == 'short' else dates[0],
                'metadata': meta}
        (clips if source['kind'] == 'short' else longs).append(clip)
    return folder, clips, longs, saved['model']
