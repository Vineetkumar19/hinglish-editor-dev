"""Prepare a separate CapCut 9.6 draft from local timeline XML.

Uses Storylens's existing draft builder. All project/media work stays in the
chosen A: folder. Registration appends only this new draft to CapCut's index.
This is file interchange, not live Dynamic Link or an effect translator.
"""
import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path
import shutil
import sys
import time
from urllib.parse import unquote, urlsplit
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from hinglish_app import capcut_adapter


def parse_xml(path):
    root = ET.parse(path).getroot()
    seq = root.find('sequence')
    if seq is None:
        raise ValueError('Choose FCP 7 timeline XML exported by Premiere or Resolve.')
    rate = seq.find('rate')
    fps = int(rate.findtext('timebase')) * (1000 / 1001 if rate.findtext('ntsc') == 'TRUE' else 1)
    chars = seq.find('media/video/format/samplecharacteristics')
    files = {f.get('id'): f.findtext('pathurl') for f in root.iter('file') if f.findtext('pathurl')}
    spec = {'fps': fps, 'width': int(chars.findtext('width')), 'height': int(chars.findtext('height')),
            'duration': round(int(seq.findtext('duration')) / fps * 1e6),
            'clips': [], 'audio_layers': [], 'mute_source_audio': True, 'sound': True}
    issues, video_tracks, audio_seen = [], [], {}
    for kind in ('video', 'audio'):
        for lane, track in enumerate(seq.findall('media/' + kind + '/track'), 1):
            nodes = list(track)
            for n, clip in enumerate(nodes):
                if clip.tag == 'transitionitem':
                    issues.append({'kind': 'transition_not_translated', 'track_type': kind,
                                   'track': lane, 'name': clip.findtext('effect/name'),
                                   'start_frame': clip.findtext('start'), 'end_frame': clip.findtext('end')})
                if clip.tag != 'clipitem':
                    continue
                f = clip.find('file')
                if f is None:
                    raise ValueError('Nested/generated clips require an appearance conversion before CapCut.')
                raw = unquote(urlsplit(f.findtext('pathurl') or files[f.get('id')]).path)
                if raw.startswith('/') and len(raw) > 2 and raw[2] == ':':
                    raw = raw[1:]
                media = Path(raw)
                if not media.is_file():
                    raise ValueError('Missing source: ' + str(media))
                start, end = int(clip.findtext('start')), int(clip.findtext('end'))
                if start == -1:
                    start = int(nodes[n-1].findtext('start'))
                if end == -1:
                    end = int(nodes[n+1].findtext('end'))
                cr = clip.find('rate')
                source_fps = int(cr.findtext('timebase')) * (1000/1001 if cr.findtext('ntsc') == 'TRUE' else 1)
                source_in = round(int(clip.findtext('in')) / source_fps * 1e6)
                row = {'path': str(media), 'name': clip.findtext('name') or media.stem,
                       'source_in': source_in, 'start': round(start/fps*1e6),
                       'duration': round((end-start)/fps*1e6), 'lane': str(lane)}
                gain = 1.
                for effect in clip.findall('filter/effect'):
                    eid = (effect.findtext('effectid') or '').lower()
                    if kind == 'audio' and eid == 'audiolevels':
                        param = effect.find('parameter')
                        if param is not None and param.find('keyframe') is None:
                            gain = float(param.findtext('value') or 1)
                        else:
                            issues.append({'kind': 'audio_keyframes_not_translated', 'clip': row['name']})
                    elif kind == 'audio' and eid == 'audiopan' and all(
                            float(p.findtext('value') or 0)==0 and p.find('keyframe') is None
                            for p in effect.findall('parameter')):
                        pass
                    else:
                        issues.append({'kind': 'effect_not_translated', 'clip': row['name'], 'name': effect.findtext('name')})
                if kind == 'video':
                    spec['clips'].append(row); video_tracks.append(lane)
                else:
                    # Premiere exports stereo as two matching channel entries.
                    # CapCut's local audio material preserves the stereo source.
                    key = (str(media).lower(), source_in, row['start'], row['duration'],gain)
                    channel = int(clip.findtext('sourcetrack/trackindex') or 1)
                    links=tuple(sorted(v.text for v in clip.findall('link/linkclipref') if v.text))
                    # Resolve 21 exports paired mono lanes with trackindex=1
                    # on both entries. Their reciprocal link group identifies
                    # the original stereo pair; do not import it twice in CapCut.
                    if key in audio_seen and (channel == 2 or (len(links)==2 and links==audio_seen[key])):
                        continue
                    audio_seen[key]=links
                    row['gain'] = gain
                    spec['audio_layers'].append(row)
    if not spec['clips']:
        raise ValueError('No local picture clips are available.')
    return spec, video_tracks, issues


def build(xml, folder, title, diagnostic=False, register=False, *, embedded_audio=False):
    folder = folder.resolve()
    receipt = folder / 'capcut-receipt.json'
    digest = hashlib.sha256(xml.read_bytes()).hexdigest()
    if receipt.exists():
        saved = json.loads(receipt.read_text('utf8'))
        if saved['xml_sha256'] != digest:
            raise ValueError('Use a new folder for this changed timeline.')
        if register and not saved['registered']:
            register_draft(folder)
            return json.loads(receipt.read_text('utf8'))
        return saved
    spec, lanes, issues = parse_xml(xml)
    if embedded_audio:
        # A wrapped movie already carries its complete mix. CapCut treats a
        # movie copied into a separate audio-material slot as missing media.
        if len(spec['clips']) != 1 or any(
                row['path'] != spec['clips'][0]['path'] for row in spec['audio_layers']):
            raise ValueError('Use embedded audio only for a single rendered video.')
        spec['audio_layers'] = []
        spec['mute_source_audio'] = False
    folder.mkdir(parents=True, exist_ok=True)
    (folder/'appearance-gaps.json').write_text(json.dumps(issues,indent=2),encoding='utf8')
    if issues and not diagnostic:
        raise ValueError('Appearance conversion is needed; see appearance-gaps.json. Diagnostic mode imports the editable media/timing only.')
    build_root = folder/'builder'
    build_root.mkdir(exist_ok=True)
    home = folder/'CapCut'
    (build_root/'config.editors.local.json').write_text(json.dumps({'capcut_home':str(home)}),encoding='utf8')
    saved = capcut_adapter.create_project(build_root, spec['clips'][0]['path'], title, digest[:12], timeline=spec)
    draft = Path(saved['folder'])
    content = json.loads((draft/'draft_content.json').read_text('utf8'))
    video = content['tracks'].pop(0)
    groups = defaultdict(list)
    for segment, lane in zip(video['segments'], lanes):
        segment['track_render_index'] = lane-1
        groups[lane].append(segment)
    import uuid
    content['tracks'] = [dict(video,id=str(uuid.uuid4()).upper(),name=f'Imported video {lane}',segments=segments)
                         for lane,segments in sorted(groups.items())] + content['tracks']
    audio_by_lane = {t['name'].removeprefix('Sound Design '):t for t in content['tracks'] if t['type']=='audio'}
    offsets = defaultdict(int)
    for row in spec['audio_layers']:
        segment = audio_by_lane[row['lane']]['segments'][offsets[row['lane']]]
        segment['volume'] = row['gain']
        offsets[row['lane']] += 1
    for target in [draft/'draft_content.json', *list((draft/'Timelines').glob('*/draft_content.json'))]:
        capcut_adapter._write(target,content)
    result = {'status':'diagnostic_draft_prepared' if issues else 'draft_prepared',
              'xml_sha256':digest,'xml':str(xml.resolve()),'title':title,'folder':str(draft),
              'video_clips':len(spec['clips']),'audio_clips':len(spec['audio_layers']),
              'appearance_gaps':issues,'rendered':False,'registered':False,
              'embedded_audio':embedded_audio,
              'live_application_verified':False,'notice':'Original sources copied; timing/gain editable. Listed appearance gaps are not preserved.'}
    capcut_adapter._write(receipt,result)
    if register:
        return register_draft(folder)
    return result


def register_draft(folder):
    import psutil
    if any((p.info.get('name') or '').lower() == 'capcut.exe' for p in psutil.process_iter(['name'])):
        raise ValueError('Save and close CapCut before adding this draft. The prepared files are kept.')
    receipt = folder / 'capcut-receipt.json'
    result = json.loads(receipt.read_text('utf8'))
    draft = Path(result['folder']).resolve()
    if not draft.is_relative_to(folder.resolve()) or not (draft/'draft_content.json').is_file():
        raise ValueError('The prepared CapCut draft has moved. Prepare the transfer again.')
    index = capcut_adapter.settings(ROOT)[1]/'root_meta_info.json'
    with capcut_adapter._LOCK:
        existing = json.loads(index.read_text('utf8')) if index.exists() else {'all_draft_store':[],'draft_ids':[],'root_path':str(index.parent)}
        meta = json.loads((draft/'draft_meta_info.json').read_text('utf8'))
        if not any(v.get('draft_id')==meta['draft_id'] for v in existing['all_draft_store']):
            if index.exists():shutil.copy2(index,folder/'capcut-index-before.json')
            entry={k:v for k,v in meta.items() if k!='draft_materials'}
            entry.update(draft_json_file=(draft/'draft_content.json').as_posix(),
                         draft_cover='',streaming_edit_draft_ready=True)
            existing['all_draft_store'].insert(0,entry)
            index.parent.mkdir(parents=True,exist_ok=True)
            capcut_adapter._write(index,existing)
        result['registered']=True
        capcut_adapter._write(receipt,result)
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--xml',type=Path,required=True); p.add_argument('--folder',type=Path,required=True)
    p.add_argument('--title',required=True); p.add_argument('--diagnostic',action='store_true')
    p.add_argument('--register',action='store_true')
    args=p.parse_args()
    try:
        result=build(args.xml,args.folder,args.title,args.diagnostic,args.register)
        print(json.dumps({k:result[k] for k in ['status','title','video_clips','audio_clips','registered']}))
    except Exception as e:
        print(json.dumps({'status':'needs_review','error':str(e)}));sys.exit(1)
