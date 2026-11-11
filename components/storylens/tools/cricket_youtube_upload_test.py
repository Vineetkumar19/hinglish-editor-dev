"""Two explicitly requested private uploads using Storylens's real publisher."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
FOLDER=ROOT/'output/validation/cricket-youtube-existing-footage-20261018'
PROFILE='cricket'
CHANNEL_ID='UCISO1Vfw20A6Tlb2xMGQqGg'
HANDLE='@fantasylegends3823'


def write_json(path,data):
    temporary=path.with_suffix('.tmp')
    temporary.write_text(json.dumps(data,indent=2,ensure_ascii=False),encoding='utf-8')
    temporary.replace(path)


def prepare():
    import av
    from imageio_ffmpeg import get_ffmpeg_exe
    FOLDER.mkdir(parents=True,exist_ok=True)
    manifest_path=FOLDER/'prepared.json'
    if manifest_path.is_file():
        saved=json.loads(manifest_path.read_text(encoding='utf-8'))
        assert saved.get('uses_existing_user_footage') is True
        assert all(Path(item['video']).is_file() for item in saved['videos'])
        print('Existing-footage test clips already prepared; reusing them.',flush=True)
        return
    sources=[('short',12,0,Path(r'D:/Editing/documentry edit/final videos/final shorts/mi/short 1.mp4')),
             ('long',90,15,Path(r'D:/Editing/documentry edit/final videos/final videos/mi2020 final.mp4'))]
    videos=[]
    for kind,seconds,offset,source in sources:
        path=FOLDER/f'cricket-{kind}-test.mp4'
        print(f'Extracting {seconds} seconds from {source.name} using NVIDIA NVENC...',flush=True)
        result=subprocess.run([get_ffmpeg_exe(),'-nostdin','-hide_banner','-loglevel','error','-y',
            '-ss',str(offset),'-i',str(source),'-t',str(seconds),'-map','0:v:0','-map','0:a:0',
            '-c:v','h264_nvenc','-preset','p4','-cq','23','-b:v','0','-pix_fmt','yuv420p',
            '-c:a','aac','-b:a','192k','-movflags','+faststart',str(path)],capture_output=True)
        if result.returncode:raise RuntimeError(result.stderr.decode(errors='replace')[-2000:])
        subject='Mumbai Indians' if kind=='short' else 'Mumbai Indians 2020 Journey'
        title=subject+f' | {seconds}-Second Upload Test'+(' #Shorts' if kind=='short' else '')
        description=(f'Private Storylens upload test for the Fantasy Legends cricket channel.\n\n'
            f'A {seconds}-second excerpt from the creator-supplied '+('Mumbai Indians Short.' if kind=='short' else 'Mumbai Indians 2020 documentary edit.')+
            ' This test checks the connected channel, title, description, video playback and original source audio. '
            'The footage and editing are taken from the existing project; no new video was generated.\n\n'
            '#MumbaiIndians #Cricket #UploadTest'+(' #Shorts' if kind=='short' else ''))
        metadata={'title':title,'description':description,'instagram_caption':'Mumbai Indians video excerpt for a private upload test. #MumbaiIndians #Cricket #UploadTest','tags':['Mumbai Indians','Cricket','Storylens','upload test']+(['Shorts'] if kind=='short' else ['IPL 2020'])}
        write_json(path.with_suffix('.publish.json'),{'metadata_language':'en','metadata':metadata})
        with av.open(str(path)) as media:
            video=media.streams.video[0];audio=media.streams.audio[0]
            actual=float(media.duration/av.time_base)
            assert abs(actual-seconds)<.1 and audio.codec_context.name=='aac'
            assert (video.height>video.width) == (kind=='short')
            width,height=video.width,video.height
            media.seek(3*av.time_base)
            for frame in media.decode(video=0):
                if frame.time>=3:
                    frame.to_image().save(FOLDER/f'{kind}-preview.png')
                    break
        videos.append({'video':str(path),'source':str(source),'source_start':offset,'kind':kind,'duration':seconds,'width':width,'height':height,'encoder':'h264_nvenc','metadata':metadata,'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'bytes':path.stat().st_size})
    write_json(manifest_path,{'profile':'cricket','channel_id':CHANNEL_ID,'handle':HANDLE,'visibility':'private','made_for_kids':False,'synthetic_media':False,'uses_existing_user_footage':True,'videos':videos})
    print(json.dumps({'prepared':True,'videos':[{k:v for k,v in item.items() if k not in ('metadata','sha256')} for item in videos]},indent=2),flush=True)


def upload():
    from hinglish_publish.providers import youtube_client
    from hinglish_publish.service import Publisher
    from hinglish_publish.store import fingerprint
    from hinglish_publish.worker_lock import acquire
    manifest=json.loads((FOLDER/'prepared.json').read_text(encoding='utf-8'))
    assert manifest['profile']==PROFILE and manifest['channel_id']==CHANNEL_ID
    publisher=Publisher(ROOT)
    assert all(not publisher.settings(profile=p)['enabled'] for p in ('general','cricket','gaming')),'Keep scheduled publishing paused.'
    client,account=youtube_client(ROOT,PROFILE)
    channels=client.channels().list(part='snippet',mine=True).execute()['items']
    assert len(channels)==1 and channels[0]['id']==CHANNEL_ID==account['channel_id']
    assert channels[0]['snippet'].get('customUrl','').casefold()==HANDLE
    receipt_path=FOLDER/'upload-receipt.json'
    receipt=json.loads(receipt_path.read_text(encoding='utf-8')) if receipt_path.exists() else {'profile':PROFILE,'channel_id':CHANNEL_ID,'channel_name':channels[0]['snippet']['title'],'handle':HANDLE,'visibility':'private','uploads':[]}
    worker_lock=acquire(ROOT)
    try:
        items=[]
        for clip in manifest['videos']:
            assert fingerprint(clip['video'])==clip['sha256']
            config={**publisher.settings(profile=PROFILE),'profile':PROFILE,'visibility':'private'}
            prepared=publisher.item(clip['video'],clip['kind'],'',config,progress=lambda s:print(s,flush=True))
            items.extend(item for item in prepared if item['platform']=='youtube')
        ids=publisher.store.add_batch(items)
        receipt['job_ids']=ids;write_json(receipt_path,receipt)
        for job_id in ids:
            job=publisher.store.get(job_id)
            if job.get('remote',{}).get('id'):
                print(f'Reusing saved remote video for {job["kind"]}; no duplicate upload.',flush=True)
                continue
            assert job['status']=='draft','An upload was already attempted; reconcile its outcome before retrying.'
            publisher.store.change(job_id,due=time.time())
            publisher.authorize({'ids':[job_id],'authorize':True,'made_for_kids':False,'synthetic_media':False})
            publisher.store.change(job_id,expected_status=('ready',),status='uploading')
            job=publisher.store.get(job_id)
            print(f'Uploading private {job["kind"]} to {HANDLE}...',flush=True)
            def checkpoint(remote):
                publisher.store.change(job_id,remote=remote)
            try:
                remote,status=publisher.providers['youtube'](ROOT,config).publish(job,checkpoint)
                publisher.store.change(job_id,status=status,remote=remote,error='')
                publisher.store.event(job_id,'Uploaded privately on youtube: '+remote['url'])
                receipt['uploads'].append({'job_id':job_id,'kind':job['kind'],'url':remote['url'],'id':remote['id'],'status':status})
                write_json(receipt_path,receipt)
                print(f'Accepted: {remote["url"]}',flush=True)
            except Exception as error:
                publisher.store.change(job_id,status='needs_review',error='Test upload outcome needs review; no automatic retry.')
                publisher.store.event(job_id,'Test upload needs review; saved remote ID retained and no duplicate attempted.')
                receipt['failure']={'job_id':job_id,'error_type':type(error).__name__,'http_status':getattr(getattr(error,'resp',None),'status',None)}
                write_json(receipt_path,receipt)
                raise RuntimeError(json.dumps(receipt['failure'])) from None
        receipt['uploads']=[]
        for job_id in ids:
            job=publisher.store.get(job_id)
            remote=job.get('remote',{})
            assert remote.get('id'),'No accepted upload receipt.'
            receipt['uploads'].append({'job_id':job_id,'kind':job['kind'],'id':remote['id'],'url':remote['url'],'status':job['status']})
        write_json(receipt_path,receipt)
        pending={row['id'] for row in receipt['uploads']}
        deadline=time.monotonic()+240
        while pending and time.monotonic()<deadline:
            data=client.videos().list(part='snippet,status,contentDetails,processingDetails',id=','.join(pending)).execute().get('items',[])
            for video in data:
                row=next(row for row in receipt['uploads'] if row['id']==video['id'])
                clip=next(clip for clip in manifest['videos'] if clip['kind']==row['kind'])
                assert video['snippet']['channelId']==CHANNEL_ID
                assert video['snippet']['title']==clip['metadata']['title']
                assert video['snippet']['description']==clip['metadata']['description']
                assert video['status']['privacyStatus']=='private'
                assert video['status'].get('selfDeclaredMadeForKids') is False
                state=video['status']['uploadStatus']
                if state in ('failed','rejected','deleted'):raise RuntimeError(f'YouTube processing failed: {state}')
                row.update(privacy='private',title=video['snippet']['title'],duration=video['contentDetails']['duration'],upload_status=state,processing_status=video.get('processingDetails',{}).get('processingStatus'),channel_verified=True,metadata_verified=True)
                if state=='processed':pending.remove(video['id'])
            receipt['all_processed']=not pending
            write_json(receipt_path,receipt)
            if pending:time.sleep(8)
        receipt['completed_at']=time.time()
        receipt['automatic_publishing_enabled']=False
        write_json(receipt_path,receipt)
        print(json.dumps(receipt,indent=2),flush=True)
        if pending:raise RuntimeError('Uploads accepted, but YouTube processing is still pending; do not upload again.')
    finally:
        worker_lock.close()


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=('prepare','upload'))
    action=parser.parse_args().action
    prepare() if action=='prepare' else upload()
