"""Native Premiere handoff for a single talking-head source plus editable B-roll.

Complex pre-edited XML timelines retain their existing XML handoff. This adapter
never flattens a multi-source edit into a misleading single source project.
"""
import gzip
from pathlib import Path
import xml.etree.ElementTree as ET


def _set(node,path,value):
    for tag in path.split('/'):
        child=node.find(tag)
        if child is None:child=ET.SubElement(node,tag)
        node=child
    node.text=str(value)


def export(project_file, destination,include_options=True, *, visual_project=None):
    import json
    from .timeline import parse_xmeml
    from hinglish_app.premiere_captions import export as base_export, TICKS
    from hinglish_app.premiere_decorations import attach
    project_file, destination = Path(project_file), Path(destination)
    project = visual_project if visual_project is not None else json.loads(project_file.read_text('utf-8'))
    timeline = parse_xmeml(project['timeline']['xml_path'])
    if Path(timeline.xml_path).name not in (('source-timeline.xml','AUDIO_BLACK.xml') if visual_project is not None else ('source-timeline.xml',)):
        return None
    if len(timeline.clips)!=1 or abs(timeline.clips[0].start)>.001 or abs(timeline.clips[0].source_in)>.001:
        return None
    if any(s.get('scale',100)!=100 for s in project['slots']):
        return None  # the XML keeps custom Motion scaling; never drop it silently
    # Do not discard existing caption/graphics tracks in an imported XML.
    source_tree=ET.parse(timeline.xml_path)
    if len(source_tree.findall('.//sequence/media/video/track'))!=1:
        return None
    source=timeline.clips[0].path
    from .library import probe_video
    if Path(source).is_file():
        source_info=probe_video(source)
        if not source_info or tuple(source_info[1:])!=(timeline.width,timeline.height):return None
    spec={'style':'caption_1','width':timeline.width,'height':timeline.height,
          'media':{'path':source,'duration':timeline.duration,'fps':str(timeline.fps),
                   'width':timeline.width,'height':timeline.height},'cues':[]}
    destination.parent.mkdir(parents=True,exist_ok=True)
    staging=destination.with_name(destination.stem+'-building.prproj')
    staging.unlink(missing_ok=True)
    try:
        base_export(Path(__file__).resolve().parents[1]/'hinglish_app/templates/premiere-caption-1.xml',
                    spec,staging,scene_rows=[])
        tree=ET.fromstring(gzip.decompress(staging.read_bytes()))
        base_ids={n.get('ObjectID'):n for n in tree if n.get('ObjectID')}
        _set(base_ids['162'],'Duration',round(timeline.duration*TICKS))
        _set(base_ids['43'],'Clip/OutPoint',round(timeline.duration*TICKS))
        seq=next(n for n in tree if n.tag=='Sequence' and n.findtext('Name','').endswith('Editable Words'))
        _set(seq,'Name',timeline.name+(' - Editable Smart Visuals' if visual_project is not None else ' - Editable B-roll'))
        group=next(n for n in tree if n.get('ObjectID')=='164').find('TrackGroup/Tracks')
        combined=[];imported={}
        for slot in sorted(project['slots'],key=lambda s:s['start']):
            if not slot.get('clip'):continue
            before={id(n) for n in tree}
            attach(tree,spec,(project_file.parent/slot['clip']).resolve(),TICKS)
            new=[n for n in tree if id(n) not in before]
            imported[str((project_file.parent/slot['clip']).resolve())]=next(n for n in new if n.tag=='MasterClip').get('ObjectUID')
            item=next(n for n in new if n.tag=='VideoClipTrackItem')
            track_item=item.find('ClipTrackItem/TrackItem')
            _set(track_item,'Start',round(slot['start']*TICKS))
            _set(track_item,'End',round(slot['end']*TICKS))
            clip_ref=item.find('ClipTrackItem/SubClip').get('ObjectRef')
            sub=next(n for n in new if n.get('ObjectID')==clip_ref)
            clip=next(n for n in new if n.get('ObjectID')==sub.find('Clip').get('ObjectRef'))
            _set(clip,'Clip/InPoint',round(slot.get('source_in',0)*TICKS))
            _set(clip,'Clip/OutPoint',round((slot.get('source_in',0)+slot['end']-slot['start'])*TICKS))
            title=(slot.get('chosen') or {}).get('title','B-roll')[:100]
            _set(sub,'Name',title)
            for n in new:
                if n.tag=='VideoStream':_set(n,'Duration',round(slot.get('source_duration',slot['end']-slot['start'])*TICKS))
                if n.tag=='VideoClip' and n is not clip:
                    _set(n,'Clip/InPoint',0)
                    _set(n,'Clip/OutPoint',round(slot.get('source_duration',slot['end']-slot['start'])*TICKS))
                if n.tag=='ClipLoggingInfo':_set(n,'MediaOutPoint',round(slot.get('source_duration',slot['end']-slot['start'])*TICKS))
                if n.tag=='MasterClip':_set(n,'Name',title)
                if n.tag=='Media':_set(n,'Title',title)
            combined.append(item.get('ObjectID'))
        # Human-choice alternatives remain ordinary independent source clips
        # in the Project panel, even when they were not selected for V2.
        if project.get('review_options') and include_options:
            import copy,uuid
            from .options import rows
            root_bin=next(n for n in tree if n.tag=='RootProjectItem')
            bin_items=root_bin.find('ProjectItemContainer/Items')
            prototype=next(n for n in tree if n.tag=='ClipProjectItem' and n.findtext('ProjectItem/Name')=='Storylens source')
            for option in rows(project,project_file.parent):
                path=option['path'];master_uid=imported.get(path)
                if master_uid is None:
                    before={id(n) for n in tree};attach(tree,spec,Path(path),TICKS)
                    new=[n for n in tree if id(n) not in before]
                    master=next(n for n in new if n.tag=='MasterClip');master_uid=master.get('ObjectUID')
                    imported[path]=master_uid
                    for node in new:
                        if node.tag=='VideoStream':_set(node,'Duration',round(option['source_duration']*TICKS))
                        if node.tag=='VideoClip':
                            _set(node,'Clip/InPoint',0);_set(node,'Clip/OutPoint',round(option['source_duration']*TICKS))
                        if node.tag in ('MasterClip','Media'):
                            _set(node,'Name' if node.tag=='MasterClip' else 'Title',option['name'])
                item=copy.deepcopy(prototype);uid=str(uuid.uuid4());item.set('ObjectUID',uid)
                _set(item,'ProjectItem/Name',option['name']);item.find('MasterClip').set('ObjectURef',master_uid)
                tree.append(item);ET.SubElement(bin_items,'Item',Index=str(len(bin_items)),ObjectURef=uid)
        # All independently trimmable cutaways share V2, rather than one track per shot.
        uids={n.get('ObjectUID'):n for n in tree if n.get('ObjectUID')}
        extras=list(group)[1:]
        if extras and visual_project is None:
            lane=uids[extras[0].get('ObjectURef')]
            items=lane.find('ClipTrack/ClipItems/TrackItems');items.clear();items.set('Version','1')
            for i,ref in enumerate(combined):ET.SubElement(items,'TrackItem',Index=str(i),ObjectRef=ref)
            for entry in extras[1:]:
                group.remove(entry);tree.remove(uids[entry.get('ObjectURef')])
            extras[0].set('Index','1')
            for key,value in [('ClipTrack/Track/ID',2),('ClipTrack/Track/Index',1),
                              ('ClipTrack/ClipItems/Index',1),('ClipTrack/TransitionItems/Index',1)]:_set(lane,key,value)
        destination.write_bytes(gzip.compress(ET.tostring(tree,encoding='utf-8',xml_declaration=True)))
        return str(destination.resolve())
    finally:
        staging.unlink(missing_ok=True)
