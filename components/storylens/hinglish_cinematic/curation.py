"""Source-bound curation records. No model calls, workers or native mutations."""
from contextlib import closing
from fractions import Fraction
from pathlib import Path
import hashlib
import json
import math
import sqlite3
import time
import uuid


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def file_hash(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


PHASES = {
    'travel': ['departure', 'travel', 'approach', 'reveal', 'experience', 'closing'],
    'waterfall': ['departure', 'travel', 'approach', 'reveal', 'experience', 'closing'],
    'party': ['preparation', 'travel', 'arrival', 'atmosphere', 'highlights', 'closing'],
}


class RevisionConflict(ValueError):
    pass


class Store:
    """Dedicated project records; deliberately not a second job scheduler."""
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with closing(self.connect()) as db, db:
            db.executescript('''
              PRAGMA journal_mode=WAL;
              CREATE TABLE IF NOT EXISTS records (
                id TEXT PRIMARY KEY, kind TEXT NOT NULL, revision INTEGER NOT NULL,
                payload TEXT NOT NULL);
              CREATE TABLE IF NOT EXISTS revisions (
                id TEXT, revision INTEGER, payload TEXT NOT NULL,
                PRIMARY KEY(id,revision));
              CREATE TABLE IF NOT EXISTS commands (
                key TEXT PRIMARY KEY, request_hash TEXT NOT NULL, response TEXT NOT NULL);
              CREATE TABLE IF NOT EXISTS analysis_cache (
                key TEXT PRIMARY KEY, payload TEXT NOT NULL);
              CREATE UNIQUE INDEX IF NOT EXISTS sound_alias_unique
                ON records(json_extract(payload,'$.alias')) WHERE kind='sound';
            ''')

    def connect(self):
        return sqlite3.connect(self.path, timeout=30)

    def get(self, id):
        with closing(self.connect()) as db:
            row = db.execute('SELECT payload FROM records WHERE id=?', (id,)).fetchone()
        if row is None:
            raise ValueError('This saved curation record is unavailable.')
        return json.loads(row[0])

    def list(self, kind):
        with closing(self.connect()) as db:
            return [json.loads(r[0]) for r in db.execute(
                'SELECT payload FROM records WHERE kind=? ORDER BY id', (kind,))]

    def mutate(self, id, kind, command, transform):
        for key in ('command_id', 'idempotency_key', 'expected_revision', 'input_hashes', 'settings_version'):
            if key not in command:
                raise ValueError('Missing command field: ' + key)
        if type(command['expected_revision']) is not int or command['expected_revision'] < 0:
            raise ValueError('Use a nonnegative saved revision.')
        if not command['idempotency_key'] or not command['command_id']:
            raise ValueError('Commands need nonempty stable identities.')
        fingerprint = digest({'id': id, 'kind': kind, 'command': command})
        with closing(self.connect()) as db:
            db.execute('BEGIN IMMEDIATE')
            try:
                prior = db.execute('SELECT request_hash,response FROM commands WHERE key=?',
                                   (command['idempotency_key'],)).fetchone()
                if prior:
                    if prior[0] != fingerprint:
                        raise RevisionConflict('This retry key belongs to a different request.')
                    db.rollback()
                    return json.loads(prior[1])
                row = db.execute('SELECT kind,revision,payload FROM records WHERE id=?', (id,)).fetchone()
                revision = row[1] if row else 0
                if row and row[0] != kind:
                    raise ValueError('Record type does not match this command.')
                if revision != command['expected_revision']:
                    raise RevisionConflict('The project changed. Reload before editing.')
                previous = json.loads(row[2]) if row else None
                result = transform(previous)
                result.update(id=id, kind=kind, revision=revision + 1)
                encoded = canonical(result)
                db.execute('INSERT OR REPLACE INTO records VALUES (?,?,?,?)', (id, kind, revision + 1, encoded))
                db.execute('INSERT INTO revisions VALUES (?,?,?)', (id, revision + 1, encoded))
                db.execute('INSERT INTO commands VALUES (?,?,?)', (command['idempotency_key'], fingerprint, encoded))
                db.commit()
                return result
            except BaseException:
                db.rollback()
                raise

    def cached(self, key, value=None):
        with closing(self.connect()) as db, db:
            if value is not None:
                db.execute('INSERT OR REPLACE INTO analysis_cache VALUES (?,?)', (key, canonical(value)))
            row = db.execute('SELECT payload FROM analysis_cache WHERE key=?', (key,)).fetchone()
            return json.loads(row[0]) if row else None


def propose_body(candidates, recipe, previous=None, *, preselection=False):
    """Only evidence-labelled phases; unknowns stay visible for review."""
    phases = PHASES.get(recipe)
    if phases is None:
        raise ValueError('Choose waterfall or party, or supply a reviewed phase order.')
    previous = previous or {}
    if previous.get('recipe',recipe)!=recipe:
        if previous.get('locked_decisions'):
            raise ValueError('Unlock or reassign saved choices before changing the story recipe.')
    else:
        phases = previous.get('phase_order', phases)
    by_id = {c['id']: c for c in candidates}
    banned = set(previous.get('banned', []))
    locks = previous.get('locked_decisions', {})
    assignments = []
    used = set()
    for phase in phases:
        locked = locks.get(phase)
        if locked:
            if locked not in by_id or locked in banned:
                raise ValueError('A locked choice is missing or banned. Resolve that choice before replanning.')
            if locked in used or by_id[locked].get('review_state')=='rejected':
                raise ValueError('Resolve the duplicate or rejected locked choice before replanning.')
            chosen = by_id[locked]
        else:
            options = [c for c in candidates if c['id'] not in used | banned
                       and phase in c.get('phase_tags', [])
                       and (c.get('review_state') == 'approved' or
                            (preselection and c.get('review_state') == 'unreviewed' and c.get('semantic_status') == 'reviewed'))]
            chosen = max(options, key=lambda c: (c.get('review_state') == 'approved', c.get('score', 0), c['id'])) if options else None
        assignments.append({'phase': phase, 'clip_id': chosen['id'] if chosen else None,
                            'locked': bool(locked), 'gap': chosen is None})
        if chosen:
            used.add(chosen['id'])
    return {**previous, 'recipe': recipe, 'phase_order': phases, 'slot_assignments': assignments,
            'ordered_clip_ids': [a['clip_id'] for a in assignments if a['clip_id']],
            'missing_phases': [a['phase'] for a in assignments if a['gap']],
            'unclassified_clip_ids': [c['id'] for c in candidates if not c.get('phase_tags')],
            'auto_preselection_enabled': preselection,
            'selection_policy': ('Source-reviewed suggestions require clip approval before body approval.' if preselection
                                 else 'Only individually approved candidates are selected.'),
            'approval_state': 'plan_review', 'assemblies_valid': False}


def span_overlap(a, b):
    if a['source_id'] != b['source_id']:
        return False
    return max(a['start'], b['start']) < min(a['end'], b['end'])


def validate_intros(plans, sources, body_revision, mode, category):
    """Hard contract checks, separate from visual/spoken spoiler review."""
    if mode not in ('cinematic', 'documentary'):
        raise ValueError('Choose Cinematic or Cricket Documentary.')
    if mode == 'documentary' and category != 'cricket':
        raise ValueError('Documentary intros are for cricket only.')
    expected_count, seconds = (3, 5) if mode == 'cinematic' else (1, 40)
    if len(plans) != expected_count:
        raise ValueError(f'This mode requires exactly {expected_count} intro plans.')
    variants = set()
    for plan in plans:
        fps = Fraction(str(plan['fps']))
        frames = seconds * 30
        if fps != 30 or plan['frame_count'] != frames or plan['body_revision'] != body_revision:
            raise ValueError('Intro duration, frame rate or body revision is inconsistent.')
        if plan['variant'] in variants:
            raise ValueError('Intro variants must have unique identities.')
        variants.add(plan['variant'])
        cursor = 0
        spans = plan['source_spans']
        if not spans:
            raise ValueError('Choose actual source moments for the intro.')
        for i,span in enumerate(spans):
            if any(span_overlap(span,other) for other in spans[i+1:]):
                raise ValueError('An intro repeats an overlapping source moment. Choose distinct shots.')
        for span in spans:
            source = sources.get(span['source_id'])
            if source is None:
                raise ValueError('An intro refers to an unknown source.')
            if not all(math.isfinite(float(span[k])) for k in ('start', 'end')):
                raise ValueError('Use finite source times.')
            if not 0 <= span['start'] < span['end'] <= source['duration']:
                raise ValueError('An intro cut extends outside its source.')
            if type(span['frames']) is not int or span['frames'] <= 0:
                raise ValueError('Each intro shot needs a positive whole-frame duration.')
            if span['frames'] / float(fps) > span['end'] - span['start'] + 1 / float(fps):
                raise ValueError('This shot needs explicit retiming or a longer source span.')
            cursor += span['frames']
            for protected in source.get('protected_spans', []):
                if max(span['start'], protected['start']) < min(span['end'], protected['end']):
                    raise ValueError('This intro leaks a protected payoff.')
        if cursor != frames:
            raise ValueError('The intro shots must fill its exact frame count.')
        if mode == 'documentary':
            promises = plan.get('promises', [])
            if not promises or any(not p.get('evidence_id') or not p.get('payoff_id') or
                                   not isinstance(p.get('payoff_timestamp'), (int, float)) or
                                   p['payoff_timestamp'] < 0 for p in promises):
                raise ValueError('Map every teased question to its body evidence and payoff time.')
            if plan.get('spoiler_review') != 'approved':
                raise ValueError('Review speech, captions and revealing visuals before rendering.')
    if mode == 'cinematic':
        for i, a in enumerate(plans):
            for b in plans[i + 1:]:
                aa, bb = a['source_spans'], b['source_spans']
                if span_overlap(aa[0], bb[0]):
                    raise ValueError('Insufficient variety: intros share their first source moment.')
                for left, right in ((aa, bb), (bb, aa)):
                    different = sum(not any(span_overlap(s, t) for t in right) for s in left)
                    if different * 2 < len(left):
                        raise ValueError('Insufficient variety: at least half the moments must differ.')
                if a.get('premise') == b.get('premise') and [s['source_id'] for s in aa] == [s['source_id'] for s in bb]:
                    raise ValueError('Choose a different source order or dramatic premise.')
    return {'hard_contracts_passed': True, 'creative_acceptance': 'pending',
            'frame_counts': [p['frame_count'] for p in plans]}


def resolve_sound(records, exact_name, expected_hash=None):
    matches = [r for r in records if exact_name in (r['id'], r.get('alias'))]
    if len(matches) != 1:
        raise ValueError('Choose one exact sound ID or unambiguous alias; no substitute was selected.')
    record = matches[0]
    if record.get('rights_state') != 'approved' or not record.get('license_evidence'):
        raise ValueError('This sound is quarantined until its rights are recorded and approved.')
    if not record.get('audition_approved'):
        raise ValueError('Audition and approve this exact recording first.')
    if record.get('expiry'):
        from datetime import date
        if date.fromisoformat(record['expiry']) < date.today():
            raise ValueError('This sound permission expired. Review its current licence before use.')
    actual = file_hash(record['path'])
    if actual != record['hash'] or expected_hash is not None and actual != expected_hash:
        raise ValueError('The chosen sound changed. Restore or explicitly reapprove it.')
    derivation = record.get('derivation')
    if derivation:
        source = next((item for item in records if item['id'] == derivation['source_id']), None)
        if source is None or source.get('derivation'):
            raise ValueError('The original ambience recording is unavailable.')
        resolve_sound(records, source['id'], derivation['source_hash'])
    return record
