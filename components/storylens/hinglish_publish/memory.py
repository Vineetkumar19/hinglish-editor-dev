"""Creator-approved preferences and examples, retrieved locally for future drafts.

This adapts context and exact spelling rules; it does not train model weights.
"""
import json
import re
import sqlite3
import time
import uuid
from contextlib import contextmanager
from dataclasses import replace
from pathlib import Path

SCOPES = {'all', 'title', 'description', 'hashtags', 'instagram_caption', 'subtitle_spelling'}


class CreatorMemory:
    def __init__(self, root, profile=None):
        from hinglish_niche.profiles import current_profile, valid_profile
        profile = valid_profile(profile or current_profile())
        filename = 'preferences.sqlite3' if profile == 'general' else 'preferences-' + profile + '.sqlite3'
        self.path = Path(root) / 'cache' / 'creator-memory' / filename
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.execute('CREATE TABLE IF NOT EXISTS preferences '
                       '(id TEXT PRIMARY KEY, created REAL, active INTEGER, data TEXT)')

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=30)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    def list(self, active_only=False):
        with self.connect() as db:
            rows = db.execute('SELECT * FROM preferences ' + ('WHERE active=1 ' if active_only else '') +
                              'ORDER BY created DESC,rowid DESC').fetchall()
        return [{**json.loads(row['data']), 'id': row['id'], 'created': row['created'],
                 'active': bool(row['active'])} for row in rows]

    def add(self, data):
        if data.get('scope') not in SCOPES:
            raise ValueError('Choose a supported writing preference or subtitle spelling correction')
        clean = {'scope': data['scope']}
        for key in ('want', 'avoid', 'before', 'after'):
            value = data.get(key, '')
            if not isinstance(value, str) or len(value) > 5000:
                raise ValueError('Each preference or example must be text under 5000 characters')
            clean[key] = value.strip()
        if not clean['want'] and not clean['after']:
            raise ValueError('Explain what you want, or supply an approved example')
        if clean['scope'] == 'subtitle_spelling':
            for key in ('before', 'after'):
                word = clean[key]
                if not word or len(word) > 80 or re.search(r'\s', word) or not any(c.isalpha() for c in word):
                    raise ValueError('Subtitle spelling needs one incorrect word and one corrected word')
                if not word[0].isalnum() or not word[-1].isalnum():
                    raise ValueError('Enter spelling words without surrounding punctuation')
        with self.connect() as db:
            encoded = json.dumps(clean, ensure_ascii=False, sort_keys=True)
            existing = db.execute('SELECT id FROM preferences WHERE active=1 AND data=?', (encoded,)).fetchone()
            if existing:
                return existing['id']
            record_id = uuid.uuid4().hex[:16]
            db.execute('INSERT INTO preferences VALUES (?,?,1,?)', (record_id, time.time(), encoded))
            return record_id

    def set_active(self, record_id, active):
        if type(active) is not bool:
            raise ValueError('Memory enabled must be true or false')
        with self.connect() as db:
            changed = db.execute('UPDATE preferences SET active=? WHERE id=?', (int(active), record_id))
            if changed.rowcount != 1:
                raise ValueError('This saved preference is unavailable')

    def writing_context(self):
        # Bound context size and prefer recent feedback. Old records remain editable.
        records = [p for p in self.list(True) if p['scope'] != 'subtitle_spelling'][:16]
        context, budget = [], 6000
        for record in records:
            if budget < 300:
                break
            limit = min(1200, max(25, (budget - 200) // 4))
            entry = {key: record[key][:limit] for key in ('want', 'avoid', 'before', 'after')}
            entry['scope'] = record['scope']
            budget -= len(json.dumps(entry, ensure_ascii=False))
            context.append(entry)
        return context

    def spellings(self):
        mapping = {}
        for record in reversed(self.list(True)):
            if record['scope'] == 'subtitle_spelling':
                mapping[record['before'].casefold()] = record['after']
        return mapping

    def remember_edit(self, before, after):
        ids = []
        for key, scope in (('title', 'title'), ('description', 'description'),
                           ('instagram_caption', 'instagram_caption'), ('tags', 'hashtags')):
            if before.get(key) == after.get(key):
                continue
            original, approved = before.get(key, ''), after.get(key, '')
            if key == 'tags':
                original, approved = ', '.join(original), ', '.join(approved)
            ids.append(self.add({'scope': scope, 'before': original, 'after': approved,
                                 'want': 'Use this correction as a writing style example; preserve the facts '
                                         'of each new video instead of copying the example topic.'}))
        return ids


def corrected_token(token, mapping):
    # Exact whole-word replacement only. Never guess, split words or retime captions.
    first = next((i for i, char in enumerate(token) if char.isalnum()), None)
    last = next((i for i in range(len(token) - 1, -1, -1) if token[i].isalnum()), None)
    if first is None:
        return token
    body = token[first:last + 1]
    return token[:first] + mapping.get(body.casefold(), body) + token[last + 1:]


def correct_words(root, words, reference_text=''):
    mapping = CreatorMemory(root).spellings()
    protected = {corrected_token(token, {}).casefold().strip('.,!?;:"\'()[]{}')
                 for token in reference_text.split()}
    result, changes = [], []
    for word in words:
        key = word.text.casefold().strip('.,!?;:"\'()[]{}')
        text = word.text if key in protected else corrected_token(word.text, mapping)
        result.append(replace(word, text=text) if text != word.text else word)
        if text != word.text:
            changes.append({'heard': word.text, 'script_spelling': text, 'start': word.start,
                            'end': word.end, 'source': 'Approved creator memory'})
    return result, changes


def correct_text(root, text):
    mapping = CreatorMemory(root).spellings()
    return re.sub(r'\S+', lambda match: corrected_token(match[0], mapping), text)
