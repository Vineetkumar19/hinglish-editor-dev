"""Local integration proof: simulated payment, real uploaded footage and engine.

Never touches merchant accounts or the preview's customer database.
"""
import hashlib
import hmac
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from fastapi.testclient import TestClient
from imageio_ffmpeg import get_ffmpeg_exe
from hinglish_saas.app import create_app
from hinglish_saas.config import Settings
from hinglish_saas.worker import run_once
from tests.test_saas import Provider


def main():
    out=ROOT/'output/saas/live-test';out.mkdir(parents=True,exist_ok=True)
    test_dir=out/('run-'+str(int(time.time())))
    source=ROOT/'input/phase1/instagram-vertical/VID20260808004509.mp4';fixture=out/'uploaded-demo.mp4'
    subprocess.run([get_ffmpeg_exe(),'-hide_banner','-loglevel','error','-y','-ss','2','-i',str(source),'-t','8',
                    '-vf','scale=360:-2','-r','30','-c:v','libx264','-preset','fast','-c:a','aac',str(fixture)],check=True)
    import av
    with av.open(str(fixture)) as clip:
        if abs(clip.duration/av.time_base-8)>.1:raise RuntimeError('Integration fixture must contain eight seconds of footage.')
    settings=Settings(data_dir=test_dir,worker_enabled=True,sales_enabled=True,enabled_tools=('clean',),
                      key_id='rzp_test_local_simulation',key_secret='local-simulation-only',webhook_secret='local-simulation-only')
    provider=Provider();app=create_app(settings,provider);client=TestClient(app,base_url=settings.origin,headers={'Origin':settings.origin})
    account=client.post('/api/auth/register',json={'email':'integration-only@example.com','password':'Local integration fixture 123456'})
    account.raise_for_status();csrf=account.json()['csrf'];headers={'X-CSRF-Token':csrf}
    user=app.state.store.one('SELECT id FROM users WHERE email=?',('integration-only@example.com',))
    # Verified email is a test fixture. Production verification uses the
    # single-use email link; there is no public grant/verification shortcut.
    app.state.store.execute('UPDATE users SET verified=1 WHERE id=?',(user['id'],))
    order=client.post('/api/billing/orders',json={'plan':'monthly'},headers=headers);order.raise_for_status();oid=order.json()['order_id']
    payment=next(p for p in provider.payments.values() if p['order_id']==oid)
    signature=hmac.new(settings.key_secret.encode(),f'{oid}|{payment["id"]}'.encode(),hashlib.sha256).hexdigest()
    activated=client.post('/api/billing/verify',json={'order_id':oid,'payment_id':payment['id'],'signature':signature},headers=headers);activated.raise_for_status()
    upload=client.post('/api/uploads?name=demo.mp4',content=fixture.read_bytes(),headers={**headers,'Content-Type':'application/octet-stream'});upload.raise_for_status()
    edit=client.post('/api/jobs',json={'tool':'clean','upload_ids':[upload.json()['id']],'options':{'format':'source'}},headers=headers);edit.raise_for_status()
    print('Real Smart Clean job queued; simulated payment only.',flush=True)
    began=time.time();run_once(settings)
    result=client.get('/api/jobs/'+edit.json()['id']);result.raise_for_status();data=result.json()
    if data['state']!='complete':raise RuntimeError('Real engine integration failed: '+data['message'])
    file=next(e for e in data['exports'] if e['name']=='cleaned.mp4')
    download=client.get('/api/exports/'+file['id']);download.raise_for_status();video=out/'SAAS_SMART_CLEAN_TEST.mp4';video.write_bytes(download.content)
    import av
    with av.open(str(video)) as encoded:
        duration=encoded.duration/av.time_base;frames=sum(1 for _ in encoded.decode(video=0))
    receipt={'status':'passed','billing':'simulated provider; no real payment','email':'verified test fixture',
             'engine':'real hinglish_clean private subprocess','job_id':data['id'],'input_seconds':8,
             'output_seconds':duration,'decoded_frames':frames,'elapsed_seconds':round(time.time()-began,2),
             'download_sha256':hashlib.sha256(download.content).hexdigest(),'output':str(video),
             'production_accounts_modified':False,'live_preview_sales_enabled':False}
    (out/'integration-receipt.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8')
    print(json.dumps(receipt),flush=True);client.close()


if __name__=='__main__':main()
