"""Reuse a finished zoom's camera plan for sound-only/overlay follow-ups."""
from pathlib import Path
import json
import hashlib


def fingerprint(video):
    with Path(video).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()


def source_signatures(plan):
    from .xml_apply import Sequence
    seq=Sequence(plan['timeline'])
    return [{'path':p,'bytes':Path(p).stat().st_size,'modified_ns':Path(p).stat().st_mtime_ns}
            for p in sorted({c.path for c in seq.clips if c.path})]


def save(video,plan_path):
    plan_path=Path(plan_path).resolve()
    plan=json.loads(plan_path.read_text('utf-8'))
    digest=fingerprint(video)
    data={'plan':str(plan_path),'sources':source_signatures(plan),'sha256':digest}
    Path(str(video)+'.zoom.json').write_text(json.dumps(data,indent=2),encoding='utf-8')
    root=next(p.parent for p in plan_path.parents if p.name=='output')
    manifest=root/'cache/zoom/exports.json';manifest.parent.mkdir(parents=True,exist_ok=True)
    rows=json.loads(manifest.read_text('utf-8')) if manifest.exists() else {}
    rows[digest]=data
    manifest.write_text(json.dumps(rows,indent=2),encoding='utf-8')


def load(root,video):
    video=Path(video)
    if video.is_dir():
        # The app stages source uploads in a job folder before invoking tools.
        # Resolve that handoff before checking the export fingerprint.
        from hinglish_broll.library import VIDEO_EXTENSIONS
        files=sorted(p for p in video.rglob('*') if p.suffix.lower() in VIDEO_EXTENSIONS)
        if len(files)==1:return load(root,files[0])
        if any(load(root,p) for p in files):
            raise ValueError('Add effects to one approved SmartZoom video at a time, so its exact camera plan can be preserved. Your videos are kept.')
        return None
    side=Path(str(video)+'.zoom.json')
    if side.is_file():
        data=json.loads(side.read_text('utf-8'))
        if data.get('sha256') and data['sha256']!=fingerprint(video):return None
    else:
        manifest=Path(root)/'cache/zoom/exports.json'
        if not manifest.is_file() or not Path(video).is_file():return None
        data=json.loads(manifest.read_text('utf-8')).get(fingerprint(video))
        if not data:return None
    path=Path(data['plan']).resolve()
    if not path.is_relative_to((Path(root)/'output').resolve()):
        raise ValueError('The saved zoom reference is outside the editor output folder. Select the original source video and run SmartZoom again.')
    plan=json.loads(path.read_text('utf-8'))
    if plan.get('framing')!='fixed_focal' or source_signatures(plan)!=data.get('sources'):
        raise ValueError('The saved zoom source has changed. Select the original source video and run SmartZoom again; your existing export is kept.')
    return plan
