"""Requested Gaming-channel test with two different existing cricket clips."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

import cricket_youtube_upload_test as shared

shared.PROFILE='gaming'
shared.CHANNEL_ID='UCtc3vpF9QPHAM7lTYCCulyg'
shared.HANDLE='@vineet_91'
shared.FOLDER=shared.ROOT/'output/validation/gaming-youtube-existing-footage-20261018'


def prepare():
    import av
    import numpy as np
    from imageio_ffmpeg import get_ffmpeg_exe
    folder=shared.FOLDER;folder.mkdir(parents=True,exist_ok=True)
    manifest_path=folder/'prepared.json'
    if manifest_path.exists():
        manifest=json.loads(manifest_path.read_text(encoding='utf-8'))
        assert manifest['profile']=='gaming' and manifest['channel_id']==shared.CHANNEL_ID
        assert all(Path(row['video']).is_file() for row in manifest['videos'])
        print('Prepared Gaming clips already exist; reusing them.',flush=True)
        return
    sources=[
        {'kind':'short','duration':12,'start':0,'source':Path(r'D:/Editing/documentry edit/final videos/final shorts/Mi 2024 shorts/2.mp4'),
         'title':'Mumbai Indians | The Early IPL Years #Shorts',
         'description':"A look back at Mumbai Indians' early IPL seasons and the team's journey through the league.\n\n#MumbaiIndians #IPL #Cricket #Shorts",
         'tags':['Mumbai Indians','IPL','Cricket','Mumbai Indians history','Shorts']},
        {'kind':'long','duration':90,'start':0,'source':Path(r'D:/Editing/documentry edit/final videos/final videos/kkr final.mp4'),
         'title':'Kolkata Knight Riders | The IPL Journey',
         'description':"Explore Kolkata Knight Riders' IPL journey through team moments, photographs and the story of the franchise.\n\n#KKR #KolkataKnightRiders #IPL #Cricket",
         'tags':['Kolkata Knight Riders','KKR','IPL','Cricket','KKR history']},
    ]
    videos=[]
    for source in sources:
        kind=source['kind'];path=folder/f'{kind}.mp4'
        print(f'Extracting {source["duration"]} seconds from {source["source"].name}...',flush=True)
        command=[get_ffmpeg_exe(),'-nostdin','-hide_banner','-loglevel','error','-y','-ss',str(source['start']),'-i',str(source['source']),
                 '-t',str(source['duration']),'-map','0:v:0','-map','0:a:0']
        if kind=='long':command+=['-vf','scale=1920:1080:flags=lanczos']
        command+=['-r','30','-c:v','h264_nvenc','-preset','p4','-cq','24','-b:v','0','-pix_fmt','yuv420p',
                  '-c:a','aac','-b:a','192k','-movflags','+faststart',str(path)]
        result=subprocess.run(command,capture_output=True)
        if result.returncode:raise RuntimeError(result.stderr.decode(errors='replace')[-2000:])
        metadata={'title':source['title'],'description':source['description'],'tags':source['tags'],
                  'instagram_caption':source['description']}
        from hinglish_publish.metadata import validate
        validate(metadata)
        shared.write_json(path.with_suffix('.publish.json'),{'metadata_language':'en','metadata':metadata})
        with av.open(str(path)) as media:
            stream=media.streams.video[0]
            assert abs(media.duration/av.time_base-source['duration'])<.1
            assert (stream.width,stream.height)==((1080,1920) if kind=='short' else (1920,1080))
            assert stream.frames==source['duration']*30 and len(media.streams.audio)==1
            media.seek(3*av.time_base)
            for frame in media.decode(video=0):
                if frame.time>=3:
                    frame.to_image().save(folder/f'{kind}-preview.png');break
        with av.open(str(path)) as media:
            media.seek(2*av.time_base)
            energy=0.;samples=0
            for frame in media.decode(audio=0):
                values=frame.to_ndarray().astype(np.float64)
                energy+=float(np.square(values).sum());samples+=values.size
                if frame.time and frame.time>=5:break
            assert (energy/samples)**.5>.001
        videos.append({'kind':kind,'video':str(path),'source':str(source['source']),'source_start':source['start'],
            'duration':source['duration'],'width':1080 if kind=='short' else 1920,'height':1920 if kind=='short' else 1080,
            'metadata':metadata,'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'bytes':path.stat().st_size,'encoder':'h264_nvenc'})
    cricket_manifest=json.loads((shared.ROOT/'output/validation/cricket-youtube-existing-footage-20261018/prepared.json').read_text(encoding='utf-8'))
    assert not {row['sha256'] for row in videos}&{row['sha256'] for row in cricket_manifest['videos']}
    assert not {row['source'] for row in videos}&{row['source'] for row in cricket_manifest['videos']}
    shared.write_json(manifest_path,{'profile':'gaming','channel_id':shared.CHANNEL_ID,'handle':shared.HANDLE,
        'visibility':'private','uses_existing_user_footage':True,'different_from_cricket_test':True,'videos':videos})
    print(json.dumps({'prepared':True,'different_sources':True,'titles':[row['metadata']['title'] for row in videos],
                      'total_mb':round(sum(row['bytes'] for row in videos)/1e6,1)},indent=2),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=('prepare','upload'))
    action=parser.parse_args().action
    prepare() if action=='prepare' else shared.upload()
