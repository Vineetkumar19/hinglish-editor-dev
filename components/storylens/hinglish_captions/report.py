from pathlib import Path
import base64
from functools import lru_cache
import html
import json

from .styles import FONT_CHOICES, SELECTABLE_TEMPLATES, template

CINEMATIC_SAMPLES={
    'cinematic_mixed_draft':'<span style="font:400 34px/1.2 \'Great Vibes\',cursive">Your</span><span style="font:400 18px/1.5 Roboto,Arial,sans-serif">story <strong>unfolds</strong></span>',
    'cinematic_clean_draft':'<span style="font:400 19px/1.5 Roboto,Arial,sans-serif;letter-spacing:.02em">Every story matters</span>',
}

def cinematic_cards_html():
    return ''.join(f'<button class="template-card" data-style="{key}" data-category="cinematic"><div class="template-sample {key}">{sample}</div><b>{html.escape(template(key)["name"])}</b><small>CINEMATIC</small></button>' for key,sample in CINEMATIC_SAMPLES.items())


@lru_cache(maxsize=1)
def bundled_font_css():
    faces=(('Barlow Condensed','BarlowCondensed-SemiBold.ttf',600),('Roboto Condensed','RobotoCondensed-Bold.ttf',700),
           ('Roboto','Roboto-Regular.ttf',400),('Roboto Black','Roboto-Black.ttf',900),
           ('Dancing Script','DancingScript-Regular.ttf',400),('Great Vibes','GreatVibes-Regular.ttf',400),
           ('Inter Caption 1','Inter-Medium.otf',500),('Inter Caption 1','Inter-Bold.otf',700),
           ('Inter Caption 2','Inter-Variable.ttf','100 900'),
           ('Caption Three Serif','caption-three/CaptionThree-RegularItalic.ttf',400),
           ('Caption Three Serif','caption-three/CaptionThree-BoldItalic.ttf',700),
           ('Caption Three Playful','caption-three/CaptionThree-Playful.ttf',400),
           ('Circle Serif','PlayfairDisplay-BoldItalic.ttf',700),('Circle Italic','InterDisplay-SemiBoldItalic.ttf',600),
           ('Circle Sans','Inter-SemiBold.ttf',600))
    rules=[]
    for family,filename,weight in faces:
        path=Path(__file__).with_name('fonts')/filename
        if family.startswith('Circle ') and not path.is_file():path=Path('C:/Windows/Fonts')/filename
        if path.is_file():
            payload=base64.b64encode(path.read_bytes()).decode('ascii')
            kind='opentype' if path.suffix=='.otf' else 'truetype'
            mime='otf' if path.suffix=='.otf' else 'ttf'
            rules.append(f"@font-face{{font-family:'{family}';font-style:normal;font-weight:{weight};font-display:block;src:url(data:font/{mime};base64,{payload}) format('{kind}')}}")
    return '\n'.join(rules)


def _safe_json(value):
    return json.dumps(value, ensure_ascii=False).replace('<', '\\u003c')


@lru_cache(maxsize=1)
def caption_one_sample():
    """Render the picker thumbnail through the same caption renderer."""
    from io import BytesIO
    from .core import CaptionCue,CaptionWord
    from .caption_one import render
    words=tuple(CaptionWord(word,i*.12,i*.12+.1) for i,word in enumerate('The Taj Mahal stands beside'.split()))
    image=render(720,300,CaptionCue(words,0,2),1,position=.5)
    box=image.getbbox()
    if box:image=image.crop((max(0,box[0]-10),max(0,box[1]-10),min(image.width,box[2]+10),min(image.height,box[3]+10)))
    buffer=BytesIO();image.save(buffer,format='PNG')
    return base64.b64encode(buffer.getvalue()).decode('ascii')


@lru_cache(maxsize=1)
def caption_two_sample():
    from io import BytesIO
    from .caption_two import render,reference_cues,paginate_cue
    from .template_patterns import pattern_context
    cue=paginate_cue(reference_cues()[0])[0]
    with pattern_context(cue):image=render(720,360,cue,cue.end-.01,position=.5)
    box=image.getbbox()
    if box:image=image.crop((max(0,box[0]-8),max(0,box[1]-8),min(image.width,box[2]+8),min(image.height,box[3]+8)))
    buffer=BytesIO();image.save(buffer,format='PNG')
    return base64.b64encode(buffer.getvalue()).decode('ascii')


@lru_cache(maxsize=1)
def caption_three_sample():
    from io import BytesIO
    from .caption_three import render,sample_cues
    from PIL import Image
    cue=sample_cues()[2]
    image=render(720,480,cue,cue.end-.2,position=.5)
    box=image.getbbox()
    if box:image=image.crop((max(0,box[0]-10),max(0,box[1]-10),min(image.width,box[2]+10),min(image.height,box[3]+10)))
    background=Image.new('RGBA',image.size,'#F8F7F2');background.alpha_composite(image)
    buffer=BytesIO();background.save(buffer,format='PNG');return base64.b64encode(buffer.getvalue()).decode('ascii')


@lru_cache(maxsize=1)
def caption_four_sample():
    from io import BytesIO
    from .caption_four import render,sample_cues
    from PIL import Image
    cue=sample_cues()[2]
    image=render(720,480,cue,cue.words[-1].start+(cue.end-cue.words[-1].start)*.65,position=.5)
    box=image.getbbox()
    if box:image=image.crop((max(0,box[0]-12),max(0,box[1]-12),min(image.width,box[2]+12),min(image.height,box[3]+12)))
    background=Image.new('RGBA',image.size,'#000000');background.alpha_composite(image)
    buffer=BytesIO();background.save(buffer,format='PNG');return base64.b64encode(buffer.getvalue()).decode('ascii')


@lru_cache(maxsize=1)
def caption_five_sample():
    from io import BytesIO
    from .caption_five import render,sample_cues
    from PIL import Image
    cue=sample_cues()[0]
    image=render(720,480,cue,cue.words[-1].start+(cue.end-cue.words[-1].start)*.65,position=.5)
    box=image.getbbox()
    if box:image=image.crop((max(0,box[0]-12),max(0,box[1]-12),min(image.width,box[2]+12),min(image.height,box[3]+12)))
    background=Image.new('RGBA',image.size,'#FFFFFF');background.alpha_composite(image)
    buffer=BytesIO();background.save(buffer,format='PNG');return base64.b64encode(buffer.getvalue()).decode('ascii')


def write_report(path, media_name, video_relative, cues, style_name, files, project=None):
    path = Path(path)
    template(style_name)
    project = dict(project or {})
    from .cinematic_reference import profile as cinematic_profile
    project['cinematic_reference_profile']=cinematic_profile()
    from .kinetic_gold import profile as gold_profile
    project['kinetic_gold_profile']=gold_profile()
    from .serif_circle import profile as circle_profile
    project['serif_circle_profile']=circle_profile()
    choices=dict(SELECTABLE_TEMPLATES)
    if style_name=='kinetic_gold_draft':choices={style_name:template(style_name),**choices}
    if style_name=='serif_circle_draft':choices={style_name:template(style_name),**choices}
    if project.get('review_draft'):
        choices.update({key:template(key) for key in ('cinematic_mixed_draft','cinematic_clean_draft')})
    from .kinetic import profile as kinetic_profile
    project['kinetic_profile'] = kinetic_profile()
    from .caption_one import profile as caption_one_profile
    project['caption_one_profile'] = caption_one_profile()
    from .caption_two import profile as caption_two_profile
    caption_two_profile.cache_clear()
    project['caption_two_profile'] = caption_two_profile()
    from .caption_three import profile as caption_three_profile
    project['caption_three_profile'] = caption_three_profile()
    from .caption_four import profile as caption_four_profile
    project['caption_four_profile'] = caption_four_profile()
    from .caption_five import profile as caption_five_profile
    project['caption_five_profile'] = caption_five_profile()
    from .project import cues_to_data
    payload = cues_to_data(cues)
    project['project_path'] = str((path.parent / 'caption-project.json').resolve())
    project['has_video']=(path.parent/'captioned-preview.mp4').is_file()
    from urllib.parse import quote
    for ancestor in path.parents:
        if ancestor.name=='captions' and ancestor.parent.name=='output':
            project['editor_url']='http://127.0.0.1:8765/caption-output/'+quote(path.resolve().relative_to(ancestor.resolve()).as_posix(),safe='/')
            break
    project.setdefault('word_colors', [[None] * len(cue.words) for cue in cues])
    links = ''.join(f'<a download href="{html.escape(name)}">{html.escape(label)}</a>'
                    for label, name in files)
    sample_markup = {
        'caption_1': '<span style="font:700 18px \'Inter Caption 1\';letter-spacing:-.08em">love<small style="font-size:11px">the</small></span><strong style="font:700 20px \'Inter Caption 1\';letter-spacing:-.08em;color:#25A8FC">CHALLENGE</strong>',
        'documentary_outline': '<strong style="font:400 26px Impact;color:transparent;-webkit-text-stroke:1px white">KOLKATTA</strong><span style="font:700 10px Arial">SE BADLA LENE</span>',
        'documentary_echo': '<span style="font:700 10px Arial">OUT KA</span><strong style="font:400 26px Impact;color:white;text-shadow:0 5px 0 #555">PRESSURE</strong><span style="font:700 10px Arial">VAH JHEL</span>',
        'kinetic_documentary': '<span style="font:700 10px Arial">YOUR STORY IN</span><strong style="font:400 26px Impact;color:#FFFFFF">WORDS</strong>',
        'typography_3': '<span>fir sawal</span><strong>uthata</strong><span>hai, vahee</span>',
        'typography_4': '<span>fir sawal uthata</span><strong>hai</strong>',
        'typography_5': '<span>vakt aur</span><strong>fasle</strong><span>ko par</span>',
    }
    sample_markup['caption_1']=f'<img alt="Caption 1: three lines with one large middle word" src="data:image/png;base64,{caption_one_sample()}" style="display:block;max-width:100%;height:70px;object-fit:contain;margin:auto">'
    sample_markup['caption_2']=f'<img alt="Caption 2: lime typography and timed motion" src="data:image/png;base64,{caption_two_sample()}" style="display:block;max-width:100%;height:70px;object-fit:contain;margin:auto">'
    sample_markup['caption_3']=f'<img alt="Caption 3: staggered italic serif typography and soft focus motion" src="data:image/png;base64,{caption_three_sample()}" style="display:block;max-width:100%;height:70px;object-fit:contain;margin:auto">'
    sample_markup['caption_4']=f'<img alt="Caption 4: italic serif typography" src="data:image/png;base64,{caption_four_sample()}" style="display:block;max-width:100%;height:70px;object-fit:contain;margin:auto">'
    sample_markup['caption_5']=f'<img alt="Caption 5: heavy black type and red emphasis" src="data:image/png;base64,{caption_five_sample()}" style="display:block;max-width:100%;height:70px;object-fit:contain;margin:auto">'
    sample_markup.update(CINEMATIC_SAMPLES)
    sample_markup['kinetic_gold_draft']='<span style="font:700 12px Arial">Kaafi</span><strong style="font:600 32px Barlow Condensed;color:#ffcc00">Overthinking</strong><span style="font:700 12px Arial">ke baad</span>'
    sample_markup['serif_circle_draft']='<span style="font:600 13px Circle Sans,Arial">Why one</span><strong style="font:700 32px Circle Serif,serif;color:#FFFFFF">single post</strong>'
    templates = ''.join(
        f'<button class="template-card" data-style="{key}" data-category="{value["category"]}">'
        f'<div class="template-sample {key}">'
        f'{sample_markup.get(key, "this is how you go <em>viral</em>")}'
        f'</div>'
        f'<b>{html.escape(value["name"])}</b><small>{html.escape(value["tag"])}</small></button>'
        for key, value in choices.items())
    fonts = ''.join(f'<option value="{key}">{html.escape(value["name"])}</option>'
                    for key, value in FONT_CHOICES.items())
    cue_editors = ''.join(
        f'<section class="cue-row" data-index="{index}"><span>{index + 1}</span>'
        f'<small>{cue.start:.2f}–{cue.end:.2f}</small>'
        f'<textarea rows="2">{html.escape(cue.text)}</textarea>'
        f'<div class="word-tools" data-word-tools="{index}"></div></section>'
        for index, cue in enumerate(cues))
    duration = max((cue.end for cue in cues), default=1)
    caption_blocks = ''.join(
        f'<button style="left:{cue.start / duration * 100:.3f}%;width:'
        f'{max(.3, (cue.end - cue.start) / duration * 100):.3f}%" '
        f'data-seek="{cue.start}">{html.escape(cue.text)}</button>' for cue in cues)

    document = _EDITOR_DOCUMENT.replace('\\"', '"')
    replacements = {
        '__MEDIA_NAME__': html.escape(media_name),
        '__VIDEO_RELATIVE__': html.escape(video_relative),
        '__TEMPLATES_HTML__': templates,
        '__FONTS_HTML__': fonts,
        '__CUE_EDITORS__': cue_editors,
        '__CAPTION_BLOCKS__': caption_blocks,
        '__LINKS__': links,
        '__DURATION__': f'{duration:.1f}',
        '__CUES_JSON__': _safe_json(payload),
        '__TEMPLATES_JSON__': _safe_json({**choices, style_name: template(style_name)}),
        '__FONTS_JSON__': _safe_json(FONT_CHOICES),
        '__PROJECT_JSON__': _safe_json(project),
        '__STYLE_NAME__': style_name,
    }
    for marker, value in replacements.items():
        document = document.replace(marker, value)
    if project.get('review_draft'):
        document=document.replace('>9:16</button>','>Vertical · max 4 words</button>').replace('>16:9</button>','>Horizontal · max 7 words</button>').replace('>1:1</button>','>Square · max 4 words</button>')
    extra_css=Path(__file__).with_name('studio.css').read_text(encoding='utf-8')
    extra_js=Path(__file__).with_name('studio.js').read_text(encoding='utf-8')
    pattern_js=Path(__file__).with_name('template_patterns.js').read_text(encoding='utf-8')
    document=document.replace('</head>',f'<script>{pattern_js}</script></head>')
    document=document.replace('</head>',f'<style>{bundled_font_css()}\n{extra_css}</style></head>')
    document=document.replace('</body>',f'<script>{extra_js}</script></body>')
    kinetic_js = Path(__file__).with_name('kinetic.js').read_text(encoding='utf-8')
    document = document.replace('</body>', f'<script>{kinetic_js}</script></body>')
    caption_one_js = Path(__file__).with_name('caption_one.js').read_text(encoding='utf-8')
    document = document.replace('</body>', f'<script>{caption_one_js}</script></body>')
    caption_two_js = Path(__file__).with_name('caption_two.js').read_text(encoding='utf-8')
    document = document.replace('</body>', f'<script>{caption_two_js}</script></body>')
    caption_three_js = Path(__file__).with_name('caption_three.js').read_text(encoding='utf-8')
    document = document.replace('</body>', f'<script>{caption_three_js}</script></body>')
    caption_four_js = Path(__file__).with_name('caption_four.js').read_text(encoding='utf-8')
    document = document.replace('</body>', f'<script>{caption_four_js}</script></body>')
    caption_five_js = Path(__file__).with_name('caption_five.js').read_text(encoding='utf-8')
    document = document.replace('</body>', f'<script>{caption_five_js}</script></body>')
    cinematic_js=Path(__file__).with_name('cinematic_reference.js').read_text('utf-8')
    document=document.replace('</body>',f'<script>{cinematic_js}</script></body>')
    gold_js=Path(__file__).with_name('kinetic_gold.js').read_text('utf-8')
    document=document.replace('</body>',f'<script>{gold_js}</script></body>')
    circle_js=Path(__file__).with_name('serif_circle.js').read_text('utf-8')
    document=document.replace('</body>',f'<script>{circle_js}</script></body>')
    if project.get('demo') or style_name == 'kinetic_documentary':
        document = document.replace('</head>', '<script src="/feedback.js"></script></head>')
    if project.get('demo'):
        document = document.replace('</body>', '<script src="/caption-demo-editor.js"></script></body>')
    path.write_text(document, encoding='utf-8')


_EDITOR_DOCUMENT = r'''<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Caption Studio · __MEDIA_NAME__</title><style>
:root{--accent:#ff6635;--caption-accent:#ff7638;--line:#302d29;--panel:#151412;--muted:#8e8982}*{box-sizing:border-box}body{margin:0;background:#0c0b0a;color:#f8f5ef;font:14px/1.4 "Segoe UI",Arial,sans-serif;overflow:hidden}button,textarea,select,input{font:inherit}header{height:58px;border-bottom:1px solid var(--line);display:flex;align-items:center;justify-content:space-between;padding:0 18px}header b{font-size:17px}header small{color:var(--muted);margin-left:12px}.ratios{display:flex;border:1px solid var(--line);border-radius:9px;padding:3px;gap:3px}.ratios button,.tabbar button,.chips button{border:0;background:transparent;color:#aaa49b;border-radius:6px;padding:7px 12px;cursor:pointer}.ratios button.active,.tabbar button.active,.chips button.active{background:#292622;color:#fff}.save{background:var(--accent);border:0;color:#180b06;font-weight:800;border-radius:9px;padding:10px 18px;cursor:pointer}.app{height:calc(100vh - 58px);display:grid;grid-template-columns:minmax(0,1fr) 360px;grid-template-rows:minmax(0,1fr) 205px;gap:10px;padding:10px}.preview{position:relative;display:grid;place-items:center;background:#090909;border:1px solid var(--line);border-radius:13px;overflow:hidden}.stage{position:relative;height:min(72vh,100%);max-width:94%;aspect-ratio:16/9;background:#000;overflow:hidden;container-type:inline-size}.stage.vertical{aspect-ratio:9/16}.stage.square{aspect-ratio:1/1}video{position:absolute;inset:0;width:100%;height:100%;object-fit:contain}#caption{position:absolute;left:5%;right:5%;top:70%;transform:translateY(-50%);text-align:center;font-size:clamp(23px,4.4vw,62px);font-weight:900;line-height:1.02;text-shadow:0 4px 14px #000,0 2px 2px #000;-webkit-text-stroke:1px #111;pointer-events:none}#caption span{display:inline-block;margin:0 .08em}#caption span.active{color:var(--caption-accent);transform:scale(1.1)}#caption.surface{display:inline-block;left:50%;right:auto;transform:translate(-50%,-50%);padding:.18em .35em;border-radius:.18em;text-shadow:none;-webkit-text-stroke:0;white-space:nowrap}#caption.one-word span:not(.active){display:none}#caption.script-active span.active{font-family:"Segoe Script",cursive;font-weight:700}.sidebar{grid-row:1/3;grid-column:2;background:var(--panel);border:1px solid var(--line);border-radius:13px;overflow:hidden;display:flex;flex-direction:column}.tabbar{display:grid;grid-template-columns:1fr 1fr;border-bottom:1px solid var(--line);padding:8px}.pane{padding:12px;overflow:auto;min-height:0}.chips{display:flex;flex-wrap:wrap;gap:5px;margin-bottom:11px}.chips button{border:1px solid var(--line);padding:5px 9px;font-size:11px}.template-list{display:grid;gap:9px}.template-card{background:#11100f;color:#fff;border:1px solid #37322d;border-radius:11px;padding:0;text-align:left;overflow:hidden;cursor:pointer}.template-card.active{border:2px solid var(--accent)}.template-sample{height:82px;display:grid;place-content:center;text-align:center;font-size:18px;font-weight:900;padding:8px}.template-sample em{color:#fff200;font-style:normal}.template-card b,.template-card small{display:inline-block;padding:9px 10px}.template-card small{float:right;color:#77716a}.soft_focus em,.aura_script em{font-family:"Segoe Script",cursive;color:#ff5a45;font-weight:500}.signal_bar em,.focus_signal em{background:#087df5;color:#fff;padding:2px 5px}.real_estate em{font-size:30px;color:#d7ff23}.template-sample.typography_1{font-family:Impact,sans-serif;letter-spacing:.03em}.template-sample.typography_1 em{background:#f12722;color:#fff;padding:1px 7px}.template-sample.typography_2{font-family:Arial,sans-serif;font-weight:400}.template-sample.typography_2 em{font-family:"Dancing Script","Segoe Script",cursive;color:#a73c2b;font-size:1.8em}.template-sample.typography_2:after{content:"signal bar";background:#137ff6;color:#fff;padding:1px 8px;margin-top:4px}.template-sample.typography_3{display:flex;flex-direction:column;align-items:flex-start;width:max-content;margin:auto;font-family:Roboto,Arial,sans-serif;line-height:.85}.template-sample.typography_3 span{font-size:10px;font-weight:400;margin:0}.template-sample.typography_3 strong{font:900 28px/.8 "Roboto Black","Arial Black",sans-serif;margin:2px 0 4px}.template-sample.typography_4{display:flex;flex-direction:column;align-items:center;gap:2px;font-family:"Roboto Black","Arial Black",sans-serif;line-height:1}.template-sample.typography_4 span{font-size:12px;margin:0}.template-sample.typography_4 strong{font-size:22px;background:linear-gradient(#f4f4f4,#52c7ff);-webkit-background-clip:text;background-clip:text;color:transparent}.text-controls{display:grid;gap:12px;margin-bottom:14px;padding:12px;background:#11100f;border:1px solid var(--line);border-radius:10px}.text-controls label{display:grid;gap:5px;color:#aaa49b;font-size:11px}select,textarea{background:#0e0d0c;color:#fff;border:1px solid #37322d;border-radius:7px;padding:8px}.cue-list{display:grid;gap:8px}.cue-row{display:grid;grid-template-columns:25px 70px 1fr;gap:6px;align-items:start;padding:8px;border:1px solid var(--line);border-radius:9px}.cue-row:focus-within{border-color:var(--accent)}.cue-row>span{color:var(--accent)}.cue-row small{color:#b6b0a8}.cue-row textarea{grid-column:1/-1;width:100%;resize:vertical}.word-tools{grid-column:1/-1;display:grid;gap:7px;padding-top:2px}.word-list,.palette{display:flex;flex-wrap:wrap;gap:5px}.word-chip{border:1px solid #3b3732;background:#0d0c0b;color:#ddd;border-radius:6px;padding:5px 8px;cursor:pointer}.word-chip.selected{border-color:#fff;background:#292622}.word-chip i{display:inline-block;width:7px;height:7px;border-radius:50%;margin-right:5px;background:var(--word-color,#fff)}.palette button{width:27px;height:27px;border:2px solid #27231f;border-radius:50%;background:var(--swatch);cursor:pointer}.palette button.active{outline:2px solid #fff;outline-offset:1px}.palette button.default{background:linear-gradient(135deg,#fff 0 44%,#e34b4b 45% 55%,#fff 56%)}.palette-note{font-size:10px;color:#77716a}.timeline{position:relative;border:1px solid var(--line);border-radius:13px;background:#11100f;padding:42px 16px 12px 62px;overflow:hidden}.transport{position:absolute;top:8px;left:14px;display:flex;gap:8px;align-items:center}.transport button{background:#f7f3eb;border:0;border-radius:7px;padding:7px 11px;cursor:pointer}.transport span{color:#aaa49b}.track{height:38px;position:relative;border-top:1px solid #292621;margin-bottom:7px;background:#0b0a09}.track:before{position:absolute;right:calc(100% + 10px);top:10px;color:#8b857d;font-size:10px;letter-spacing:.12em}.track.video:before{content:'VID'}.track.captions:before{content:'CAP'}.track.audio:before{content:'AUD'}.track.video div,.track.audio div{position:absolute;inset:4px;background:#3a2d20;border-radius:5px}.track.audio div{background:repeating-linear-gradient(90deg,#29536a 0 2px,#122d3a 2px 5px)}.track.captions button{position:absolute;top:4px;height:30px;border:0;border-radius:4px;background:#5e2b1d;color:#fff;font-size:9px;overflow:hidden;white-space:nowrap;cursor:pointer}.links{display:flex;gap:7px;position:absolute;right:14px;top:8px}.links a{color:#ddd;text-decoration:none;border:1px solid var(--line);border-radius:7px;padding:6px 8px;font-size:10px}#status{color:#a9d8ba;font-size:11px}.hidden{display:none!important}
#caption.typography-one{display:flex;flex-direction:column;align-items:center;justify-content:center;left:4%;right:4%;gap:.07em;line-height:.88;text-shadow:none;-webkit-text-stroke:0;filter:drop-shadow(0 0 .055em #ffffff77)}#caption.typography-one .t1-line{display:block;position:relative;max-width:94%;white-space:nowrap;font-family:Impact,sans-serif;color:#fff;text-align:center;text-shadow:none;-webkit-text-stroke:0;letter-spacing:.015em}#caption.typography-one .t1-small{font:700 .25em/1 Arial,sans-serif;letter-spacing:.08em}#caption.typography-one .t1-big{font-size:.82em}#caption.typography-one .t1-giant{font-size:1.02em}#caption.typography-one .t1-bar{min-width:60%;padding:0 .12em;z-index:1}#caption.typography-one .t1-bar:before{content:"";position:absolute;z-index:-1;left:0;right:0;top:29%;height:51%;background:var(--t1-color,#f12722);box-shadow:0 0 .08em var(--t1-color,#f12722)}#caption.typography-one .t1-outline{font-size:1.05em;color:transparent;-webkit-text-stroke:.012em #fff;filter:drop-shadow(0 0 .04em #ffffff88)}#caption.typography-one .t1-echo{position:absolute;left:0;right:0;top:58%;font-size:1.22em;color:transparent;-webkit-text-stroke:.010em #fff;opacity:.24;z-index:-1}#caption.typography-one .t1-script{font:400 .43em/1 "Ink Free","Segoe Print",cursive;letter-spacing:.01em;text-transform:none;margin-bottom:.06em}
#caption.typography-two{left:5%;right:5%;display:flex;align-items:center;justify-content:center;text-shadow:none;-webkit-text-stroke:0;font-weight:400;line-height:1;white-space:nowrap}#caption.typography-two .t2-wrap{position:relative;display:grid;place-items:center;min-width:58%;min-height:2.1em}#caption.typography-two .t2-wrap.t2-script-scene{display:inline-block;min-width:0;min-height:0}#caption.typography-two .t2-script{font-family:"Dancing Script","Segoe Script",cursive;font-size:1.80em;color:#a73c2b;filter:drop-shadow(0 0 .025em #a73c2b22)}#caption.typography-two .t2-support{position:absolute;right:.26em;top:92%;font:400 .70em/1 Arial,sans-serif;color:#ababa8}#caption.typography-two .t2-signal{position:relative;display:inline-block;padding-top:.80em}.t2-top-row{position:absolute;left:0;right:0;top:0;height:.80em}#caption.typography-two .t2-bar{height:1.06em;background:#137ff6;box-shadow:0 0 .10em #137ff655;display:flex;align-items:center;padding:0 .22em;transform-origin:left center;overflow:visible}#caption.typography-two .t2-bar-word{font:400 .76em/1 Arial,sans-serif;color:#fff;margin:0 .08em 0 0;text-shadow:.025em .035em .06em #0009}#caption.typography-two .t2-top{position:absolute;top:0;font:400 .76em/1 Arial,sans-serif;color:#fff;text-shadow:.02em .03em .05em #0007}.t2-top-left{left:0}.t2-top-right{right:0}
#caption.typography-two .t2-support.side{top:55%}
#caption.typography-three{left:5%;right:5%;display:flex;justify-content:center;align-items:center;text-align:left;line-height:1;text-shadow:none;-webkit-text-stroke:0;font-weight:400;white-space:nowrap}#caption.typography-three .t3-wrap{display:flex;flex-direction:column;align-items:flex-start;line-height:1;filter:drop-shadow(0 0 .025em #ffffff20)}#caption.typography-three .t3-line{display:block;white-space:nowrap;text-align:left;color:#fff}#caption.typography-three .t3-top,#caption.typography-three .t3-bottom{font:400 .414em/1 "Roboto",Arial,sans-serif}#caption.typography-three .t3-hero{font:900 1em/.78 "Roboto Black","Arial Black",sans-serif;margin:.025em 0 .115em}#caption.typography-three .t3-word{display:inline-block;margin:0 .20em 0 0;text-shadow:.025em .035em .055em #000b;-webkit-text-stroke:0;transform-origin:center center}#caption.typography-three .t3-word:last-child{margin-right:0}
#caption.typography-four{left:5%;right:5%;display:flex;justify-content:center;align-items:center;text-align:center;line-height:1;text-shadow:none;-webkit-text-stroke:0;font-weight:900;white-space:nowrap}#caption.typography-four .t4-wrap{display:flex;flex-direction:column;align-items:center;gap:.10em;margin:0}#caption.typography-four .t4-line{display:flex;justify-content:center;align-items:center;white-space:nowrap;margin:0}#caption.typography-four .t4-word{display:inline-block;margin:0 .105em;transform:none;filter:none;-webkit-text-stroke:0;text-shadow:none}#caption.typography-four .t4-accent{background:linear-gradient(180deg,#f4f4f4 0%,#f4f4f4 8%,#52c7ff 100%);-webkit-background-clip:text;background-clip:text;color:transparent}#caption.typography-four .t4-accent.t4-custom{background:none;-webkit-background-clip:border-box;background-clip:border-box}
#caption.typography-five{left:7%;right:7%;display:flex;justify-content:center;align-items:center;text-align:left;line-height:1;text-shadow:none;-webkit-text-stroke:0;font-weight:400;white-space:nowrap}#caption.typography-five .t5-wrap{position:relative;display:block;width:min(86cqw,30em);height:1.55em;margin:0}#caption.typography-five .t5-line{position:absolute;display:flex;white-space:nowrap;font:400 .30em/1 Arial,sans-serif;color:#f4f4f4}#caption.typography-five .t5-hero{position:absolute;font:400 1em/1 "Great Vibes",cursive;color:#ef4937;white-space:nowrap}#caption.typography-five .t5-word{display:inline-block;margin:0 .23em 0 0;transform-origin:center center}#caption.typography-five .t5-word:last-child{margin-right:0}.template-sample.typography_5{position:relative;display:block;width:145px;height:70px;margin:auto;font-family:Arial,sans-serif;font-weight:400;line-height:1}.template-sample.typography_5 span,.template-sample.typography_5 strong{position:absolute;margin:0;padding:0;white-space:nowrap}.template-sample.typography_5 span:first-child{left:30px;top:14px;font-size:11px}.template-sample.typography_5 strong{left:28px;top:12px;color:#ef4937;font:400 34px/1 "Great Vibes",cursive}.template-sample.typography_5 span:last-child{right:25px;top:42px;font-size:11px}
@media(max-width:900px){body{overflow:auto}.app{height:auto;display:block}.preview{height:70vh}.sidebar{margin-top:10px;height:680px}.timeline{height:205px;margin-top:10px}}
</style></head><body>
<header><div><b>English Caption Studio</b><small>__MEDIA_NAME__</small></div><div class="ratios"><button data-format="instagram_vertical">9:16</button><button data-format="square">1:1</button><button data-format="youtube_horizontal">16:9</button></div><div><span id="status">Ready to edit</span> <button id="save" class="save">Save &amp; rebuild</button></div></header>
<main class="app"><section class="preview"><div id="stage" class="stage"><video id="video" controls src="__VIDEO_RELATIVE__"></video><div id="caption"></div></div></section>
<aside class="sidebar"><div class="tabbar"><button class="active" data-tab="templates">Templates</button><button data-tab="text">Text &amp; words</button></div>
<div id="templatesPane" class="pane"><div class="chips"><button class="active" data-category="all">All</button><button data-category="cinematic">Cinematic</button><button data-category="aesthetic">Aesthetic</button><button data-category="boxed">Boxed</button><button data-category="editorial">Editorial</button><button data-category="oneword">One word</button></div><div class="template-list">__TEMPLATES_HTML__</div></div>
<div id="textPane" class="pane hidden"><div class="text-controls"><label>Font<select id="font">__FONTS_HTML__</select></label><label>Vertical position <input id="position" type="range" min="10" max="92" value="70"></label><label>Text size <input id="size" type="range" min="55" max="180" value="100"></label></div><div class="cue-list">__CUE_EDITORS__</div></div></aside>
<section class="timeline"><div class="transport"><button id="play" aria-label="Play preview"><svg viewBox="0 0 24 24" width="20" height="20" fill="currentColor" aria-hidden="true"><path d="m8 5 11 7-11 7z"/></svg></button><span id="time">0:00 / __DURATION__s</span></div><div class="links">__LINKS__</div><div class="track video"><div></div></div><div class="track captions">__CAPTION_BLOCKS__</div><div class="track audio"><div></div></div></section></main>
<script>
const cues=__CUES_JSON__,templates=__TEMPLATES_JSON__,fonts=__FONTS_JSON__,project=__PROJECT_JSON__;
const palette=[['Default',null],['Red','#F04444'],['Yellow','#FFD400'],['Blue','#1677FF'],['Dark blue','#0B2E8F'],['Light blue','#52C7FF'],['Purple','#8B5CF6']];
let currentStyle=project.style||'__STYLE_NAME__',currentFormat=project.output_format||'source';
let wordColors=(project.word_colors||cues.map(q=>q.words.map(()=>null))).map(row=>[...row]);
const selectedWords=cues.map(()=>0),$=s=>document.querySelector(s),$$=s=>document.querySelectorAll(s),video=$('#video'),caption=$('#caption'),stage=$('#stage');
function currentTexts(){return [...$$('.cue-row textarea')].map(x=>x.value.trim())}
function wordsAt(index){return (currentTexts()[index]||'').split(/\s+/).filter(Boolean)}
function wordsFor(q){return wordsAt(cues.indexOf(q))}
function esc(value){return String(value).replace(/[&<>]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]))}
function heroToken(value){return String(value).toLowerCase().replace(/[^a-z0-9%]/g,'')}
const heroStop=new Set(['a','an','the','and','or','but','of','to','in','on','at','for','from','with','is','am','are','was','were','be','been','being','aur','jo','toh','hi','hai','hain','tha','thi','the','na','mein','me','ka','ki','ke','ko','se','pe','par','bhi','ye','yeh','woh','wo','usme','isme','iska','uska','ek','bas','sirf','ab','tab','phir','kya','kyun','main','mai','hum','ham','tum','aap','tu','mera','mere','meri','tumhara','tumhare','tumhari','hamara','hamare','hamari']);
const heroNegative=new Set(['nahi','nahin','not','never','no']);
function importantIndex(words){if(!words.length)return 0;const tokens=words.map(heroToken);let best=0,bestScore=-1e9;words.forEach((raw,index)=>{const token=tokens[index],digits=/\d/.test(token);let score=token.length*2+(index/Math.max(1,words.length-1))*5;if(heroStop.has(token))score-=100;if(heroNegative.has(token))score-=45;if(index+1<tokens.length&&heroNegative.has(tokens[index+1]))score+=20;if(digits)score+=25;if(token.length<=2&&!digits)score-=16;if(/(tion|sion)$/.test(token))score+=8;else if(/ment$/.test(token))score+=5;else if(/ed$/.test(token))score+=4;else if(/ing$/.test(token))score+=3;if(/ly$/.test(token))score-=5;if(score>bestScore){best=index;bestScore=score}});return best}
function typographyThreeAnchor(words){if(!words.length)return 0;let best=0,bestScore=-1e9;words.forEach((word,index)=>{const token=heroToken(word),digits=/\d/.test(token);let score=token.length*3+(digits?30:0)-(heroStop.has(token)?100:0);if(score>bestScore){best=index;bestScore=score}});return best}
function sandwichWords(words){if(!words.length)return ['','',''];let start=importantIndex(words),end=start+1,tokens=words.map(heroToken);if(/\d/.test(tokens[start])&&end<words.length&&['percent','percentage','pratishat'].includes(tokens[end]))end++;else if(['percent','percentage','pratishat'].includes(tokens[start])&&start>0&&/\d/.test(tokens[start-1]))start--;if(end<words.length&&heroNegative.has(tokens[end]))end++;return [words.slice(0,start).join(' '),words.slice(start,end).join(' '),words.slice(end).join(' ')]}
function typeLine(kind,text,preserve=false){return text?`<span class="t1-line ${kind}">${esc(preserve?text:text.toUpperCase())}</span>`:''}
function sandwichMarkup(words,kind='',echo=false){const [top,hero,bottom]=sandwichWords(words);return (echo?typeLine('t1-echo',hero.split(/\s+/).slice(-1)[0]):'')+typeLine('t1-small',top)+typeLine(`t1-giant ${kind}`,hero)+typeLine('t1-small',bottom)}
function typographyOneMarkup(words,q){const variant=Math.round(q.start*30)%8;if(!words.length)return '';if(variant===0){const cut=Math.max(0,words.length-3),setup=words.slice(0,cut).join(' '),main=words.slice(cut),upper=main.length>=3?main.slice(0,-1).join(' '):main[0],lower=main.length>=3?main.slice(-1)[0]:main.slice(1).join(' ');return typeLine('t1-echo',lower||upper)+typeLine('t1-small',setup)+typeLine('t1-giant',upper)+typeLine('t1-big',lower)}if(variant===1)return sandwichMarkup(words,'t1-bar');if(variant===2)return sandwichMarkup(words,'t1-outline');if(variant===3)return sandwichMarkup(words,'t1-bar');if(variant===4)return sandwichMarkup(words);if(variant===5){if(words.length===1)return typeLine('t1-giant t1-bar',words[0]);const count=Math.min(2,Math.max(1,words.length-2)),script=words.slice(0,count).join(' '),rest=words.slice(count),focus=importantIndex(rest);return typeLine('t1-script',script,true)+typeLine('t1-small',rest.slice(0,focus).join(' '))+typeLine('t1-giant t1-bar',rest[focus])+typeLine('t1-small',rest.slice(focus+1).join(' '))}if(variant===6)return sandwichMarkup(words,'',true);return sandwichMarkup(words)}
function colorStyle(cueIndex,wordIndex){const color=wordColors[cueIndex]?.[wordIndex];return color?` style="color:${color};--word:${color}"`:''}
function typographyTwoMarkup(words,q,cueIndex,active){const script=words.length<=2;if(script){const hero=0,support=words.length>1?1:null,letters=(words[hero].match(/[\p{L}\p{N}]/gu)||[]).length,scale=Math.min(2.24,1.80+Math.max(0,letters-2)*.22),side=/[gjpqy]/i.test(words[hero]),heroColor=wordColors[cueIndex]?.[hero],heroStyle=` style="font-size:${scale}em${heroColor?`;color:${heroColor};--word:${heroColor}`:''}"`,supportMarkup=support===null?'':`<span class="t2-support ${side?'side':''}" data-word="${support}"${colorStyle(cueIndex,support)}>${esc(words[support])}</span>`;return `<div class="t2-wrap t2-script-scene"><span class="t2-script"${heroStyle} data-word="${hero}">${esc(words[hero])}</span>${supportMarkup}</div>`}let left=null,right=null,bar=[];if(words.length===1)bar=[0];else if(words.length<=3){left=0;bar=words.map((_,i)=>i).slice(1)}else{left=0;right=words.length-1;bar=words.map((_,i)=>i).slice(1,-1)}const topLeft=left===null?'':`<span class="t2-top t2-top-left" data-word="${left}"${colorStyle(cueIndex,left)}>${esc(words[left])}</span>`,topRight=right===null?'':`<span class="t2-top t2-top-right" data-word="${right}"${colorStyle(cueIndex,right)}>${esc(words[right])}</span>`,barWords=bar.map((index,order)=>`<span class="t2-bar-word" data-order="${order}" data-word="${index}"${colorStyle(cueIndex,index)}>${esc(words[index])}</span>`).join('');return `<div class="t2-wrap"><div class="t2-signal"><div class="t2-top-row">${topLeft}${topRight}</div><div class="t2-bar">${barWords}</div></div></div>`}
function typographyThreeMarkup(words,q,cueIndex){if(!words.length)return '';const hero=typographyThreeAnchor(words),word=(index)=>`<span class="t3-word" data-word="${index}"${colorStyle(cueIndex,index)}>${esc(words[index])}</span>`,line=(kind,indices)=>indices.length?`<span class="t3-line ${kind}">${indices.map(word).join('')}</span>`:'';return `<span class="t3-wrap">${line('t3-top',words.map((_,i)=>i).slice(0,hero))}${line('t3-hero',[hero])}${line('t3-bottom',words.map((_,i)=>i).slice(hero+1))}</span>`}
function typographyFourMarkup(words,q,cueIndex){if(!words.length)return '';const accent=words.length-1,word=(index,kind='')=>`<span class="t4-word ${kind} ${wordColors[cueIndex]?.[index]?'t4-custom':''}" data-word="${index}"${colorStyle(cueIndex,index)}>${esc(words[index])}</span>`,top=words.length>1?`<span class="t4-line t4-top">${words.slice(0,-1).map((_,index)=>word(index)).join('')}</span>`:'';return `<span class="t4-wrap">${top}<span class="t4-line t4-bottom">${word(accent,'t4-accent')}</span></span>`}
function typographyFiveAnchor(words){if(!words.length)return 0;const tokens=words.map(heroToken);const recipe=templates.typography_5.reference_recipes.find(r=>r.text.split(/\s+/).map(heroToken).join(' ')===tokens.join(' '));if(recipe)return recipe.hero;if(tokens[0].length>=7)return 0;let candidates=words.map((_,index)=>index).slice(1);if(!candidates.length)candidates=[0];return candidates.reduce((best,index)=>{const score=tokens[index].length*3-(heroStop.has(tokens[index])?100:0)+(/\d/.test(tokens[index])?18:0),bestScore=tokens[best].length*3-(heroStop.has(tokens[best])?100:0)+(/\d/.test(tokens[best])?18:0);return score>bestScore?index:best},candidates[0])}
function typographyFiveMarkup(words,q,cueIndex){if(!words.length)return '';const hero=typographyFiveAnchor(words),top=words.map((_,i)=>i).slice(0,hero),bottom=words.map((_,i)=>i).slice(hero+1),word=index=>`<span class="t5-word" data-word="${index}"${colorStyle(cueIndex,index)}>${esc(words[index])}</span>`,line=(kind,indices)=>indices.length?`<span class="t5-line ${kind}">${indices.map(word).join('')}</span>`:'';return `<span class="t5-wrap" data-hero="${hero}">${line('t5-top',top)}<span class="t5-hero" data-word="${hero}"${colorStyle(cueIndex,hero)}>${esc(words[hero])}</span>${line('t5-bottom',bottom)}</span>`}
function layoutTypographyFive(words){
  const wrap=caption.querySelector('.t5-wrap');if(!wrap)return;
  const hero=wrap.querySelector('.t5-hero'),top=wrap.querySelector('.t5-top'),bottom=wrap.querySelector('.t5-bottom');
  if(!hero)return;
  const geometry=templates.typography_5.reference_geometry,recipe=(!storylensTemplateRebound(words)&&templates.typography_5.reference_recipes.find(r=>r.text.split(/\s+/).map(heroToken).join(' ')===words.map(heroToken).join(' ')))||storylensTemplatePattern(words,templates.typography_5.reference_recipes)||{};
  const index=Number(wrap.dataset.hero),context=document.createElement('canvas').getContext('2d');
  const family=$('#font').value==='template'?'Arial':fonts[$('#font').value].css;
  let size=Math.max(24,Math.round(parseFloat(getComputedStyle(caption).fontSize))),support=Math.max(12,Math.round(size*geometry.support_ratio));
  const maximum=stage.clientWidth*.86;
  function metrics(text,fontSize,fontFamily){
    context.font=`400 ${fontSize}px ${fontFamily}`;
    const m=context.measureText(text||'H'),ascent=m.fontBoundingBoxAscent??fontSize*.85,descent=m.fontBoundingBoxDescent??fontSize*.35;
    return {width:m.width,left:m.actualBoundingBoxLeft,right:m.actualBoundingBoxRight,
      top:ascent-m.actualBoundingBoxAscent,bottom:ascent+m.actualBoundingBoxDescent,
      inkOffset:(fontSize-ascent-descent)/2+ascent-m.actualBoundingBoxAscent};
  }
  function lineWidth(element){
    if(!element)return 0;
    context.font=`400 ${support}px ${family}`;const space=context.measureText(' ').width*.92;
    return [...element.children].reduce((sum,e,i)=>sum+context.measureText(e.textContent).width+(i?space:0),0);
  }
  while(size>20){
    const m=metrics(words[index],size,'"Great Vibes"');
    if(Math.max(m.left+m.right,lineWidth(top),lineWidth(bottom))<=maximum)break;
    size--;support=Math.max(11,Math.round(size*geometry.support_ratio));
  }
  const h=metrics(words[index],size,'"Great Vibes"'),heroWidth=h.left+h.right;
  const t=top?metrics(top.textContent,support,family):null,b=bottom?metrics(bottom.textContent,support,family):null;
  const topY=t?size*geometry.top_origin+t.top:h.top,bottomY=b?size*geometry.bottom_origin+b.top:h.top;
  const first=Math.min(h.top,topY),last=Math.max(h.bottom,b?size*geometry.bottom_origin+b.bottom:h.bottom);
  const wrapWidth=wrap.clientWidth,heroX=(wrapWidth-heroWidth)/2;
  let topX=heroX+size*geometry.inset,bottomX=heroX+heroWidth-lineWidth(bottom)-size*(recipe.bottom_inset??geometry.inset);
  if(geometry.centered_headers.includes(heroToken(words[index])))topX=heroX+(heroWidth-lineWidth(top))/2;
  const left=Math.min(heroX,top?topX:heroX,bottom?bottomX:heroX),right=Math.max(heroX+heroWidth,top?topX+lineWidth(top):0,bottom?bottomX+lineWidth(bottom):0);
  const shift=Math.max(0,-left)+Math.min(0,wrapWidth-right);
  Object.assign(hero.style,{left:(heroX+shift+h.left)+'px',top:(h.top-first-h.inkOffset)+'px',fontSize:size+'px',lineHeight:size+'px'});
  hero.dataset.inkTop=String(h.top-first);hero.dataset.inkBottom=String(h.bottom-first);
  for(const [element,m,x,y] of [[top,t,topX,topY],[bottom,b,bottomX,bottomY]]){
    if(!element)continue;
    context.font=`400 ${support}px ${family}`;
    Object.assign(element.style,{left:(x+shift)+'px',top:(y-first-m.inkOffset)+'px',fontSize:support+'px',lineHeight:support+'px',fontFamily:family,columnGap:(context.measureText(' ').width*.92)+'px'});
    for(const word of element.children)word.style.margin='0';
    element.dataset.inkTop=String(y-first);element.dataset.inkBottom=String(y-first+m.bottom-m.top);
  }
  wrap.style.height=(last-first)+'px';
}

function applyTypographyOneColors(words,cueIndex){caption.querySelectorAll('.t1-line').forEach(line=>{const outline=line.classList.contains('t1-outline')||line.classList.contains('t1-echo'),tokens=line.textContent.trim().split(/\s+/),used=new Set;line.innerHTML=tokens.map(token=>{const clean=heroToken(token),index=words.findIndex((word,i)=>!used.has(i)&&heroToken(word)===clean);if(index>=0)used.add(index);const color=index>=0?wordColors[cueIndex]?.[index]:null,style=color?(outline?`-webkit-text-stroke-color:${color};color:transparent`:`color:${color}`):'';return `<span${style?` style="${style}"`:''}>${esc(token)}</span>`}).join(' ')})}
function applyStyle(){const t=templates[currentStyle],templateFonts={'impact.ttf':'Impact, sans-serif','arial.ttf':'Arial, sans-serif','arialbd.ttf':'Arial, sans-serif','bahnschrift.ttf':'Bahnschrift, sans-serif','segoeuib.ttf':'Segoe UI, sans-serif','georgiab.ttf':'Georgia, serif','segoesc.ttf':'Segoe Script, cursive','trebucbd.ttf':'Trebuchet MS, sans-serif','Roboto-Black.ttf':'Roboto Black, Arial Black, sans-serif','Roboto-Bold.ttf':'Roboto, Arial, sans-serif'},chosen=$('#font').value,scale=Number($('#size').value)/100;caption.style.color=t.base;caption.style.background=t.surface||'transparent';document.documentElement.style.setProperty('--caption-accent',t.accent);caption.className=(t.surface?'surface ':'')+(t.one_word?'one-word ':'')+(t.active_font?'script-active ':'')+(t.layout==='typography_1'?'typography-one ':t.layout==='typography_2'?'typography-two ':t.layout==='typography_3'?'typography-three ':t.layout==='typography_4'?'typography-four ':t.layout==='typography_5'?'typography-five ':'');caption.style.fontFamily=chosen==='template'?(templateFonts[t.font]||'inherit'):(fonts[chosen]?.css||'inherit');caption.style.top=$('#position').value+'%';caption.style.fontSize=t.layout==='typography_1'?`calc(clamp(48px,8.8vw,138px) * ${scale})`:t.layout==='typography_2'?`calc(clamp(52px,7.2vw,124px) * ${scale})`:t.layout==='typography_3'?`calc(clamp(42px,5.5vw,84px) * ${scale})`:t.layout==='typography_4'?`calc(6.8cqw * ${scale})`:t.layout==='typography_5'?`calc(16.67cqw * ${scale})`:`calc(clamp(23px,4.4vw,62px) * ${scale})`;$$('.template-card').forEach(x=>x.classList.toggle('active',x.dataset.style===currentStyle))}
function previewMotion(t,q,now,holdGroup=false){const clamp=v=>Math.min(1,Math.max(0,v)),ease=v=>1-Math.pow(1-clamp(v),3),back=v=>{v=clamp(v)-1;return 1+2.15*v*v*v+1.15*v*v},elapsed=now-q.start,outro=holdGroup?1:ease((q.end-now)/(t.layout==='typography_2'?.20:t.layout==='typography_3'?.12:.24));if(t.layout==='typography_1'){const intro=ease(elapsed/.28),direction=Math.round(q.start*10)%2?-1:1,scale=.975+.025*back(elapsed/.28)-.018*(1-outro),blur=(1-intro)*3.5+(1-outro)*6,colors=[['#f12722','#870b0b'],['#f4b400','#9a6500'],['#1769f5','#07388f']],color=colors[Math.round(q.start*100)%3];caption.style.setProperty('--t1-color',color[0]);caption.style.transform=`translateY(-50%) translateX(${direction*(1-intro)*2.5}%) scale(${scale})`;caption.style.filter=`blur(${blur}px) drop-shadow(0 0 .055em #ffffff77)`;caption.style.opacity=String(Math.min(1,intro*1.7,outro*1.55));caption.querySelectorAll('.t1-line').forEach((line,index)=>{const linear=clamp((elapsed-index*.08)/.24),resolve=ease(linear),settle=back(linear);line.style.opacity=String(Math.min(1,linear*1.65));line.style.transform=`translateX(${(index%2?1:-1)*(1-resolve)*.10}em) scale(${.94+.06*settle})`;line.style.filter=`blur(${(1-resolve)*.12}em) drop-shadow(0 0 .035em #ffffff66)`});return}if(t.layout==='typography_2'){const intro=ease(elapsed/.28),scale=.985+.015*back(elapsed/.28)-.012*(1-outro);caption.style.transform=`translateY(-50%) translateX(${-(1-intro)*1.8}%) scale(${scale})`;caption.style.filter=`blur(${(1-intro)*4+(1-outro)*5}px)`;caption.style.opacity=String(Math.min(1,intro*1.8,outro*1.7));const bar=caption.querySelector('.t2-bar'),left=caption.querySelector('.t2-top-left'),right=caption.querySelector('.t2-top-right');if(bar){bar.style.transform=`scaleX(${Math.max(.015,ease((elapsed-.04)/.28))})`;if(left&&right){right.style.left='';right.style.right='0';const gap=parseFloat(getComputedStyle(caption).fontSize)*.20;if(left.offsetWidth+right.offsetWidth+gap>bar.offsetWidth){right.style.left=`${left.offsetLeft+left.offsetWidth+gap}px`;right.style.right='auto'}}}caption.querySelectorAll('.t2-bar-word').forEach(word=>{const show=ease((elapsed-.16-Number(word.dataset.order)*.14)/.16);word.style.opacity=show;word.style.filter=`blur(${(1-show)*.12}em)`});if(left)left.style.opacity=ease((elapsed-.04)/.20);if(right)right.style.opacity=ease((elapsed-.44)/.18);return}if(t.layout==='typography_3'){caption.style.transform='translateY(-50%)';caption.style.filter='';caption.style.opacity='1';const words=wordsFor(q);caption.querySelectorAll('.t3-word').forEach(element=>{const index=Number(element.dataset.word),fallback=q.start+(q.end-q.start)*index/Math.max(1,words.length),start=q.words?.[index]?.start??fallback,local=now-start,progress=clamp(local/.28),show=ease(local/.22),focus=progress*progress*(3-2*progress),scale=.55+.45*back(progress);element.style.opacity=String(show);element.style.transform=`scale(${Math.max(.04,scale)})`;element.style.filter=`blur(${(1-focus)*.23}em)`});return}if(t.layout==='typography_4'){caption.style.transform='translateY(-50%)';caption.style.filter='';caption.style.opacity='1';const words=wordsFor(q);caption.querySelectorAll('.t4-word').forEach(element=>{const index=Number(element.dataset.word),fallback=q.start+(q.end-q.start)*index/Math.max(1,words.length),start=q.words?.[index]?.start??fallback;element.style.opacity=String(clamp((now-start)/.24));element.style.transform='none';element.style.filter='none'});return}if(t.layout==='typography_5'){caption.style.transform='translateY(-50%)';caption.style.filter='';caption.style.opacity='1';const words=wordsFor(q);layoutTypographyFive(words);caption.querySelectorAll('[data-word]').forEach(element=>{const index=Number(element.dataset.word),fallback=q.start+(q.end-q.start)*index/Math.max(1,words.length),start=q.words?.[index]?.start??fallback,local=now-start,progress=clamp(local/.28),show=ease(local/.24),focus=progress*progress*(3-2*progress);element.style.opacity=String(show);element.style.transform=`scale(${.94+.06*ease(progress)})`;element.style.filter=`blur(${(1-focus)*.075}em)`});return}caption.style.transform='translateY(-50%)';caption.style.filter='';caption.style.opacity='1'}
function draw(){const now=video.currentTime,q=cues.find(x=>x.start<=now&&now<x.end);if(!q){caption.innerHTML='';return}const cueIndex=cues.indexOf(q),t=templates[currentStyle],words=wordsFor(q);wordColors[cueIndex]=[...(wordColors[cueIndex]||[]).slice(0,words.length),...Array(Math.max(0,words.length-(wordColors[cueIndex]||[]).length)).fill(null)];let active=Math.min(words.length-1,Math.max(0,Math.floor((now-q.start)/Math.max(.01,q.end-q.start)*words.length)));if(t.layout==='typography_1'){caption.innerHTML=typographyOneMarkup(words,q);applyTypographyOneColors(words,cueIndex)}else if(t.layout==='typography_2')caption.innerHTML=typographyTwoMarkup(words,q,cueIndex,active);else if(t.layout==='typography_3')caption.innerHTML=typographyThreeMarkup(words,q,cueIndex);else if(t.layout==='typography_4')caption.innerHTML=typographyFourMarkup(words,q,cueIndex);else if(t.layout==='typography_5')caption.innerHTML=typographyFiveMarkup(words,q,cueIndex);else caption.innerHTML=words.map((word,index)=>`<span class="${index===active?'active':''}"${colorStyle(cueIndex,index)}>${esc(t.case==='upper'?word.toUpperCase():word)}</span>`).join(' ');applyStyle();previewMotion(t,q,now)}
function renderWordEditor(index){const host=document.querySelector(`[data-word-tools="${index}"]`),words=wordsAt(index),old=wordColors[index]||[];wordColors[index]=words.map((_,i)=>old[i]||null);selectedWords[index]=Math.min(selectedWords[index],Math.max(0,words.length-1));const selected=selectedWords[index],chips=words.map((word,i)=>`<button type="button" class="word-chip ${i===selected?'selected':''}" data-word-index="${i}"><i style="--word-color:${wordColors[index][i]||'#fff'}"></i>${esc(word)}</button>`).join(''),swatches=palette.map(([name,color])=>`<button type="button" title="${name}" class="${color?'':'default'} ${wordColors[index][selected]===color?'active':''}" data-color="${color||''}" style="--swatch:${color||'#fff'}"></button>`).join('');host.innerHTML=`<div class="palette-note">Select a word, then choose its color</div><div class="word-list">${chips}</div><div class="palette">${swatches}</div>`;host.querySelectorAll('.word-chip').forEach(button=>button.onclick=event=>{event.stopPropagation();selectedWords[index]=Number(button.dataset.wordIndex);renderWordEditor(index)});host.querySelectorAll('.palette button').forEach(button=>button.onclick=event=>{event.stopPropagation();wordColors[index][selectedWords[index]]=button.dataset.color||null;renderWordEditor(index);draw()})}
function renderAllWordEditors(){cues.forEach((_,index)=>renderWordEditor(index))}
function setFormat(value,displayOnly=false){if(!displayOnly)currentFormat=value;stage.className='stage '+(value==='instagram_vertical'?'vertical':value==='square'?'square':'');$$('.ratios button').forEach(x=>x.classList.toggle('active',x.dataset.format===value));draw()}
$$('.template-card').forEach(x=>x.onclick=()=>{currentStyle=x.dataset.style;if(templates[currentStyle].default_position)$('#position').value=Math.round(templates[currentStyle].default_position*100);draw()});$$('.chips button').forEach(x=>x.onclick=()=>{$$('.chips button').forEach(b=>b.classList.toggle('active',b===x));$$('.template-card').forEach(card=>card.classList.toggle('hidden',x.dataset.category!=='all'&&card.dataset.category!==x.dataset.category))});$$('.tabbar button').forEach(x=>x.onclick=()=>{$$('.tabbar button').forEach(b=>b.classList.toggle('active',b===x));$('#templatesPane').classList.toggle('hidden',x.dataset.tab!=='templates');$('#textPane').classList.toggle('hidden',x.dataset.tab!=='text')});$$('.ratios button').forEach(x=>x.onclick=()=>setFormat(x.dataset.format));$$('[data-seek]').forEach(x=>x.onclick=()=>{video.currentTime=Number(x.dataset.seek);video.play()});$$('.cue-row').forEach(row=>row.onclick=e=>{if(!['TEXTAREA','BUTTON'].includes(e.target.tagName))video.currentTime=cues[Number(row.dataset.index)].start});
$('#font').value=project.font||'template';$('#position').value=Math.round((project.position||.70)*100);$('#size').value=Math.round((project.size||1)*100);['input','change'].forEach(event=>{$('#font').addEventListener(event,draw);$('#position').addEventListener(event,draw);$('#size').addEventListener(event,draw)});$$('.cue-row textarea').forEach((x,index)=>x.addEventListener('input',()=>{renderWordEditor(index);draw()}));video.addEventListener('timeupdate',()=>{draw();$('#time').textContent=`${video.currentTime.toFixed(1)}s / ${video.duration?video.duration.toFixed(1):'?'}s`});video.addEventListener('seeked',draw);$('#play').onclick=()=>video.paused?video.play():video.pause();
async function save(){const button=$('#save'),status=$('#status');button.disabled=true;status.textContent='Rebuilding caption layer…';try{const bridge=await (await fetch('http://127.0.0.1:8765/api/bridge')).json();const response=await fetch('http://127.0.0.1:8765/api/captions/rebuild',{method:'POST',headers:{'Content-Type':'application/json','X-Hinglish-Token':bridge.token},body:JSON.stringify({project_path:project.project_path,texts:currentTexts(),word_colors:wordColors,style:currentStyle,font:$('#font').value,position:Number($('#position').value)/100,size:Number($('#size').value)/100,output_format:currentFormat})});const result=await response.json();if(!response.ok)throw new Error(result.error||'Could not rebuild captions');status.textContent='Saved — XML and caption layer updated';setTimeout(()=>location.reload(),900)}catch(error){status.textContent=error.message;button.disabled=false}}
$('#save').onclick=save;renderAllWordEditors();const displayFormat=currentFormat==='source'?(project.width<project.height?'instagram_vertical':'youtube_horizontal'):currentFormat;setFormat(displayFormat,currentFormat==='source');applyStyle();draw();
</script></body></html>'''


def write_index(path, results, errors):
    cards = ''.join(f'<a href="{html.escape(row["folder"])}/report.html">'
                    f'<b>{html.escape(row["name"])}</b><span>{row["cues"]} caption phrases · '
                    f'{html.escape(row["style"])}</span></a>' for row in results)
    issues = ''.join(f'<li>{html.escape(error["source"])}: {html.escape(error["error"])}</li>'
                     for error in errors)
    Path(path).write_text(
        '<!doctype html><html><head><meta charset="utf-8"><title>Premium Hinglish Captions</title>'
        '<style>body{background:#0d0f12;color:#fff;font:16px Segoe UI;margin:40px auto;max-width:850px;padding:0 20px}'
        'h1{font-size:42px}p,span{color:#9ca3ad}main{display:grid;gap:12px;margin-top:30px}'
        'a{display:flex;justify-content:space-between;background:#1b1f25;border:1px solid #30353d;border-radius:12px;padding:18px;color:#fff;text-decoration:none}'
        'li{color:#ff9b70}</style></head><body><p>HINGLISH EDITOR</p><h1>Premium captions ready</h1>'
        '<p>Open a video to edit every word, color, template, font, position, size and aspect ratio.</p>'
        f'<main>{cards}</main><ul>{issues}</ul></body></html>', encoding='utf-8')

