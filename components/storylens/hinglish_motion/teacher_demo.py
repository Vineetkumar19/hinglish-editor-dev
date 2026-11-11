"""Render an expressly supplied teacher package without another local authoring loop."""
import hashlib,json,re,subprocess
from pathlib import Path
from fractions import Fraction


def teacher_package(root,source,brief):
    match=re.search(r'^Teacher package:\s*([^\r\n]+)$',brief,re.M|re.I)
    if not match:return None
    root=Path(root).resolve();file=Path(match[1].strip().strip('"')).resolve()
    if not any(file.is_relative_to(root/p) for p in ('output/motion','library/motion-teacher')):raise ValueError('Teacher package unavailable: choose a saved Motion Graphics teacher plan.')
    data=json.loads(file.read_text('utf-8'))
    if data.get('source_sha256')!=hashlib.sha256(Path(source).read_bytes()).hexdigest():raise ValueError('Teacher package unavailable: this plan belongs to another reference.')
    return file


def run(root,source,file,progress=print,*,student=None):
    import av
    from .teacher_memory import validate_plan
    from .creative_export import render_hyperframes
    from hinglish_cut.xml_export import export_xml
    from hinglish_cut.model import Media,Cut
    from imageio_ffmpeg import get_ffmpeg_exe
    file=Path(file);folder=file.parent;plan=validate_plan(json.loads(file.read_text('utf-8')))
    assets=[{'id':f.stem,'src':f.resolve().as_uri()} for f in (folder/'assets').glob('*.png')]
    silent=folder/('student-picture.mp4' if student else 'teacher-picture.mp4')
    progress('Hyperframes rendering the local Qwen scene plan with GSAP and Three.js' if student else 'Rendering the teacher-authored layers with Hyperframes, GSAP and Three.js; no local LLM generation')
    render_hyperframes({'template':'teacher_editorial','mode':'full','duration':plan['duration'],'quality':'preview','data':{'teacher_plan':plan,'assets':assets}},silent,30,360,640,progress)
    target=folder/'MOTION_GRAPHICS.mp4'
    progress('Adding supplied reference audio for this labelled comparison')
    r=subprocess.run([get_ffmpeg_exe(),'-hide_banner','-loglevel','error','-y','-i',str(silent),'-i',str(source),'-map','0:v:0','-map','1:a:0','-c:v','copy','-c:a','aac','-t',str(plan['duration']),'-movflags','+faststart',str(target)],capture_output=True,timeout=120)
    if r.returncode:raise RuntimeError('Teacher example audio stopped: '+r.stderr.decode(errors='replace')[-600:])
    with av.open(str(target)) as c:
        v=c.streams.video[0];frames=sum(1 for _ in c.decode(video=0));fps=v.average_rate;seconds=c.duration/1e6;channels=c.streams.audio[0].codec_context.channels if c.streams.audio else 0
    if abs(seconds-plan['duration'])>.15 or frames<450 or channels!=2:raise ValueError('Teacher example incomplete: inspect the saved picture/audio before retrying.')
    media=Media('teacher',str(target.resolve()),frames/float(fps),str(fps),360,640,2,48000)
    export_xml(folder/('QWEN_STUDENT_SEQUENCE.xml' if student else 'TEACHER_SEQUENCE.xml'),[Cut('teacher',0,frames,0)],{'teacher':media})
    receipt={'author':student['model'] if student else 'Codex teacher, explicitly requested by owner','weights_updated':False,'source_photo_crops_used':True,'source_audio_used':True,'scenes':len(plan['scenes']),'frames':frames,'seconds':seconds,'channels':channels,'approval':'draft','three_d':'Reference-derived photo/pose planes with real Three.js camera/debris; original 3D scene not recovered'}
    receipt.update(student or {})
    (folder/('student-render-receipt.json' if student else 'teacher-render-receipt.json')).write_text(json.dumps(receipt,indent=2),'utf-8')
    page=folder/'report.html';page.write_text('''<!doctype html><meta charset="utf-8"><title>Storylens teacher example</title><style>body{margin:30px auto;max-width:1100px;background:#101216;color:#eee;font:16px system-ui}video{max-height:78vh;width:auto;max-width:100%}a{color:#71d9c8}.columns{display:flex;gap:24px}</style><h1>Motion Graphics — teacher example</h1><p>Teacher · GSAP · Hyperframes · Three.js</p><p>Reference-derived photo crops and supplied reference audio. Editable text and newly authored camera/layer movement. Procedural 3D scenes approximate the reference. Draft awaiting owner review; model weights unchanged.</p><video controls src="MOTION_GRAPHICS.mp4"></video><p><a href="teacher-plan.json">Full timed layer plan</a> · <a href="teacher-notes.txt">Construction notes</a> · <a href="teacher-render-receipt.json">Actual render receipt</a></p>''','utf-8')
    if student:
        page.write_text('''<!doctype html><meta charset="utf-8"><title>Storylens local Qwen result</title><style>body{margin:30px auto;max-width:1100px;background:#101216;color:#eee;font:16px system-ui}video{max-height:78vh;width:auto;max-width:100%}a{color:#71d9c8}</style><h1>Motion Graphics — local Qwen result</h1><p>Local Qwen · teacher reference knowledge · GSAP · Hyperframes · Three.js</p><p>Local Qwen authored the numeric scene layouts, camera keys, reveals and parallax. Reference words, image/pose assets, audio and existing renderer are reused. Codex did not manually edit this composition. Model weights unchanged; quality awaits your review.</p><video controls src="MOTION_GRAPHICS.mp4"></video><p><a href="student-plan.json">Qwen scene plan</a> · <a href="authorship.json">Authorship receipt</a> · <a href="student-render-receipt.json">Actual render receipt</a></p>''','utf-8')
    progress('Local Qwen video ready for owner review' if student else 'Teacher comparison ready; no weight training or student quality claim')
    return page
