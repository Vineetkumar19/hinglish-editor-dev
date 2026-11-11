"""Low-resolution analysis preview with exact decoded-frame/source-PTS lineage."""
from pathlib import Path
from fractions import Fraction
import json,uuid
from .curation import file_hash,digest

VERSION='source-proxy-v1'


def proxy_id(source_hash):
    return digest({'source':source_hash,'version':VERSION})

def make_proxy(source,folder,stop,progress=lambda *args:None):
    import av
    from PIL import Image,ImageOps,ImageDraw
    from hinglish_cut.media import video_rotation,orient_frame
    from hinglish_app.workbench_jobs import atomic_json,replace_retry
    source=Path(source);folder=Path(folder);folder.mkdir(parents=True,exist_ok=True)
    identity=file_hash(source);receipt=folder/'source-proxy.json'
    if receipt.exists():
        try:
            saved=json.loads(receipt.read_text('utf-8'))
            if saved['source_sha256']==identity and saved['version']==VERSION and file_hash(saved['path'])==saved['checksum'] and file_hash(saved['mapping'])==saved['mapping_sha256']:
                return {**saved,'cache_hit':True}
        except (OSError,ValueError,KeyError):pass
    partial=folder/('proxy-'+uuid.uuid4().hex+'.part.mp4');target=folder/'Source_preview.mp4'
    rotation=video_rotation(source);rows=[];thumbs=[]
    try:
        with av.open(str(source)) as incoming,av.open(str(partial),'w') as outgoing:
            stream=incoming.streams.video[0];stream.thread_count=2
            encoded=outgoing.add_stream('libx264',rate=stream.average_rate or 30)
            encoded.pix_fmt='yuv420p';encoded.codec_context.thread_count=2
            encoded.options={'crf':'30','preset':'veryfast'}
            origin=None;tickbase=Fraction(1,90000);next_thumb=0.
            for index,frame in enumerate(incoming.decode(video=0)):
                if stop.is_set():raise InterruptedError('Source preview stopped; source bytes unchanged.')
                if frame.pts is None:raise ValueError('Source preview needs reliable presentation timestamps.')
                original=frame.pts;tb=frame.time_base;origin=original*tb if origin is None else origin
                timestamp=original*tb-origin
                pixels=orient_frame(frame,rotation).to_ndarray(format='rgb24')
                picture=Image.fromarray(pixels);picture.thumbnail((480,480),Image.Resampling.BILINEAR)
                width=max(2,picture.width//2*2);height=max(2,picture.height//2*2)
                picture=picture.resize((width,height))
                if index==0:
                    encoded.width=width;encoded.height=height;encoded.time_base=tickbase
                    encoded.codec_context.time_base=tickbase
                proxy=av.VideoFrame.from_image(picture);proxy.pts=round(timestamp/tickbase);proxy.time_base=tickbase
                rows.append({'proxy_frame':index,'source_pts':original,'source_timebase':str(tb),'relative_seconds':float(timestamp),'proxy_pts':proxy.pts,'proxy_timebase':str(tickbase)})
                for packet in encoded.encode(proxy):outgoing.mux(packet)
                if float(timestamp)>=next_thumb and len(thumbs)<60:
                    tile=ImageOps.pad(picture,(160,110),color='black');ImageDraw.Draw(tile).text((4,4),f'{float(timestamp):.2f}s',fill='white');thumbs.append(tile);next_thumb=float(timestamp)+max(1,float((incoming.duration or 0)/1e6)/60)
                if index%100==0:progress(f'Analysis preview {index} frames',min(95,100*float(timestamp)/max(1,(incoming.duration or 1)/1e6)))
            for packet in encoded.encode():outgoing.mux(packet)
        if not rows:raise ValueError('No source frames decoded.')
        with av.open(str(partial)) as verify:
            actual=[float(f.time) for f in verify.decode(video=0)]
        if len(actual)!=len(rows) or any(abs(t-r['relative_seconds'])>1/45000 for t,r in zip(actual,rows)):
            raise ValueError('Proxy/source frame mapping did not verify.')
        if file_hash(source)!=identity:raise ValueError('The source changed during preview generation.')
        replace_retry(partial,target)
        sheet=Image.new('RGB',(800,110*((len(thumbs)+4)//5)),'#151515')
        for i,tile in enumerate(thumbs):sheet.paste(tile,((i%5)*160,(i//5)*110))
        strip=folder/'Source_strip.jpg';sheet.save(strip,quality=88)
        mapping=folder/'source-frame-map.json';atomic_json(mapping,rows)
        result={'path':str(target),'checksum':file_hash(target),'source':str(source),'source_sha256':identity,'version':VERSION,'mapping':str(mapping),'mapping_sha256':file_hash(mapping),'strip':str(strip),'frame_count':len(rows),'duration':actual[-1],'rotation_applied':rotation,'audio':'silent analysis proxy; original/candidate audio remains separate','cache_hit':False}
        atomic_json(receipt,result);return result
    finally:
        if partial.exists():partial.unlink()

def run_proxy(root,request,folder,stop,progress):
    import re
    if not re.fullmatch('[a-f0-9]{32}',request['dataset_id']):raise ValueError('Choose a saved dataset.')
    job=json.loads((Path(root)/'output/workbench'/request['dataset_id']/'job.json').read_text('utf-8'))
    if job['kind']!='footage' or job['status']!='complete':raise ValueError('Choose a completed footage dataset.')
    row=next((r for r in job['result']['assets'] if r['id']==request['candidate_id']),None)
    if row is None:raise ValueError('Choose a source from this dataset.')
    if file_hash(row['source'])!=row['source_sha256']:raise ValueError('The original source changed.')
    cache=Path(root)/'cache/curation/proxies'/proxy_id(row['source_sha256'])
    result=make_proxy(row['source'],cache,stop,progress)
    source_duration=row['duration']
    if {'in_pts','out_pts','timebase'} <= row.keys():
        source_duration=float((row['out_pts']-row['in_pts'])*Fraction(row['timebase']))
    return {**result,'proxy_id':cache.name,'dataset_id':job['id'],'candidate_id':row['id'],
            'span_start':row['start'],'span_end':row['start']+source_duration}
