"""Token-protected Voiceover API. Downloads only expose completed job audio."""
import secrets
from urllib.parse import parse_qs, quote
from hinglish_voice.service import service
from hinglish_voice.audio import MAX_UPLOAD


def upload(handler, state, parsed):
    size = int(handler.headers.get('Content-Length','0'))
    if not 0 < size <= MAX_UPLOAD:
        handler.close_connection = True
        return handler._json(413, {'error':'Voice sample: choose one recording up to 50 MB.'})
    content = handler.rfile.read(size)
    if len(content)!=size: raise ValueError('Voice sample: the upload stopped early. Choose the recording again.')
    return handler._json(201, service(state.root).upload(parse_qs(parsed.query).get('name',['sample.wav'])[0],content))


def get(handler, state, parsed):
    query = parse_qs(parsed.query)
    media = parsed.path == '/api/voiceover/file'
    if not handler._authorized() and not (media and secrets.compare_digest(query.get('token',[''])[0],state.token)):
        return handler._json(403, {'error':'Not connected'})
    voice = service(state.root)
    if parsed.path == '/api/voiceover/status': return handler._json(200,voice.status())
    if parsed.path == '/api/voiceover/job': return handler._json(200,voice.job(query.get('id',[''])[0]))
    if not media: return handler._json(404,{'error':'Voiceover action: choose a saved voice or generation.'})
    kind = query.get('format',['mp3'])[0]
    path = voice.file(query.get('id',[''])[0],kind)
    handler.send_response(200)
    handler.send_header('Content-Type','audio/mpeg' if kind=='mp3' else 'audio/wav')
    handler.send_header('Content-Length',str(path.stat().st_size))
    handler.send_header('Cache-Control','no-store')
    handler.send_header('Referrer-Policy','no-referrer')
    handler.send_header('X-Content-Type-Options','nosniff')
    if query.get('download')==['1']:
        handler.send_header('Content-Disposition',"attachment; filename*=UTF-8''"+quote('Storylens-'+path.parent.name[:8]+'.'+kind))
    handler.end_headers()
    with path.open('rb') as stream:
        while data:=stream.read(256*1024): handler.wfile.write(data)


def post(handler, state, path, payload):
    voice = service(state.root)
    if path == '/api/voiceover/voices': return handler._json(201,voice.create_voice(payload))
    if path == '/api/voiceover/start': return handler._json(202,voice.start(payload))
    return handler._json(404,{'error':'Voiceover action: choose Save voice or Generate voiceover.'})
