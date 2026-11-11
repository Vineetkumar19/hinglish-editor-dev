"""Serve the saved intro edit and its explicitly registered local sources."""
import json
import math
import uuid
from pathlib import Path

from .workbench_http import _media


def get_draft(handler, state, route, query):
    folder = state.root / 'output' / 'intro-drafts' / 'fast-hooks'
    project = json.loads((folder/'manifest.json').read_text('utf-8'))
    if route.endswith('/hook-drafts'):
        assets = {key:{field:value for field,value in asset.items() if field!='path'}
                  for key,asset in project['assets'].items()}
        return handler._json(200, {**project, 'assets':assets})
    asset = project['assets'].get(query.get('asset',[''])[0])
    if not asset:
        return handler._json(404, {'error':'This draft source is unavailable.'})
    path = Path(asset['path']).resolve()
    if not path.is_file() or path.stat().st_size != asset['bytes'] or path.stat().st_mtime_ns != asset['modified']:
        return handler._json(409, {'error':'This draft source changed. Reopen the saved source.'})
    return _media(handler,path,False)


def _validated_draft(root, draft):
    folder = root / 'output' / 'intro-drafts' / 'fast-hooks'
    project = json.loads((folder/'manifest.json').read_text('utf-8'))
    assets = project['assets']
    fps = project['fps']
    frames = draft.get('frames')
    shots, audio = draft.get('shots'), draft.get('audio')
    if type(frames) is not int or not 1 <= frames <= 90*fps or not isinstance(shots,list) or not 1<=len(shots)<=180:
        raise ValueError('Choose a valid intro duration and cut count.')
    if not isinstance(audio,list) or len(audio)>48:
        raise ValueError('Choose a valid sound track list.')
    def number(value,low,high):
        if type(value) not in (int,float) or not math.isfinite(value) or not low<=value<=high+1e-8:
            raise ValueError('A cut or cue is outside its source or timeline.')
        return value
    used = set()
    if not isinstance(draft.get('original_audio',False),bool):
        raise ValueError('Choose an intro type.')
    for shot in shots:
        asset=assets.get(shot['asset'])
        if not asset or Path(asset['path']).suffix.lower() not in ('.mp4','.mov'):
            raise ValueError('Choose a registered picture source.')
        if type(shot['frames']) is not int:
            raise ValueError('Shot length must be a whole number of frames.')
        number(shot['frames'],1,frames)
        number(shot['in'],0,asset['duration']-shot['frames']/fps)
        number(shot.get('x',50),0,100)
        used.add(shot['asset'])
    if sum(shot['frames'] for shot in shots)!=frames:
        raise ValueError('The cut lengths must add up to the intro duration.')
    for cue in audio:
        asset=assets.get(cue['asset'])
        if not asset or Path(asset['path']).suffix.lower() not in ('.wav','.mp3'):
            raise ValueError('Choose a registered sound source.')
        length=number(cue['length'],.01,frames/fps)
        number(cue['at'],0,frames/fps-length)
        number(cue['in'],0,asset['duration']-length)
        number(cue['db'],-48,0)
        number(cue.get('fade_out',.12),.001,1)
        used.add(cue['asset'])
    title=str(draft.get('title','Intro'))[:100]
    data={'name':'StoryLens · '+title,'fps':fps,'drafts':[{**draft,'title':title}],
          'assets':{key:assets[key] for key in used}}
    for asset in data['assets'].values():
        path=Path(asset['path'])
        if not path.is_file() or path.stat().st_size != asset['bytes'] or path.stat().st_mtime_ns != asset['modified']:
            raise ValueError('An original intro source changed. Reopen the saved draft.')
    return data, folder


def download_precomps(handler, state, draft):
    data, folder = _validated_draft(state.root, draft)
    script=(folder/'precomp-template.jsx').read_text('utf-8')
    return handler._json(200,{'script':script.replace('STORYLENS_INTRO_DATA',json.dumps(data),1)})


def prepare_export(root, editor, draft):
    from . import editor_link
    if editor not in editor_link.EDITORS or not isinstance(draft,dict):
        raise ValueError('Choose a saved intro and one of the four editors.')
    data, template = _validated_draft(root,draft)
    key = uuid.uuid4().hex
    folder = editor_link._base(root) / key
    folder.mkdir(parents=True)
    title = data['name'] + ' ' + key[:8]
    if editor == 'aftereffects':
        data.update(name=title, receipt=str(folder/'intro-precomps.tsv'))
        script = folder/'Intro pre-comps.jsx'
        script.write_text((template/'precomp-template.jsx').read_text('utf-8')
                          .replace('STORYLENS_INTRO_DATA',json.dumps(data),1),encoding='utf-8')
        result = {'id':key,'source':'intro','target':editor,'kind':'intro','title':title,'status':'prepared',
                  'artifact':str(script),'instruction':'Open the intro composition in After Effects.','media':''}
        editor_link.resolve_handoff.write_receipt(folder/'handoff.json',result)
        return result
    _build_timeline(folder, data, root=root)
    return editor_link.package_timeline(folder,key,'intro',editor,'intro',title)


def _build_timeline(folder, data, *, root):
    """Conform individual cuts and cues; keep each piece editable on the timeline."""
    from contextlib import nullcontext
    from fractions import Fraction
    import subprocess
    import xml.etree.ElementTree as ET
    from imageio_ffmpeg import get_ffmpeg_exe
    from hinglish_cut.compute_policy import ffmpeg_h264, heavy_device
    from hinglish_cut.gpu_lock import gpu_lock
    from hinglish_cut.media import probe
    from hinglish_cut.model import Cut
    from hinglish_cut.xml_export import export_xml
    from hinglish_sound.xml_export import export_sound_xml

    device = heavy_device(root)
    encoder = ffmpeg_h264(device, 18) if device == 'cuda' else [
        '-c:v', 'libx264', '-threads', '2', '-preset', 'veryfast', '-crf', '18']
    draft = data['drafts'][0]
    assets, fps = data['assets'], data['fps']
    size = (1920,1080) if draft.get('original_audio') else (1080,1920)
    width,height = size
    clips, media, cues = [],{},[]
    cursor = 0
    sources = folder/'Media'
    sources.mkdir()

    def ffmpeg(*args):
        command = [get_ffmpeg_exe(),'-nostdin','-hide_banner','-loglevel','error','-filter_threads','2',*map(str,args)]
        subprocess.run(command,check=True,timeout=180,capture_output=True,
                       creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))

    def audio_layer(path, start, length, db=0, fade=0):
        wav = sources/f'Audio-{len(cues)+1:03}.wav'
        filters = [f'volume={db}dB']
        if fade:
            filters.extend(['afade=t=in:d=0.012',f'afade=t=out:st={length-fade}:d={fade}'])
        ffmpeg('-ss',start,'-i',path,'-t',length,'-vn','-af',','.join(filters),
               '-ac',2,'-ar',48000,'-c:a','pcm_s16le',wav)
        return wav

    for index,shot in enumerate(draft['shots'],1):
        source = assets[shot['asset']]['path']
        clip = sources/f'Shot-{index:03}.mp4'
        length = shot['frames']/fps
        anchor = float(shot.get('x',50))/100
        framing = (f'fps={fps},scale={width}:{height}:force_original_aspect_ratio=increase:force_divisible_by=2,'
                   f'crop={width}:{height}:(iw-ow)*{anchor}:(ih-oh)/2,setsar=1,'
                   f'tpad=stop_mode=clone:stop_duration={1/fps}')
        with gpu_lock(root) if device == 'cuda' else nullcontext():
            ffmpeg('-ss',shot['in'],'-i',source,'-map','0:v:0','-vf',framing,'-frames:v',shot['frames'],
                   '-an',*encoder,'-pix_fmt','yuv420p',clip)
        info = probe(clip,allow_silent=True)
        media[info.id] = info
        clips.append(Cut(info.id,0,shot['frames'],index-1))
        if draft.get('original_audio'):
            voice = audio_layer(source,shot['in'],length)
            cues.append({'path':str(voice),'start':cursor/fps,'length':length,'category':'Narration'})
        cursor += shot['frames']
    for cue in draft['audio']:
        source = assets[cue['asset']]
        fade = min(cue.get('fade_out',.12),cue['length']/3)
        wav = audio_layer(source['path'],cue['in'],cue['length'],cue['db'],fade)
        cues.append({'path':str(wav),'start':cue['at'],'length':cue['length'],'category':source['name']})
    timeline = folder/'timeline.xml'
    export_xml(timeline,clips,media)
    if cues:
        export_sound_xml(timeline,Fraction(fps),{'effects':cues},timeline,suffix='')
    tree = ET.parse(timeline)
    tree.find('sequence/name').text = draft['title']
    for node,shot in zip(tree.findall('sequence/media/video/track/clipitem'),draft['shots']):
        node.find('name').text = str(shot['label'])[:100]
    tree.write(timeline,encoding='utf-8',xml_declaration=True)
    (folder/'intro-sources.json').write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')

