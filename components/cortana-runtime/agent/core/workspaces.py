"""Explicit, device-bound workspace snapshots with per-item recovery receipts."""
import hashlib
import json
import platform
from pathlib import Path
from urllib.parse import urlsplit, parse_qs, urlencode, urlunsplit

from pydantic import BaseModel, ConfigDict, Field, field_validator
from core import local_store as store
from core.app_config import approved_apps, approved_search_roots
from core.tasks import check_cancelled
from tools.files import within_approved_roots
from tools.openpath import SAFE_OPEN_EXTENSIONS


class WorkspaceItem(BaseModel):
    model_config = ConfigDict(extra='forbid')
    kind: str
    target: str = Field(min_length=1, max_length=3000)
    browser: str = 'chrome'
    profile: str = 'Default'
    title: str = Field(default='', max_length=500)
    playback_seconds: float | None = Field(default=None, ge=0, le=604800)
    tab_id: int | None = None
    group: str = ''

    @field_validator('kind')
    @classmethod
    def kind_supported(cls, value):
        if value not in {'file', 'folder', 'project', 'app', 'tab'}:
            raise ValueError('Unsupported workspace item kind.')
        return value


def validate_item(raw):
    item = WorkspaceItem.model_validate(raw).model_dump()
    kind, target = item['kind'], item['target']
    if kind in {'file', 'folder', 'project'}:
        path = Path(target).resolve(strict=True)
        if not within_approved_roots(str(path), approved_search_roots()):
            raise ValueError('Workspace item is outside approved roots.')
        if kind == 'file' and (not path.is_file() or path.suffix.lower() not in SAFE_OPEN_EXTENSIONS):
            raise ValueError('Only supported document/media files can be restored.')
        if kind in {'folder', 'project'} and not path.is_dir():
            raise ValueError('Select an existing project or folder directory.')
        item['target'] = str(path)
        stat = path.stat()
        item['identity'] = {'size': stat.st_size, 'mtime_ns': stat.st_mtime_ns,
                            'file_id': stat.st_ino, 'device': stat.st_dev}
    elif kind == 'app':
        if target not in approved_apps():
            raise ValueError('Choose a configured application ID.')
    else:
        parsed = urlsplit(target)
        if parsed.scheme not in {'http', 'https'} or not parsed.hostname or parsed.username or parsed.password:
            raise ValueError('Only ordinary HTTP(S) workspace pages are supported.')
        if item['browser'] not in {'chrome', 'brave'} or not item['profile'].strip():
            raise ValueError('Select Chrome or Brave and an explicit profile.')
        if item['playback_seconds'] is not None and parsed.hostname not in {'youtube.com', 'www.youtube.com', 'm.youtube.com'}:
            raise ValueError('Playback capture is supported only on YouTube.')
    return item


def capture_workspace(name, items, context_note=''):
    if not name.strip() or len(name) > 120 or not 1 <= len(items) <= 50:
        raise ValueError('Name the workspace and select 1–50 items.')
    prepared = [validate_item(item) for item in items]
    from datetime import datetime, timezone
    return store.put('workspace', {'name': name.strip(), 'device_id': platform.node(),
        'captured_at': datetime.now(timezone.utc).isoformat(), 'items': prepared,
        'context_note': context_note[:4000], 'capture_mode': 'explicit selection'})


def find_workspace(query=''):
    return [w for w in store.records('workspace', 1000) if query.casefold() in w['name'].casefold()]


def resolve_workspace(query):
    snapshots = store.records('workspace', 1000)
    matches = [w for w in snapshots if w['id'] == query or w['name'].casefold() == query.casefold()]
    if len(matches) == 1:
        return {'workspace_id': matches[0]['id'], 'revision': matches[0]['revision']}
    candidates = matches or [w for w in snapshots if query.casefold() in w['name'].casefold()]
    if not candidates:
        raise ValueError('No saved workspace has that name. Use Show workspaces to inspect saved names.')
    choices = '\n'.join(f"{w['name']} — {w['captured_at']} — {w['id']}" for w in candidates[:10])
    raise ValueError('Choose an exact workspace name or ID; nothing was restored.\n' + choices)


def capture_browser_workspace(name, browser, profile, items=None, context_note=''):
    from core.browser_bridge import command
    selected = items or []
    for item in selected:
        validate_item(item)
    snapshot = command(browser, profile, 'capture', {})
    if not snapshot.get('verified') or not snapshot.get('items'):
        raise ValueError('Select supported browser tabs before capture.')
    check_cancelled()
    return capture_workspace(name, selected + snapshot['items'], context_note)


def preview_restore(workspace_id):
    snapshot = store.get('workspace', workspace_id)
    items = []
    for index, item in enumerate(snapshot['items']):
        status, note = 'ready', ''
        if snapshot['device_id'] != platform.node():
            status, note = 'waiting_for_mapping', 'Snapshot belongs to another device; map its paths explicitly.'
        elif item['kind'] in {'file', 'folder', 'project'}:
            path = Path(item['target'])
            if not within_approved_roots(str(path), approved_search_roots()):
                status, note = 'permission_denied', 'Path access is no longer granted.'
            elif not path.exists():
                status, note = 'waiting_for_file', 'File/drive missing or renamed.'
            elif item.get('identity') and (path.stat().st_ino != item['identity']['file_id'] or path.stat().st_dev != item['identity']['device']):
                status, note = 'changed_identity', 'A different filesystem item now occupies this path.'
        elif item['kind'] == 'tab':
            from core.browser_bridge import profile_status
            bridge = profile_status(item['browser'], item['profile'])
            if not bridge['connected']:
                status, note = 'waiting_for_browser', bridge['note']
        items.append({'index': index, **item, 'status': status, 'note': note})
    return {'workspace': snapshot, 'items': items,
            'note': 'Restore preserves unrelated windows. Video resumes paused; unsupported cursor/window positions remain unchanged.'}


def restore_workspace(workspace_id, revision):
    preview = preview_restore(workspace_id)
    snapshot = preview['workspace']
    if snapshot['revision'] != revision:
        raise ValueError('Workspace changed after review.')
    outcomes = []
    from core.tool_registry import dispatch, serialized_effects
    with serialized_effects():
        for item in preview['items']:
            check_cancelled()
            if item['status'] != 'ready':
                outcomes.append(item)
                continue
            try:
                kind = item['kind']
                if kind == 'tab':
                    from core.browser_bridge import command
                    result = command(item['browser'], item['profile'], 'restore', {'url': item['target'],
                        'playback_seconds': item['playback_seconds'], 'paused': True})
                elif kind == 'app':
                    result = dispatch('open_application', {'name': item['target']})
                elif kind == 'project':
                    result = dispatch('open_in_ide', {'project': item['target'], 'ide': 'vscode'})
                else:
                    result = dispatch('open_path', {'path': item['target']})
                # A launch receipt is deliberately not reported as visual acceptance.
                status = 'failed' if result.get('error') or result.get('opened') is False else 'opened_unverified'
                if result.get('verified'):
                    status = 'verified'
                outcomes.append({'index': item['index'], 'target': item['target'], 'status': status, 'result': result})
            except Exception as exc:
                outcomes.append({'index': item['index'], 'target': item['target'], 'status': 'failed', 'error': str(exc)[:500]})
    receipt = store.put('restore', {'workspace_id': workspace_id, 'revision_used': revision, 'outcomes': outcomes})
    return receipt
