"""Compare actual native Resolve media/transition positions with captured XML."""
from collections import Counter
from pathlib import Path
from urllib.parse import unquote,urlsplit
import xml.etree.ElementTree as ET


def normalized(path):
    return str(path).replace('\\','/').lower().removeprefix('/')


def audit_timing(xml, timeline):
    root=ET.parse(xml).getroot()
    files={f.get('id'):f.findtext('pathurl') for f in root.iter('file') if f.findtext('pathurl')}
    expected=[];actual=[];expected_transitions=[];actual_transitions=[]
    for kind in ('video','audio'):
        for lane,track in enumerate(root.findall('sequence/media/'+kind+'/track'),1):
            children=list(track)
            for index,clip in enumerate(children):
                if clip.tag=='transitionitem':
                    expected_transitions.append((kind,lane,int(clip.findtext('start')),int(clip.findtext('end'))))
                if clip.tag!='clipitem':continue
                file=clip.find('file')
                if file is None:raise ValueError('Nested/generated picture needs an appearance conversion.')
                url=file.findtext('pathurl') or files.get(file.get('id'))
                if not url:raise ValueError('An XML clip has no local media path.')
                start,end=int(clip.findtext('start')),int(clip.findtext('end'))
                # FCP 7 uses -1 on the clip body where a separate transition
                # item supplies the boundary. Resolve exposes it separately too.
                if start==-1:start=int(children[index-1].findtext('end'))
                if end==-1:end=int(children[index+1].findtext('start'))
                expected.append((kind,lane,normalized(unquote(urlsplit(url).path)),start,end))
        for lane in range(1,timeline.GetTrackCount(kind)+1):
            for clip in timeline.GetItemListInTrack(kind,lane) or []:
                pool=clip.GetMediaPoolItem()
                start,end=clip.GetStart()-timeline.GetStartFrame(),clip.GetEnd()-timeline.GetStartFrame()
                if pool:
                    actual.append((kind,lane,normalized(pool.GetClipProperty('File Path')),start,end))
                else:actual_transitions.append((kind,lane,start,end))
    wanted,got=Counter(expected),Counter(actual)
    tw,tg=Counter(expected_transitions),Counter(actual_transitions)
    return {'status':'exact_timing_verified' if wanted==got and tw==tg else 'needs_review',
            'media_source_track_start_end_match':wanted==got,'transition_track_start_end_match':tw==tg,
            'expected_media_entries':len(expected),'actual_media_entries':len(actual),
            'expected_transition_entries':len(expected_transitions),'actual_transition_entries':len(actual_transitions),
            'missing_media':list((wanted-got).elements()),'extra_media':list((got-wanted).elements()),
            'missing_transitions':list((tw-tg).elements()),'extra_transitions':list((tg-tw).elements()),
            'scope':'Media paths, track numbers and timeline frame positions; not gain/processing, source trim or listening/visual parity.'}
