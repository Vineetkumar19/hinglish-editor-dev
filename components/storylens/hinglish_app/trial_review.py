"""Local notes for manually uploaded comparisons. No platform operations."""
from datetime import datetime, timezone
from pathlib import Path

from hinglish_cinematic.curation import Store, digest, file_hash
from .workbench_jobs import service


def _trial(state, job_id, variant):
    job = service(state).snapshot(job_id)
    if job['kind'] != 'trials' or job['status'] != 'complete':
        raise ValueError('Choose a completed comparison.')
    if type(variant) is not int or variant not in range(len(job['result']['trials'])):
        raise ValueError('Choose a trial from this comparison.')
    artifact = job['result']['trials'][variant]
    path = Path(artifact['path']).resolve()
    if not path.is_relative_to((state.root / 'output/workbench').resolve()) or not path.is_file():
        raise ValueError('The saved trial file is unavailable.')
    return artifact


def _identity(job_id, variant):
    return digest({'trial_review': job_id, 'variant': variant})[:32]


def _clock(value):
    try:
        time = datetime.fromisoformat(value)
        if time.tzinfo is None:
            raise ValueError
        return time.astimezone(timezone.utc)
    except (TypeError, ValueError):
        raise ValueError('Enter a valid date, time and time zone.') from None


def read(state, job_id, variant):
    artifact = _trial(state, job_id, variant)
    store = Store(state.root / 'cache/curation/projects.sqlite3')
    record_id = _identity(job_id, variant)
    try:
        return store.get(record_id)
    except ValueError:
        return {'id': record_id, 'revision': 0, 'title': '', 'cover_note': '', 'observations': [],
                'job_id': job_id, 'variant': variant, 'input_hashes': [artifact['checksum']]}


def save(state, value):
    job_id = value['job_id']
    variant = value['variant']
    artifact = _trial(state, job_id, variant)
    if value.get('input_hashes') != [artifact['checksum']] or file_hash(artifact['path']) != artifact['checksum']:
        raise ValueError('The trial changed. Reload the matching comparison.')
    title, cover = value.get('title', ''), value.get('cover_note', '')
    if not isinstance(title, str) or not isinstance(cover, str) or len(title) > 220 or len(cover) > 1000:
        raise ValueError('Shorten the title or cover note.')
    observation = value.get('observation')
    if observation is not None:
        post_id = observation.get('post_id', '').strip()
        if not post_id or len(post_id) > 200:
            raise ValueError('Enter the actual trial ID or post URL.')
        posted, observed = _clock(observation.get('posted_at')), _clock(observation.get('observed_at'))
        if observed < posted:
            raise ValueError('Observation time must follow the post time.')
        metrics = {key: observation[key] for key in ('views', 'reach', 'likes', 'comments', 'shares') if key in observation}
        if not metrics or any(type(count) is not int or count < 0 for count in metrics.values()):
            raise ValueError('Enter at least one available metric as a nonnegative whole number.')
        observation = {'post_id': post_id, 'posted_at': posted.isoformat(), 'observed_at': observed.isoformat(),
                       'elapsed_seconds': (observed - posted).total_seconds(), 'metrics': metrics}

    def change(previous):
        history = list(previous.get('observations', [])) if previous else []
        if observation is not None:
            if history and (observation['post_id'], observation['posted_at']) != (history[0]['post_id'], history[0]['posted_at']):
                raise ValueError('Keep the observations bound to the same trial ID and post time.')
            if any(row['observed_at'] == observation['observed_at'] for row in history):
                raise ValueError('An observation already exists for that time.')
            history.append(observation)
            history.sort(key=lambda row: row['observed_at'])
        return {'job_id': job_id, 'variant': variant, 'title': title, 'cover_note': cover,
                'input_hashes': [artifact['checksum']], 'observations': history}

    store = Store(state.root / 'cache/curation/projects.sqlite3')
    return store.mutate(_identity(job_id, variant), 'trial-review', value, change)
