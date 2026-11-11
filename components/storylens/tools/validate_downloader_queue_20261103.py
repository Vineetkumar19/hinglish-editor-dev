"""Isolated real UI/FFmpeg validation; no production workers or Adobe launch."""
from pathlib import Path
import json, re, shutil, subprocess, sys, threading, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from hinglish_app.server import serve
from hinglish_app.downloader import service, probe
from hinglish_cut.gpu_lock import gpu_lock
import imageio_ffmpeg

BASE=ROOT/'output/downloader-queue-20261103'
BASE.mkdir(parents=True,exist_ok=True)
APP=BASE/'isolated-app';APP.mkdir(exist_ok=True)
SAVED=BASE/'Saved videos';SAVED.mkdir(exist_ok=True)
(APP/'config.models.local.json').write_text(json.dumps({'device':'cuda','heavy_workloads_gpu_only':True}))
fixture=BASE/'range-source.mp4'
if not fixture.exists():
    with gpu_lock(ROOT):
        subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(),'-hide_banner','-loglevel','error','-y',
            '-f','lavfi','-i','testsrc2=size=640x360:rate=30','-f','lavfi','-i','sine=frequency=440:sample_rate=48000',
            '-t','30','-c:v','h264_nvenc','-preset','p4','-b:v','5M','-c:a','aac','-movflags','+faststart',str(fixture)],check=True)

traffic=[]
class RangeHandler(BaseHTTPRequestHandler):
    def log_message(self,*args): pass
    def do_GET(self):
        size=fixture.stat().st_size; start=0;end=size-1;request=self.headers.get('Range')
        if request:
            m=re.fullmatch(r'bytes=(\d+)-(\d*)',request)
            if not m or int(m[1])>=size:self.send_error(416);return
            start=int(m[1]);end=min(end,int(m[2])) if m[2] else end
        self.send_response(206 if request else 200)
        self.send_header('Content-Type','video/mp4');self.send_header('Accept-Ranges','bytes')
        self.send_header('Content-Length',str(end-start+1))
        if request:self.send_header('Content-Range',f'bytes {start}-{end}/{size}')
        self.end_headers();count=0
        try:
            with fixture.open('rb') as file:
                file.seek(start)
                while count<end-start+1:
                    data=file.read(min(16384,end-start+1-count))
                    if not data:break
                    self.wfile.write(data);self.wfile.flush();count+=len(data)
                    time.sleep(.002)
        except (BrokenPipeError,ConnectionResetError,ConnectionAbortedError): pass
        finally:traffic.append({'range':request,'start':start,'bytes':count})

media=ThreadingHTTPServer(('127.0.0.1',0),RangeHandler)
threading.Thread(target=media.serve_forever,daemon=True).start()
downloads=service(APP)
section_folder=BASE/'section-check';section_folder.mkdir(exist_ok=True)
section=downloads._section_transfer({'mode':'video','section':{'start':10.0,'end':12.0}},
    {'title':'Range test','duration':30,'url':f'http://127.0.0.1:{media.server_port}/source.mp4','vcodec':'h264','acodec':'aac'},
    section_folder,lambda *args:None,threading.Event(),lambda url:None) # controlled localhost fixture only
time.sleep(.1)
result={'duration':probe(section)['duration'],'source_bytes':fixture.stat().st_size,'served_bytes':sum(t['bytes'] for t in traffic),'requests':traffic,
    'scope':'Real CUDA FFmpeg remote seek against controlled HTTP Range source; not a public YouTube extractor test.'}
assert abs(result['duration']-2)<.1,result
assert any(t['start']>0 for t in traffic),result
assert result['served_bytes']<result['source_bytes'],result
(BASE/'section-validation.json').write_text(json.dumps(result,indent=2))
media.shutdown();media.server_close()

original=downloads.transfer
def transfer(request,folder,progress,cancel):
    if 'queue-slow-test' in request['url']:
        progress('Downloading fixture',25)
        deadline=time.monotonic()+180
        while not (BASE/'release-fixture').exists() and time.monotonic()<deadline:
            if cancel.wait(.1): raise ValueError('Download cancelled. Saved files are kept.')
    elif 'queue-fail-test' in request['url']:
        raise ValueError('This fixture is unavailable. Retry this item or use another video link.')
    elif 'queue-fast-test' not in request['url']:
        return original(request,folder,progress,cancel)
    target=folder/'source.mp4';shutil.copy2(section,target);progress('Downloading fixture',85)
    return target,{'title':'Queue fixture '+request['platform']}
downloads.transfer=transfer
server,state=serve(APP,0,publish_bridge=False)
receipt={'url':f'http://127.0.0.1:{state.port}/downloader.html','root':str(APP),'destination':str(SAVED),'pid':__import__('os').getpid(),
    'scope':'Isolated actual application UI; named queue-* links use controlled transfer fixture. Other URLs use real yt-dlp.'}
(BASE/'preview-server.json').write_text(json.dumps(receipt,indent=2))
print(json.dumps(receipt),flush=True)
try:server.serve_forever()
finally:server.server_close();downloads.close()
