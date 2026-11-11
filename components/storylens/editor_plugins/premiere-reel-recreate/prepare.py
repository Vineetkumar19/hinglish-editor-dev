"""Prepare native Premiere inputs from a saved, measured Reel Recreate plan."""
from pathlib import Path
import sys,json,copy,hashlib,shutil,gzip,uuid,re
import xml.etree.ElementTree as ET
from PIL import Image

ROOT=Path(r'D:\Full Drive\remove silence')
SOURCE=Path(sys.argv[1]) if len(sys.argv)>1 else Path(r'D:\Workflow_Automation\reel_trial\reel-plan.json')
OUT=Path(sys.argv[2]) if len(sys.argv)>2 else Path(__file__).parent
OUT.mkdir(parents=True,exist_ok=True);sys.path.insert(0,str(ROOT))
plan=json.loads(SOURCE.read_text('utf-8-sig'))
reel_id=hashlib.sha256(Path(plan['source']).read_bytes()).hexdigest()[:32]
revision=plan.get('revision_id','')
plan['id']=revision if re.fullmatch('[a-f0-9]{32}',revision) else reel_id
suffix=' - '+plan['id'][:8] if revision else ''
main_name='REEL1 - STAGE 1 - PREMIERE'+suffix
caption_name='REEL1_LYRIC_SOURCE'+suffix
project=json.loads(Path(plan['caption_project']).read_text('utf-8-sig'))
if not plan['sections'] or not plan['caption']['words']:
    raise ValueError('Choose the saved measured reel preparation, with captions and beat sections.')
rows=copy.deepcopy(plan['caption']['words'])
fonts=OUT/'fonts';fonts.mkdir(exist_ok=True)
font_hashes=[]
for row in rows:
    original=Path(row['font_path']);target=fonts/original.name
    digest=hashlib.sha256(original.read_bytes()).hexdigest()
    if not target.exists():shutil.copy2(original,target)
    if hashlib.sha256(target.read_bytes()).hexdigest()!=digest:raise ValueError('A saved font changed; existing files kept.')
    row['font_path']=str(target)
    if not any(r['sha256']==digest for r in font_hashes):font_hashes.append({'source':str(original),'copy':str(target),'sha256':digest})

from hinglish_app.premiere_captions import export,TICKS
template=ROOT/'hinglish_app/templates/premiere-caption-1.xml'
seed=OUT/'reel1-caption-source.prproj'
main=OUT/'reel1-premiere-stage-one.prproj'
native=copy.deepcopy(project)
native.update(omit_source_video=True,word_visibility='spoken')
# scene_rows already contain phrase-held Caption 3 geometry. The visibility flag
# skips an unrelated decoration-movie pass; it does not retime these native rows.
if not seed.exists():
    receipt=export(template,native,seed,scene_rows=rows)
    print(json.dumps(receipt),flush=True)
    tree=ET.fromstring(gzip.decompress(seed.read_bytes()))
    seq=next(n for n in tree if n.tag=='Sequence' and n.findtext('Name','').endswith('Editable Words'))
    seq.find('Name').text=caption_name
    for track in tree:
        if track.tag=='AudioClipTrack':
            items=track.find('ClipTrack/ClipItems/TrackItems')
            if items is not None:items.clear()
    seed.write_bytes(gzip.compress(ET.tostring(tree,encoding='utf-8',xml_declaration=True)))
if not main.exists():
    blank=copy.deepcopy(native);blank['style']='caption_1'
    export(template,blank,main,scene_rows=[])
    tree=ET.fromstring(gzip.decompress(main.read_bytes()))
    ids={n.get('ObjectID'):n for n in tree if n.get('ObjectID')}
    seq=next(n for n in tree if n.tag=='Sequence' and n.findtext('Name','').endswith('Editable Words'))
    seq.find('Name').text=main_name
    group=ids['164'].find('TrackGroup/Tracks')
    prototype=next(n for n in tree if n.get('ObjectUID')==group[0].get('ObjectURef'))
    for index in range(1,5):
        track=copy.deepcopy(prototype);uid=str(uuid.uuid4());track.set('ObjectUID',uid)
        for path,value in [('ClipTrack/Track/ID',index+1),('ClipTrack/Track/Index',index),
                           ('ClipTrack/ClipItems/Index',index),('ClipTrack/TransitionItems/Index',index)]:
            node=track.find(path)
            if node is not None:node.text=str(value)
        tree.append(track);ET.SubElement(group,'Track',Index=str(index),ObjectURef=uid)
    ids['164'].find('TrackGroup/NextTrackID').text='6'
    main.write_bytes(gzip.compress(ET.tostring(tree,encoding='utf-8',xml_declaration=True)))
placeholder=OUT/'EMPTY-FOOTAGE-PLACEHOLDER.png'
if not placeholder.exists():Image.new('RGBA',(plan['width'],plan['height']),(0,0,0,0)).save(placeholder)
bank_path=Path(plan.get('sound_bank') or SOURCE.parent/'sound-bank.json')
sound_bank=json.loads(bank_path.read_text('utf-8')) if bank_path.is_file() else {'sounds':[]}
bundle={'version':1,'id':plan['id'],'source':plan['source'],'source_sha256':plan['reference_identity']['sha256'],
        'project':str(main),'caption_source_project':str(seed),'caption_sequence':caption_name,
        'sequence':main_name,'name_suffix':suffix,'reel_id':reel_id,'soundtrack':plan['audio'],'placeholder':str(placeholder),
        'duration':plan['duration'],'width':plan['width'],'height':plan['height'],'fps':plan['fps'],
        'beats':plan['beats'],'sections':plan['sections'],'cues':plan['cues'],'sounds':sound_bank['sounds'],
        'receipt_dir':str(OUT),'caption_style':'Caption 3','stage_two':'paused',
        'caption_snapshot':plan['caption'],'cues_snapshot':plan['cues'],
        'font_hashes':font_hashes,'lyric_timing':'Model-timed; uncertain sung passages require review',
        'slot_note':'Transparent replacement placeholder inside each footage nest; no stage-two footage selected.'}
for key in ('source','project','caption_source_project','soundtrack','placeholder'):
    if not Path(bundle[key]).is_file():raise FileNotFoundError(bundle[key])
(OUT/'premiere-bundle.json').write_text(json.dumps(bundle,indent=2),encoding='utf-8')
(OUT/'native-rows.json').write_text(json.dumps(rows,indent=2),encoding='utf-8')
print(json.dumps({'project':str(main),'caption_source':str(seed),'beats':len(plan['beats']),
                  'slots':len(plan['sections']),'caption_groups':len(plan['cues']),'native_words':len(rows)}),flush=True)
