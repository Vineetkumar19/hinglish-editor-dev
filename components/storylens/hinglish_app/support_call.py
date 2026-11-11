"""Informational browser support calls, isolated from editing and publishing."""
import json
import os
from threading import Lock
from urllib.error import URLError
from urllib.request import Request, urlopen
from uuid import uuid4


_REALTIME_LOCK = Lock()

INSTRUCTIONS = (
    "You are Cortana AI, the voice assistant inside Storylens. Introduce yourself as Cortana AI. "
    "Greet the caller warmly without listing categories. Speak in short, natural turns. "
    "Match the caller’s English, Hindi, or Hinglish. Keep track of what they said earlier. Ask one question "
    "at a time. Provide informational help only. Storylens runs editing locally. "
    "It can remove silence with Smart Clean, generate captions, extract clips with Long "
    "to Shorts, and hand off media to Premiere Pro, After Effects, Resolve and CapCut. "
    "The Storylens subscription includes Desktop and Editor Plugins on this computer. "
    "Activation starts from the Storylens activation page. Refer callers to the existing "
    "Support link for current prices, billing, refunds, account status, or personal help. "
    "Do not guess prices, quotes, availability, or account details. Do not collect payment "
    "information or passwords. You cannot edit, publish, change settings, or access accounts."
)


def _realtime_model():
    if os.environ.get('OPENAI_API_KEY', '').strip():
        return os.environ.get('STORYLENS_SUPPORT_REALTIME_MODEL', '').strip() or 'gpt-realtime-2.1'
    return ''


def _read(handler, limit):
    size = int(handler.headers.get('Content-Length', '0'))
    if not 0 < size <= limit:
        raise ValueError('The call request was empty or too large.')
    return handler.rfile.read(size)


def _openai_session(sdp, model):
    boundary = uuid4().hex
    session = {
        'type': 'realtime',
        'model': model,
        'instructions': INSTRUCTIONS,
        'output_modalities': ['audio'],
        'tools': [],
        'audio': {
            'input': {'turn_detection': {
                'type': 'semantic_vad',
                'eagerness': 'high',
                'create_response': True,
                'interrupt_response': True,
            }},
            'output': {'voice': 'marin'},
        },
    }
    body = b''
    for name, data in (('sdp', sdp), ('session', json.dumps(session).encode())):
        body += f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n'.encode()
        body += data + b'\r\n'
    body += f'--{boundary}--\r\n'.encode()
    request = Request('https://api.openai.com/v1/realtime/calls', data=body, headers={
        'Authorization': 'Bearer ' + os.environ['OPENAI_API_KEY'].strip(),
        'Content-Type': f'multipart/form-data; boundary={boundary}',
    })
    with urlopen(request, timeout=20) as response:
        return response.read(65536).decode('utf-8')


def handle(handler, state, path):
    reply = handler._json
    origin = handler.headers.get('Origin')
    if not handler._authorized() or (origin and origin != 'http://' + handler.headers['Host']):
        return reply(403, {'error': 'Open Storylens to start a support call.'})
    model = _realtime_model()
    if handler.command == 'GET' and path == '/api/support-call/status':
        from .support_call_speech import available
        return reply(200, {'realtime': bool(model), 'local': available(state.root)})
    if handler.command == 'GET' and path == '/api/support-call/recent':
        from .support_call_local import recent
        return reply(200, recent())
    if handler.command == 'GET' and path == '/api/support-call/catalog':
        from urllib.parse import urlsplit, parse_qs
        from .support_call_knowledge import FEATURES, TOPICS
        from .support_call_controls import controls, select_fields, _description
        selected = parse_qs(urlsplit(handler.path).query).get('tool', [''])[0]
        if selected and selected not in FEATURES:
            return reply(404, {'error': 'Unknown feature ID.'})
        features = [{'id': key, 'label': row[0], 'purpose': row[2],
                     'button_count': len(controls(key)), 'setting_count': len(select_fields(key))}
                    for key, row in FEATURES.items()]
        value = {'scope': 'source catalog; current control availability requires the live screen',
                 'features': features, 'topics': TOPICS}
        if selected:
            value['selected'] = {'id': selected,
                'buttons': [{'label': label, 'purpose': _description(label,title,handler_name,selected)}
                            for label,title,handler_name in controls(selected)],
                'settings': select_fields(selected)}
        return reply(200, value)
    if handler.command != 'POST':
        return reply(404, {'error': 'Unknown support call operation.'})
    if path in ('/api/support-call/local-warm', '/api/support-call/local-turn', '/api/support-call/local-step', '/api/support-call/local-end', '/api/support-call/local-speech', '/api/support-call/local-result'):
        from .support_call_local import handle as local_handle
        if path == '/api/support-call/local-turn':
            from .support_call_avatar import yield_to_voice
            yield_to_voice()
        return local_handle(handler, state.root, path)
    if path in ('/api/support-call/avatar-warm', '/api/support-call/avatar-frames'):
        from .support_call_avatar import handle as avatar_handle
        return avatar_handle(handler, state.root, warm=path.endswith('/avatar-warm'))
    if path == '/api/support-call/connect':
        if not model:
            return reply(503, {'error': 'OpenAI voice is unavailable on this installation.'})
        sdp = _read(handler, 65536)
        if handler.headers.get_content_type() != 'application/sdp' or not sdp.startswith(b'v=0'):
            return reply(400, {'error': 'The call connection offer is invalid.'})
        if not _REALTIME_LOCK.acquire(blocking=False):
            return reply(429, {'error': 'Another call is connecting. Please try again.'})
        try:
            answer = _openai_session(sdp, model)
        except (URLError, TimeoutError, UnicodeError):
            return reply(502, {'error': 'OpenAI voice could not connect.'})
        finally:
            _REALTIME_LOCK.release()
        return reply(200, {'sdp': answer})
    return reply(404, {'error': 'Unknown support call operation.'})
