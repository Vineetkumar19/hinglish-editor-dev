"""Upgrade old Caption Studio reports without rerendering or altering saved edits."""
import json
import re
from pathlib import Path


def caption_html(content,folder,token):
    data=content.decode('utf-8')
    pattern_js=(Path(__file__).resolve().parents[1]/'hinglish_captions/template_patterns.js').read_text('utf-8')
    data=data.replace('<script>','<script>'+pattern_js+'\n',1)
    from hinglish_captions.styles import TEMPLATES
    catalog=json.dumps(TEMPLATES,ensure_ascii=True).replace('<','\\u003c')
    data=data.replace('<script>// Direct editing', '<script>Object.assign(templates,'+catalog+');</script><script>// Direct editing',1)
    for name,marker in [('caption_one','// Caption 1 uses'),('caption_four','// Caption 4 mirrors'),('caption_five','// Caption 5 shares'),('kinetic_gold','// First reference draft:'),('serif_circle','// Second reference draft:')]:
        start=data.find('<script>'+marker)
        if start>=0:
            end=data.find('</script>',start)
            if end>=0:
                code=(Path(__file__).resolve().parents[1]/('hinglish_captions/'+name+'.js')).read_text('utf-8')
                prefix=''
                if name=='kinetic_gold':
                    # Upgrade saved gold studios together with their code. Old
                    # embedded profiles lack the explicit inline/echo slots.
                    from hinglish_captions.kinetic_gold import profile as gold_profile
                    gold_profile.cache_clear()
                    config=json.dumps(gold_profile(),ensure_ascii=True).replace('<','\\u003c')
                    prefix='<script>project.kinetic_gold_profile='+config+';</script>'
                if name=='serif_circle':
                    from hinglish_captions.serif_circle import profile as serif_circle_profile
                    serif_circle_profile.cache_clear()
                    config=json.dumps(serif_circle_profile(),ensure_ascii=True).replace('<','\\u003c')
                    prefix='<script>project.serif_circle_profile='+config+';</script>'
                if name=='caption_four':
                    from hinglish_captions.caption_four import profile as caption_four_profile
                    caption_four_profile.cache_clear()
                    config=json.dumps(caption_four_profile(),ensure_ascii=True).replace('<','\\u003c')
                    prefix='<script>project.caption_four_profile='+config+';</script>'
                data=data[:start]+prefix+'<script>'+code+data[end:]
    # Hide retired choices in saved reports too; retain saved designs and edits.
    data=re.sub(r'<button\b(?=[^>]*\bclass="template-card\b)(?=[^>]*\bdata-style="(?:typography_1|typography_2|minimal)")[^>]*>.*?</button>', '', data, flags=re.DOTALL)
    marker='<script>// Direct editing augments the existing template library without losing edits.'
    start=data.find(marker)
    if start>=0:
        end=data.find('</script>',start)
        if end>=0:
            # The refreshed editor draws immediately, before the later kinetic
            # script runs. Old saved projects need the new zoom profile first.
            from hinglish_captions.kinetic import profile as reference_profile
            config=json.dumps(reference_profile(),ensure_ascii=True).replace('<','\\u003c')
            from hinglish_captions.report import CINEMATIC_SAMPLES,cinematic_cards_html
            from hinglish_captions.styles import template
            choices=json.dumps({key:template(key) for key in CINEMATIC_SAMPLES}).replace('<','\\u003c')
            cards=json.dumps(cinematic_cards_html()).replace('<','\\u003c')
            upgrade=f'''Object.assign(templates,{choices});
const cinematicCards=document.createElement('div');cinematicCards.innerHTML={cards};
for(const card of [...cinematicCards.children]){{const old=document.querySelector('.template-card[data-style="'+card.dataset.style+'"]');if(old)old.replaceWith(card);else document.querySelector('.template-list')?.append(card);}}
'''
            data=data[:start]+'<script>project.kinetic_profile='+config+';'+upgrade+'</script><script>'+ (Path(__file__).resolve().parents[1]/'hinglish_captions/studio.js').read_text('utf-8')+data[end:]
    # Saved reports embed their preview code. Refresh the design and its profile
    # together so an older report cannot disagree with the current exporter.
    caption_two_marker='<script>// Caption 2 keeps the measured row roles'
    start=data.find(caption_two_marker)
    if start>=0:
        end=data.find('</script>',start)
        if end>=0:
            from hinglish_captions.caption_two import profile as caption_two_profile
            caption_two_profile.cache_clear()
            code=(Path(__file__).resolve().parents[1]/'hinglish_captions/caption_two.js').read_text('utf-8')
            config=json.dumps(caption_two_profile(),ensure_ascii=True).replace('<','\\u003c')
            data=data[:start]+'<script>project.caption_two_profile='+config+';</script><script>'+code+data[end:]
    design_marker='<script>// Caption 3 uses the same compositions'
    cinematic_marker='<script>// Review-only cinematic caption reference engine;'
    cinematic_start=data.find(cinematic_marker)
    if cinematic_start>=0:
        cinematic_end=data.find('</script>',cinematic_start)
        if cinematic_end>=0:
            from hinglish_captions.cinematic_reference import profile as cinematic_profile
            code=(Path(__file__).resolve().parents[1]/'hinglish_captions/cinematic_reference.js').read_text('utf-8')
            config=json.dumps(cinematic_profile(),ensure_ascii=True).replace('<','\\u003c')
            data=data[:cinematic_start]+'<script>project.cinematic_reference_profile='+config+';</script><script>'+code+data[cinematic_end:]
    elif marker in data:
        from hinglish_captions.cinematic_reference import profile as cinematic_profile
        code=(Path(__file__).resolve().parents[1]/'hinglish_captions/cinematic_reference.js').read_text('utf-8')
        config=json.dumps(cinematic_profile(),ensure_ascii=True).replace('<','\\u003c')
        data=data.replace('</body>','<script>project.cinematic_reference_profile='+config+';</script><script>'+code+'</script></body>')
    start=data.find(design_marker)
    if start>=0:
        end=data.find('</script>',start)
        if end>=0:
            from hinglish_captions.caption_three import profile, font_css
            profile.cache_clear()
            code=(Path(__file__).resolve().parents[1]/'hinglish_captions/caption_three.js').read_text('utf-8')
            config=json.dumps(profile(),ensure_ascii=True).replace('<','\\u003c')
            data=data[:start]+'<style>'+font_css()+'</style><script>project.caption_three_profile='+config+';</script><script>'+code+data[end:]
    reference_marker='<script>// Kinetic Documentary uses a canvas'
    start=data.find(reference_marker)
    if start>=0:
        end=data.find('</script>',start)
        if end>=0:
            code=(Path(__file__).resolve().parents[1]/'hinglish_captions/kinetic.js').read_text('utf-8')
            from hinglish_captions.kinetic import profile as reference_profile
            config=json.dumps(reference_profile(),ensure_ascii=True).replace('<','\\u003c')
            data=data[:start]+'<script>project.kinetic_profile='+config+';</script><script>'+code+data[end:]
    data=data.replace('Caption Studio Â·','Caption Studio ·').replace('Draft restored Â·','Draft restored ·')
    folder_json=json.dumps(str(folder),ensure_ascii=True).replace('<','\\u003c')
    token_json=json.dumps(token)
    studio_css=(Path(__file__).resolve().parents[1]/'hinglish_captions/studio.css').read_text('utf-8')
    extras='<style id="current-caption-studio">'+studio_css+'</style><link rel="stylesheet" href="/editor-handoff.css"><script src="/icons.js"></script><script src="/feedback.js"></script>'
    data=data.replace('</head>',extras+'</head>')
    data=data.replace('</body>',f'''<script>document.documentElement.dataset.token={token_json};</script>
<script src="/editor-handoff.js"></script><script>
(()=>{{const play=document.querySelector('#play'),media=document.querySelector('video');
if(play&&media){{const draw=()=>{{play.innerHTML=window.storylensIcon(media.paused?'play':'pause');play.setAttribute('aria-label',media.paused?'Play preview':'Pause preview')}};media.addEventListener('play',draw);media.addEventListener('pause',draw);draw();}}
window.storylensBeforeHandoff=async (options)=>{{if(options.caption_mode==='words'&&window.storylensSaveForEditor)return await window.storylensSaveForEditor();if(typeof studioSaving!=='undefined'&&studioSaving)throw Error('Caption export is still running. Wait for it to finish, then choose your editor.');if(typeof studioDirty!=='undefined'&&studioDirty)throw Error('Save the finished video first for this import mode, or choose editable words. Your draft is kept.');}};
window.storylensEditors.render(document.querySelector('.links'),{{folder:{folder_json}}});
}})();</script></body>''')
    return data.encode('utf-8')
