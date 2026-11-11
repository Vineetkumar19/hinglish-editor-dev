"""Finalize the existing model render from decoded frame counts; never regenerate it."""
import json
from pathlib import Path
from fractions import Fraction
from html import escape


def frame_media(path,frames,fps,width,height):
    from hinglish_cut.model import Media
    if frames<=0:raise ValueError('Motion reference export stopped: the decoded video is empty.')
    fps=Fraction(fps)
    return Media('1',str(Path(path).resolve()),frames/float(fps),str(fps),width,height,2,48000)


def finish(folder,progress=print):
    import av
    from .reference_composer import save
    from hinglish_cut.model import Cut
    from hinglish_cut.xml_export import export_xml
    folder=Path(folder);target=folder/'MOTION_GRAPHICS.mp4'
    plan=json.loads((folder/'reference-motion-project.json').read_text('utf-8'))
    expected=sum(s['duration'] for s in plan['scenes'])
    with av.open(str(target)) as c:
        stream=c.streams.video[0];fps=stream.average_rate;width,height=stream.width,stream.height
        actual=c.duration/1e6;audio=bool(c.streams.audio);channels=c.streams.audio[0].codec_context.channels if audio else 0
        frames=sum(1 for _ in c.decode(video=0))
    if abs(actual-expected)>.3 or frames<expected*float(fps)-5 or channels!=2:
        raise ValueError('Motion reference export stopped: saved picture/soundtrack is incomplete. Retry the saved project.')
    media=frame_media(target,frames,fps,width,height)
    export_xml(folder/'MOTION_GRAPHICS_SEQUENCE.xml',[Cut('1',0,frames,0)],{'1':media})
    assets=json.loads((folder/'asset-receipts.json').read_text('utf-8'))
    catalogue=json.loads((folder/'sound-catalogue.json').read_text('utf-8'))
    save(folder/'render-validation.json',{'seconds':actual,'frames':frames,'audio':audio,'channels':channels,
      'scene_count':len(plan['scenes']),'assets':len(assets),'sound_files':catalogue['count'],
      'reference_pixels_or_audio_used':False,'visual_approval':False,'export_count_source':'actual decoded frames'})
    page=folder/'report.html'
    page.write_text('<!doctype html><meta charset="utf-8"><title>Storylens local motion example</title><style>body{background:#111;color:#eee;font:16px system-ui;max-width:1000px;margin:40px auto}video{max-height:75vh;max-width:100%}a{color:#b4e06c}</style><h1>'+escape(plan['title'])+'</h1><p>Local Qwen + Vision · ReelMimic analysis · GSAP · Hyperframes · local sound library</p><video src="MOTION_GRAPHICS.mp4" controls></video><p>Original independent assets and soundtrack. The selected reference supplied analysis only. Source layers, motion and cue choices are saved as JSON. Rendered editor layers are video.</p><a href="reference-motion-project.json">Editable layer plan</a> · <a href="asset-receipts.json">Asset sources</a> · <a href="sound-events.json">Sound choices</a>','utf-8')
    progress('One local-model reference example is ready for review; no next reference was started.')
    return page
