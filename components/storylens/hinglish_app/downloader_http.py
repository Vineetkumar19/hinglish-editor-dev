"""Token-protected downloader status and private, range-aware media delivery."""
import mimetypes
import re
import secrets
from urllib.parse import parse_qs, quote
from .downloader import service


def get(handler, state, parsed):
    query = parse_qs(parsed.query)
    if not handler._authorized() and not (parsed.path == '/api/downloader/media' and secrets.compare_digest(query.get('token',[''])[0],state.token)):
        return handler._json(403,{'error':'Not connected'})
    downloads = service(state.root)
    if parsed.path == '/api/downloader/settings': return handler._json(200,downloads.settings())
    if parsed.path == '/api/downloader/queue': return handler._json(200,{'jobs':downloads.queue()})
    if parsed.path == '/api/downloader/history': return handler._json(200,{'jobs':downloads.history()})
    if parsed.path == '/api/downloader/job': return handler._json(200,downloads.snapshot(query.get('id',[''])[0]))
    if parsed.path != '/api/downloader/media': return handler._json(404,{'error':'Choose a downloader action.'})
    path=downloads.media(query.get('id',[''])[0],query.get('kind',[''])[0]); size=path.stat().st_size
    start,end=0,size-1; requested=handler.headers.get('Range')
    if requested:
        match=re.fullmatch(r'bytes=(\d+)-(\d*)',requested)
        if not match or int(match[1])>=size or (match[2] and int(match[2])<int(match[1])):
            handler.send_response(416);handler.send_header('Content-Range',f'bytes */{size}');handler.send_header('Content-Length','0');handler.end_headers();return
        start=int(match[1]);end=min(end,int(match[2])) if match[2] else end
    handler.send_response(206 if requested else 200)
    handler.send_header('Content-Type',mimetypes.guess_type(path)[0] or 'application/octet-stream')
    if query.get('download')==['1']: handler.send_header('Content-Disposition',"attachment; filename*=UTF-8''"+quote(path.name))
    handler.send_header('Content-Length',str(end-start+1));handler.send_header('Accept-Ranges','bytes')
    handler.send_header('Cache-Control','no-store');handler.send_header('Referrer-Policy','no-referrer')
    if requested:handler.send_header('Content-Range',f'bytes {start}-{end}/{size}')
    handler.end_headers()
    with path.open('rb') as stream:
        stream.seek(start);remaining=end-start+1
        while remaining:
            data=stream.read(min(1024**2,remaining))
            if not data:break
            handler.wfile.write(data);remaining-=len(data)
