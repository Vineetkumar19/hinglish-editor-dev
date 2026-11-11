"""Keep Caption 3's animated frame separate from its native editable words."""
import copy
from fractions import Fraction
from pathlib import Path
import uuid
import xml.etree.ElementTree as ET


def render(project, destination):
    from hinglish_cut.compute_policy import heavy_device
    device=heavy_device(Path(__file__).resolve().parents[1])
    style=project.get('style','caption_3')
    if style=='kinetic_gold_draft':
        from hinglish_captions.kinetic_gold import decorations_only
    elif style=='serif_circle_draft':
        from hinglish_captions.serif_circle import decorations_only
    elif style=='caption_2':
        from hinglish_captions.caption_two import decorations_only
    else:
        from hinglish_captions.caption_three import decorations_only
    from hinglish_captions.project import cues_from_data
    from hinglish_captions.renderer import render_overlay
    from hinglish_captions.styles import template
    destination=Path(destination)
    path=destination.with_name(destination.stem+'-FRAMES.mov')
    with decorations_only():
        render_overlay(path,cues_from_data(project['cues']),project['width'],project['height'],
            float(project['media']['duration']),fps=project['media'].get('fps',30),
            style_name=style,font_id=project.get('font','template'),
            position=project.get('position',template(style)['default_position']),
            size_scale=project.get('size',1),cue_layouts=project.get('cue_layouts'),
            word_colors=project.get('word_colors'),
            word_visibility=project.get('word_visibility','phrase'),device=device)
    return path.resolve()


def attach(tree, project, path, ticks):
    """Clone the template's ordinary media clip as one independent alpha layer."""
    ids={n.get('ObjectID'):n for n in tree if n.get('ObjectID')}
    uids={n.get('ObjectUID'):n for n in tree if n.get('ObjectUID')}
    selected=['238','245','246','372','65','43','162','64','40']
    next_id=max(map(int,ids))+1
    mapping={old:str(next_id+i) for i,old in enumerate(selected)}
    media_uid=ids['65'].find('MediaSource/Media').get('ObjectURef')
    master_uid=ids['246'].find('MasterClip').get('ObjectURef')
    uidmap={old:str(uuid.uuid4()) for old in (media_uid,master_uid)}
    clones={}
    for old in selected+[media_uid,master_uid]:
        node=copy.deepcopy(ids[old] if old in ids else uids[old])
        if old in mapping:node.set('ObjectID',mapping[old])
        else:node.set('ObjectUID',uidmap[old])
        for element in node.iter():
            if element.get('ObjectRef') in mapping:element.set('ObjectRef',mapping[element.get('ObjectRef')])
            if element.get('ObjectURef') in uidmap:element.set('ObjectURef',uidmap[element.get('ObjectURef')])
            if element.tag in ('ClipID','FileKey'):element.text=str(uuid.uuid4())
            if element.tag in ('FilePath','ActualMediaFilePath','RelativePath'):element.text=str(path)
        tree.append(node);clones[old]=node
    master=clones[master_uid]
    for name in ('AudioComponentChains','AudioClipChannelGroups'):
        child=master.find(name)
        if child is not None:master.remove(child)
    clips=master.find('Clips')
    for child in list(clips):
        if child.get('ObjectRef')!=mapping['43']:clips.remove(child)
    label='Kinetic Gold shadows and brush strokes' if project.get('style')=='kinetic_gold_draft' else 'Caption 3 reference text annotations'
    if project.get('style')=='serif_circle_draft':label='Serif Circle animated annotations'
    if project.get('style')=='caption_2':label='Caption 2 glow, shadows and cross-outs'
    master.find('Name').text=label
    master.find('Node/ID').text=str(next_id+len(selected))
    media=clones[media_uid]
    for name in ('AudioStream','ConformedAudioRate'):
        child=media.find(name)
        if child is not None:media.remove(child)
    media.find('Title').text=label
    stream=clones['162'];stream.find('IgnoreAlpha').text='false'
    for name in ('CodecType','AlphaType','OriginalColorSpace'):
        child=stream.find(name)
        if child is not None:stream.remove(child)
    width,height=project['width'],project['height']
    stream.find('FrameRect').text=f'0,0,{width},{height}'
    stream.find('Duration').text=str(round(float(project['media']['duration'])*ticks))
    stream.find('FrameRate').text=str(round(ticks/float(Fraction(str(project['media'].get('fps',30))))))
    clones['246'].find('Name').text=label+' (editable words above)'
    clones['238'].find('ClipTrackItem/LinkRefCount').text='0'
    clones['238'].find('FrameRect').text=f'0,0,{width},{height}'
    tracks=ids['164'].find('TrackGroup/Tracks')
    # Decorations sit over the footage but under the editable word graphics.
    # This also keeps filled label backgrounds from covering their own text.
    for entry in tracks:
        previous=int(entry.get('Index'))
        if previous==0:continue
        entry.set('Index',str(previous+1))
        word_track=next(n for n in tree if n.get('ObjectUID')==entry.get('ObjectURef'))
        for name,value in [('ClipTrack/Track/ID',previous+3),('ClipTrack/Track/Index',previous+1),
                           ('ClipTrack/ClipItems/Index',previous+1),('ClipTrack/TransitionItems/Index',previous+1)]:
            child=word_track.find(name)
            if child is not None:child.text=str(value)
    index=1
    track=copy.deepcopy(uids[tracks[0].get('ObjectURef')]);uid=str(uuid.uuid4())
    track.set('ObjectUID',uid)
    for name,value in [('ClipTrack/Track/ID',index+1),('ClipTrack/Track/Index',index),
                       ('ClipTrack/ClipItems/Index',index),('ClipTrack/TransitionItems/Index',index)]:
        child=track.find(name)
        if child is not None:child.text=str(value)
    items=track.find('ClipTrack/ClipItems/TrackItems');items.clear();items.set('Version','1')
    ET.SubElement(items,'TrackItem',Index='0',ObjectRef=mapping['238'])
    tree.append(track);tracks.insert(1,ET.Element('Track',Index=str(index),ObjectURef=uid))
    ids['164'].find('TrackGroup/NextTrackID').text=str(len(tracks)+1)
