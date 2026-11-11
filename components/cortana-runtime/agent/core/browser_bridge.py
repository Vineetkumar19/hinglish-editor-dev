"""Native extension mailbox: profile-bound operations, bounded waits, no web port."""
import json
import time
from uuid import uuid4
from core import local_store as store
from core.tasks import check_cancelled


def profile_status(browser, profile):
    matches = [r for r in store.records('browser_profile') if r['browser'] == browser and r['profile'] == profile]
    live = [r for r in matches if time.time() - r['seen_at'] < 8]
    if len(live) != 1:
        return {'connected': False, 'note': 'Connect exactly one Cortana extension with this browser/profile label.', 'matches': len(live)}
    return {'connected': True, 'profile': live[0]}


def command(browser, profile, operation, arguments, timeout=25):
    if operation not in {'capture', 'capture_saved', 'restore', 'read', 'find', 'focus'}:
        raise ValueError('Unsupported browser operation.')
    status = profile_status(browser, profile)
    if not status['connected']:
        raise ValueError(status['note'])
    client_id = status['profile']['client_id']
    request = store.put('browser_command', {'client_id': client_id, 'operation': operation,
        'arguments': arguments, 'state': 'pending', 'expires_at': time.time()+timeout})
    try:
        while time.time() < request['expires_at']:
            check_cancelled()
            result = store.get('browser_command', request['id'])
            if result['state'] == 'completed':
                return result['result']
            if result['state'] == 'failed':
                raise ValueError(result.get('error', 'Browser operation failed.'))
            time.sleep(.15)
        raise TimeoutError('Browser result unknown. Inspect the existing tab before retrying.')
    finally:
        result = store.get('browser_command', request['id'])
        if result['state'] in {'pending', 'claimed'}:
            result['state'] = 'cancelled' if result['state'] == 'pending' else 'unknown'
            store.put('browser_command', result, result['id'], result['revision'])


def exchange(message):
    """Called only by the native host, never by a website/API route."""
    client = str(message.get('client_id', ''))
    if len(client) != 36 or message.get('browser') not in {'chrome', 'brave'}:
        raise ValueError('Invalid browser identity.')
    profile = str(message.get('profile', '')).strip()
    if not profile or len(profile) > 100:
        raise ValueError('Name this browser profile.')
    store.put('browser_profile', {'client_id': client, 'browser': message['browser'], 'profile': profile,
        'seen_at': time.time(), 'version': '1.0.0', 'capabilities': ['selected_tabs', 'restore', 'youtube_pause']}, client)
    for result in message.get('results', [])[:20]:
        row = store.get('browser_command', result['id'])
        if row['client_id'] != client or row['state'] not in {'claimed', 'unknown'}:
            continue
        row.update(state='failed' if result.get('error') else 'completed', result=result.get('result'), error=result.get('error'))
        store.put('browser_command', row, row['id'], row['revision'])
    commands, cancelled = [], []
    for row in reversed(store.records('browser_command', 100)):
        if row['client_id'] == client and (row['state'] in {'cancelled', 'unknown'} or row['expires_at'] <= time.time()):
            cancelled.append(row['id'])
        if not message.get('busy') and row['client_id'] == client and row['state'] == 'pending' and row['expires_at'] > time.time():
            row['state'] = 'claimed'
            try:
                store.put('browser_command', row, row['id'], row['revision'])
                commands.append(row)
            except ValueError:
                continue
    return {'commands': commands, 'cancelled': cancelled}
