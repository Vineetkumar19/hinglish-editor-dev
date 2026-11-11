"""Safe adversarial evidence. Findings are recorded, deliberately not repaired."""
import json
import socket
import tempfile
import threading
from pathlib import Path
from http.server import ThreadingHTTPServer,BaseHTTPRequestHandler
from unittest.mock import patch
from yt_dlp import YoutubeDL
from yt_dlp.networking import Request
from hinglish_app.downloader import DownloadService,format_selector,validate_request

root=Path(__file__).resolve().parents[1]
base=root/'output/downloader-validation';base.mkdir(parents=True,exist_ok=True)
tempfile.tempdir=str(base/'tmp')
findings=[]
formats=[{'format_id':'a','url':'https://cdn.example/audio','vcodec':'none','acodec':'aac','ext':'m4a','abr':128}]
formats += [{'format_id':str(h),'url':'https://cdn.example/'+str(h),'width':int(h*9/16),'height':h,'vcodec':'h264','acodec':'none','ext':'mp4','fps':30} for h in (640,1280,1920)]
with YoutubeDL({'quiet':True}) as y:
    selected=list(y.build_format_selector(format_selector('720','video'))({'formats':formats,'has_merged_format':False,'incomplete_formats':False}))[0]
findings.append({'id':'D1','status':'confirmed','severity':'medium','title':'Portrait YouTube quality uses the long edge',
 'trigger':'Offer portrait 360x640, 720x1280 and 1080x1920 formats; request 720p.',
 'expected':'720x1280 portrait selection','actual':f"{selected['width']}x{selected['height']}",
 'impact':'Portrait Shorts can download below the intended quality. Only the supplied landscape YouTube link was tested live.'})

hits=[]
class Fixture(BaseHTTPRequestHandler):
 def log_message(self,*args):pass
 def do_GET(self):
    hits.append(self.path)
    if self.path=='/redirect':
        self.send_response(302);self.send_header('Location',f'http://127.0.0.1:{self.server.server_port}/controlled-private-fixture');self.end_headers()
    else:
        body=b'Harmless local audit fixture';self.send_response(200);self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
server=ThreadingHTTPServer(('127.0.0.1',0),Fixture);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
original_dns=socket.getaddrinfo;lookups=0

def fixture_dns(host,port,*args,**kwargs):
 global lookups
 if host=='public-download.invalid':
    lookups+=1
    # First lookup is the guard, second is the transport. The separate redirect
    # then goes to the harmless local fixture. No owner service is accessed.
    return original_dns('8.8.8.8' if lookups==1 else '127.0.0.1',port,*args,**kwargs)
 return original_dns(host,port,*args,**kwargs)

with tempfile.TemporaryDirectory() as tmp:
 folder=Path(tmp);downloads=DownloadService(folder)
 class ProbeDL(YoutubeDL):
    def __init__(self,options):super().__init__({**options,'proxy':''})
    def extract_info(self,url,download):
        with self.urlopen(Request(f'http://public-download.invalid:{server.server_port}/redirect')) as response:response.read()
        return {'title':'Controlled audit fixture','duration':1}
    def process_ie_result(self,info,download):
        (folder/'source.mp4').write_bytes(b'Controlled fixture only');return info
 try:
    with patch('yt_dlp.YoutubeDL',ProbeDL),patch('socket.getaddrinfo',fixture_dns):
        downloads.transfer(validate_request({'url':'https://youtu.be/audit'}),folder,lambda *args:None,threading.Event())
    findings.append({'id':'D2','status':'confirmed' if '/controlled-private-fixture' in hits else 'not_reproduced','severity':'high',
      'title':'Network address guard is not bound to the actual connection or redirects',
      'trigger':'Controlled public-host lookup changes before connection and redirects to our own temporary loopback fixture.',
      'expected':'Reject a connection or redirect to a private address','actual':{'fixture_requests':hits,'dns_lookups':lookups},
      'impact':'A downloaded page or media redirect can reach a local address despite the initial public-address check. This is a controlled transport test; an exploit through a real platform post is not established. No owner service or sensitive data was accessed.'})
 except Exception as error:
    findings.append({'id':'D2','status':'not_reproduced','details':str(error),'fixture_requests':hits})
 finally:downloads.close();server.shutdown();server.server_close();thread.join(2)
(base/'adversarial-findings.json').write_text(json.dumps(findings,indent=2),encoding='utf-8')
print(json.dumps(findings,indent=2))
