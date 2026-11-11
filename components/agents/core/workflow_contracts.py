"""Version 1 contracts for additive Suite workflows. No execution at import."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
import hashlib
import json
import math

VERSION = 1
STATES = frozenset(('queued', 'planning', 'running', 'waiting_for_review',
    'waiting_for_device', 'waiting_for_network', 'waiting_for_auth', 'reconciling',
    'succeeded', 'partially_succeeded', 'failed', 'cancelled'))
TERMINAL = frozenset(('succeeded', 'failed', 'cancelled'))
ROLES = {
    'system_health': 'System Health & Recovery',
    'client_delivery': 'Client Delivery',
    'inbox_commitment': 'Inbox & Commitment',
    'research_experiment': 'Research-to-Experiment',
    'learning_evidence': 'Learning & Evidence',
    'content_release': 'Content Release',
    'saas_sales': 'SaaS demand research',
}
# These are broker capabilities, not prose supplied by a model.
ROLE_PERMISSIONS = {
    'system_health': {'probe', 'diagnostics.read'},
    'client_delivery': {'prepare', 'storylens.prepare', 'repository.prepare', 'delivery.send', 'delivery.package'},
    'inbox_commitment': {'prepare'},
    'research_experiment': {'prepare', 'experiment.run'},
    'learning_evidence': {'prepare'},
    'content_release': {'prepare', 'storylens.package', 'storylens.publish'},
    'saas_sales': {'prepare'},
}


def canonical(value) -> str:
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False,
                      allow_nan=False)


def digest(value) -> str:
    return hashlib.sha256(canonical(value).encode('utf-8')).hexdigest()


def input_references(value):
    """Collect declared source and artifact identities without copying content."""
    found = {}
    def visit(item):
        if isinstance(item, dict):
            if all(key in item for key in ('artifact_id', 'revision', 'content_hash')):
                ref = {key: item[key] for key in ('artifact_id', 'revision', 'content_hash')}
                found[digest(ref)] = ref
            if isinstance(item.get('source_ref'), str):
                ref = {'source_ref': item['source_ref']}
                found[digest(ref)] = ref
            for child in item.values():
                visit(child)
        elif isinstance(item, list):
            for child in item:
                visit(child)
    visit(value)
    return [found[key] for key in sorted(found)]


def require_fields(obj, fields):
    if not isinstance(obj, dict):
        raise ValueError('Expected a JSON object')
    for key in fields:
        if obj.get(key) in (None, '', [], {}):
            raise ValueError(f'Missing {key}')


@dataclass(frozen=True)
class TaskEnvelope:
    task_id: str
    role: str
    intent: str
    input_refs: list
    device_id: str
    budgets: dict
    permissions: list
    parent_task_id: str | None
    idempotency_key: str
    contract_version: int = VERSION

    def validate(self):
        if self.role not in ROLES or not self.intent.strip() or not self.device_id:
            raise ValueError('Known role, intent and device_id are required')
        if not self.idempotency_key or len(self.idempotency_key) > 200:
            raise ValueError('A bounded idempotency_key is required')
        if not set(self.permissions) <= ROLE_PERMISSIONS[self.role]:
            raise PermissionError('Permissions exceed the role boundary')
        for key, cap in (('runtime_seconds', 3600), ('storage_bytes', 10_000_000_000),
                         ('retries', 3)):
            val = self.budgets.get(key, 0)
            if isinstance(val, bool) or not isinstance(val, (int, float)) or not math.isfinite(val) or not 0 <= val <= cap:
                raise ValueError(f'Invalid {key} budget')
        return self

    def to_json(self):
        return asdict(self)


@dataclass(frozen=True)
class ArtifactRef:
    artifact_id: str
    project: str
    revision: str
    content_hash: str
    device_id: str
    locator: str
    type: str
    evidence: list
    approval_status: str = 'unreviewed'
    contract_version: int = VERSION

    def to_json(self):
        return asdict(self)


@dataclass(frozen=True)
class Opportunity:
    contact_id: str
    source_ref: str
    expressed_need: str
    qualification_facts: list
    inferred_signals: list
    status: str
    owner_role: str


@dataclass(frozen=True)
class Approval:
    action_type: str
    exact_payload_hash: str
    target: str
    artifact_refs: list
    expiry: float
    consumed: bool = False


@dataclass(frozen=True)
class Outcome:
    task_id: str
    verified_result: str
    evidence_refs: list
    errors: list = field(default_factory=list)
    partial_results: list = field(default_factory=list)
    next_valid_action: str = ''

    def to_json(self):
        return asdict(self)
