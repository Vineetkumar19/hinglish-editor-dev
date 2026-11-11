"""Prove editor exports preserve the original five typography renderers."""
import hashlib
import json
import os
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))


def main():
    import av
    import numpy as np
    from PIL import Image,ImageDraw
    from hinglish_captions.core import CaptionCue,CaptionWord
    from hinglish_captions.renderer import draw_caption,render_overlay
    from hinglish_captions.styles import template
    from hinglish_captions.project import rebuild_project
    from hinglish_cut.gpu_lock import gpu_lock

    proof=ROOT/'output/validation/caption-style-restoration'
    proof.mkdir(parents=True,exist_ok=True)
    phrases=['this is how you go','jata hai bas ek shareer','fir sawal uthata hai vahee',
             'fir sawal uthata hai','vakt aur fasle ko par']
    checked=[];sheet=Image.new('RGB',(360*5,680),'#121212');labels=ImageDraw.Draw(sheet)
    with gpu_lock(ROOT):
        for number,phrase in enumerate(phrases,1):
            style=f'typography_{number}';position=template(style).get('default_position',.7)
            cue=CaptionCue(tuple(CaptionWord(word,i*.15,(i+1)*.15) for i,word in enumerate(phrase.split())),0,1.3)
            path=proof/f'{style}-original-preserved.mov'
            render_overlay(path,[cue],360,640,1.3,25,style,lambda _:None,
                           cue_layouts=[{'x':.5,'y':position,'size':1}],word_visibility='phrase')
            frames=0
            with av.open(str(path)) as video:
                for index,frame in enumerate(video.decode(video=0)):
                    expected=np.asarray(draw_caption(360,640,cue,index/25,style,position=position))
                    assert np.array_equal(frame.to_ndarray(format='rgba'),expected),(style,index)
                    frames+=1
            background=Image.new('RGBA',(360,640),'black')
            background.alpha_composite(draw_caption(360,640,cue,.95,style,position=position))
            sheet.paste(background.convert('RGB'),((number-1)*360,40))
            labels.text(((number-1)*360+18,12),f'Typography {number} - original renderer',fill='white')
            checked.append({'style':style,'frames_checked':frames,'all_exported_pixels_match_original':True})
            print(f'{style}: {frames} original frames preserved exactly',flush=True)
        sheet.save(proof/'all-five-original-styles.jpg',quality=92)

        source_project=ROOT/'output/captions/20261018-132541-cb8768/001-0000-0000-711239f3-Rog Music/caption-project.json'
        before=hashlib.sha256(source_project.read_bytes()).hexdigest()
        data=json.loads(source_project.read_text(encoding='utf-8'))
        folder=ROOT/'output/captions/restored-original-typography/Rog Music'
        (folder/'media').mkdir(parents=True,exist_ok=True)
        source=source_project.parent/data['source_relative'];target=folder/'media/source.mp4'
        if not target.exists():
            os.link(source,target)
        data['media']['path']=str(target.resolve())
        position=template('typography_4')['default_position']
        data.update(style='typography_4',font='template',position=position,size=1,
                    word_visibility='phrase',cue_layouts=[{'x':.5,'y':position,'size':1} for _ in data['cues']])
        project=folder/'caption-project.json'
        project.write_text(json.dumps(data,indent=2,ensure_ascii=False),encoding='utf-8')
        result=rebuild_project(project,{'export_video':True},lambda line:print(line,flush=True))
        assert hashlib.sha256(source_project.read_bytes()).hexdigest()==before
    receipt={'passed':True,'five_original_presets':checked,'unchanged_source_project':True,
             'review':result,'original_template_animation_restored':True}
    (proof/'verification.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8')
    print(json.dumps(receipt,indent=2),flush=True)


if __name__=='__main__':
    main()
