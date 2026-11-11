"""Local UI and editor bridge for the Hinglish editing engines."""
import json
import os
from pathlib import Path
import secrets

DEFAULT_PORT = 8765
BRIDGE_URL = os.environ.get('STORYLENS_BRIDGE_URL') or f'http://127.0.0.1:{DEFAULT_PORT}'
BRIDGE_FILE = Path(__file__).resolve().parent.parent / 'cache' / 'app' / 'bridge.json'


def app_token(bridge_file=BRIDGE_FILE):
    """The app's access token. It is kept in cache/app/bridge.json (only this PC's files can read it) and
    survives restarts, so review pages made earlier keep working."""
    bridge_file = Path(bridge_file)
    try:
        token = json.loads(bridge_file.read_text(encoding='utf-8')).get('token')
        if token:
            return token
    except (OSError, ValueError):
        pass
    token = secrets.token_urlsafe(32)
    bridge_file.parent.mkdir(parents=True, exist_ok=True)
    bridge_file.write_text(json.dumps({'url': BRIDGE_URL, 'token': token}, indent=2), encoding='utf-8')
    return token


def embed_token(page):
    """Local review pages (opened as files) carry the token themselves. The server no longer gives the
    token to "null"-origin pages, because any website can make one (a sandboxed frame)."""
    token = json.dumps(app_token())
    for pattern in (f"await(await fetch('{BRIDGE_URL}/api/bridge')).json()",
                    f"await (await fetch('{BRIDGE_URL}/api/bridge')).json()"):
        page = page.replace(pattern, '{token:' + token + '}')
    return page
