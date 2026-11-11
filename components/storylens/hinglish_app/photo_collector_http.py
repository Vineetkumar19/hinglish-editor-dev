"""Private Photo Collector endpoints; no client-supplied filesystem paths."""
import mimetypes
import secrets
from urllib.parse import parse_qs,quote
from hinglish_photos.service import service
from hinglish_photos.core import MAX_UPLOAD

def upload(handler,state):
    length=int(handler.headers.get('Content-Length','0'))
    if not 0<length<=MAX_UPLOAD:raise ValueError('Photo screenshot invalid: choose one PNG, JPEG or WebP screenshot up to 25 MB.')
    return handler._json(201,service(state.root).upload(handler.rfile.read(length)))

def get(handler,state,parsed):
    query=parse_qs(parsed.query)
    media=parsed.path=='/api/photos/file'
    if not handler._authorized() and not (media and secrets.compare_digest(query.get('token',[''])[0],state.token)):
        return handler._json(403,{'error':'Not connected'})
    photos=service(state.root)
    if parsed.path=='/api/photos/history':return handler._json(200,{'jobs':photos.history()})
    if parsed.path=='/api/photos/job':
        if query.get('quality')==['available']:
            with photos.lock:
                if photos._get(query.get('id',[''])[0]).get('min_edge')!=0:photos.apply_quality(query.get('id',[''])[0],0)
        return handler._json(200,photos.snapshot(query.get('id',[''])[0]))
    if not media:raise ValueError('Photo action invalid: choose a saved collection.')
    if query.get('kind')==['download']:
        from hinglish_photos.downloads import download_path
        path=download_path(photos,query.get('id',[''])[0],query.get('item',[''])[0])
    else:path=photos.file(query.get('id',[''])[0],query.get('kind',[''])[0],query.get('item',[''])[0])
    handler.send_response(200)
    handler.send_header('Content-Type',mimetypes.guess_type(path)[0] or 'application/octet-stream')
    handler.send_header('Content-Length',str(path.stat().st_size))
    handler.send_header('Cache-Control','no-store');handler.send_header('Referrer-Policy','no-referrer')
    handler.send_header('X-Content-Type-Options','nosniff')
    if query.get('kind')==['download']:handler.send_header('Content-Disposition',"attachment; filename*=UTF-8''"+quote(path.name))
    if query.get('kind')==['zip']:handler.send_header('Content-Disposition',"attachment; filename*=UTF-8''"+quote(path.parent.name+'-photos.zip'))
    handler.end_headers()
    with path.open('rb') as stream:
        while data:=stream.read(256*1024):handler.wfile.write(data)

def post(handler,state,path,payload):
    photos=service(state.root);action=path.rsplit('/',1)[-1]
    if action=='start':return handler._json(202,photos.start(payload))
    if action=='save' and payload.get('selective'):
        from hinglish_photos.downloads import download_one
        return handler._json(200,download_one(photos,payload.get('id',''),payload.get('item'),min_edge=0))
    if action=='save':return handler._json(200,photos.save(payload.get('id',''),payload.get('item'),min_edge=payload.get('min_edge')))
    if action=='aftereffects':return handler._json(200,photos.send_ae(payload.get('id',''),min_edge=payload.get('min_edge')))
    if action=='retry':
        if payload.get('selective'):photos.update(payload.get('id',''),destination='folder',ae_requested=False,selective_downloads=True)
        return handler._json(202,photos.retry(payload.get('id',''),min_edge=payload.get('min_edge'),previews=payload.get('previews')))
    if action in ('retry','cancel','archive','restore'):
        return handler._json(202 if action=='retry' else 200,getattr(photos,action)(payload.get('id','')))
    if action=='open-folder':
        job=photos.snapshot(payload.get('id',''))
        if job['status']=='archived':raise ValueError('Photo collection archived: restore it before opening the folder.')
        state.open_path(job['output_folder']);return handler._json(200,{'ok':True})
    raise ValueError('Photo action invalid: choose a collection action from this tool.')
