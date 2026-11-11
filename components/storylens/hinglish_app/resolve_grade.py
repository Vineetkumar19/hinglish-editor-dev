"""Apply either saved native SDR grade on a duplicate Resolve timeline."""
from pathlib import Path
import hashlib
import json
import math
from threading import Lock
import time

NODE_NAMES=['CAM-DWG','BAL/EXP','CONTRAST','SAT','TEMP','HDR','WARPER','CURVES',
            'Parallel mixer','TRIM','PW1','PW2','PW3','Parallel mixer','Texture',
            'SPARE','DWG-709','CINEON (off)','KODAK2383 (off)']
TEMPLATE_SHA256='2fa3aa537c179f9d89c4a477e3aa261b15527fea6201fccc4b8116985743c9a7'
REALFILM_LABEL='RealFilmV2_Rec709'
LUT_PREVIEW='Storylens LUT Preview'
_grade_lock=Lock()


def template():
    file=Path(__file__).resolve().parents[1]/'library/resolve-node-grade/node-structure-sdr.drx'
    if not file.is_file() or hashlib.sha256(file.read_bytes()).hexdigest()!=TEMPLATE_SHA256:
        raise ValueError('The approved Resolve node template is unavailable or changed. Restore its verified DRX before applying it.')
    return file


def _realfilm_template(project, folder):
    gallery=project.GetGallery()
    matches=[(album, still) for album in gallery.GetGalleryPowerGradeAlbums() or []
             for still in album.GetStills() or [] if album.GetLabel(still)==REALFILM_LABEL]
    if len(matches)!=1:
        raise ValueError(f'Keep exactly one {REALFILM_LABEL} still in a PowerGrade album in the current Resolve project library.')
    album,still=matches[0]
    export_folder=folder/'realfilm-powergrade'
    export_folder.mkdir(exist_ok=False)
    if not album.ExportStills([still],str(export_folder),REALFILM_LABEL,'dpx'):
        raise RuntimeError(f'Resolve could not export {REALFILM_LABEL} from the Gallery.')
    files=list(export_folder.glob('*.drx'))
    if len(files)!=1 or not files[0].stat().st_size:
        raise RuntimeError('Resolve did not export a usable RealFilm grade file.')
    return files[0]


def apply_grade(root,value,folder):
    if not _grade_lock.acquire(blocking=False):
        raise ValueError('A Resolve grade is already running. Wait for it to finish before applying another.')
    try:
        return _apply_grade(value,folder)
    finally:
        _grade_lock.release()


def preview_lut(root, value):
    """Preview a factory LUT in a reversible local version of the clip at the playhead."""
    from .library_assets import resolve_luts
    from .resolve_adapter import _project

    action = value.get('action', 'apply')
    if action not in ('apply', 'restore'):
        raise ValueError('Choose a built-in LUT or restore the previous grade.')
    if action == 'apply':
        lut = next((row for row in resolve_luts() if row['id'] == value.get('id')), None)
        if lut is None:
            raise ValueError('Choose a LUT from the DaVinci Built-in LUTs list.')
    if not _grade_lock.acquire(blocking=False):
        raise ValueError('Wait for the current Resolve grade to finish.')
    try:
        resolve, project = _project()
        timeline = project.GetCurrentTimeline()
        clip = timeline.GetCurrentVideoItem() if timeline else None
        if not clip:
            raise ValueError('Move the Resolve playhead onto a footage clip first.')
        version = clip.GetCurrentVersion() or {}
        if version.get('versionType') != 0 or not version.get('versionName'):
            raise ValueError('Switch this clip to Local Grades before previewing a LUT.')
        target = [project.GetUniqueId(), timeline.GetUniqueId(), clip.GetUniqueId()]
        if not all(target):
            raise RuntimeError('Resolve did not return an identifiable preview clip.')
        if value.get('target') and value['target'] != target:
            raise ValueError('The Resolve playhead moved to a different clip. Choose the LUT again to preview it there.')
        key = hashlib.sha256(json.dumps(target).encode()).hexdigest()
        receipt = Path(root) / 'cache' / 'resolve-lut-previews' / (key + '.json')
        saved = json.loads(receipt.read_text('utf-8')) if receipt.is_file() else None
        current = version['versionName']
        if action == 'restore':
            if current != LUT_PREVIEW or not saved:
                raise ValueError('Move the playhead to the clip with the active Storylens LUT preview.')
            previous = saved['previous']
            if not clip.LoadVersionByName(previous, 0) or (clip.GetCurrentVersion() or {}).get('versionName') != previous:
                raise RuntimeError('Resolve could not restore the previous color version.')
            resolve.OpenPage('color')
            return {'target':target, 'message':f'Restored {previous} on {clip.GetName()}.'}

        versions = clip.GetVersionNameList(0) or []
        if LUT_PREVIEW in versions and not saved:
            raise ValueError('This clip already has a color version named Storylens LUT Preview. Rename it in Resolve before creating a preview.')
        switched = current != LUT_PREVIEW
        previous = current if switched else saved['previous']
        try:
            if LUT_PREVIEW not in versions:
                if not clip.AddVersion(LUT_PREVIEW, 0):
                    raise RuntimeError('Resolve could not create the LUT preview version.')
                created = True
            else:
                created = False
            if (clip.GetCurrentVersion() or {}).get('versionName') != LUT_PREVIEW:
                if not clip.LoadVersionByName(LUT_PREVIEW, 0):
                    raise RuntimeError('Resolve could not open the LUT preview version.')
            if (clip.GetCurrentVersion() or {}).get('versionName') != LUT_PREVIEW:
                raise RuntimeError('Resolve did not select the LUT preview version.')
            graph = clip.GetNodeGraph()
            if created:
                if not graph.ResetAllGrades():
                    raise RuntimeError('Resolve could not initialize the separate LUT preview graph.')
                graph = clip.GetNodeGraph()
                if not graph.SetNodeLabel(1, LUT_PREVIEW):
                    raise RuntimeError('Resolve could not label the LUT preview node.')
            if graph.GetNumNodes() != 1 or graph.GetNodeLabel(1) != LUT_PREVIEW:
                raise ValueError('The LUT preview version has been edited. Select another local version to continue grading in Resolve.')
            receipt.parent.mkdir(parents=True, exist_ok=True)
            pending = receipt.with_suffix('.tmp')
            pending.write_text(json.dumps({'previous':previous}), encoding='utf-8')
            pending.replace(receipt)
            if not graph.SetLUT(1, lut['id']):
                raise RuntimeError('Resolve could not load the selected LUT.')
            if (graph.GetLUT(1) or '').replace('\\', '/').casefold() != lut['id'].casefold():
                raise RuntimeError('Resolve did not report the selected LUT on the preview node.')
            resolve.OpenPage('color')
            return {'target':target, 'id':lut['id'], 'message':f"Previewing {lut['name']} on {clip.GetName()}."}
        except Exception:
            if switched:
                clip.LoadVersionByName(previous, 0)
            raise
    finally:
        _grade_lock.release()


def _apply_grade(value,folder):
    if value.get('input_profile')!='rec709':raise ValueError('Use SDR Rec.709 / Rec.709 footage with this template. HDR and Log need the correct input transform first.')
    mode=value.get('grade_mode','nodes')
    if mode not in ('realfilm','nodes'):
        raise ValueError('Choose Color Grade 1 or Color Grade 2.')
    values={}
    if mode=='nodes':
        for key,default,low,high in [('balance',0.,-.03,.03),('contrast',1.,.9,1.15),('saturation',1.,.8,1.2)]:
            v=value.get(key,default)
            if type(v) not in (int,float) or not math.isfinite(v) or not low<=v<=high:raise ValueError('Choose a supported '+key+' setting.')
            values[key]=v
    from .resolve_adapter import _project
    resolve,project=_project();timeline=project.GetCurrentTimeline()
    if not timeline:raise ValueError('Open the Resolve footage timeline first.')
    settings=project.GetSettings()
    if settings.get('colorScienceMode')!='davinciYRGB':
        raise ValueError('Use manual DaVinci YRGB for this grade. Set it in Resolve Project Settings > Color Management.')
    if mode=='nodes' and settings.get('colorSpaceTimeline')!='DaVinci WG/Intermediate':
        raise ValueError('Use a DaVinci Wide Gamut / Intermediate timeline for the original node structure.')
    if any(timeline.GetItemListInTrack('video',i) for i in range(2,timeline.GetTrackCount('video')+1)):
        raise ValueError('Use a footage-only V1 timeline. Keep titles and overlays outside this grade operation.')
    if not timeline.GetItemListInTrack('video',1):raise ValueError('The current footage track is empty.')
    folder=Path(folder);folder.mkdir(parents=True,exist_ok=True)
    label=REALFILM_LABEL if mode=='realfilm' else 'Storylens nodes'
    file=_realfilm_template(project,folder) if mode=='realfilm' else template()
    template_sha256=hashlib.sha256(file.read_bytes()).hexdigest() if mode=='realfilm' else TEMPLATE_SHA256
    manager=resolve.GetProjectManager()
    if not manager.SaveProject():raise RuntimeError('Resolve could not save the project checkpoint.')
    backup=folder/'Before node grade.drp'
    if not manager.ExportProject(project.GetName(),str(backup),True):raise RuntimeError('Resolve could not create a recovery project. Nothing was graded.')
    duplicate=timeline.DuplicateTimeline(timeline.GetName()+' - '+label+' '+time.strftime('%H%M%S'))
    if not duplicate or not project.SetCurrentTimeline(duplicate):raise RuntimeError('Resolve could not create the separate grade timeline.')
    receipt={'state':'applying','original':timeline.GetName(),'timeline':duplicate.GetName(),
             'grade_mode':mode,'grade_label':label,'template_sha256':template_sha256,
             'clips':0,'node_count':None,'values':values}
    if mode=='nodes':receipt['film_nodes_enabled']=False
    def save():
        tmp=folder/'grade-receipt.tmp';tmp.write_text(json.dumps(receipt,indent=2),encoding='utf-8');tmp.replace(folder/'grade-receipt.json')
    try:
        clips=duplicate.GetItemListInTrack('video',1) or []
        if not clips:raise RuntimeError('The duplicate timeline has no footage.')
        if any((clip.GetCurrentVersion() or {}).get('versionType')!=0 for clip in clips):
            raise ValueError('Switch the footage to Local Grades in Resolve before applying this grade. Remote grades can affect other timelines.')
        for clip in clips:
            if not clip.GetNodeGraph().ApplyGradeFromDRX(str(file),0):raise RuntimeError('Resolve could not apply the native DRX. The original timeline is kept.')
            graph=clip.GetNodeGraph()
            count=graph.GetNumNodes()
            if mode=='realfilm':
                labels={str(graph.GetNodeLabel(i)).strip().casefold() for i in range(1,count+1)}
                if not {'cst in','look','density'}.issubset(labels) or receipt['node_count'] not in (None,count):
                    raise RuntimeError('Resolve returned an unexpected RealFilm node graph.')
            else:
                if count!=19:raise RuntimeError('Resolve returned an unexpected node graph. The original timeline is kept.')
                triplet=lambda n:' '.join([str(n)]*3)
                for node,slope,offset,sat in [(2,1,values['balance'],1),(3,values['contrast'],.4*(1-values['contrast']),1),(4,1,0,values['saturation'])]:
                    if not clip.SetCDL({'NodeIndex':node,'Slope':triplet(slope),'Offset':triplet(offset),'Power':'1 1 1','Saturation':sat}):raise RuntimeError('Resolve rejected an editable grade control.')
                for node in (18,19):
                    if not graph.SetNodeEnabled(node,False):raise RuntimeError('Resolve could not keep the optional film nodes off.')
            receipt['node_count']=count
            receipt['clips']+=1;save()
        if not manager.SaveProject():raise RuntimeError('Resolve could not save the duplicate grade timeline.')
        resolve.OpenPage('color');receipt['state']='complete';save()
        return {'folder':str(folder),'grade_mode':mode,'node_count':receipt['node_count'],'clips':receipt['clips'],'timeline':duplicate.GetName(),
                'message':'Editable nodes applied to a duplicate timeline. Review and adjust the grade for your footage.'}
    except Exception:
        receipt['state']='partial';save();project.SetCurrentTimeline(timeline);raise
