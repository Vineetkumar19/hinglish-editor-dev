"""Project-local memory built only from explicit human review choices."""
from datetime import datetime, timezone
from difflib import SequenceMatcher
import hashlib
import json
from pathlib import Path

from hinglish_cut.text import tokens


def _span_id(candidate):
    if not candidate:
        return None
    value = candidate.get('span')
    return value.get('id') if isinstance(value, dict) else value.id


def _span_text(candidate):
    if not candidate:
        return None
    value = candidate.get('span')
    return value.get('text') if isinstance(value, dict) else value.text


def _similarity(a, b):
    left, right = tokens(a), tokens(b)
    if not left or not right:
        return 0.0
    overlap = len(set(left) & set(right)) / len(set(left) | set(right))
    order = SequenceMatcher(None, left, right).ratio()
    return .65 * overlap + .35 * order


class LearningMemory:
    """Store review evidence; never alter model weights or invent source timing."""

    def __init__(self, root):
        self.path = Path(root) / 'cache' / 'learning' / 'assembly-feedback.jsonl'

    def _records(self):
        if not self.path.exists():
            return []
        records = []
        for line in self.path.read_text(encoding='utf-8').splitlines()[-5000:]:
            try:
                record = json.loads(line)
                if record.get('version') == 1 and record.get('idea'):
                    records.append(record)
            except (TypeError, ValueError):
                continue
        return records

    def record_review(self, rows, choices, project_key):
        """Remember only radio choices the user explicitly saved and applied."""
        existing = {r.get('event_id') for r in self._records()}
        additions = []
        for row in rows:
            key = str(row['index'])
            if key not in choices:
                continue
            reviewed_id = choices[key] or None
            auto_id = row.get('selected_id')
            alternatives = {_span_id(c): c for c in row.get('alternatives', [])}
            if reviewed_id and reviewed_id not in alternatives:
                raise ValueError('Unknown source choice')
            approved = _span_text(alternatives.get(reviewed_id))
            rejected = _span_text(alternatives.get(auto_id)) if auto_id != reviewed_id else None
            identity = {'project': str(project_key), 'index': row['index'],
                        'auto': auto_id, 'reviewed': reviewed_id}
            event_id = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()
            if event_id in existing:
                continue
            additions.append({'version': 1, 'event_id': event_id,
                'created_at': datetime.now(timezone.utc).isoformat(),
                'idea': row['idea'], 'approved_spoken': approved,
                'rejected_spoken': rejected,
                'decision': 'unmatched' if reviewed_id is None else
                            'confirmed' if reviewed_id == auto_id else 'corrected'})
            existing.add(event_id)
        if additions:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open('a', encoding='utf-8') as target:
                for record in additions:
                    target.write(json.dumps(record, ensure_ascii=False) + '\n')
        return len(additions)

    def examples_for(self, idea, limit=3):
        """Return only closely related human-reviewed examples for the local LLM."""
        ranked = []
        for record in self._records():
            score = _similarity(idea, record['idea'])
            if score >= .38:
                ranked.append((score, record))
        ranked.sort(key=lambda item: (item[0], item[1]['created_at']), reverse=True)
        return [{'similar_script': r['idea'],
                 'human_approved_spoken': r.get('approved_spoken'),
                 'human_rejected_spoken': r.get('rejected_spoken'),
                 'decision': r['decision']} for _, r in ranked[:limit]]
