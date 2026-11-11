"""Import a Premiere XML into a separate Resolve project without rendering.

Uses the installed Blackmagic scripting API. No model calls, source edits,
render jobs or app launches. A receipt prevents blind duplicate imports.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
from urllib.parse import unquote, urlsplit
import xml.etree.ElementTree as ET
if __package__:
    from .timing_audit import audit_timing
else:
    from timing_audit import audit_timing


def require(value, message):
    valid = value is not None if isinstance(value, ET.Element) else bool(value)
    if not valid:
        raise RuntimeError(message)
    return value


def write_receipt(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix('.tmp')
    temp.write_text(json.dumps(value, indent=2, ensure_ascii=False), encoding='utf-8')
    temp.replace(path)


def inspect_xml(path):
    data = path.read_bytes()
    root = ET.fromstring(data)
    require(root.tag == 'xmeml', 'Choose a Premiere Final Cut Pro XML file.')
    sequence = require(root.find('sequence'), 'The XML has no top-level sequence.')
    media = {}
    for file in root.iter('file'):
        url = file.findtext('pathurl')
        if not url:
            continue
        parsed = urlsplit(url)
        require(parsed.scheme == 'file', 'The XML references non-local media.')
        name = unquote(parsed.path)
        if parsed.netloc and parsed.netloc.lower() != 'localhost':
            name = '//' + parsed.netloc + name
        elif len(name) > 2 and name[0] == '/' and name[2] == ':':
            name = name[1:]
        media[name] = Path(name).is_file()
    missing = [p for p, exists in media.items() if not exists]
    require(not missing, 'Missing media: ' + ', '.join(missing[:5]))
    require(media, 'The XML contains no source media paths.')
    chars = require(sequence.find('media/video/format/samplecharacteristics'),
                    'The XML has no video format.')
    rate = require(sequence.find('rate'), 'The XML has no frame rate.')
    timebase = int(rate.findtext('timebase'))
    fps = timebase * (1000 / 1001 if rate.findtext('ntsc') == 'TRUE' else 1)
    return {
        'xml_sha256': hashlib.sha256(data).hexdigest(),
        'sequence': sequence.findtext('name') or path.stem,
        'frames': int(sequence.findtext('duration')),
        'fps': fps,
        'width': int(chars.findtext('width')),
        'height': int(chars.findtext('height')),
        'media_paths': list(media),
        'video_entries': len(sequence.findall('media/video/track/clipitem')),
        'audio_entries': len(sequence.findall('media/audio/track/clipitem')),
        'effect_names': sorted({f.findtext('effect/name') or '' for f in root.iter('filter')}),
    }


def snapshot(timeline):
    tracks = {}
    offline = []
    for kind in ('video', 'audio'):
        tracks[kind] = []
        for index in range(1, timeline.GetTrackCount(kind) + 1):
            clips = []
            for item in timeline.GetItemListInTrack(kind, index) or []:
                pool = item.GetMediaPoolItem()
                properties = pool.GetClipProperty() if pool else {}
                path = properties.get('File Path', '')
                if path and not Path(path).is_file():
                    offline.append(path)
                clips.append({'name': item.GetName(), 'start': item.GetStart(),
                              'end': item.GetEnd(), 'source': path,
                              'online_status': properties.get('Online Status')})
            tracks[kind].append({'index': index, 'clips': clips})
    return {'name': timeline.GetName(), 'start': timeline.GetStartFrame(),
            'end': timeline.GetEndFrame(), 'settings': timeline.GetSettings(),
            'tracks': tracks, 'missing_paths': sorted(set(offline))}


def run(xml, project_name, receipt_path, compound=False, *, source_label='Premiere'):
    info = inspect_xml(xml)
    receipt = {'status': 'preflight', 'xml': str(xml), 'project': project_name,
               'preflight': info, 'rendered': False}
    prior = json.loads(receipt_path.read_text('utf-8')) if receipt_path.exists() else None
    if prior:
        require(prior.get('project') == project_name and
                prior.get('preflight', {}).get('xml_sha256') == info['xml_sha256'],
                'This receipt belongs to another source or project. Use a new receipt.')
    from hinglish_app.resolve_adapter import _module
    resolve = require(_module().scriptapp('Resolve'),
                      'Open and activate Resolve, then retry this same handoff.')
    pm = resolve.GetProjectManager()
    exists = project_name in (pm.GetProjectListInCurrentFolder() or [])
    current = pm.GetCurrentProject()
    if current and current.GetName() != project_name:
        folder = current.GetMediaPool().GetRootFolder()
        if current.GetTimelineCount() or folder.GetClipList() or folder.GetSubFolderList():
            require(pm.SaveProject(), 'Resolve could not save the current project before switching.')
    if exists:
        require(prior is not None, 'A project with this name already exists without this receipt.')
        project = current if current and current.GetName() == project_name else require(
            pm.LoadProject(project_name), 'Could not reopen the handoff project.')
    else:
        project = require(pm.CreateProject(project_name), 'Could not create the separate handoff project.')
        write_receipt(receipt_path, receipt)
    try:
        name = info['sequence'] + ' [' + source_label + ' handoff]'
        timelines = [project.GetTimelineByIndex(i) for i in range(1, project.GetTimelineCount() + 1)]
        matches = [t for t in timelines if t.GetName() == name]
        require(len(matches) <= 1, 'More than one matching timeline exists. Inspect Resolve before retrying.')
        if matches:
            timeline = matches[0]
        else:
            require(not timelines, 'A partial import exists. Inspect it instead of blindly repeating the import.')
            fps = {23.976023976023978: '23.976', 29.97002997002997: '29.97',
                   59.94005994005994: '59.94'}.get(info['fps'], str(info['fps']))
            require(project.SetSettings({'timelineFrameRate': fps,
                'timelineResolutionWidth': str(info['width']),
                'timelineResolutionHeight': str(info['height'])}), 'Resolve rejected the timeline format.')
            receipt['status'] = 'importing'
            write_receipt(receipt_path, receipt)
            timeline = require(project.GetMediaPool().ImportTimelineFromFile(str(xml),
                {'timelineName': name, 'importSourceClips': True}), 'Resolve did not confirm the XML import.')
        require(project.SetCurrentTimeline(timeline), 'Could not activate the imported timeline.')
        state = snapshot(timeline)
        require(state['end'] - state['start'] == info['frames'], 'Imported duration differs from the source timeline.')
        require(not state['missing_paths'], 'Some imported media paths are missing.')
        video_count = sum(bool(clip.GetMediaPoolItem())
                          for i in range(1,timeline.GetTrackCount('video')+1)
                          for clip in timeline.GetItemListInTrack('video',i) or [])
        require(video_count == info['video_entries'], 'The imported video clip count differs from the source timeline.')
        require(abs(float(state['settings']['timelineFrameRate']) - info['fps']) < .001,
                'The imported frame rate differs from the source timeline.')
        receipt['timing_audit'] = audit_timing(xml,timeline)
        require(receipt['timing_audit']['status']=='exact_timing_verified',
                'Some media or transition positions differ from the source XML. Inspect the timing audit before grading.')
        receipt.update(status='native_import_verified', imported=state,
                       prior_project_preserved=True,
                       limitation='Structure and source availability verified; visual/audio/effect parity needs native review.')
        require(pm.SaveProject(), 'Resolve did not save the imported project.')
        write_receipt(receipt_path, receipt)
        if compound:
            compound_name = name + ' - complete compound with fades'
            grouped = [t for t in timelines if t.GetName() == compound_name]
            if grouped:
                require(prior and prior.get('status') == 'native_compound_verified',
                        'A compound version already exists without a finished receipt. Inspect it before retrying.')
                grouped_timeline = grouped[0]
            else:
                grouped_timeline = require(timeline.DuplicateTimeline(compound_name), 'Could not preserve a separate compound version.')
                require(project.SetCurrentTimeline(grouped_timeline), 'Could not activate the compound version.')
                # Include transition objects as well as media. Omitting these
                # dropped two audio crossfades in the native verification test.
                items = [item for kind in ('video','audio')
                         for i in range(1, grouped_timeline.GetTrackCount(kind) + 1)
                         for item in grouped_timeline.GetItemListInTrack(kind, i) or []]
                receipt['status'] = 'compounding'
                write_receipt(receipt_path, receipt)
                native_result = grouped_timeline.CreateCompoundClip(items, {'name': info['sequence'] + ' - Grade here',
                        'startTimecode': timeline.GetStartTimecode()})
                # Resolve 21.1.2 can return None after successfully grouping.
                # Verify native postconditions instead of replaying the mutation.
                picture = [item for i in range(1, grouped_timeline.GetTrackCount('video')+1)
                           for item in grouped_timeline.GetItemListInTrack('video',i) or []]
                sound = [item for i in range(1, grouped_timeline.GetTrackCount('audio')+1)
                         for item in grouped_timeline.GetItemListInTrack('audio',i) or []]
                require(len(picture)==1 and picture[0].GetMediaPoolItem() and
                        picture[0].GetMediaPoolItem().GetClipProperty('Type')=='Compound' and
                        len(sound)==(1 if info['audio_entries'] else 0),
                        'The full compound was not verified. Inspect the preserved original; do not blindly repeat.')
                receipt['compound_api_returned_object'] = bool(native_result)
            require(project.SetCurrentTimeline(grouped_timeline), 'Could not select the compound timeline.')
            receipt['compound'] = snapshot(grouped_timeline)
            receipt['compound_scope'] = 'all_picture_sound_and_transition_items'
            receipt['compound_version'] = 3
            require(receipt['compound']['end'] - receipt['compound']['start'] == info['frames'],
                    'The compound duration differs from Premiere.')
            require(pm.SaveProject(), 'Could not save the compound timeline.')
            receipt['status'] = 'native_compound_verified'
            write_receipt(receipt_path, receipt)
        resolve.OpenPage('edit')
        return receipt
    except Exception as error:
        receipt.update(status='needs_review', error=str(error))
        write_receipt(receipt_path, receipt)
        raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--xml', type=Path, required=True)
    parser.add_argument('--project', required=True)
    parser.add_argument('--receipt', type=Path, required=True)
    parser.add_argument('--compound', action='store_true')
    args = parser.parse_args()
    try:
        result = run(args.xml.resolve(), args.project, args.receipt.resolve(), args.compound)
        print(json.dumps({key: result[key] for key in ('status', 'project', 'rendered')}))
    except Exception as error:
        print(json.dumps({'status': 'needs_review', 'error': str(error)}))
        sys.exit(1)
