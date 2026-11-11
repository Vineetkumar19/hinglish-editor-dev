"""Small real-engine smoke check. This is not evidence of a native editor import."""
from pathlib import Path
import json
import subprocess
import sys
from urllib.request import Request,urlopen

ROOT=Path(__file__).resolve().parents[1]
DEST=ROOT/'output/plugin-validation'

def api(path,body=None):
    with urlopen('http://127.0.0.1:8765/api/bridge',timeout=10) as response:token=json.load(response)['token']
    request=Request('http://127.0.0.1:8765'+path,headers={'X-Hinglish-Token':token,'Content-Type':'application/json'},
                    data=json.dumps(body).encode() if body is not None else None)
    with urlopen(request,timeout=60) as response:return json.load(response)

def start():
    import imageio_ffmpeg
    from hinglish_cut.media import probe
    from hinglish_app.editor_panel import snapshot_xml
    DEST.mkdir(parents=True,exist_ok=True)
    source=ROOT/'output/downloads/4958ed97ebff4e6cb808ef35a29d23d2/video/downloaded-video.mp4'
    clip=DEST/'native-panel-check-10sec.mp4'
    subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(),'-y','-i',str(source),'-vf',
                    'trim=duration=8,setpts=PTS-STARTPTS,scale=640:360,fps=30,tpad=stop_mode=clone:stop_duration=2',
                    '-af','atrim=duration=8,asetpts=PTS-STARTPTS,apad=pad_dur=2','-t','10',
                    '-c:v','libx264','-preset','ultrafast','-crf','25','-c:a','aac',str(clip)],check=True,capture_output=True)
    context={'host':'aftereffects','project_id':'Storylens isolated validation fixture','sequence_id':'10-second-test',
             'name':'Plugin validation footage','width':640,'height':360,'fps':30,'duration':10,
             'clips':[{'path':str(clip),'start':0,'end':10,'source_in':0,'kind':'video','track':0}],'script':''}
    xml=snapshot_xml(ROOT,context)
    (DEST/'native-fixture-context.json').write_text(json.dumps(context,indent=2),encoding='utf-8')
    saved=api('/api/panel/context',context)
    job=api('/api/panel/run',{'context_id':saved['id'],'mode':'clean','settings':{'format':'original'}})
    receipt={'kind':'real engine with explicit test fixture; not a native-editor capture','context_id':saved['id'],
             'job_id':job['id'],'fixture':str(clip),'timeline_xml':str(xml),'status':job['status']}
    (DEST/'real-clean-check.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8')
    print(json.dumps(receipt,indent=2))

def check():
    file=DEST/'real-clean-check.json';receipt=json.loads(file.read_text(encoding='utf-8'))
    result=api('/api/panel/job?id='+receipt['job_id']);receipt['result']=result;receipt['status']=result['status']
    file.write_text(json.dumps(receipt,indent=2),encoding='utf-8')
    print(json.dumps({'status':result['status'],'stage':result.get('stage'),'error':result.get('error'),
                      'manifest_type':(result.get('manifest') or {}).get('type'),'engine_id':result.get('engine_id')},indent=2))

if __name__=='__main__':start() if sys.argv[-1]=='start' else check()
