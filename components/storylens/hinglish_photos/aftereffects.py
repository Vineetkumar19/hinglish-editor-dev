"""Import verified local photos into the currently open AE project, with a host receipt."""
import json
from pathlib import Path
import subprocess
import time
import uuid

def running_ae():
    if not hasattr(subprocess,'CREATE_NO_WINDOW'):return None
    result=subprocess.run(['powershell','-NoProfile','-Command',
        "@(Get-Process AfterFX -ErrorAction SilentlyContinue | Where-Object {$_.MainWindowHandle -ne 0} | Select-Object -ExpandProperty Path) | ConvertTo-Json -Compress"],
        capture_output=True,text=True,timeout=10,creationflags=subprocess.CREATE_NO_WINDOW)
    try:value=json.loads(result.stdout or 'null')
    except ValueError:return None
    paths=[value] if isinstance(value,str) else value or []
    if len(paths)!=1:return None
    path=Path(paths[0])
    return str(path) if path.is_file() and path.name.lower()=='afterfx.exe' else None

def make_script(manifest,receipt):
    data=json.dumps(manifest,ensure_ascii=True).replace('</','<\\/')
    target=json.dumps(str(receipt).replace('\\','/'),ensure_ascii=True)
    host=Path(__file__).with_name('native_host.jsx').read_text('utf8')
    return host+'\n(function(){\nvar m='+data+',receipt=new File('+target+');\n'+r'''
var result=storylensPhotoImportAE(m);
try{receipt.encoding='UTF-8';if(!receipt.open('w'))throw Error('File access disabled');receipt.write(storylensPhotoJSON(result));receipt.close();}
catch(error){alert('Storylens could not confirm the import. Enable Scripts to Write Files in Scripting & Expressions preferences, then inspect the project before retrying.');}
})();'''

def prepare_files(folder,paths,photos=None,allow_downloads=False):
    folder=Path(folder).resolve();bridge=folder/'after-effects';bridge.mkdir(exist_ok=True)
    verified=[];records=[]
    source_rows=photos if photos is not None else [{'id':i+1,'path':v,'origin':'original'} for i,v in enumerate(paths)]
    for row in source_rows:
        value=row['path']
        path=Path(value).resolve()
        if not any(path.is_relative_to((folder/name).resolve()) for name in (('photos','previews','downloads') if allow_downloads else ('photos','previews'))) or not path.is_file():raise ValueError('Photo file invalid: only this collection’s saved photos can be imported.')
        if path.suffix.lower() not in ('.png','.jpg','.jpeg','.tif','.tiff','.psd'):
            from PIL import Image
            converted=bridge/(path.stem+'.png')
            with Image.open(path) as image:
                pixels=image.convert('RGBA');profile=image.info.get('icc_profile')
                def same(target):
                    try:
                        with Image.open(target) as prior:return prior.size==pixels.size and prior.convert('RGBA').tobytes()==pixels.tobytes() and prior.info.get('icc_profile')==profile
                    except (OSError,ValueError):return False
                if not same(converted):
                    if converted.exists():
                        import hashlib
                        converted=bridge/(path.stem+'-'+hashlib.sha256(path.read_bytes()).hexdigest()[:12]+'.png')
                    if not same(converted):pixels.save(converted,icc_profile=profile)
            path=converted
        verified.append(str(path));records.append({'id':row['id'],'path':str(path),'origin':row['origin']})
    return verified,records

def import_photos(folder,job,paths,*,expected=None,photos=None,find_app=running_ae,runner=subprocess.Popen,timeout=30):
    executable=find_app()
    if not executable:raise ValueError('Photo After Effects unavailable: Open After Effects with one project, then choose Import into After Effects again. Saved photos are kept.')
    console=Path(executable).with_suffix('.com')
    if console.is_file():executable=str(console)
    folder=Path(folder).resolve();bridge=folder/'after-effects';bridge.mkdir(exist_ok=True)
    request=uuid.uuid4().hex[:12];receipt=bridge/(request+'-receipt.json');script=bridge/(request+'.jsx')
    verified,records=prepare_files(folder,paths,photos)
    manifest={'id':job['id'],'name':job['title'],'paths':verified,'photos':records,'expected':expected}
    script.write_text(make_script(manifest,receipt),encoding='utf8')
    log=(bridge/(request+'-launcher.log')).open('wb')
    try:
        process=runner([executable,'-r',str(script)],stdout=log,stderr=subprocess.STDOUT,**({'creationflags':subprocess.CREATE_NO_WINDOW} if hasattr(subprocess,'CREATE_NO_WINDOW') else {}))
    finally:log.close()
    deadline=time.monotonic()+timeout
    while time.monotonic()<deadline:
        if receipt.is_file():
            try:result=json.loads(receipt.read_text('utf-8-sig'))
            except (OSError,ValueError):result={}
            if result.get('status')=='done':return {**result,'receipt':str(receipt)}
            if result.get('status')=='failed':raise ValueError('Photo After Effects import stopped: '+result.get('error','Check the open project.')+' Saved photos are kept.')
        time.sleep(.1)
    code=process.poll() if process is not None and hasattr(process,'poll') else None
    raise ValueError('Photo After Effects unconfirmed: After Effects did not confirm the import. Check its open dialogs and Scripting & Expressions file-access preference, then check the project before retrying. Saved photos are kept. Launcher exit: '+str(code)+'. Diagnostic file: '+str(bridge/(request+'-launcher.log')))
