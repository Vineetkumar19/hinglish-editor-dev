"""Owner-requested non-destructive reference rename with hash receipts."""
from pathlib import Path
import hashlib
import json
import shutil

ROOT=Path(__file__).resolve().parents[1]
FOLDER=Path('D:/Full Drive/Styles/Videos').resolve()

def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    catalog_path=ROOT/'hinglish_captions/reference_catalog.json'
    catalog=json.loads(catalog_path.read_text('utf-8'))
    record_path=ROOT/'docs/caption-reference-rename-2026-10-23.json'
    if record_path.exists():
        print('Reference rename already recorded; no files changed.');return
    operations=[];seen=set()
    for row in catalog['references']:
        if row['number']==3:continue  # Same current source as4; make an independent copy below.
        source=Path(row['source']).resolve();target=FOLDER/f"Caption {row['number']}.mp4"
        if source.parent!=FOLDER or target.parent!=FOLDER:raise ValueError('Reference path leaves the requested directory')
        if not source.is_file() or target.exists():raise ValueError('Source missing or destination already exists: '+str(target))
        actual=digest(source)
        if actual!=row['sha256']:raise ValueError('Reference hash changed: '+str(source))
        operations.append({'old':str(source),'new':str(target),'sha256':actual});seen.add(source)
    previous=FOLDER/'From Klickpin.com- Natural Makeup Looks You Can Try This Weekend-pin-id-35817759534066891.mp4'
    if previous.is_file():operations.append({'old':str(previous),'new':str(FOLDER/'Caption 3 - previous reference.mp4'),'sha256':digest(previous)})
    for op in operations:
        if Path(op['new']).exists():raise ValueError('Destination already exists: '+op['new'])
    if (FOLDER/'Caption 3.mp4').exists():raise ValueError('Caption 3 destination already exists')
    # Write intentions before changing anything; no delete or overwrite is used.
    receipt={'operations':operations,'duplicate':'Caption 3.mp4 is a copy of Caption 4.mp4; owner selected the same reference for both.','completed':False}
    record_path.write_text(json.dumps(receipt,indent=2),'utf-8')
    for op in operations:Path(op['old']).rename(op['new'])
    shutil.copy2(FOLDER/'Caption 4.mp4',FOLDER/'Caption 3.mp4')
    for row in catalog['references']:row['source']=str(FOLDER/f"Caption {row['number']}.mp4")
    catalog_path.write_text(json.dumps(catalog,ensure_ascii=False,indent=2),'utf-8')
    # Update executable references, preserving historical evidence and previous profiles.
    for file in list((ROOT/'hinglish_captions').glob('*reference.json'))+list((ROOT/'tools').glob('*.py')):
        if file.resolve()==Path(__file__).resolve():continue
        before=file.read_text('utf-8');after=before
        for op in operations:
            old=op['old'];new=op['new']
            after=after.replace(old,new).replace(old.replace('\\','/'),new.replace('\\','/')).replace(old.replace('\\','\\\\'),new.replace('\\','\\\\'))
        if file.name=='caption_three_reference.json':after=after.replace('Caption 4.mp4','Caption 3.mp4')
        if before!=after:file.write_text(after,'utf-8')
    styles=[]
    for style,number in [('caption_1',1),('caption_2',2),('caption_3',3),('caption_4',4),('caption_5',5),('kinetic_gold_draft',8),('serif_circle_draft',6)]:
        styles.append({'style':style,'source':str(FOLDER/f'Caption {number}.mp4'),'number':number})
    (ROOT/'hinglish_captions/auto_caption_references.json').write_text(json.dumps({'styles':styles},indent=2),'utf-8')
    for op in operations:
        if digest(Path(op['new']))!=op['sha256']:raise ValueError('Post-rename hash mismatch')
    receipt['completed']=True;record_path.write_text(json.dumps(receipt,indent=2),'utf-8')
    (FOLDER/'Caption reference names.json').write_text(json.dumps(receipt,indent=2),'utf-8')
    print(json.dumps({'renamed':len(operations),'copied':1,'verified_hashes':True,'styles':styles},indent=2))

if __name__=='__main__':main()
