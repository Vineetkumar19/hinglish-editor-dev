"""Explicit opt-in refresh of a named selection, never browser history capture."""
import asyncio
import time
from uuid import uuid4
from core import local_store as store, tasks


def configure(workspace_id, revision, enabled, minutes=15):
    from core.workspaces import preview_restore
    snapshot = preview_restore(workspace_id)['workspace']
    if snapshot['revision'] != revision:
        raise ValueError('Workspace changed; review the current selection.')
    if not isinstance(enabled, bool) or not 5 <= minutes <= 1440:
        raise ValueError('Choose enabled/disabled and an interval of 5–1440 minutes.')
    return store.put('workspace_schedule', {'workspace_id':workspace_id,'workspace_revision':revision,
        'enabled':enabled,'minutes':minutes,'next_due':time.time()+minutes*60,
        'status':'enabled' if enabled else 'disabled'}, workspace_id)


def refresh_selected(policy):
    from core.workspaces import validate_item, capture_workspace
    from core.browser_bridge import command
    original = store.get('workspace', policy['workspace_id'])
    if original['revision'] != policy['workspace_revision']:
        raise ValueError('Saved selection changed; review periodic capture again.')
    items, groups = [], {}
    for item in original['items']:
        tasks.check_cancelled()
        raw = {k:v for k,v in item.items() if k != 'identity'}
        if item['kind'] == 'tab':
            groups.setdefault((item['browser'], item['profile']), []).append(raw)
        else:
            # Validate without taking over an editor or opening a missing file.
            validated = validate_item(raw)
            items.append({k:v for k,v in validated.items() if k != 'identity'})
    for (browser, profile), selected in groups.items():
        captured = command(browser, profile, 'capture_saved', {'items':selected})
        if not captured.get('verified') or len(captured.get('items',[])) != len(selected):
            raise ValueError('The selected tabs could not all be refreshed; prior snapshot preserved.')
        items.extend(captured['items'])
    tasks.check_cancelled()
    current = store.get('workspace_schedule', policy['id'])
    if not current['enabled'] or current['revision'] != policy['revision']:
        raise ValueError('Periodic capture changed or was disabled.')
    snapshot = capture_workspace(original['name'], items, original['context_note'])
    snapshot.update(capture_mode='opt-in periodic selection', parent_workspace_id=original['id'])
    return store.put('workspace',snapshot,snapshot['id'],snapshot['revision'])


async def _capture_due(policy):
    from fastapi.concurrency import run_in_threadpool
    from fastapi import HTTPException
    request_id = 'snapshot_' + uuid4().hex
    try:
        token = tasks.begin(request_id)
    except HTTPException:
        return
    try:
        snapshot = await run_in_threadpool(refresh_selected, policy)
        policy.update(status='captured',last_snapshot_id=snapshot['id'],error=None)
    except asyncio.CancelledError:
        policy.update(status='cancelled',error='Capture stopped; previous snapshots preserved.')
        raise
    except Exception as exc:
        policy.update(status='waiting',error=str(exc)[:300])
    finally:
        policy['next_due'] = time.time()+policy['minutes']*60
        try:
            store.put('workspace_schedule',policy,policy['id'],policy['revision'])
        except ValueError:
            pass  # A newer disable/edit wins.
        tasks.finish(request_id,token)


async def run():
    while True:
        await asyncio.sleep(15)
        for policy in store.records('workspace_schedule',1000):
            if not policy['enabled'] or policy['next_due'] > time.time():
                continue
            try:
                await asyncio.create_task(_capture_due(policy))
            except asyncio.CancelledError:
                if asyncio.current_task().cancelling():
                    raise
