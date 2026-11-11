"""Prepend an intro to the same frozen body; verify every body video frame."""
from pathlib import Path
import hashlib,json,shutil
from .curation import file_hash
from .render import run_ffmpeg


def decoded_frame_hashes(path):
    import av
    with av.open(str(path)) as container:
        for frame in container.decode(video=0):
            yield hashlib.sha256(frame.to_ndarray(format='rgb24').tobytes()).hexdigest()


def assemble(intro, body, folder, stop, mode='prepend', *, reusable=None, workbench_root=None):
    import av
    if mode!='prepend':raise ValueError('Dedicated intro-slot replacement requires the inspected native template adapter.')
    if intro['body_revision']!=body['body_revision']:raise ValueError('This intro belongs to a different body revision.')
    for artifact in (intro,body):
        if file_hash(artifact['path'])!=artifact['checksum']:raise ValueError('A rendered artifact changed after validation.')
    def properties(path):
        with av.open(str(path)) as con:
            s=con.streams.video[0]
            return (s.width,s.height,str(s.average_rate),s.codec_context.name)
    if properties(intro['path'])!=properties(body['path']):raise ValueError('Render the intro and body with matching frame rate and canvas before assembly.')
    folder=Path(folder);folder.mkdir(parents=True,exist_ok=True)
    from hinglish_app.workbench_jobs import atomic_json
    if stop.is_set():
        raise InterruptedError('Comparison rendering stopped.')
    target = folder / 'Trial.mp4'
    manifest = folder / 'assembly-manifest.json'
    try:
        saved = json.loads(manifest.read_text(encoding='utf-8'))
        if (saved.get('mode') == mode and saved.get('body_revision') == body['body_revision']
                and saved.get('body_checksum') == body['checksum'] and saved.get('intro_checksum') == intro['checksum']
                and saved.get('frame_count') == intro['frame_count'] + body['frame_count']
                and saved.get('body_video_frames_identical') is True
                and saved.get('path') == str(target) and saved.get('checksum') == file_hash(target)):
            return saved
    except (OSError, ValueError):
        pass
    if (reusable and workbench_root is not None and reusable.get('mode') == mode
            and reusable.get('body_revision') == body['body_revision']
            and reusable.get('body_checksum') == body['checksum'] and reusable.get('intro_checksum') == intro['checksum']
            and reusable.get('frame_count') == intro['frame_count'] + body['frame_count']
            and reusable.get('body_video_frames_identical') is True):
        source = Path(reusable['path']).resolve()
        if source.is_relative_to(workbench_root.resolve()) and source.is_file() and file_hash(source) == reusable['checksum']:
            temporary = folder / 'Trial.reuse.partial.mp4'
            shutil.copy2(source, temporary)
            if file_hash(temporary) != reusable['checksum']:
                raise ValueError('The prior trial changed while copying it.')
            temporary.replace(target)
            receipt = {**reusable, 'path': str(target), 'reused_from': str(source)}
            atomic_json(manifest, receipt)
            return receipt
    # Portable copies use generated names and cannot inject concat directives.
    for artifact,name in ((intro,'intro.mp4'),(body,'body.mp4')):shutil.copy2(artifact['path'],folder/name)
    intro_seconds=intro['frame_count']/float(intro['fps']);body_seconds=body['frame_count']/float(body['fps'])
    listing=folder/'assembly.txt';listing.write_text(f"file 'intro.mp4'\nduration {intro_seconds}\nfile 'body.mp4'\nduration {body_seconds}\n",encoding='utf-8')
    partial=folder/'Trial.partial.mp4';target=folder/'Trial.mp4'
    graph=f'[1:a]atrim=duration={intro_seconds},asetpts=PTS-STARTPTS[a];[2:a]atrim=duration={body_seconds},asetpts=PTS-STARTPTS[b];[a][b]concat=n=2:v=0:a=1[audio]'
    run_ffmpeg(['-f','concat','-safe','1','-i',listing,'-i',folder/'intro.mp4','-i',folder/'body.mp4',
                '-filter_complex',graph,'-map','0:v:0','-map','[audio]','-c:v','copy','-c:a','aac','-ar','48000','-ac','2',
                '-t',str(intro_seconds+body_seconds),'-movflags','+faststart',partial],folder,stop)
    assembled=list(decoded_frame_hashes(partial));body_hashes=list(decoded_frame_hashes(body['path']))
    if len(assembled)!=intro['frame_count']+body['frame_count'] or assembled[intro['frame_count']:]!=body_hashes:
        raise ValueError('The assembled trial did not preserve every decoded body frame.')
    partial.replace(target)
    receipt={'path':str(target),'checksum':file_hash(target),'body_revision':body['body_revision'],
             'body_checksum':body['checksum'],'intro_checksum':intro['checksum'],'mode':'prepend',
             'frame_count':len(assembled),'duration':intro_seconds+body_seconds,'body_video_frames_identical':True,
             'audio_note':'Original intro/body audio joined and encoded once as AAC.','approval_state':'preview'}
    atomic_json(manifest, receipt)
    return receipt
